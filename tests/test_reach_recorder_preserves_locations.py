"""Recording each code location once retains branches, threads and child processes."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import support
sys.path.insert(0, str(support.ROOT / 'src/tools'))
import check_test_reach as reach  # noqa: E402


class RecorderLocations(unittest.TestCase):
    @unittest.skipUnless(hasattr(sys, 'monitoring'), 'optimization uses Python 3.12+ monitoring')
    def test_one_shot_and_repeated_callbacks_record_exactly_the_same_locations(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            measured = root / 'measured'
            measured.mkdir()
            (measured / 'fixture.py').write_text('''import threading

def branch(n):
    if n % 2:
        return n + 3
    return n - 1

def late():
    return 'only the child reaches this'

if __name__ == '__main__':
    import subprocess,sys
    for i in range(300):
        branch(i)
    thread=threading.Thread(target=lambda: branch(7))
    thread.start()
    thread.join()
    subprocess.run([sys.executable,'-c','from fixture import late;late()'],check=True,stdin=subprocess.DEVNULL)
''', encoding='utf-8')
            merged = []
            for label, recorder in [('once', reach._RECORDER), ('repeated', reach._RECORDER.replace('return _mon.DISABLE', 'return None'))]:
                site, dumps = root / label, root / (label + '-dumps')
                site.mkdir(); dumps.mkdir()
                (site / 'sitecustomize.py').write_text(recorder, encoding='utf-8')
                env = support.env()
                env.update(SCHOLION_REACH_DIR=str(dumps), SCHOLION_REACH_ROOT=str(measured),
                           PYTHONPATH=os.pathsep.join([str(site), str(measured)]))
                result = subprocess.run([sys.executable, str(measured / 'fixture.py')], env=env,
                                        capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=15)
                self.assertEqual(0, result.returncode, result.stderr)
                hits = {}
                files = list(dumps.glob('*.json'))
                self.assertGreaterEqual(len(files), 2)
                for path in files:
                    for name, lines in json.loads(path.read_text(encoding="utf-8")).items():
                        hits.setdefault(name, set()).update(lines)
                merged.append(hits)
            self.assertEqual(merged[0], merged[1])
            self.assertIn(9, merged[0][str(measured / 'fixture.py')])
