"""The user's side of the EZ folder: one folder per project with an inbox, the reports and an index.

    <EZ>/projects/<project>/
        README.md     index of researches, with a link to each report
        inbox/        the user drops PDFs here; EZ takes them when a work is missing
        reports/      a copy of each report and its bibliography (.bib)
        notes/        one note per source with its cited passages, one per research (see vault.py)

Folders created by earlier versions with Spanish names (proyectos/, bandeja/, informes/,
LEEME.md) are renamed in place the first time EZ touches the project.

The runs themselves stay in <EZ>/runs/ez-…: they are the verifiable record, and the
copies here are derived from them and regenerated on every delivery.
"""
from datetime import datetime, timezone
from pathlib import Path
import re
import shutil

INBOX_NOTE = ('# Inbox\n\nDrop here the PDFs EZ asks for, or any article you want to add to this project. When an '
              'article is missing, EZ looks here first and recognises each PDF by its title and DOI. Your files are '
              'never moved or deleted; EZ keeps a copy inside the research.\n')
LEGACY_PROJECT = (('bandeja', 'inbox'), ('informes', 'reports'), ('LEEME.md', 'README.md'))


def slug(text, limit=60):
    import unicodedata
    plain = unicodedata.normalize('NFKD', str(text or '')).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+', '-', plain).strip('-')[:limit].strip('-') or 'general'


def home(runs_root):
    """The EZ folder: the parent of the standard runs/ folder, or the given folder itself for any other layout."""
    runs_root = Path(runs_root).resolve()
    return runs_root.parent if runs_root.name == 'runs' else runs_root


def project_dir(runs_root, project):
    folder = home(runs_root) / 'projects' / slug(project)
    migrate(folder, home(runs_root) / 'proyectos' / slug(project))
    return folder


def migrate(folder, legacy):
    """Rename a project folder and its parts from the Spanish names of earlier versions, never overwriting."""
    if legacy.is_dir() and not folder.exists():
        folder.parent.mkdir(parents=True, exist_ok=True)
        legacy.rename(folder)
        if not any(legacy.parent.iterdir()):
            legacy.parent.rmdir()
    for old, new in LEGACY_PROJECT:
        if (folder / old).exists() and not (folder / new).exists():
            (folder / old).rename(folder / new)
    note = folder / 'inbox' / 'LEEME.md'
    if note.exists() and not (folder / 'inbox' / 'README.md').exists():
        note.rename(folder / 'inbox' / 'README.md')


def pdfs(folder):
    """PDF files directly inside a folder, whatever the case of their extension (.pdf, .PDF)."""
    folder = Path(folder)
    return sorted(p for p in folder.iterdir() if p.is_file() and p.suffix.lower() == '.pdf') if folder.is_dir() else []


def link(path):
    """A file:// link the user can click to open the folder or file on their computer."""
    return Path(path).resolve().as_uri()


def ensure(runs_root, project):
    """Create the project's folders if missing and return their paths and links."""
    folder = project_dir(runs_root, project)
    inbox, reports = folder / 'inbox', folder / 'reports'
    inbox.mkdir(parents=True, exist_ok=True)
    reports.mkdir(parents=True, exist_ok=True)
    note = inbox / 'README.md'
    if not note.exists():
        note.write_text(INBOX_NOTE, encoding='utf-8')
    if not (folder / 'README.md').exists():
        write_index(runs_root, project)
    return {'project': str(folder), 'inbox': str(inbox), 'reports': str(reports),
            'project_link': link(folder), 'inbox_link': link(inbox), 'reports_link': link(reports)}


def report_name(contract, state):
    created = str(contract.get('created_at') or datetime.now(timezone.utc).isoformat())[:10]
    return f'{created}-{slug(contract["question"]["original"], 50)}-{state["run_id"][3:9]}'


