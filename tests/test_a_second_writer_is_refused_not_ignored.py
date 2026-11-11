"""Where the profile cannot be locked between processes, the write is refused.

`flock` is what makes two writers take turns, and it does not exist on Windows.
Until now its absence was handled by carrying on: the thread lock still covered
the web server's own threads, and a separate command-line process was simply not
covered at all. Two writers each read a file, change one field and write it back;
the later one erases the earlier one's change, with no error anywhere. The lost
update is invisible — the file parses, the number is just the wrong one.

So the platform without `flock` takes a lock of its own — a file created with
`O_CREAT | O_EXCL`, which is atomic everywhere — and where that lock is already
held, it says so and stops. A refusal a person can read beats a change they
never learn they lost.

These tests run on the machine they are run on. The `flock` path is exercised
where `fcntl` exists; the other path is exercised everywhere, by hiding `fcntl`
from the module the way the platform hides it.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from unittest import mock
from pathlib import Path

import support
from scholion import core


class TestTheLockIsTakenEvenWithoutFlock(unittest.TestCase):
    """The `fcntl`-less path, run on this machine by removing `fcntl`."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.was_profile = os.environ.get("SCHOLION_PROFILE_DIR")
        os.environ["SCHOLION_PROFILE_DIR"] = self.tmp
        core.reset_cache()
        # Hidden the way the platform hides it, and put back afterwards — a test
        # that leaves a module attribute changed makes the NEXT test lie.
        self.was_fcntl = core._fcntl
        core._fcntl = None
        self.addCleanup(self._restore)

    def _restore(self):
        core._fcntl = self.was_fcntl
        if self.was_profile is None:
            os.environ.pop("SCHOLION_PROFILE_DIR", None)
        else:
            os.environ["SCHOLION_PROFILE_DIR"] = self.was_profile
        core.reset_cache()

    def test_a_write_still_goes_through(self):
        """The refusal must be about contention, not about the platform.

        A lock nobody else holds is taken, used and released; if this failed,
        the whole product would refuse to write on Windows.
        """
        with core.profile_write_lock():
            (Path(self.tmp) / "x.json").write_text("{}", encoding="utf-8")
        self.assertTrue((Path(self.tmp) / "x.json").exists())
        self.assertEqual(core._msvcrt is not None, (Path(self.tmp) / ".write.lock").exists(),
                         "the lock outlived the write — the next one would be "
                         "refused for no reason")

    def test_a_lock_somebody_else_holds_is_refused(self):
        lock = Path(self.tmp) / ".write.lock"
        if core._msvcrt is not None:
            holder = core._native_write_lock(lock)
            holder.__enter__()
            self.addCleanup(lambda: holder.__exit__(None, None, None))
        else:
            fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o600)
            os.write(fd, b"pid 999999")
            self.addCleanup(lambda: os.close(fd))
        was = core._LOCK_WAIT
        core._LOCK_WAIT = 0.2                     # the wait is not what is under test
        self.addCleanup(lambda: setattr(core, "_LOCK_WAIT", was))
        with self.assertRaises(core.ProfileBusy) as e:
            with core.profile_write_lock():
                self.fail("the write ran while another process held the lock")
        said = str(e.exception)
        self.assertTrue(said, "the refusal has no explanation")
        # `profile_dir()` resolves the path it is handed; a temporary root reached
        # through a symlink (macOS /var, the CI job that reproduces it) is named
        # in the refusal in its resolved form. Compare like with like.
        if core._msvcrt is None:
            self.assertIn(str(lock.resolve()), said, "the fallback refusal does not identify its lock")

    def test_a_lock_left_by_a_dead_process_is_taken_over(self):
        """Otherwise a crash mid-write locks somebody out of their own history
        until they find the file and delete it by hand."""
        lock = Path(self.tmp) / ".write.lock"
        lock.write_text("pid 999999", encoding="utf-8")
        old = time.time() - 3600
        os.utime(lock, (old, old))
        if core._msvcrt is not None:
            with core.profile_write_lock():
                pass
        else:
            core._LOCK_WAIT = 0.02
            self.addCleanup(lambda: setattr(core, "_LOCK_WAIT", 5.0))
            with self.assertRaises(core.ProfileBusy):
                with core.profile_write_lock():
                    self.fail("An old file cannot prove the holder has exited")

    def test_liveness_is_not_checked_by_signalling(self):
        """`os.kill(pid, 0)` is the obvious check and is forbidden here: on
        Windows `os.kill` does not send a signal, it calls `TerminateProcess`.
        The check for «is the other writer alive» would kill it."""
        import ast
        src = (support.ROOT / "src" / "scholion" / "core.py").read_text(encoding="utf-8")
        # The source is parsed rather than searched: the comment beside the lock
        # names `os.kill` in order to explain why it is not used, and a plain
        # text search cannot tell an explanation from a call. This test caught
        # its own explanation the first time it ran.
        calls = [n for n in ast.walk(ast.parse(src))
                 if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                 and n.func.attr == "kill"
                 and isinstance(n.func.value, ast.Name) and n.func.value.id == "os"]
        self.assertEqual(calls, [],
                         "core.py signals a process to test whether it is alive — "
                         "on Windows that terminates it")

    def test_an_inaccessible_lock_never_allows_an_unlocked_write(self):
        was = core._LOCK_WAIT
        core._LOCK_WAIT = 0
        self.addCleanup(lambda: setattr(core, "_LOCK_WAIT", was))
        with mock.patch.object(core.os, "open", side_effect=PermissionError("lock access denied")):
            with self.assertRaises(core.ProfileBusy):
                with core.profile_write_lock():
                    self.fail("a failed lock acquisition allowed an unprotected write")

    def test_transient_lock_access_is_retried_before_the_write(self):
        original = os.open
        attempts = []
        lock = Path(self.tmp).resolve() / ".write.lock"

        def transient(path, *args, **kwargs):
            if Path(path) == lock:
                attempts.append(path)
                if len(attempts) == 1:
                    raise PermissionError("Windows lock pending deletion")
            return original(path, *args, **kwargs)

        with mock.patch.object(core.os, "open", side_effect=transient):
            if core._msvcrt is not None:
                with self.assertRaises(core.ProfileBusy):
                    with core.profile_write_lock():
                        self.fail("Native open failure was ignored")
            else:
                with core.profile_write_lock():
                    self.assertTrue(lock.exists(), "the write ran without acquiring the lock")
        self.assertEqual(1 if core._msvcrt is not None else 2, len(attempts))
        self.assertEqual(core._msvcrt is not None and len(attempts) == 2, lock.exists())

    def test_a_nested_write_does_not_deadlock(self):
        """A mutator that calls another mutator is ordinary here. Without the
        depth counter the second one would meet its own lockfile and be refused."""
        with core.profile_write_lock():
            with core.profile_write_lock():
                pass


