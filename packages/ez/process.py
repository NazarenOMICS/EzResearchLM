"""Bounded external process execution, including descendants on timeout."""
from dataclasses import dataclass
import os
import signal
import subprocess
import sys
import tempfile
import time


@dataclass
class Result:
    returncode: int
    stdout: str
    stderr: str
    reason: str = ''


def terminate_tree(process, job=None):
    if job is not None:
        job.close()
    elif os.name == 'nt':
        # This fallback is reached only if job assignment itself failed, before
        # the trampoline is permitted to launch the requested command.
        process.kill()
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    if process.poll() is None:
        process.kill()
    process.wait(timeout=5)


def run(argv, timeout=60, *, cwd=None, env=None, max_output_bytes=8 * 1024 * 1024):
    if timeout <= 0:
        return Result(124, '', '', 'deadline_exceeded')
    started = time.monotonic()
    with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
        command = [str(a) for a in argv]
        job = None
        if os.name == 'nt':
            from .winjob import Job
            job = Job()
            # The child cannot launch the target until it belongs to our job.
            bootstrap = ('import subprocess,sys; token=sys.stdin.buffer.read(1); '
                         'sys.exit(subprocess.call(sys.argv[1:], stdin=subprocess.DEVNULL) if token == b"G" else 126)')
            command = [sys.executable, '-c', bootstrap, *command]
        try:
            process = subprocess.Popen(command, cwd=cwd, env=env, stdin=subprocess.PIPE if job else subprocess.DEVNULL,
                                       stdout=out, stderr=err, start_new_session=os.name != 'nt',
                                       creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        except BaseException:
            if job:
                job.close()
            raise
        reason = ''
        try:
            if job:
                job.assign(process)
                process.stdin.write(b'G')
                process.stdin.flush()
                process.stdin.close()
            while process.poll() is None:
                if time.monotonic() - started >= timeout:
                    reason = 'deadline_exceeded'
                    terminate_tree(process, job)
                    break
                if os.fstat(out.fileno()).st_size + os.fstat(err.fileno()).st_size > max_output_bytes:
                    reason = 'output_limit'
                    terminate_tree(process, job)
                    break
                time.sleep(min(.05, max(.001, timeout / 10)))
        except BaseException:
            terminate_tree(process, job)
            raise
        finally:
            if job:
                job.close()
            elif os.name != 'nt':
                # A normally exiting parent must not leave a background child.
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
        size = os.fstat(out.fileno()).st_size + os.fstat(err.fileno()).st_size
        if size > max_output_bytes:
            reason = reason or 'output_limit'
        out.seek(0)
        err.seek(0)
        return Result(124 if reason == 'deadline_exceeded' else (125 if reason else process.returncode),
                      out.read(max_output_bytes).decode('utf-8-sig', errors='replace'),
                      err.read(max_output_bytes).decode('utf-8-sig', errors='replace'), reason)


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--timeout', type=float, default=60)
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    if not command:
        parser.error('command required')
    result = run(command, args.timeout)
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    if result.reason:
        sys.stderr.write('\nEZ_EXTERNAL_FAILURE: ' + result.reason + '\n')
    return result.returncode


if __name__ == '__main__':
    raise SystemExit(main())
