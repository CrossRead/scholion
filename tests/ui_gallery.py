"""Build an offline, synthetic gallery using the shipped assets and catalogues."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import shutil

from scholion import i18n


def build(web: Path, destination: Path) -> Path:
    destination.mkdir(parents=True, exist_ok=True)
    page = (web / 'index.html').read_text(encoding='utf-8')
    # Styles are used verbatim in their original cascade, not reconstructed.
    style = page.split('<style>', 1)[1].split('</style>', 1)[0]
    for name in ('crossread.css', 'gene-cards.css', 'gene-cards.js', 'measurements.js', 'system-views.js', 'system-views.css'):
        if (web / name).exists():
            shutil.copy2(web / name, destination / name)
    fixtures = Path(__file__).parent / 'browser'
    for path in fixtures.glob('gallery*.js'):
        shutil.copy2(path, destination / path.name)
    messages = json.dumps({k: i18n.CATALOGUES[k] for k in ('en', 'ru')}, ensure_ascii=True).replace('<', '\\u003c')
    measurement = '<script src="measurements.js"></script><script src="gallery-measurements.js"></script>' if (web / 'measurements.js').exists() else ''
    systems = '<script src="system-views.js"></script><script src="gallery-system-cases.js"></script><script src="gallery-systems.js"></script>' if (web / 'system-views.js').exists() else ''
    html = '''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Scholion synthetic component gallery</title><link rel="stylesheet" href="crossread.css">
<style>''' + style + '''</style><link rel="stylesheet" href="system-views.css"><link rel="stylesheet" href="gene-cards.css"></head><body>
<main style="padding:16px;max-width:1100px;margin:auto">
<h1>Synthetic component gallery</h1><p>No personal data. Presentation fixtures only.</p>
<label>Language <select id="language"><option>en</option><option>ru</option></select></label>
<label>Register <select id="register"><option>patient</option><option>clinician</option></select></label>
<label>Theme <select id="theme"><option>light</option><option>dark</option></select></label>
<div id="cards"></div><div id="measurements"></div><div id="systems"></div></main>
<script src="gene-cards.js"></script><script src="gallery-cases.js"></script>''' + measurement + systems + '''
<script>const MESSAGES=''' + messages + ''';</script><script src="gallery.js"></script></body></html>'''
    target = destination / 'index.html'
    target.write_text(html, encoding='utf-8')
    return target


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--web', type=Path, default=Path(__file__).resolve().parents[1] / 'src/scholion/web')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    print(build(args.web.resolve(), args.out.resolve()))
