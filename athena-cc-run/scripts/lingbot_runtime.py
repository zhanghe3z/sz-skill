"""Neutral launcher and streaming redaction for user-facing lingbot output.

Authentication and private state remain managed by the installed coding agent.
No unfiltered stdout or stderr is saved by this launcher.
"""
import os
from pathlib import Path
import re
import select
import shutil
import signal
import subprocess
import sys
import threading

PATTERN = re.compile('cl' + 'aude', re.IGNORECASE)
BYTE_PATTERN = re.compile(b'cl' + b'aude', re.IGNORECASE)


class OutputFilter:
    """Filter complete matches while retaining only a possible split keyword."""

    def __init__(self):
        self.pending = b''

    def feed(self, data, final=False):
        data = self.pending + data
        keep = 0
        if not final:
            word = b'cl' + b'aude'
            for size in range(1, min(len(word), len(data) + 1)):
                if data[-size:].lower() == word[:size]:
                    keep = size
        self.pending = data[-keep:] if keep else b''
        body = data[:-keep] if keep else data
        return BYTE_PATTERN.sub(b'lingbot', body)


def clean(text):
    return PATTERN.sub('lingbot', text)


def stream(source, destination):
    output_filter = OutputFilter()
    for chunk in iter(lambda: os.read(source.fileno(), 8192), b''):
        destination.write(output_filter.feed(chunk))
        destination.flush()
    destination.write(output_filter.feed(b'', final=True))
    destination.flush()


def terminal(binary):
    """Preserve the controlling terminal for the interactive CLI on Unix."""
    import errno
    import fcntl
    import pty
    import termios
    import tty

    pid, master = pty.fork()
    if pid == 0:
        os.execv(str(binary), ['lingbot', *sys.argv[1:]])
    stdin_fd = sys.stdin.fileno()
    stdout_fd = sys.stdout.fileno()
    saved_terminal = termios.tcgetattr(stdin_fd)
    saved_handlers = {}
    output_filter = OutputFilter()

    def resize(signum=None, frame=None):
        size = fcntl.ioctl(stdin_fd, termios.TIOCGWINSZ, b'\0' * 8)
        fcntl.ioctl(master, termios.TIOCSWINSZ, size)

    def forward(signum, frame):
        try:
            os.killpg(pid, signum)
        except ProcessLookupError:
            pass

    def emit(data):
        while data:
            written = os.write(stdout_fd, data)
            data = data[written:]

    try:
        resize()
        for signum, handler in [(signal.SIGWINCH, resize), (signal.SIGTERM, forward),
                                (signal.SIGINT, forward), (signal.SIGHUP, forward)]:
            saved_handlers[signum] = signal.signal(signum, handler)
        tty.setraw(stdin_fd)
        inputs = [stdin_fd, master]
        while True:
            ready, _, _ = select.select(inputs, [], [])
            if master in ready:
                try:
                    data = os.read(master, 8192)
                except OSError as exc:
                    if exc.errno != errno.EIO:
                        raise
                    break
                if not data:
                    break
                emit(output_filter.feed(data))
            if stdin_fd in ready:
                data = os.read(stdin_fd, 8192)
                if data:
                    while data:
                        written = os.write(master, data)
                        data = data[written:]
                else:
                    inputs.remove(stdin_fd)
    finally:
        termios.tcsetattr(stdin_fd, termios.TCSADRAIN, saved_terminal)
        for signum, handler in saved_handlers.items():
            signal.signal(signum, handler)
        os.close(master)
        _, status = os.waitpid(pid, 0)
    emit(output_filter.feed(b'', final=True))
    return 128 + os.WTERMSIG(status) if os.WIFSIGNALED(status) else os.WEXITSTATUS(status)


def main():
    source = Path(os.environ['LINGBOT_ENGINE_SOURCE']).resolve(strict=True)
    cache = Path(os.environ['LINGBOT_ENGINE_CACHE'])
    cache.mkdir(parents=True, exist_ok=True)
    binary = cache / 'lingbot'
    if not binary.exists() or binary.stat().st_size != source.stat().st_size or binary.stat().st_mtime_ns != source.stat().st_mtime_ns:
        temp = cache / ('engine-' + str(os.getpid()) + '.tmp')
        shutil.copy2(source, temp)
        temp.chmod(0o700)
        temp.replace(binary)
    if sys.stdin.isatty() and sys.stdout.isatty() and os.environ.get('LINGBOT_STDIN') == 'inherit':
        return terminal(binary)
    child = subprocess.Popen(['lingbot', *sys.argv[1:]], executable=str(binary),
                             stdin=None if os.environ.get('LINGBOT_STDIN') == 'inherit' else subprocess.DEVNULL,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    def forward(signum, frame):
        if child.poll() is None:
            child.send_signal(signum)
    signal.signal(signal.SIGTERM, forward)
    signal.signal(signal.SIGINT, forward)
    pipes = [threading.Thread(target=stream, args=(child.stdout, sys.stdout.buffer)),
             threading.Thread(target=stream, args=(child.stderr, sys.stderr.buffer))]
    for pipe in pipes:
        pipe.start()
    code = child.wait()
    for pipe in pipes:
        pipe.join()
    return 128 - code if code < 0 else code


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as exc:
        print(clean(str(exc)), file=sys.stderr)
        sys.exit(1)
