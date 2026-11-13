#!/usr/bin/env python3
"""Build an offline presentation. Python 3.9+; standard library only."""
import argparse
import base64
import hashlib
import html
import json
import math
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
VERSION = '1.1.1'
THEMES = ('blue-note', 'paper-grid', 'midnight', 'mono-signal', 'acid-notes')
THEME_LABELS = {
    'blue-note': '黑白蓝 / Blue note — 大观点、蓝色开场；适合观点分享',
    'paper-grid': '白底报告 / Paper grid — 细线、留白、分栏；适合研究复盘',
    'midnight': '深靛科技 / Midnight — 深色、亮字、细框；适合技术流程',
    'mono-signal': '黑白系统 / Mono signal — 粗标题、模块结构；适合方法框架',
    'acid-notes': '荧光黄点阵 / Acid notes — 酸黄、方点、强文字；适合创意表达',
}
MOTIONS = ('static', 'words', 'list', 'metrics', 'timeline', 'draw')
TYPES = ('cover', 'contents', 'statement', 'columns', 'metrics', 'ratio',
         'timeline', 'process', 'comparison', 'chart', 'gallery', 'end', 'section', 'rows', 'dialogue')
TOP_KEYS = {'title', 'subtitle', 'theme', 'language', 'footer', 'slides'}
COMMON = {'id', 'type', 'title', 'kicker', 'body', 'notes', 'sources', 'motion', 'tone', 'emphasis'}
FIELDS = {
    'cover': {'subtitle'}, 'contents': {'items'}, 'statement': {'subtitle'},
    'columns': {'items'}, 'metrics': {'items'},
    'ratio': {'value', 'total', 'unit', 'caption', 'basis', 'dots'},
    'timeline': {'items'}, 'process': {'items'}, 'comparison': {'items'},
    'chart': {'values', 'labels', 'unit', 'basis', 'caption'},
    'gallery': {'items'}, 'end': {'subtitle'},
    'section': {'items', 'active', 'subtitle'}, 'rows': {'items'}, 'dialogue': {'items'},
}
DEFAULT_MOTION = {'cover': 'words', 'contents': 'list', 'statement': 'words',
                  'columns': 'list', 'metrics': 'metrics', 'ratio': 'metrics',
                  'timeline': 'timeline', 'process': 'timeline', 'comparison': 'list',
                  'chart': 'draw', 'gallery': 'static', 'end': 'static',
                  'section': 'list', 'rows': 'list', 'dialogue': 'words'}

# Deterministic semantic backgrounds; no random or page-number alternation.
AUTO_TONES = {
    'blue-note': {'cover': 'accent', 'contents': 'dark', 'section': 'dark', 'statement': 'dark', 'end': 'accent'},
    'paper-grid': {},
    'midnight': {kind: 'dark' for kind in TYPES},
    'mono-signal': {'cover': 'dark', 'section': 'dark', 'statement': 'dark', 'end': 'dark'},
    'acid-notes': {'cover': 'accent', 'section': 'accent', 'statement': 'dark', 'end': 'accent'},
}


def text(value, where, limit=1000, required=False):
    if value is None and not required:
        return
    if not isinstance(value, str) or (required and not value.strip()):
        raise ValueError(f'{where}: expected nonempty text' if required else f'{where}: expected text')
    if len(value) > limit:
        raise ValueError(f'{where}: {len(value)} characters; limit {limit}. Split or edit the slide.')
    if any(ord(c) < 32 and c not in '\n\t' for c in value):
        raise ValueError(f'{where}: control characters are not supported')


def number(value, where, low=0):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < low:
        raise ValueError(f'{where}: expected a finite number >= {low}')


def check_keys(obj, allowed, where):
    if not isinstance(obj, dict):
        raise ValueError(f'{where}: expected an object')
    extra = set(obj) - allowed
    if extra:
        raise ValueError(f'{where}: unknown fields {sorted(extra)}')