def publish(runs_root, run_folder, contract, state, answer):
    """Copy the report and its bibliography to the project's reports/ and refresh the index."""
    from .deliver import bibliography, export_bibliography
    project = contract.get('context', {}).get('project') or 'general'
    paths = ensure(runs_root, project)
    name = report_name(contract, state)
    target = Path(paths['reports']) / (name + '.md')
    shutil.copyfile(Path(run_folder) / 'report.md', target)
    cited = [source for _, (_, source, _) in sorted(bibliography(answer).items(), key=lambda item: item[1][0]) if source]
    if cited:
        (Path(paths['reports']) / (name + '.bib')).write_text(export_bibliography(cited), encoding='utf-8')
    write_index(runs_root, project)
    from .vault import write
    notes = write(runs_root, project)
    return dict(paths, report=str(target), report_link=link(target), notes=notes['notes'], notes_link=link(notes['notes']))


def write_index(runs_root, project):
    """README.md of a project: every research with its date, state and links."""
    from .context import history
    folder = project_dir(runs_root, project)
    folder.mkdir(parents=True, exist_ok=True)
    labels = {'complete': 'complete', 'partial': 'partial', 'unavailable': 'running or no answer yet'}
    lines = [f'# Project: {project}', '',
             f'- Inbox for your PDFs: [inbox/]({link(folder / "inbox")})',
             f'- Reports: [reports/]({link(folder / "reports")})',
             f'- Notes (Obsidian vault): [notes/]({link(folder / "notes")})', '',
             '## Researches', '', '| Date | Question | Answer | Report | Working folder |', '|---|---|---|---|---|']
    for row in history(Path(runs_root), project, limit=200):
        report = next(iter(sorted((folder / 'reports').glob(f'*-{row["run_id"][3:9]}.md'))), None)
        question = row['question'].replace('|', '/')
        lines.append(f'| {row["updated_at"][:10]} | {question} | {labels.get(row["saved_answer_status"], row["saved_answer_status"])} | '
                     + (f'[open]({link(report)})' if report else '—') + f' | [{row["run_id"]}]({link(row["path"])}) |')
    lines += ['', 'EZ rewrites this index on every delivery. Working folders (`runs/ez-…`) are the verifiable record of '
              'each research; do not edit them by hand.', '']
    (folder / 'README.md').write_text('\n'.join(lines), encoding='utf-8')


def projects(runs_root, question=None):
    """Every project with its researches, library and folders; with a question, ranked by how related it is."""
    from .context import history
    from .library import project_sources
    from .state import read_json
    runs_root = Path(runs_root)
    names = set()
    for path in runs_root.glob('ez-*/research-contract.json'):
        try:
            names.add(read_json(path).get('context', {}).get('project') or 'general')
        except (OSError, ValueError):
            continue
    names |= {p.stem for p in (runs_root.parent / 'contexts').glob('*.json')}
    words = topic_words(question) if question else set()
    result = []
    for name in sorted(names):
        runs = history(runs_root, name, limit=500)
        library = project_sources(runs_root, name)
        context_file = runs_root.parent / 'contexts' / (name + '.json')
        context = read_json(context_file) if context_file.exists() else {}
        notebooks = runs_root / 'projects' / slug(name) / 'notebooks.json'
        notebook = (read_json(notebooks).get('notebooks') or [None])[-1] if notebooks.exists() else None
        folder = project_dir(runs_root, name)
        row = {'project': name, 'researches': len(runs), 'last_activity': runs[0]['updated_at'][:10] if runs else None,
               'recent_questions': [r['question'] for r in runs[:3]], 'goal': context.get('goal'),
               'library_pdfs': len(library), 'notebooklm_sources': len(notebook['sources']) if notebook else 0,
               'inbox_pdfs': len(pdfs(folder / 'inbox')), 'folder_link': link(folder)}
        if words:
            texts = [r['question'] for r in runs] + [context.get('goal') or ''] + [s.get('title') or '' for s in library]
            row['relatedness'] = round(max((len(words & topic_words(t)) / len(words) for t in texts if t), default=0.0), 2)
        result.append(row)
    if words:
        result.sort(key=lambda r: -r['relatedness'])
    return result


STOPWORDS = {'que', 'qué', 'como', 'cómo', 'sobre', 'para', 'entre', 'desde', 'cual', 'cuál', 'cuales', 'cuáles', 'what',
             'which', 'with', 'from', 'this', 'that', 'efecto', 'efectos', 'se', 'sabe', 'conoce', 'según', 'segun'}


def topic_words(text):
    from .acquisition import plain_words
    return {w for w in plain_words(text) if len(w) > 3 and w not in STOPWORDS}
