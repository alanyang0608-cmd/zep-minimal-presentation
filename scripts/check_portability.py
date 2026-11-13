#!/usr/bin/env python3
"""Smoke-test the renderer in an isolated, dependency-free Python environment."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
THEMES = ('blue-note', 'paper-grid', 'midnight', 'mono-signal', 'acid-notes')


def main():
    with tempfile.TemporaryDirectory(prefix='talkframe-') as temp:
        workspace = Path(temp)
        package = workspace / 'copy with spaces' / 'zep-minimal-presentation'
        # Copy only renderer inputs. No installed skill, user files, plugins,
        # optional dependencies, or knowledge-base files are available here.
        for name in ('scripts/build.py', 'assets/runtime/deck.css',
                     'assets/runtime/deck.js', 'assets/runtime/shell.html',
                     'examples/demo.json', 'examples/minimal.json'):
            target = package / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)
        working = workspace / 'separate working directory'
        working.mkdir()
        command = [sys.executable, '-I', '-S', str(package / 'scripts/build.py')]

        def call(*args, success=True):
            result = subprocess.run(command + list(args), cwd=working,
                                    capture_output=True, text=True, encoding='utf-8')
            if (result.returncode == 0) != success:
                raise RuntimeError(result.stderr or result.stdout or 'Unexpected build result')
            return result

        unselected = working / 'must-not-exist.html'
        call(str(package / 'examples/minimal.json'), '--out', str(unselected), success=False)
        if unselected.exists():
            raise RuntimeError('Unselected template unexpectedly produced output')
        demo = json.loads((package / 'examples/demo.json').read_text(encoding='utf-8'))
        for theme in THEMES:
            output = working / (theme + '.html')
            call(str(package / 'examples/demo.json'), '--theme', theme, '--check')
            call(str(package / 'examples/demo.json'), '--theme', theme, '--out', str(output))
            call(str(package / 'examples/demo.json'), '--theme', theme, '--verify', str(output))
            data = output.read_bytes()
            if data.count(b'<article class="slide ') != len(demo['slides']):
                raise RuntimeError('Unexpected slide count')
            if data != (ROOT / 'examples' / (theme + '.html')).read_bytes():
                raise RuntimeError('Bundled example differs from isolated build: ' + theme)
            print('PASS:', theme, str(len(demo['slides'])) + ' slides', hashlib.sha256(data).hexdigest())
        print('PASS: template selection, isolated Python, separate working directory, five exact builds.')
        print('This checks execution portability, not model judgment or browser rendering.')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, RuntimeError) as exc:
        print('ERROR:', exc, file=sys.stderr)
        sys.exit(1)