def validate(deck):
    check_keys(deck, TOP_KEYS, 'deck')
    text(deck.get('title'), 'title', 100, True)
    for key in ('subtitle', 'footer'):
        text(deck.get(key), key, 160)
    if 'theme' in deck and deck['theme'] not in THEMES:
        raise ValueError('theme: choose ' + ', '.join(THEMES))
    if deck.get('language', 'zh-CN') not in ('zh-CN', 'en'):
        raise ValueError('language: use zh-CN or en')
    slides = deck.get('slides')
    if not isinstance(slides, list) or not 1 <= len(slides) <= 100:
        raise ValueError('slides: expected 1–100 slides')
    ids = set()
    for i, s in enumerate(slides):
        where = f'slides[{i}]'
        if not isinstance(s, dict) or s.get('type') not in TYPES:
            raise ValueError(f'{where}: type must be one of {TYPES}')
        kind = s['type']
        check_keys(s, COMMON | FIELDS[kind], where)
        text(s.get('id'), where + '.id', 64, True)
        if s['id'] in ids:
            raise ValueError(f'{where}: duplicate id {s["id"]}')
        ids.add(s['id'])
        text(s.get('title'), where + '.title', 72 if kind in ('cover', 'statement', 'end', 'section', 'dialogue') else 48, True)
        emphasis = s.get('emphasis', [])
        if not isinstance(emphasis, list) or len(emphasis) > 3:
            raise ValueError(f'{where}.emphasis: use up to three title phrases')
        for phrase in emphasis:
            text(phrase, where + '.emphasis', 32, True)
            if '\n' in phrase or phrase not in s['title']:
                raise ValueError(f'{where}.emphasis: phrase must occur within one title line')
        for key, limit in [('kicker', 45), ('body', 170), ('subtitle', 100), ('caption', 130), ('basis', 170), ('notes', 4000), ('unit', 20)]:
            text(s.get(key), where + '.' + key, limit)
        if s.get('tone', 'auto') not in ('auto', 'light', 'dark', 'accent'):
            raise ValueError(f'{where}.tone: auto, light, dark or accent')
        if s.get('motion', DEFAULT_MOTION[kind]) not in MOTIONS:
            raise ValueError(f'{where}.motion: {MOTIONS}')
        sources = s.get('sources', [])
        if not isinstance(sources, list):
            raise ValueError(f'{where}.sources: expected a list')
        for source in sources:
            check_keys(source, {'label', 'url'}, where + '.sources')
            text(source.get('label'), where + '.source.label', 160, True)
            u = urlparse(source.get('url', ''))
            if u.scheme != 'https' or not u.netloc or u.username or u.password:
                raise ValueError(f'{where}: source links must use HTTPS without embedded credentials')
        if kind == 'ratio':
            number(s.get('value'), where + '.value')
            number(s.get('total'), where + '.total', 0.000001)
            if s['value'] > s['total']:
                raise ValueError(f'{where}: value exceeds total')
            text(s.get('basis'), where + '.basis', 170, True)
            count = s.get('dots', 0)
            if not isinstance(count, int) or isinstance(count, bool) or not 0 <= count <= 100:
                raise ValueError(f'{where}.dots: integer from 0 to 100; 0 uses a bar')
            if count and not math.isclose(s['value'] / s['total'] * count, round(s['value'] / s['total'] * count), abs_tol=1e-8):
                raise ValueError(f'{where}: dot count cannot represent this proportion exactly; use dots=0 or a compatible count')
        if kind == 'chart':
            values, labels = s.get('values'), s.get('labels')
            if not isinstance(values, list) or not 2 <= len(values) <= 8 or not isinstance(labels, list) or len(values) != len(labels):
                raise ValueError(f'{where}: chart needs 2–8 equally spaced values and matching labels')
            for v in values:
                number(v, where + '.values')
            for label in labels:
                text(label, where + '.labels', 16, True)
            text(s.get('basis'), where + '.basis', 170, True)
        if 'items' in FIELDS[kind] and not (kind == 'section' and 'items' not in s):
            items = s.get('items')
            bounds = {'contents': (2, 7), 'columns': (2, 4), 'metrics': (2, 4), 'timeline': (2, 5),
                      'process': (2, 5), 'comparison': (2, 2), 'gallery': (1, 3),
                      'section': (2, 7), 'rows': (2, 4), 'dialogue': (2, 3)}[kind]
            if not isinstance(items, list) or not bounds[0] <= len(items) <= bounds[1]:
                raise ValueError(f'{where}.items: expected {bounds[0]}–{bounds[1]} entries')
            for j, item in enumerate(items):
                loc = f'{where}.items[{j}]'
                check_keys(item, {'title', 'body', 'value', 'unit', 'label', 'target', 'image', 'alt', 'credit', 'art'}, loc)
                for key, limit in [('title', 32), ('body', 95), ('value', 14), ('unit', 12), ('label', 20), ('target', 64), ('alt', 160), ('credit', 200)]:
                    text(item.get(key), loc + '.' + key, limit, key == 'title')
                if kind == 'metrics':
                    text(item.get('value'), loc + '.value', 14, True)
                if kind == 'timeline':
                    text(item.get('label'), loc + '.label', 20, True)
                if kind == 'gallery':
                    if bool(item.get('image')) == bool(item.get('art')):
                        raise ValueError(f'{loc}: choose either a local image or built-in art')
                    if item.get('art') and item['art'] not in ('layers', 'route', 'window'):
                        raise ValueError(f'{loc}.art: layers, route or window')
                    if item.get('image'):
                        text(item['image'], loc + '.image', 300, True)
                        text(item.get('alt'), loc + '.alt', 160, True)
                        text(item.get('credit'), loc + '.credit', 200, True)
    for s in slides:
        if s['type'] in ('contents', 'section'):
            for item in s.get('items', []):
                if item.get('target') not in ids:
                    raise ValueError(f'contents target not found: {item.get("target")}')
            if 'active' in s and s['active'] not in [x['target'] for x in s.get('items', [])]:
                raise ValueError('section active target must appear in its navigation')
    return deck


