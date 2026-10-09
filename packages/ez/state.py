"""Atomic projections, OS locks and a hash-chained authoritative event journal."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import tempfile

from .contracts import digest, now, ContractError


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.' + path.name, dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@contextmanager
def lock(directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / '.ez.lock').open('a+b') as handle:
        handle.seek(0, 2)
        if not handle.tell():
            handle.write(b'0')
            handle.flush()
        handle.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise ContractError('Esta corrida ya tiene un escritor activo.') from exc
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == 'nt':
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle, fcntl.LOCK_UN)


class Store:
    def __init__(self, root):
        self.root = Path(root)
        self.journal = self.root / 'events.jsonl'

    def events(self):
        if not self.journal.exists():
            return []
        result = []
        raw = self.journal.read_bytes()
        lines = raw.splitlines(keepends=True)
        for i, line in enumerate(lines):
            if not line.endswith(b'\n'):
                if i == len(lines) - 1:
                    break  # interrupted append; never treat it as a committed event
                raise ContractError('Journal incompleto.')
            event = json.loads(line)
            if not isinstance(event, dict) or event.get('schema_version') != '2.0':
                raise ContractError('La versión del journal no es compatible; no se modifica.')
            event_hash = event.get('event_hash')
            body = {k: v for k, v in event.items() if k != 'event_hash'}
            if event_hash != digest(body) or event.get('seq') != len(result) + 1 or event.get('previous_hash') != (result[-1]['event_hash'] if result else None):
                raise ContractError('La integridad del journal no se puede verificar.')
            result.append(event)
        return result

    def append(self, kind, payload):
        """Caller must hold lock(root) for the entire operation."""
        events = self.events()
        event = {'schema_version': '2.0', 'seq': len(events) + 1, 'at': now(), 'kind': kind,
                 'payload': payload, 'previous_hash': events[-1]['event_hash'] if events else None}
        event['event_hash'] = digest(event)
        self.root.mkdir(parents=True, exist_ok=True)
        if self.journal.exists():
            data = self.journal.read_bytes()
            if data and not data.endswith(b'\n'):
                offset = data.rfind(b'\n') + 1
                # Preserve the incomplete tail for diagnosis before repairing it.
                tail = data[offset:]
                from hashlib import sha256
                tail_path = self.root / ('interrupted-' + sha256(tail).hexdigest() + '.bin')
                if not tail_path.exists():
                    tail_path.write_bytes(tail)
                with self.journal.open('r+b') as stream:
                    stream.truncate(offset)
        with self.journal.open('ab') as stream:
            stream.write((json.dumps(event, ensure_ascii=False, sort_keys=True) + '\n').encode())
            stream.flush()
            os.fsync(stream.fileno())
        return event

    def state(self):
        for event in reversed(self.events()):
            if event['kind'] == 'transaction':
                return event['payload']['state']
            if event['kind'] == 'state':
                return event['payload']
        return None

    def recover(self, repair=False):
        """Replay committed projections only if their bytes still match the before-image.

        Call with repair=True only while holding the run lock. An unrelated edit is
        an integrity failure, never permission to overwrite the user's file.
        """
        documents = {}
        for event in self.events():
            if event['kind'] == 'transaction':
                documents.update(event['payload']['documents'])
        pending = []
        for name, document in documents.items():
            from .paths import contained
            path = contained(self.root, name)
            try:
                actual = digest(read_json(path)) if path.exists() else None
            except (ValueError, UnicodeError) as exc:
                raise ContractError(f'El artefacto {name} no es verificable.') from exc
            expected = digest(document['value'])
            if actual == expected:
                continue
            if actual != document['before_hash']:
                raise ContractError(f'El artefacto {name} cambió fuera de la transacción.')
            pending.append(name)
            if repair:
                atomic_json(path, document['value'])
        return pending

    def commit(self, state, documents):
        """Commit documents and state in one journal record before projecting files.

        Caller holds the run lock. A crash while projecting can be replayed; a
        crash before the journal newline leaves all previous files authoritative.
        """
        self.recover(repair=True)
        from .paths import contained
        entries = {}
        for name, value in documents.items():
            path = contained(self.root, name)
            entries[name] = {'before_hash': digest(read_json(path)) if path.exists() else None, 'value': value}
        state = dict(state, schema_version='2.0', updated_at=now())
        self.append('transaction', {'state': state, 'documents': entries})
        for name, entry in entries.items():
            atomic_json(self.root / name, entry['value'])
        atomic_json(self.root / 'run-state.json', state)
        return state

    def update(self, state):
        state = dict(state, schema_version='2.0', updated_at=now())
        self.append('state', state)
        atomic_json(self.root / 'run-state.json', state)
        return state
