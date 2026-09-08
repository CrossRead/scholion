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
        self.assertFalse((Path(self.tmp) / ".write.lock").exists(),
                         "the lock outlived the write — the next one would be "
                         "refused for no reason")

    def test_a_lock_somebody_else_holds_is_refused(self):
        lock = Path(self.tmp) / ".write.lock"
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
        self.assertIn("pid 999999", said, "the refusal does not say who holds it")
        # `profile_dir()` resolves the path it is handed; a temporary root reached
        # through a symlink (macOS /var, the CI job that reproduces it) is named
        # in the refusal in its resolved form. Compare like with like.
        self.assertIn(str(lock.resolve()), said, "the refusal does not say which file to remove")

    def test_a_lock_left_by_a_dead_process_is_taken_over(self):
        """Otherwise a crash mid-write locks somebody out of their own history
        until they find the file and delete it by hand."""
        lock = Path(self.tmp) / ".write.lock"
        lock.write_text("pid 999999", encoding="utf-8")
        old = time.time() - (core._LOCK_STALE_AFTER + 5)
        os.utime(lock, (old, old))
        ran = False
        with core.profile_write_lock():
            ran = True
        self.assertTrue(ran, "a stale lock was believed")

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


if __name__ == "__main__":
    unittest.main()
