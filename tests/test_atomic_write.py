"""Writing the profile never leaves a file half-written.

The point of this test is not "writing works" (the smoke pass checks that) but
the behaviour on an INTERRUPTION. Overwriting in place first truncates the file:
a process killed at that moment leaves behind truncated JSON, and a `labs.json`
holding years of history stops parsing at all. We check the property the write
was reworked for: at any moment the target path holds either the old version in
full, or the new one.
"""
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

import support
from scholion import core


class TestAtomicWrite(unittest.TestCase):

    def test_interruption_during_write_does_not_damage_the_previous_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "labs.json"
            core.write_json(target, {"markers": {"ldl": 3.1}})

            # an object that serialises halfway and then fails: exactly what a
            # killed process does, only deterministically
            class Explosion:
                def __repr__(self): return "<Explosion>"

            with self.assertRaises(TypeError):
                core.write_json(target, {"markers": {"ldl": 3.1}, "bad": Explosion()})

            # the previous content is in place and parses
            data = json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(data["markers"]["ldl"], 3.1,
                             "a failed write damaged the previous file")

    def test_temporary_file_does_not_remain(self):
        """Debris next to the profile reads to a human as "something broke"."""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "labs.json"
            core.write_json(target, {"a": 1})
            with self.assertRaises(TypeError):
                core.write_json(target, {"b": object()})
            leftovers = [p.name for p in Path(tmp).iterdir() if p.name != "labs.json"]
            self.assertEqual(leftovers, [], f"files were left behind: {leftovers}")

    def test_directory_is_created(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "missing" / "nested" / "labs.json"
            core.write_json(target, {"a": 1})
            self.assertTrue(target.exists())

    def test_file_permissions_are_not_widened(self):
        """The temporary file is created with the process umask, not with 0666:
        medical data must not become more accessible than before after a rewrite."""
        if os.name != "posix":
            self.skipTest("the permissions check is POSIX-only")
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "labs.json"
            core.write_json(target, {"a": 1})
            mode = target.stat().st_mode & 0o777
            self.assertEqual(mode & 0o007, 0, f"the file is readable by outsiders: {oct(mode)}")


if __name__ == "__main__":
    unittest.main()


class TestTheProfileCarriesTheVersionOfItsShape(unittest.TestCase):
    """A profile file says which shape it is in, and a build refuses a newer one.

    Two things lived under one key before this. In `knowledge/` `_meta.schema` is
    a NUMBER (`lab_markers.json` carries `"schema": 2`); in the profile templates
    the same key held a PARAGRAPH describing the layout. One is for a person
    reading the file, the other is for code deciding whether it may read it at
    all, and nothing can be migrated by a paragraph. The prose moved to
    `_meta.shape` and the number took the key back.

    Forward migration has nothing to do yet — version 1 is the only shape that
    has ever existed. The direction that matters is the other one, and it is the
    direction that cannot be added later: by the time there is a version 2, the
    builds that would have to refuse it are already on people's machines. So the
    refusal ships before there is anything to refuse.
    """

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        self._old = os.environ.get("SCHOLION_PROFILE_DIR")
        os.environ["SCHOLION_PROFILE_DIR"] = str(self.dir)
        core.reset_cache()

    def tearDown(self):
        if self._old is None:
            os.environ.pop("SCHOLION_PROFILE_DIR", None)
        else:
            os.environ["SCHOLION_PROFILE_DIR"] = self._old
        core.reset_cache()

    def _write(self, name, data):
        p = self.dir / name
        p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        core.reset_cache()
        return p

    def test_a_file_with_no_number_is_the_original_shape(self):
        """Every file this project has ever written is version 1.

        Treating silence as «unknown» and refusing would lock existing users out
        of their own history on the upgrade that introduced the check.
        """
        self.assertEqual(core.profile_schema_of({"markers": {}}), 1)
        self.assertEqual(core.profile_schema_of({"_meta": {"purpose": "x"}}), 1)

    def test_prose_left_in_the_number_field_does_not_read_as_a_version(self):
        """The exact state this change was made to end."""
        self.assertEqual(core.profile_schema_of({"_meta": {"schema": "markers: { … }"}}), 1)

    def test_the_legacy_meta_key_is_still_read(self):
        """`pharmacogenomics.json` shipped with `meta`, not `_meta`.

        A file already on somebody's disk will not rename its own key.
        """
        self.assertEqual(core.profile_schema_of({"meta": {"schema": 3}}), 3)

    def test_a_file_from_a_newer_build_is_refused_by_name(self):
        p = self._write("labs.json", {"_meta": {"schema": core.PROFILE_SCHEMA + 1}, "markers": {}})
        with self.assertRaises(core.ProfileFromTheFuture) as caught:
            core.read_profile_json(p)
        msg = str(caught.exception)
        self.assertIn("labs.json", msg, "the refusal does not say which file")
        self.assertIn(str(core.PROFILE_SCHEMA + 1), msg, "it does not say what it found")
        self.assertIn(str(core.PROFILE_SCHEMA), msg, "it does not say what this build reads")

    def test_the_current_version_is_read(self):
        p = self._write("labs.json", {"_meta": {"schema": core.PROFILE_SCHEMA}, "markers": {"x": 1}})
        self.assertEqual(core.read_profile_json(p).get("markers"), {"x": 1})

    def test_a_write_into_the_profile_stamps_the_version(self):
        p = self.dir / "metrics.json"
        core.write_json(p, {"metrics": {}})
        self.assertEqual(json.loads(p.read_text(encoding="utf-8"))["_meta"]["schema"],
                         core.PROFILE_SCHEMA)

    def test_the_stamp_moves_a_legacy_meta_block_across(self):
        """Stamping must not leave a file with two metadata blocks."""
        d = core.stamp_profile_schema({"meta": {"purpose": "x"}, "genotypes": {}})
        self.assertNotIn("meta", d, "the legacy block was left behind next to the new one")
        self.assertEqual(d["_meta"]["purpose"], "x", "the legacy contents were dropped")
        self.assertEqual(d["_meta"]["schema"], core.PROFILE_SCHEMA)

    def test_the_stamp_survives_a_profile_reached_through_a_symlink(self):
        """The macOS shape, reproduced where a runner is cheap.

        `profile_dir()` resolves; a path handed in by a caller need not. On macOS
        `/var` and `/tmp` are symlinks to `/private/...`, so an ordinary profile
        directory compared UNEQUAL to itself, the stamp was skipped, and the file
        was written with no version — silently, which is the whole point of
        having one. Green on Linux, red on the owner's machine, and found by the
        package's own test run rather than by anything in this repository.

        The same class as `test_lab_dir_boundary` (v2.18.0) and the reason the CI
        matrix has a symlinked-TMPDIR job. Written here so the next one is caught
        by a test rather than by a person publishing.
        """
        real = self.dir / "real"
        link = self.dir / "link"
        real.mkdir()
        try:
            link.symlink_to(real, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("this filesystem does not do symlinks")
        self.assertNotEqual(link, link.resolve(), "the link is not a link — this proves nothing")

        old = os.environ.get("SCHOLION_PROFILE_DIR")
        os.environ["SCHOLION_PROFILE_DIR"] = str(link)
        core.reset_cache()
        try:
            p = link / "metrics.json"
            core.write_json(p, {"metrics": {}})
            written = json.loads(p.read_text(encoding="utf-8"))
            self.assertIn("_meta", written,
                          "a profile reached through a symlink was written with no version")
            self.assertEqual(written["_meta"]["schema"], core.PROFILE_SCHEMA)
        finally:
            if old is None:
                os.environ.pop("SCHOLION_PROFILE_DIR", None)
            else:
                os.environ["SCHOLION_PROFILE_DIR"] = old
            core.reset_cache()

    def test_a_write_outside_the_profile_is_left_alone(self):
        """Caches and knowledge files are not the profile."""
        p = self.dir.parent / "not-a-profile.json"
        self.addCleanup(lambda: p.unlink(missing_ok=True))
        core.write_json(p, {"a": 1})
        self.assertNotIn("_meta", json.loads(p.read_text(encoding="utf-8")))

    def test_every_shipped_template_declares_the_version(self):
        """A template that ships without the number teaches the absence of it."""
        tpl = support.ROOT / "src" / "scholion" / "templates" / "profile"
        if not tpl.is_dir():
            self.skipTest("the templates are not part of this build")
        missing = []
        for f in sorted(tpl.glob("*.json")):
            d = json.loads(f.read_text(encoding="utf-8"))
            meta = d.get("_meta") if isinstance(d.get("_meta"), dict) else d.get("meta")
            if not isinstance(meta, dict) or not isinstance(meta.get("schema"), int):
                missing.append(f.name)
        self.assertEqual(missing, [], "templates with no version number: " + ", ".join(missing))

    def test_no_template_still_keeps_prose_in_the_number_field(self):
        tpl = support.ROOT / "src" / "scholion" / "templates" / "profile"
        if not tpl.is_dir():
            self.skipTest("the templates are not part of this build")
        prose = []
        for f in sorted(tpl.glob("*.json")):
            d = json.loads(f.read_text(encoding="utf-8"))
            meta = d.get("_meta") if isinstance(d.get("_meta"), dict) else d.get("meta") or {}
            if isinstance(meta.get("schema"), str):
                prose.append(f.name)
        self.assertEqual(prose, [],
                         "the layout description is back in the version field, where it "
                         "cannot be compared: " + ", ".join(prose))
