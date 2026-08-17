#!/usr/bin/env python3
"""A check on what goes into a commit: there must be no personal data in it.

Called by the `pre-commit` hook (installed via `src/tools/install_hooks.sh`),
but it also works by hand:

    python3 src/tools/check_staged.py            # check the index
    python3 src/tools/check_staged.py --all      # check the whole tree (audit)

Two lines of defence, because `.gitignore` protects only against inattention,
not against `git add -f` and not against a file that ended up in the wrong
folder by accident:

1. **By path** — a hard ban on the profile directories and genomic formats.
   An error blocks the commit, always.
2. **By content** — a search for the owner's identifiers (sample number, surname,
   e-mail and so on) in the text of the changed files. The patterns themselves are
   NOT kept in git: they live in `.personal_patterns` next to the project, a file
   listed in .gitignore. No file — the content check is skipped with a warning,
   not silently.

Format of `.personal_patterns`: one pattern per line, `#` is a comment. A line of
the form `re:...` is treated as a regular expression, `sub:SOURCE => TARGET` is the
sanitiser's replacement table (only SOURCE is an identifier here), the rest as
case-insensitive substrings.
"""
import re
import os
import subprocess
import sys
from pathlib import Path

# Reading calls must not touch the index: otherwise .git/index.lock is left
# behind, and over the bridge to the device it cannot be removed (deletion is
# forbidden there).
GIT_ENV = {**os.environ, "GIT_OPTIONAL_LOCKS": "0"}

# The one genome file allowed into the history, judged by content rather than by
# name. The rule lives in its own module because four separate gates need the
# same answer and an exception written out four times is an exception that drifts.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import synthetic_fixture                                          # noqa: E402


ROOT = Path(__file__).resolve().parents[2]
PATTERNS_FILE = ROOT / ".personal_patterns"

# Directories that must not appear in the history under any circumstances.
# Matched ONLY from the repository root (paths from git are repository-relative
# anyway): a directory with the same name deeper down is legitimate, for example
# `src/scholion/templates/profile/` with the package's synthetic templates. What is
# personal in a nested place is the content check's business, not the folder name's.
# The layout slots (`docs/DATA-LAYOUT.md`) plus historical names: folders with the
# old names are still on the owner's disk, and the ban has to survive the move.
# The list is extended, not replaced — otherwise a change of layout silently
# lifts the protection from whatever was renamed.
# The last entry is a real folder name on the owner's disk, not prose: it is the
# name the lab hands its documents out under, so it stays in Russian.
FORBIDDEN_DIRS = ("profile/", "genome/", "raw/", "work/", "archive/", "reports/",
                  "_backups/", "_to_delete/", "inbox/",
                  "kb/", "data/", "EvogenGenomeApp/", "Лабораторные исследования/")
# Extensions: either large, or almost always personal
FORBIDDEN_EXT = (".vcf", ".vcf.gz", ".bam", ".cram", ".bai", ".tbi",
                 ".fq.gz", ".fastq.gz", ".pdf", ".docx", ".xlsx", ".log")
# Only these count as text — we do not look inside anything else
TEXT_EXT = (".md", ".py", ".sh", ".json", ".txt", ".html", ".js", ".css",
            ".yml", ".yaml", ".toml", ".cfg", ".tsv", ".csv", "")
MAX_BYTES = 2_000_000


# `-z` is not decoration. Without it git ESCAPES names with non-ASCII characters and
# hands them back in quotes: `"docs/\320\241..."`. Such a name does not open, the file
# was skipped silently — and the personal-data leak check read not a single document
# with a Russian name. There were eight of them, and one held the owner's sample
# identifier. The report meanwhile stated the full number of files: a check that
# overstates its coverage is more dangerous than one that fails — it is the number
# that people believe.
def _git_files(args) -> list:
    out = subprocess.run(["git", *args, "-z"],
                         capture_output=True, text=True, cwd=ROOT, env=GIT_ENV)
    return [f for f in out.stdout.split("\0") if f.strip()]


def staged_files():
    return _git_files(["diff", "--cached", "--name-only", "--diff-filter=ACMR"])


_DELETED_CACHE: list = []


