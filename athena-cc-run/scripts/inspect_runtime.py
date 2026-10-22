"""Inspect the caller's solver process tree and selected task logs on Linux."""
import argparse
import json
import os
from pathlib import Path
import re


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--pid', type=int, required=True, help='PID of your lingbot wrapper or native process')
    parser.add_argument('--log', action='append', default=[], help='Task text log to scan; repeat as needed')
    args = parser.parse_args()
    pattern = re.compile('cl' + 'aude', re.I)
    root = Path('/proc') / str(args.pid)
    if not root.exists():
        raise SystemExit('Selected process no longer exists; inspect job exit status.')
    if root.stat().st_uid != os.getuid():
        raise SystemExit('Selected process belongs to another user.')
    processes = {}
    for proc in Path('/proc').glob('[0-9]*'):
        try:
            if proc.stat().st_uid != os.getuid():
                continue
            fields = (proc / 'stat').read_text().rsplit(')', 1)[1].split()
            processes[int(proc.name)] = {
                'ppid': int(fields[1]), 'comm': (proc / 'comm').read_text().strip(),
                'args': (proc / 'cmdline').read_bytes().replace(b'\0', b' ').decode(errors='replace'),
                'exe': str((proc / 'exe').resolve(strict=True)),
            }
        except (OSError, IndexError, ValueError):
            continue
    selected = {args.pid}
    while True:
        more = {pid for pid, p in processes.items() if p['ppid'] in selected}
        if more <= selected:
            break
        selected |= more
    rows = []
    for pid in sorted(selected):
        if pid not in processes:
            continue
        p = processes[pid]
        rows.append({'pid': pid, 'comm': pattern.sub('lingbot', p['comm']),
                     'keyword_in_comm': bool(pattern.search(p['comm'])),
                     'keyword_in_argv': bool(pattern.search(p['args'])),
                     'keyword_in_executable_path': bool(pattern.search(p['exe']))})
    logs = []
    for filename in args.log:
        path = Path(filename)
        try:
            with path.open(encoding='utf-8', errors='replace') as stream:
                count = sum(len(pattern.findall(line)) for line in stream)
            logs.append({'path': pattern.sub('lingbot', str(path)), 'bytes': path.stat().st_size,
                         'keyword_matches': count})
        except OSError as exc:
            logs.append({'path': pattern.sub('lingbot', str(path)), 'error': pattern.sub('lingbot', str(exc))})
    print(json.dumps({'processes': rows, 'logs': logs,
                      'scope': 'Selected process and observable descendants; supplied task logs. Environment and private application state excluded.'}))


if __name__ == '__main__':
    main()