def esc(value):
    return html.escape(str(value), quote=True)


def para(value, cls=''):
    return f'<p class="{cls}">{esc(value).replace(chr(10), "<br>")}</p>' if value else ''


def heading(value, tag='h1', emphasis=()):
    pattern = re.compile('|'.join(re.escape(x) for x in sorted(set(emphasis), key=lambda x: (-len(x), x)))) if emphasis else None
    def line_html(line):
        if pattern is None:
            return esc(line)
        result, start = [], 0
        for match in pattern.finditer(line):
            result.extend([esc(line[start:match.start()]), '<em class="highlight">' + esc(match.group()) + '</em>'])
            start = match.end()
        return ''.join(result) + esc(line[start:])
    return f'<{tag}>' + ''.join(f'<span class="line">{line_html(line)}</span>' for line in value.split('\n')) + f'</{tag}>'


def artwork(name):
    # Authored geometric diagrams; no imported brand shapes or external resources.
    shapes = {
        'layers': '<rect x="64" y="45" width="290" height="42"/><rect x="88" y="105" width="290" height="42"/><rect x="112" y="165" width="290" height="42"/><path d="M64 110H35V230H402"/>',
        'route': '<path d="M45 210H150V125H270V55H435"/><circle cx="45" cy="210" r="12"/><circle cx="150" cy="125" r="12"/><circle cx="270" cy="55" r="12"/><circle cx="435" cy="55" r="12"/>',
        'window': '<rect x="55" y="38" width="370" height="205"/><path d="M55 82H425M190 82V243M220 115H390M220 145H350M220 175H375M220 205H310"/><circle cx="78" cy="60" r="3"/><circle cx="94" cy="60" r="3"/>',
    }
    return f'<svg class="art" viewBox="0 0 480 280" aria-hidden="true"><g>{shapes[name]}</g></svg>'


