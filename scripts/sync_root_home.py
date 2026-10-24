#!/usr/bin/env python3
"""Copy the built homepage into the local user Pages checkout; never publish."""
import argparse
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DESTINATION = ROOT.parent / 'dadablog888.github.io'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination', type=Path, default=DEFAULT_DESTINATION)
    parser.add_argument('--check', action='store_true', help='Verify without writing')
    args = parser.parse_args()
    destination = args.destination.resolve()
    if not (destination / '.git').exists():
        parser.error(f'User Pages checkout missing: {destination}')
    remote = subprocess.check_output(
        ['git', '-C', str(destination), 'remote', 'get-url', 'origin'], text=True
    ).strip().removesuffix('.git')
    if remote not in ['https://github.com/dadablog888/dadablog888.github.io',
                      'git@github.com:dadablog888/dadablog888.github.io']:
        parser.error('Destination origin must be dadablog888/dadablog888.github.io')
    sources = {name: (ROOT / 'root-site' / name).read_bytes()
               for name in ['index.html', '.nojekyll']}
    if sources['index.html'] != (ROOT / 'index.html').read_bytes():
        parser.error('Homepage copy is stale; run python3 scripts/build.py first')
    for name, data in sources.items():
        target = destination / name
        matches = target.is_file() and target.read_bytes() == data
        if args.check and not matches:
            parser.error(f'User Pages copy missing or stale: {target}')
        if not args.check and not matches:
            target.write_bytes(data)
        if target.read_bytes() != data:
            parser.error(f'User Pages copy does not match: {target}')
    print(f'PASS: root homepage and .nojekyll match in {destination}; no commit or push.')


if __name__ == '__main__':
    main()
