#!/usr/bin/env python3
"""Keep the host-root homepage equal to /blog/ in this single Pages checkout."""
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Verify without writing')
    args = parser.parse_args()
    source = ROOT / 'blog/index.html'
    if not source.is_file():
        parser.error('Missing blog/index.html; run python3 scripts/build.py first')
    target = ROOT / 'index.html'
    matches = target.is_file() and target.read_bytes() == source.read_bytes()
    if args.check and not matches:
        parser.error('Root homepage differs from /blog/; run build.py or sync_root_home.py')
    if not args.check:
        if not matches:
            target.write_bytes(source.read_bytes())
        if not (ROOT / '.nojekyll').is_file():
            (ROOT / '.nojekyll').write_bytes(b'')
    if not (ROOT / '.nojekyll').is_file():
        parser.error('Missing root .nojekyll; run build.py')
    print('PASS: index.html matches blog/index.html in this repository; no commit or push.')


if __name__ == '__main__':
    main()