class TestTwoProcessesDoNotLoseEachOthersChange(unittest.TestCase):
    """The behaviour itself, across real processes rather than in one."""

    #: Each child appends its own name to a list in one file, under the lock.
    #: Without a lock between processes, some of the names are missing at the
    #: end — that is the lost update, in its simplest form.
    CHILD = textwrap.dedent('''
        import json, os, sys, time
        sys.path.insert(0, sys.argv[1])
        from scholion import core
        core._fcntl = None                       # the platform without flock
        core._LOCK_WAIT = 20.0
        who = sys.argv[2]
        p = os.path.join(os.environ["SCHOLION_PROFILE_DIR"], "list.json")
        with core.profile_write_lock():
            data = json.loads(open(p, encoding="utf-8").read())
            time.sleep(0.05)                     # widen the window the race needs
            data.append(who)
            open(p, "w", encoding="utf-8").write(json.dumps(data))
    ''')

    def test_every_change_survives(self):
        tmp = tempfile.mkdtemp()
        (Path(tmp) / "list.json").write_text("[]", encoding="utf-8")
        script = Path(tmp) / "child.py"
        script.write_text(self.CHILD, encoding="utf-8")
        env = dict(os.environ)
        env["SCHOLION_PROFILE_DIR"] = tmp
        kids = [subprocess.Popen([sys.executable, str(script), str(support.SRC), f"w{i}"],
                                 env=env, stdin=subprocess.DEVNULL,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                for i in range(6)]
        for k in kids:
            out, err = k.communicate(timeout=90)
            self.assertEqual(k.returncode, 0, err.decode("utf-8", "replace"))
        got = json.loads((Path(tmp) / "list.json").read_text(encoding="utf-8"))
        self.assertEqual(sorted(got), [f"w{i}" for i in range(6)],
                         f"lost updates: only {len(got)}/6 survived")



class TestNativeLockAndManifestIntegrity(unittest.TestCase):
    def setUp(self):
        import shutil
        self.root = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, self.root)
        self.env = mock.patch.dict(os.environ, {
            "SCHOLION_PROFILE_DIR": str(self.root),
            "SCHOLION_WORKSTATION": str(self.root / "no-workstation.json"),
        })
        self.env.start()
        self.addCleanup(self.env.stop)
        self.addCleanup(core.reset_cache)
        core.reset_cache()

    @unittest.skipUnless(core._fcntl is not None, "POSIX flock")
    def test_failed_lock_open_never_enters_the_write(self):
        real_open = core.os.open
        def blocked(path, *args, **kwargs):
            if Path(path).name == ".write.lock":
                raise PermissionError("synthetic denial")
            return real_open(path, *args, **kwargs)
        with mock.patch.object(core.os, "open", side_effect=blocked):
            with self.assertRaises(core.ProfileBusy):
                with core.profile_write_lock():
                    self.fail("Unprotected write")
        self.assertEqual(getattr(core._WRITE_DEPTH, "n", 0), 0)

    @unittest.skipUnless(core._fcntl is not None or core._msvcrt is not None, "native lock")
    def test_age_never_steals_a_live_native_lock(self):
        worker = """
from scholion import core
import sys
with core.profile_write_lock():
    print('locked', flush=True)
    sys.stdin.readline()
"""
        child = subprocess.Popen([sys.executable, "-c", worker], env=os.environ.copy(),
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            self.assertEqual("locked", child.stdout.readline().strip())
            old = time.time() - 86400
            os.utime(self.root / ".write.lock", (old, old))
            with mock.patch.object(core, "_LOCK_WAIT", 0.05):
                with self.assertRaises(core.ProfileBusy):
                    with core.profile_write_lock():
                        self.fail("A live writer lost its lock due to age")
        finally:
            if child.poll() is None:
                child.kill()
            child.communicate()

    def test_two_import_snapshots_keep_both_files_and_do_not_revert_a_new_checkpoint(self):
        a, b = str(self.root / "a.pdf"), str(self.root / "b.pdf")
        core.write_ingest_manifest("labs", {a: 1.0})
        first, second = core.read_ingest_manifest("labs"), core.read_ingest_manifest("labs")
        before_first, before_second = dict(first), dict(second)
        first[a] = 2.0
        core.write_ingest_manifest("labs", first, before_first)
        second[b] = 3.0
        core.write_ingest_manifest("labs", second, before_second)
        self.assertEqual({a: 2.0, b: 3.0}, core.read_ingest_manifest("labs"))

    def test_two_processes_keep_distinct_manifest_updates(self):
        worker = """
from scholion import core
import sys
before = core.read_ingest_manifest('labs')
data = dict(before)
print('ready', flush=True)
assert sys.stdin.readline().strip() == 'write'
data[sys.argv[1]] = 1.0
core.write_ingest_manifest('labs', data, before)
"""
        children = [subprocess.Popen([sys.executable, "-c", worker, str(self.root / name)],
                    env=os.environ.copy(), stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                    for name in ("a.pdf", "b.pdf")]
        try:
            for child in children:
                self.assertEqual("ready", child.stdout.readline().strip())
            for child in children:
                _, errors = child.communicate("write\n", timeout=15)
                self.assertEqual(0, child.returncode, errors)
            self.assertEqual(2, len(core.read_ingest_manifest("labs")))
        finally:
            for child in children:
                if child.poll() is None:
                    child.kill()
                child.communicate()

    @unittest.skipUnless(core._fcntl is not None or core._msvcrt is not None, "native lock")
    def test_lock_is_released_when_the_writer_exits(self):
        worker = """
from scholion import core
import sys
with core.profile_write_lock():
    print('locked', flush=True)
    sys.stdin.readline()
"""
        child = subprocess.Popen([sys.executable, "-c", worker], env=os.environ.copy(),
                   stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            self.assertEqual("locked", child.stdout.readline().strip())
            child.kill()
            child.communicate(timeout=15)
            with core.profile_write_lock():
                core.write_json(self.root / "after.json", {"intact": True})
            self.assertTrue((self.root / "after.json").is_file())
        finally:
            if child.poll() is None:
                child.kill()
            child.communicate()

    def test_failed_checkpoint_is_reported(self):
        with mock.patch.object(core, "write_json", side_effect=OSError("synthetic disk failure")):
            with self.assertRaises(OSError):
                core.write_ingest_manifest("labs", {str(self.root / "x.pdf"): 1.0})


if __name__ == "__main__":
    unittest.main()