def local_image(item, parent):
    raw_path = parent / item['image']
    if raw_path.is_symlink():
        raise ValueError('image symlinks are not supported')
    path = raw_path.resolve()
    try:
        path.relative_to(parent.resolve())
    except ValueError:
        raise ValueError('image must be inside the JSON file directory')
    if not path.is_file() or path.is_symlink():
        raise ValueError('image file missing or unsupported')
    mime = {'.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.webp': 'image/webp'}.get(path.suffix.lower())
    if not mime or path.stat().st_size > 10 * 1024 * 1024:
        raise ValueError('images: PNG/JPEG/WebP up to 10 MiB; SVG/raw HTML not accepted')
    data = base64.b64encode(path.read_bytes()).decode('ascii')
    return f'<img src="data:{mime};base64,{data}" alt="{esc(item["alt"])}">'


def render_body(s, ids, parent):
    kind = s['type']
    h = heading(s['title'], 'h1' if kind in ('cover', 'statement', 'end', 'section', 'dialogue') else 'h2', s.get('emphasis', []))
    lead = para(s.get('body'), 'lead')
    if kind in ('cover', 'statement', 'end'):
        return f'<div class="hero">{h}{para(s.get("subtitle"), "subhead")}{lead}</div><div class="signature" aria-hidden="true"><i></i><i></i><i></i><i></i></div>'
    if kind == 'section':
        rows = []
        for j, item in enumerate(s.get('items', [])):
            active = item['target'] == s.get('active')
            current = 'aria-current="step"' if active else ''
            rows.append(f'<button class="chapter-row animate-item {"selected" if active else ""}" data-go="{ids[item["target"]]}" {current}><small>{j+1:02}</small><span>{esc(item["title"])}</span></button>')
        rows = ''.join(rows)
        nav = f'<nav class="chapter-index" aria-label="Chapter navigation">{rows}</nav>' if rows else ''
        return nav + f'<div class="chapter-title">{h}{para(s.get("subtitle"), "subhead")}{lead}</div>'
    if kind == 'contents':
        rows = ''.join(f'<button class="toc-row animate-item" data-go="{ids[item["target"]]}"><small>{j+1:02}</small><strong>{esc(item["title"])}</strong><span aria-hidden="true">↗</span></button>' for j, item in enumerate(s['items']))
        return f'<div class="contents-intro">{h}{lead}</div><nav class="toc" aria-label="Contents">{rows}</nav>'
    if kind in ('columns', 'metrics', 'process', 'timeline', 'comparison', 'rows', 'dialogue'):
        cards = []
        for j, item in enumerate(s['items']):
            top = ''
            if kind == 'metrics':
                top = f'<div class="metric-value">{esc(item["value"])}<small>{esc(item.get("unit", ""))}</small></div>'
            elif kind == 'timeline':
                top = f'<div class="time-label">{esc(item["label"])}</div>'
            else:
                top = f'<div class="item-index">{j+1:02}</div>'
            cards.append(f'<section class="item animate-item">{top}<h3>{esc(item["title"])}</h3>{para(item.get("body"))}</section>')
        return f'<header class="content-heading">{h}{lead}</header><div class="items {kind}" style="--count:{len(cards)}">{"".join(cards)}</div>'
    if kind == 'ratio':
        fraction = s['value'] / s['total']
        percent = f'{fraction * 100:.1f}'.rstrip('0').rstrip('.') if fraction * 100 % 1 else str(int(fraction * 100))
        count = s.get('dots', 0)
        if count:
            filled = round(fraction * count)
            shape = '<div class="dot-matrix" role="img" aria-label="' + esc(f'{s["value"]} / {s["total"]}; {percent}%') + '">' + ''.join(f'<i class="matrix-dot {"filled" if j<filled else "empty"}" aria-hidden="true"></i>' for j in range(count)) + '</div>'
        else:
            shape = f'<div class="ratio-track" role="img" aria-label="{esc(percent)}%"><div class="ratio-fill" style="width:{fraction*100}%"></div></div>'
        return f'<div class="ratio-intro">{h}{lead}{para(s["basis"], "basis")}</div><div class="ratio-visual"><div class="ratio-value">{percent}<small>%</small></div>{shape}{para(s.get("caption"))}</div>'
    if kind == 'chart':
        values = s['values']; peak = max(max(values), 1); ceiling = math.ceil(peak / 4) * 4
        coords = [(60 + j * 820 / (len(values)-1), 250 - v / ceiling * 210) for j, v in enumerate(values)]
        grid = ''.join(f'<line x1="60" x2="880" y1="{250-j*52.5}" y2="{250-j*52.5}"/><text x="40" y="{256-j*52.5}" text-anchor="end">{ceiling*j/4:g}</text>' for j in range(5))
        labels = ''.join(f'<text x="{x}" y="290" text-anchor="middle">{esc(label)}</text>' for (x,y),label in zip(coords,s['labels']))
        points = ''.join(f'<circle cx="{x}" cy="{y}" r="5"/><text class="data-value" x="{x}" y="{y-14}" text-anchor="middle">{v:g}</text>' for (x,y),v in zip(coords,values))
        path = 'M' + 'L'.join(f'{x},{y}' for x,y in coords)
        svg = f'<svg class="chart-svg" viewBox="0 0 940 315" role="img" aria-label="{esc(s["title"])}"><g class="chart-grid">{grid}</g><path class="chart-line" d="{path}"/><g class="chart-points">{points}</g><g class="chart-labels">{labels}</g></svg>'
        return f'<header class="content-heading">{h}{lead}</header><div class="chart-wrap">{para(s.get("unit"), "axis-unit")}{svg}</div>{para(s["basis"], "basis")}{para(s.get("caption"), "caption")}'
    if kind == 'gallery':
        cards = []
        for item in s['items']:
            media = local_image(item, parent) if item.get('image') else artwork(item['art'])
            cards.append(f'<figure><div class="media">{media}</div><figcaption><h3>{esc(item["title"])}</h3>{para(item.get("body"))}{para(item.get("credit"), "credit")}</figcaption></figure>')
        return f'<header class="content-heading">{h}{lead}</header><div class="gallery" style="--count:{len(cards)}">{"".join(cards)}</div>'
    raise ValueError('Unknown slide type')


