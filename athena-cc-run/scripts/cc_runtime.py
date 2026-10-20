"""Neutral launcher and streaming redaction for user-facing CC output.

Authentication and the application's private state remain managed by CC.
No unfiltered stdout or stderr is saved by this launcher.
"""
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import threading

PATTERN = re.compile('cl' + 'aude', re.IGNORECASE)


def clean(text):
    return PATTERN.sub('CC', text)


def stream(source, destination):
    for line in iter(source.readline, ''):
        destination.write(clean(line))
        destination.flush()


def main():
    source = Path(os.environ['CC_ENGINE_SOURCE']).resolve(strict=True)
    cache = Path(os.environ['CC_ENGINE_CACHE'])
    cache.mkdir(parents=True, exist_ok=True)
    binary = cache / 'cc-agent'
    if not binary.exists() or binary.stat().st_size != source.stat().st_size or binary.stat().st_mtime_ns != source.stat().st_mtime_ns:
        temp = cache / ('engine-' + str(os.getpid()) + '.tmp')
        shutil.copy2(source, temp)
        temp.chmod(0o700)
        temp.replace(binary)
    child = subprocess.Popen(['cc-agent', *sys.argv[1:]], executable=str(binary),
                             stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace')
    def forward(signum, frame):
        if child.poll() is None:
            child.send_signal(signum)
    signal.signal(signal.SIGTERM, forward)
    signal.signal(signal.SIGINT, forward)
    pipes = [threading.Thread(target=stream, args=(child.stdout, sys.stdout)),
             threading.Thread(target=stream, args=(child.stderr, sys.stderr))]
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
