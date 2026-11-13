#!/usr/bin/env python3
"""Check a release directory for common accidental disclosures. Standard library only.

This is a heuristic aid, not a rights review or a complete secret scanner.
It does not inspect pixels, OCR, image metadata, or arbitrary encoded payloads.
"""
import argparse
import json
import re
import sys
from pathlib import Path

TEXT_EXT = {'.md', '.txt', '.json', '.yaml', '.yml', '.py', '.js', '.css', '.html', '.svg'}
PRIVATE_DIRS = {'private', 'private-backup', 'private-original-installed', '.git', 'node_modules', '__pycache__'}
PATTERNS = {
    'personal filesystem path': re.compile(r'(?:/(?:Users|home)/[\w. -]+/|[A-Z]:\\Users\\[\w. -]+\\)'),
    'private key': re.compile(r'-----BEGIN [A-Z ]*PRIVATE KEY-----'),
    'credential assignment': re.compile(r'''(?i)(?:api[_-]?key|access[_-]?token|password)\s*[:=]\s*["'][A-Za-z0-9_+/=-]{16,}["']'''),
    'private network URL': re.compile(r'https?://(?:localhost|127\.0\.0\.1|10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+|172\.(?:1[6-9]|2\d|3[01])\.\d+\.\d+)(?=[:/\s"\'])'),
    'embedded HTML payload': re.compile(r'(?i)data:text/html\s*[;,]'),
}
REMOTE = re.compile(r'''(?i)(?:\bsrc\s*=\s*["']https?://|url\(\s*["']?https?://|@import\s+["']https?://)''')


def audit(root, forbidden=()):
    findings = []
    files = 0
    for path in sorted(root.rglob('*')):
        rel = path.relative_to(root)
        name = str(rel)
        if path.is_symlink():
            findings.append((name, 'symlink needs review'))
            continue
        if not path.is_file():
            continue
        files += 1
        if any(part in PRIVATE_DIRS or part.startswith('.env') for part in rel.parts) or path.name in ('.DS_Store', 'private-baseline.json') or path.suffix in ('.pyc', '.pem', '.key'):
            findings.append((name, 'private or generated file'))
        if path.suffix.lower() not in TEXT_EXT and path.name not in ('LICENSE', '.gitignore'):
            continue
        try:
            content = path.read_text(encoding='utf-8')
        except UnicodeError:
            findings.append((name, 'unexpected non-UTF-8 text'))
            continue
        for label, pattern in PATTERNS.items():
            if pattern.search(content):
                findings.append((name, label))
        # Offline player assets must not load external resources. Attribution links are allowed.
        if path.suffix in ('.html', '.css') and REMOTE.search(content):
            findings.append((name, 'remote runtime asset'))
        if path.suffix in ('.html', '.js') and re.search(r'\b(?:fetch|XMLHttpRequest|atob)\s*\(', content):
            findings.append((name, 'network or encoded runtime payload needs review'))
        folded = content.casefold()
        if any(term.casefold() in folded or term.casefold() in name.casefold() for term in forbidden):
            findings.append((name, 'project-specific term'))
    return files, findings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--forbid-file', type=Path, help='private JSON list of exact terms; keep outside release')
    args = parser.parse_args()
    try:
        root = args.directory.resolve()
        if not root.is_dir():
            raise ValueError('directory does not exist')
        forbidden = json.loads(args.forbid_file.read_text(encoding='utf-8')) if args.forbid_file else []
        if not isinstance(forbidden, list) or any(not isinstance(x, str) or not x.strip() for x in forbidden):
            raise ValueError('forbid file must contain a JSON list of nonempty strings')
        files, findings = audit(root, forbidden)
        # Do not print matched text: it could itself be a secret.
        for path, label in findings:
            print(f'REVIEW: {path}: {label}')
        print(f'{"REVIEW REQUIRED" if findings else "PASS"}: {files} files; {len(findings)} findings. Images and rights need manual review.')
        return 1 if findings else 0
    except (ValueError, OSError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