def resolve_theme(deck, override=None):
    selected = override if override is not None else deck.get('theme')
    if selected is None:
        raise ValueError('No template selected / 尚未选择模板。Show the five options with --list-themes, ask the user, then set theme or --theme. No default is applied.')
    if selected not in THEMES:
        raise ValueError('Unknown theme; choose ' + ', '.join(THEMES))
    return selected


def review_content(deck):
    """Nonblocking editorial prompts; never remove facts or force a page quota."""
    slides, advice, run = deck['slides'], [], 0
    if len(slides) >= 8 and not any(s['type'] == 'statement' for s in slides):
        advice.append('No standalone viewpoint page. Consider separating one supported conclusion from its explanation.')
    for i, slide in enumerate(slides, 1):
        run = run + 1 if slide['type'] == 'columns' else 0
        if run == 4:
            advice.append(f'Slide {i}: four consecutive column layouts. Check whether rows, an image, a process or a viewpoint better expresses the relationship.')
        if slide['type'] == 'statement' and slide.get('body'):
            advice.append(f'Slide {i}: statement includes body text. Consider keeping the viewpoint on screen and moving explanation to notes or the next slide.')
    return advice


def build(deck, parent, theme=None):
    validate(deck)
    selected = resolve_theme(deck, theme)
    ids = {s['id']: i for i, s in enumerate(deck['slides'])}
    slides = []
    overview = []
    for i, s in enumerate(deck['slides']):
        tone = s.get('tone', 'auto')
        if tone == 'auto':
            tone = AUTO_TONES[selected].get(s['type'], 'light')
        default_motion = 'words' if s['type'] == 'section' and not s.get('items') else DEFAULT_MOTION[s['type']]
        motion = s.get('motion', default_motion)
        sources = ''.join(f'<li><a href="{esc(x["url"])}" target="_blank" rel="noopener noreferrer">{esc(x["label"])}</a></li>' for x in s.get('sources', []))
        notes = para(s.get('notes') or '—') + (f'<ul>{sources}</ul>' if sources else '')
        extra = ' gallery-single' if s['type'] == 'gallery' and len(s['items']) == 1 else ''
        slides.append(f'<article class="slide type-{s["type"]} tone-{tone}{extra}" id="slide-{i+1}" data-index="{i}" data-motion="{motion}" data-motion-state="idle" aria-label="{i+1}. {esc(s["title"])}" {"hidden" if i else ""}><div class="slide-head"><span>{esc(s.get("kicker", ""))}</span><span>{i+1:02} / {len(deck["slides"]):02}</span></div><div class="content">{render_body(s,ids,parent)}</div><footer class="slide-foot"><span>{esc(deck.get("footer", ""))}</span><span>{i+1:02}</span></footer><template class="notes-template">{notes}</template></article>')
        overview.append(f'<button data-go="{i}" class="overview-item"><span>{i+1:02}</span><strong>{esc(s["title"]).replace(chr(10), " ")}</strong><small>{esc(s["type"])}</small></button>')
    shell = (ROOT/'assets/runtime/shell.html').read_text(encoding='utf-8')
    css = (ROOT/'assets/runtime/deck.css').read_text(encoding='utf-8')
    values = {'TITLE': esc(deck['title']), 'LANG': deck.get('language', 'zh-CN'), 'THEME': selected,
              'VERSION': VERSION, 'STYLE_HASH': hashlib.sha256(css.encode('utf-8')).hexdigest(),
              'CSS': css,
              'JS': (ROOT/'assets/runtime/deck.js').read_text(encoding='utf-8'),
              'SLIDES': ''.join(slides), 'OVERVIEW': ''.join(overview)}
    # One pass: content containing a placeholder must stay literal content.
    return re.sub(r'@@(TITLE|LANG|THEME|VERSION|STYLE_HASH|CSS|JS|SLIDES|OVERVIEW)@@',
                  lambda match: values[match.group(1)], shell)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('deck', type=Path, nargs='?')
    parser.add_argument('--theme', choices=THEMES)
    parser.add_argument('--list-themes', action='store_true', help='show all five templates without generating a presentation')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--out', type=Path, help='write HTML (default: presentation.html)')
    mode.add_argument('--check', action='store_true', help='validate input without writing output')
    mode.add_argument('--verify', type=Path, metavar='HTML', help='compare an existing HTML against a fresh build; write nothing')
    args = parser.parse_args()
    if args.list_themes:
        for index, theme in enumerate(THEMES, 1):
            print(f'{index}. {theme} — {THEME_LABELS[theme]}')
        print('Preview: assets/previews/overview.jpg')
        print('Ask for a number or name before generating. / 请先选择编号或模板名称。')
        return 0
    if args.deck is None:
        parser.error('provide a deck JSON, or use --list-themes')
    try:
        deck = json.loads(args.deck.read_text(encoding='utf-8'))
        result = build(deck, args.deck.parent, args.theme)
        if args.verify is not None:
            if args.verify.read_bytes() != result.encode('utf-8'):
                raise ValueError('Output differs from the supplied JSON, selected theme or current renderer. '
                                 'Use the same package version and --theme, then regenerate from JSON. '
                                 'Do not patch output HTML/CSS. / 成稿与当前输入或模板不一致；请从JSON重新生成。')
            status = 'verified: exact build match (read-only)'
        elif args.check:
            status = 'validated'
            for advice in review_content(deck):
                print('ADVICE: ' + advice, file=sys.stderr)
        else:
            output = args.out if args.out is not None else Path('presentation.html')
            output.parent.mkdir(parents=True, exist_ok=True)
            # Fixed UTF-8 bytes also avoid platform-dependent newline conversion.
            output.write_bytes(result.encode('utf-8'))
            status = str(output)
        print(f'OK: v{VERSION}; {len(deck["slides"])} slides; {resolve_theme(deck, args.theme)}; {status}')
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
