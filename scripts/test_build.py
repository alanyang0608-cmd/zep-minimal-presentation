#!/usr/bin/env python3
"""Behavioral checks for validation, escaping, ratios and standalone builds."""
import json
import hashlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from build import ROOT, THEMES, VERSION, build, validate, review_content
from audit_release import audit


class DeckTests(unittest.TestCase):
    def setUp(self):
        self.deck = json.loads((ROOT/'examples/demo.json').read_text(encoding='utf-8'))

    def rejects(self, edit):
        edit(self.deck)
        with self.assertRaises(ValueError):
            validate(self.deck)

    def test_all_themes_standalone(self):
        for theme in THEMES:
            out = build(self.deck, ROOT/'examples', theme)
            self.assertEqual(out.count('<article class="slide '), len(self.deck['slides']))
            self.assertNotIn('@@CSS@@', out)
            self.assertNotIn('src="http', out)
            self.assertNotIn('fetch(', out)
            self.assertNotIn('<script src=', out)

    def test_missing_theme_stops_build(self):
        self.deck.pop('theme')
        with self.assertRaisesRegex(ValueError, 'No template selected'):
            build(self.deck, ROOT/'examples')

    def test_explicit_theme_builds_unselected_starter(self):
        deck = json.loads((ROOT/'examples/minimal.json').read_text(encoding='utf-8'))
        self.assertNotIn('theme', deck)
        for theme in THEMES:
            out = build(deck, ROOT/'examples', theme)
            self.assertIn(f'class="theme-{theme}"', out)
        self.assertNotIn('theme', deck)

    def test_explicit_override_takes_precedence(self):
        out = build(self.deck, ROOT/'examples', 'midnight')
        self.assertIn('class="theme-midnight"', out)
        self.assertEqual(self.deck['theme'], 'paper-grid')

    def test_missing_theme_cli_does_not_write_or_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)/'talk.html'
            command = [sys.executable, str(ROOT/'scripts/build.py'), str(ROOT/'examples/minimal.json'), '--out', str(output)]
            result = subprocess.run(command, cwd=tmp, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(output.exists())
            output.write_text('keep existing output', encoding='utf-8')
            result = subprocess.run(command, cwd=tmp, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(output.read_text(), 'keep existing output')

    def test_list_templates_without_build(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run([sys.executable, str(ROOT/'scripts/build.py'), '--list-themes'], cwd=tmp, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0)
            for theme in THEMES:
                self.assertIn(theme, result.stdout)
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_ratio_is_exact(self):
        out = build(self.deck, ROOT/'examples')
        self.assertEqual(out.count('class="matrix-dot filled"'), 16)
        self.assertEqual(out.count('class="matrix-dot empty"'), 4)

    def test_bad_ratio(self):
        self.rejects(lambda d:d['slides'][5].update(value=12))

    def test_fractional_dot_rejected(self):
        self.rejects(lambda d:d['slides'][5].update(value=1,total=3,dots=20))

    def test_duplicate_id(self):
        self.rejects(lambda d:d['slides'][2].update(id='opening'))

    def test_missing_target(self):
        self.rejects(lambda d:d['slides'][1]['items'][0].update(target='missing'))

    def test_invalid_chart(self):
        self.rejects(lambda d:d['slides'][9].update(labels=['one']))

    def test_nan(self):
        self.rejects(lambda d:d['slides'][9]['values'].__setitem__(0,float('nan')))

    def test_title_budget(self):
        self.rejects(lambda d:d['slides'][0].update(title='长'*73))

    def test_unknown_field(self):
        self.rejects(lambda d:d['slides'][0].update(raw_html='<b>bad</b>'))

    def test_source_javascript(self):
        self.rejects(lambda d:d['slides'][0].update(sources=[{'label':'x','url':'javascript:alert(1)'}]))

    def test_escape_content(self):
        self.deck['slides'][0]['title']='</script><script>alert(1)</script>'
        out=build(self.deck,ROOT/'examples')
        self.assertNotIn('<script>alert(1)</script>',out)
        self.assertIn('&lt;/script&gt;',out)

    def test_template_tokens_stay_text(self):
        self.deck['title'] = '@@JS@@'
        self.deck['slides'][0]['title'] = '@@OVERVIEW@@'
        out = build(self.deck, ROOT/'examples')
        self.assertIn('<title>@@JS@@</title>', out)
        self.assertIn('<span class="line">@@OVERVIEW@@</span>', out)

    def test_image_path_escape(self):
        self.deck['slides'][10]['items'][0]={'title':'x','image':'../outside.png','alt':'x','credit':'x'}
        with self.assertRaisesRegex(ValueError,'inside'):
            build(self.deck,ROOT/'examples')

    def test_valid_image_embedding(self):
        import base64
        with tempfile.TemporaryDirectory() as tmp:
            parent=Path(tmp)
            (parent/'sample.png').write_bytes(base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aN1sAAAAASUVORK5CYII='))
            self.deck['slides'][10]['items'][0]={'title':'x','image':'sample.png','alt':'test pixel','credit':'Authored test pixel'}
            out=build(self.deck,parent)
            self.assertIn('src="data:image/png;base64,',out)
            self.assertIn('alt="test pixel"',out)

    def test_identical_input_is_deterministic(self):
        self.assertEqual(build(self.deck, ROOT/'examples'), build(self.deck, ROOT/'examples'))

    def test_provenance_matches_renderer(self):
        css = (ROOT/'assets/runtime/deck.css').read_text(encoding='utf-8')
        digest = hashlib.sha256(css.encode('utf-8')).hexdigest()
        for theme in THEMES:
            out = build(self.deck, ROOT/'examples', theme)
            self.assertIn(f'<meta name="presentation-version" content="{VERSION}">', out)
            self.assertIn(f'<meta name="presentation-theme" content="{theme}">', out)
            self.assertIn(f'<meta name="presentation-style-sha256" content="{digest}">', out)
            self.assertIn('<style>' + css + '</style>', out)

    def verify_cli(self, mutate=None, theme='paper-grid'):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)/'talk.html'
            command = [sys.executable, str(ROOT/'scripts/build.py'), str(ROOT/'examples/demo.json')]
            generated = subprocess.run(command + ['--out', str(output)], cwd=tmp, capture_output=True, text=True)
            self.assertEqual(generated.returncode, 0, generated.stderr)
            if mutate:
                original = output.read_bytes()
                changed = mutate(original)
                self.assertNotEqual(changed, original, 'test mutation must change the output')
                output.write_bytes(changed)
            before = output.read_bytes()
            mtime = output.stat().st_mtime_ns
            result = subprocess.run(command + ['--theme', theme, '--verify', str(output)], cwd=tmp, capture_output=True, text=True)
            self.assertEqual(output.read_bytes(), before)
            self.assertEqual(output.stat().st_mtime_ns, mtime)
            self.assertEqual(list(Path(tmp).iterdir()), [output])
            return result

    def test_verify_accepts_exact_build_without_writing(self):
        result = self.verify_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('exact build match', result.stdout)

    def test_verify_rejects_changed_color(self):
        result = self.verify_cli(lambda data: data.replace(b'#1769e6', b'#176a51', 1))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('regenerate from JSON', result.stderr)

    def test_verify_rejects_override_even_when_metadata_is_unchanged(self):
        result = self.verify_cli(lambda data: data.replace(b'</head>', b'<style>body{color:red!important}</style></head>'))
        self.assertNotEqual(result.returncode, 0)

    def test_verify_rejects_wrong_theme(self):
        result = self.verify_cli(theme='midnight')
        self.assertNotEqual(result.returncode, 0)

    def test_verify_rejects_changed_content(self):
        result = self.verify_cli(lambda data: data.replace(b'<title>', b'<title>changed ', 1))
        self.assertNotEqual(result.returncode, 0)

    def test_verify_cannot_overwrite_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)/'talk.html'
            output.write_bytes(b'keep')
            result = subprocess.run([sys.executable, str(ROOT/'scripts/build.py'), str(ROOT/'examples/demo.json'), '--verify', str(output), '--out', str(output)], cwd=tmp, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(output.read_bytes(), b'keep')

    def test_auto_tones_are_fixed_for_each_template(self):
        deck = {'title': 'Template tones', 'slides': [
            {'id': 'cover', 'type': 'cover', 'title': 'Cover'},
            {'id': 'body', 'type': 'statement', 'title': 'Body'},
            {'id': 'chapter', 'type': 'section', 'title': 'Chapter'},
            {'id': 'end', 'type': 'end', 'title': 'End'},
        ]}
        expected = {
            'blue-note': ('accent','dark','dark','accent'),
            'paper-grid': ('light','light','light','light'),
            'midnight': ('dark','dark','dark','dark'),
            'mono-signal': ('dark','dark','dark','dark'),
            'acid-notes': ('accent','dark','accent','accent'),
        }
        for theme in THEMES:
            out = build(deck, ROOT/'examples', theme)
            for kind, tone in zip(('cover','statement','section','end'), expected[theme]):
                self.assertIn(f'class="slide type-{kind} tone-{tone}"', out)

    def test_explicit_tone_is_preserved(self):
        self.deck['slides'][0]['tone']='light'
        self.assertIn('class="slide type-cover tone-light"',build(self.deck,ROOT/'examples','blue-note'))

    def test_emphasis_is_escaped_and_matched_as_text(self):
        s=self.deck['slides'][0]
        s['title']='Use <script> as text'
        s['emphasis']=['<script>']
        out=build(self.deck,ROOT/'examples')
        self.assertIn('<em class="highlight">&lt;script&gt;</em>',out)
        self.assertNotIn('<em class="highlight"><script>',out)
        s['emphasis']=['missing']
        with self.assertRaises(ValueError):validate(self.deck)
        s['emphasis']='Use'
        with self.assertRaises(ValueError):validate(self.deck)

    def test_section_links_and_active_item_are_validated(self):
        section=next(x for x in self.deck['slides'] if x['type']=='section')
        section['items'][0]['target']='missing'
        with self.assertRaises(ValueError):validate(self.deck)
        section['items'][0]['target']='opening'
        section['active']='not-in-menu'
        with self.assertRaises(ValueError):validate(self.deck)

    def test_single_figure_preserves_alt_and_credit(self):
        s=self.deck['slides'][10]
        s['items']=s['items'][:1]
        out=build(self.deck,ROOT/'examples')
        self.assertIn('type-gallery tone-light gallery-single',out)
        s['items']=[]
        with self.assertRaises(ValueError):validate(self.deck)

    def test_editorial_review_is_non_mutating_and_nonblocking(self):
        import copy
        deck={'title':'A talk','theme':'blue-note','slides':[
            {'id':str(i),'type':'columns','title':'A topic','items':[{'title':'First'},{'title':'Second'}]} for i in range(8)]}
        before=copy.deepcopy(deck)
        self.assertEqual(len(review_content(deck)),2)
        build(deck,ROOT/'examples')
        self.assertEqual(deck,before)

    def test_private_term_scanner(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp)
            (parent/'note.md').write_text('PrivateExampleName', encoding='utf-8')
            _, findings = audit(parent, ['PrivateExampleName'])
            self.assertEqual(findings, [('note.md', 'project-specific term')])

    def test_audit_detects_remote_resource(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp)
            (parent/'page.html').write_text('<img ' + 'src="https://example.org/image.png">', encoding='utf-8')
            _, findings = audit(parent)
            self.assertIn(('page.html', 'remote runtime asset'), findings)

    def test_audit_detects_home_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp)
            (parent/'note.md').write_text('/' + 'Users' + '/sample-account/doc.txt', encoding='utf-8')
            _, findings = audit(parent)
            self.assertIn(('note.md', 'personal filesystem path'), findings)

    def test_audit_allows_public_attribution(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp)
            (parent/'page.html').write_text('<a href="https://example.org/source">Source</a>', encoding='utf-8')
            _, findings = audit(parent)
            self.assertEqual(findings, [])


if __name__=='__main__':
    unittest.main()