def _deleted_in_worktree() -> set:
    """Files git still remembers but which have been removed from disk.

    For them "does not open" is a normal state, not a leak: the deletion has not
    been committed yet. Telling this case apart is mandatory, otherwise the check
    starts shouting at every uncommitted deletion, and a shout that sounds all the
    time stops being reacted to.
    """
    if not _DELETED_CACHE:
        _DELETED_CACHE.append(set(_git_files(["ls-files", "--deleted"])))
    return _DELETED_CACHE[0]


def all_files():
    """Everything git considers its own: tracked PLUS new non-ignored files.

    There used to be a bare `git ls-files` here, and on a repository without a
    single commit it returned nothing — the pre-flight `--all` check printed
    "nothing to check" and silently did nothing at exactly the moment it was needed
    most. Caught on the first commit: `--others --exclude-standard` adds files that
    are not in the index yet but are not under .gitignore either.
    """
    return sorted(set(_git_files(["ls-files", "--cached", "--others", "--exclude-standard"])))


def load_patterns():
    """Patterns from .personal_patterns → a list of (kind, pattern, level).

    Two levels, because not everything personal is equally dangerous:
      · `block` (the default) — name, e-mail, phone. Nothing of the sort may be in
        the repository anywhere, ever; the commit is stopped.
      · `warn:` — an identifier that legitimately lives in a PRIVATE repository but
        must not travel to a public one. The classic case is the sample number: it
        stands as the default value in a couple of dozen pipeline scripts, and the
        sanitiser strips it out of the depersonalised package. Blocking a commit
        over it is pointless, whereas knowing where it lies is useful.
    """
    if not PATTERNS_FILE.exists():
        return None
    pats = []
    for line in PATTERNS_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        level = "block"
        if line.startswith("warn:"):
            level, line = "warn", line[5:].strip()
        if line.startswith("sub:"):
            # `sub:SOURCE => TARGET` — the sanitiser's replacement table lives in the
            # same file, because the two gates asking different questions about the
            # same identifiers is how one of them goes stale. Here only the SOURCE
            # matters: it is an identifier like any other. Read as a whole line it
            # would match nothing, and the hook would quietly stop protecting the
            # three identifiers that need it most — the ones a build rewrites.
            line = line[4:].split("=>")[0].strip()
            if not line:
                continue
        if line.startswith("re:"):
            pats.append(("re", re.compile(line[3:], re.IGNORECASE), level))
        else:
            pats.append(("sub", line.lower(), level))
    return pats


def check_paths(files):
    bad = []
    for f in files:
        low = f.lower()
        if any(f.startswith(d) for d in FORBIDDEN_DIRS):
            bad.append((f, "personal-data directory", "block"))
        elif any(low.endswith(e) for e in FORBIDDEN_EXT if e):
            # …unless it is the declared, size-capped test fixture. The refusal
            # carries the reason from `synthetic_fixture`, because "personal or
            # bulk format" on a file somebody deliberately put in the fixture
            # directory reads as a bug in the check rather than as an answer.
            ok, why = synthetic_fixture.check(ROOT / f)
            if not ok:
                reason = "personal or bulk format" if not _looks_like_a_fixture(f) \
                    else f"a genome fixture that does not qualify: {why}"
                bad.append((f, reason, "block"))
    return bad


def _looks_like_a_fixture(f: str) -> bool:
    return "/".join(synthetic_fixture.FIXTURE_DIR) in f.replace("\\", "/")


# The only exception to the content check: THE COPYRIGHT LINE.
# The author's name in the licence is published deliberately — that is a condition
# of Apache-2.0, not a leak. The exception is made as narrow as possible along
# three axes:
#   · only a line containing the word Copyright / © / (c) with a year;
#   · only that line, not the whole file: the name on any other line of the same
#     NOTICE still stops the commit;
#   · no file names in the exception list — the rule is about the content of the
#     line, so it cannot be bypassed by naming a file LICENSE.
# This concession does not extend to medical data: a sample number, an e-mail and
# everything else have no business being in a copyright line, and if they do end up
# there, the line stops being a copyright line only in the eyes of a human —
# therefore the exception below is lifted when the line holds anything beyond the
# name and the licence.
_COPYRIGHT_LINE = re.compile(r"(?i)(copyright|©|\(c\))\s*(\d{4}|\b)")
_SUSPICIOUS_IN_COPYRIGHT = re.compile(r"(?i)(@|\+7|\bWG\d|\brs\d{3,}|\d{2}[./-]\d{2}[./-]\d{2,4})")


