"""Load the shipped shared renderer alongside extracted web entry points."""
from __future__ import annotations
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
import support


def javascript() -> str:
    page = (support.SRC / 'scholion/web/index.html').read_text(encoding='utf-8')
    parts = ["globalThis.DISPLAY_MODE='patient';",
             'const ScholionGeneCards=require(' + json.dumps(str(support.SRC / 'scholion/web/gene-cards.js')) + ');']
    for name in ('geneDisplayCard', 'geneFindingCards', 'geneReferenceExtras'):
        start = page.index('function ' + name + '(')
        parts.append(page[start:page.index('\n}\n', start) + 2])
    return '\n'.join(parts) + '\n'


def run(script: str, *, input=None, stdin=subprocess.DEVNULL, **kwargs):
    """Use a script file so Windows command length is independent of markup size."""
    with tempfile.TemporaryDirectory(prefix='scholion-card-render-') as folder:
        path = Path(folder) / 'probe.cjs'
        path.write_text(script, encoding='utf-8')
        if input is not None:
            return subprocess.run([shutil.which('node'), str(path)], input=input, **kwargs)
        return subprocess.run([shutil.which('node'), str(path)], stdin=stdin, **kwargs)
