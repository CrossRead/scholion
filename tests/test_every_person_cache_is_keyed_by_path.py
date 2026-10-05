"""C3 of the 0.6.0 brief: every cache that can hold a person's data is keyed by the file.

On a workstation with several people (task 192) one process serves them in
turn. A cache keyed by anything but the file it read — a gene name, a fixed
"v" — hands the previous person's answer to the next one, and it looks like
an ordinary answer. The review of 13.09 found six caches; 0.5.9 had eighteen,
and every one of them had the path in its key but one (`labs._FLAGS`, keyed
by nothing, fixed with this test).

The walk finds every module-level container a function writes into, and
every `lru_cache`. Each must be listed below with what its key is. A new one
fails until somebody writes down why it cannot carry one person's answer to
another — which is the review this test exists to force.
"""
from __future__ import annotations

import ast
import unittest

import support

PKG = support.SRC / "scholion"

#: module.name → what the key is. «path» entries hold a person's data and key
#: it by the file it came from; «program» entries hold nothing about a person.
KEYED = {
    "core._JSON_CACHE": ("path", "the file's path and its modification time"),
    "core._STAMP_CACHE": ("path", "the file's path and its modification time"),
    "core._KB_CACHE": ("path", "path|language; the path may be a local copy beside the profile"),
    "array_genome._CACHE": ("path", "the array file's path, checked against its mtime"),
    "array_genome._SNIFF_CACHE": ("path", "the file's path, size and mtime"),
    "limits._CALLABILITY_CACHE": ("path", "profile/callability.tsv's path, size and mtime"),
    "ingest_labs._OWNER_CACHE": ("path", "metrics.json's path, mtime and size under «_key»"),
    "genome._KIND_CACHE": ("path", "the VCF's path, size and mtime"),
    "genome._REGION_CACHE": ("path", "the VCF's path among the key's parts"),
    "genome._CONTIGS_CACHE": ("path", "the VCF's path among the key's parts"),
    "linear._MEMO": ("path", "abspath|size|mtime_ns of the VCF"),
    "engine/labs._FLAGS": ("path", "the profile folder under «path»; cleared when it differs"),
    "drugsource._MISS_REASON": ("program", "why a drug NAME was not found in RxNorm — "
                                "offline or unknown; a fact about the network, not a person"),
    "recompute._last_write": ("program", "when the progress file was last written"),
    "server._UPD": ("program", "the state of the background update of the program"),
    "container._ONE_COMMAND": ("program", "the --patient of the running command; reset after it"),
    "container._LAZY_NAMES": ("path", "resolved container directory; only naming events witnessed "
                              "after capture, with the live ID and profile/repo paths rechecked"),
}

#: lru_cache functions → the parameter that names the file, or «package» for a
#: function of no arguments that reads only the catalogue every container shares.
LRU = {
    "genome.loci": "package",
    "genome.catalogue_assembly": "package",
    "genome._header": "vcf",
    "genome.samples_of": "vcf",
    "genome.assembly_evidence": "vcf",
    "genome._chr_prefix": "vcf",
    "tabixlite._index_cached": "vcf",
}

DATA_PATHS = {"repo_dir", "profile_dir", "slot_dir", "raw_dir", "work_dir", "cache_dir",
              "genome_dir", "source_path", "chosen_genome_vcf", "knowledge_dir_local"}


def _module(f) -> str:
    rel = f.relative_to(PKG).with_suffix("")
    return "/".join(rel.parts) if rel.parts[0] == "engine" else ".".join(rel.parts)


def walk():
    """({module.name of a written module-level container}, {module.func: (params, body)})."""
    containers, lrus = set(), {}
    for f in sorted(PKG.rglob("*.py")):
        tree = ast.parse(f.read_text(encoding="utf-8"))
        mod = _module(f)
        names = set()
        for n in tree.body:
            targets, value = [], None
            if isinstance(n, ast.Assign):
                targets, value = n.targets, n.value
            elif isinstance(n, ast.AnnAssign) and n.value is not None:
                targets, value = [n.target], n.value
            ctor = isinstance(value, ast.Call) and getattr(value.func, "id", None) in (
                "dict", "set", "list", "OrderedDict", "defaultdict")
            if isinstance(value, (ast.Dict, ast.List, ast.Set)) or ctor:
                names |= {t.id for t in targets if isinstance(t, ast.Name)}
        for fn in ast.walk(tree):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for d in fn.decorator_list:
                target = d.func if isinstance(d, ast.Call) else d
                name = target.attr if isinstance(target, ast.Attribute) else getattr(target, "id", "")
                if name in ("lru_cache", "cache"):
                    lrus[f"{mod}.{fn.name}"] = ([a.arg for a in fn.args.args], fn)
            for m in ast.walk(fn):
                tgt = []
                if isinstance(m, ast.Assign):
                    tgt = m.targets
                elif isinstance(m, ast.AugAssign):
                    tgt = [m.target]
                for t in tgt:
                    if isinstance(t, ast.Subscript) and isinstance(t.value, ast.Name) \
                            and t.value.id in names:
                        containers.add(f"{mod}.{t.value.id}")
                if isinstance(m, ast.Call) and isinstance(m.func, ast.Attribute) \
                        and isinstance(m.func.value, ast.Name) and m.func.value.id in names \
                        and m.func.attr in ("update", "setdefault", "append", "add", "extend"):
                    containers.add(f"{mod}.{m.func.value.id}")
    return containers, lrus


class TestEveryCacheIsReviewed(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.containers, cls.lrus = walk()

    def test_every_written_module_container_is_listed_with_its_key(self):
        new = sorted(self.containers - set(KEYED))
        self.assertEqual([], new,
                         "module-level state a function writes into, with no key on record: "
                         + ", ".join(new) + ". A cache of a person's data keys it by the file "
                         "it read (task 192); list it in KEYED with that key, or with why it "
                         "holds nothing about a person")

    def test_no_entry_outlives_its_cache(self):
        self.assertEqual([], sorted(set(KEYED) - self.containers))
        self.assertEqual([], sorted(set(LRU) - set(self.lrus)))

    def test_every_lru_cache_is_keyed_by_its_file_or_reads_only_the_package(self):
        for name, (params, fn) in sorted(self.lrus.items()):
            with self.subTest(fn=name):
                self.assertIn(name, LRU, f"{name} is an lru_cache with no key on record")
                if LRU[name] == "package":
                    self.assertEqual([], params)
                    used = {getattr(c.func, "attr", getattr(c.func, "id", None))
                            for c in ast.walk(fn) if isinstance(c, ast.Call)}
                    self.assertFalse(used & DATA_PATHS,
                                     f"{name} is cached with no key and reads a person's folder")
                else:
                    self.assertEqual(LRU[name], params[0] if params else None)

    def test_the_walk_finds_what_it_looks_for(self):
        self.assertIn("core._JSON_CACHE", self.containers)
        self.assertIn("genome._header", self.lrus)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