def _only_in_copyright(text, kind, pat) -> bool:
    """Are all occurrences of the pattern in copyright lines and nowhere else?

    Every occurrence is checked: one legitimate copyright line must not excuse a
    name standing further down the file.
    """
    found_any = False
    for line in text.splitlines():
        hit = pat.search(line) if kind == "re" else (pat in line.lower())
        if not hit:
            continue
        found_any = True
        if not _COPYRIGHT_LINE.search(line):
            return False
        if _SUSPICIOUS_IN_COPYRIGHT.search(line):
            return False          # e-mail, phone, sample number, date — that is not a copyright
    return found_any


def check_content(files, pats):
    bad = []
    for f in files:
        p = ROOT / f
        if not p.exists():
            if f in _deleted_in_worktree():
                continue          # the deletion is not committed yet — nothing to check
            # The file is on git's books and does not open. This used to be a silent
            # `continue`: the list counted as checked in full, although part of it
            # had been read by nobody. A file the check COULD NOT READ is not a
            # file it approved.
            bad.append((f, "the file does not open — it could not be checked", "block"))
            continue
        if not p.is_file() or p.stat().st_size > MAX_BYTES:
            continue
        # A fixture let through by name is not let through by content: the price
        # of the exception is that the file gets read, header and calls both.
        fixture_text = synthetic_fixture.vcf_text(p) if synthetic_fixture.allowed(p) else None
        if fixture_text is None and p.suffix.lower() not in TEXT_EXT:
            continue
        try:
            text = fixture_text if fixture_text is not None \
                else p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        low = text.lower()
        for kind, pat, level in pats:
            hit = pat.search(text) if kind == "re" else (pat if pat in low else None)
            if hit:
                if _only_in_copyright(text, kind, pat):
                    continue      # authorship in the licence — deliberate publication
                shown = pat.pattern if kind == "re" else "…"
                bad.append((f, f"owner's identifier in the text ({shown})", level))
                break
    return bad


def main(argv):
    files = all_files() if "--all" in argv else staged_files()
    if not files:
        print("nothing to check")
        return 0

    problems = check_paths(files)
    pats = load_patterns()
    if pats is None:
        print(f"⚠ no {PATTERNS_FILE.name} — the CONTENT check was skipped.\n"
              f"  Create the file with your own identifiers (it is in .gitignore):\n"
              f"  printf '%s\\n' 'SAMPLE_NUMBER' 'Surname' 'mail@…' > {PATTERNS_FILE.name}")
    elif pats:
        problems += check_content(files, pats)

    warns = [p for p in problems if p[2] == "warn"]
    problems = [p for p in problems if p[2] == "block"]

    if warns:
        print(f"\n⚠ warning ({len(warns)}): an identifier that is acceptable in a private")
        print("  repository but not in a public one. The sanitiser strips it out of the")
        print("  package — check that the build audit passes before publishing.")
        shown = sorted({f for f, _, _ in warns})
        for f in shown[:8]:
            print(f"   {f}")
        if len(shown) > 8:
            print(f"   … and {len(shown) - 8} more")

    if problems:
        print(f"\n❌ COMMIT STOPPED — personal data ({len(problems)}):\n")
        for f, why, _ in problems:
            print(f"   {f}\n      └─ {why}")
        print("\nWhat to do:")
        print("  · take it out of the index:  git restore --staged <file>")
        print("  · if the file has no business being in the project at all — move it")
        print("    to _to_delete/ (deletion over the bridge is forbidden) and clear it")
        print("    out by hand;")
        print("  · a deliberate exception (last resort): git commit --no-verify")
        print("\nRemember: deleting a file does not clear personal data out of the git")
        print("history. Stopping now is cheaper.")
        return 1

    print(f"✅ files checked: {len(files)} — no personal data found")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
