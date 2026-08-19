#!/usr/bin/env python3
"""Sanitiser + automatic audit: build a DEPERSONALISED package to hand to colleagues.

Builds TWO packages in the output folder:
  <out>/                   — the full runnable project (code+application+knowledge+
                                   skill+plugin), with an EMPTY profile/ (templates) and genome/README.
  <out>/claude-skill/    — the standalone Claude skill (SKILL.md + guide).

What it does:
  1) copies ONLY what is portable (whitelist), excluding personal material (profile/, genome/, PDF, VCF, BAM…);
  2) swaps the owner's SKILL.md for the generalised one (share/skill/INSTRUCTION.md);
  3) replaces personal identifiers (sample ID, home paths) with neutral ones;
  4) AUDITS the result: looks for signs of personal data (strings, files, templates,
     and also UNapproved embedded screenshots) — on a finding it FAILS (non-zero code).

Run (from the ORIGINAL repository):
    python3 src/tools/make_shareable.py [<out_dir>]
Check a ready package:
    python3 src/tools/make_shareable.py --audit-only <package_folder>
Build AND zip it for handoff outside git (e.g. to an external reviewer):
    python3 src/tools/make_shareable.py [<out_dir>] --zip
"""
from __future__ import annotations
import base64
import hashlib
import re
import shutil
import subprocess
import sys
import zipfile
import pathlib
from pathlib import Path
from typing import Optional

# The single definition of when a genome file may ship (see the module's own
# docstring). Shared with `check_staged.py` so that the pre-commit gate and the
# build audit cannot come to different conclusions about the same file.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import synthetic_fixture                                          # noqa: E402

_DATAURI = re.compile(r"data:[a-zA-Z0-9.+/-]+;base64,[A-Za-z0-9+/=\s]+")

# Raster data-URIs: a text audit cannot check their CONTENT.
# Small blobs are the application's icons/favicons (safe).
# Large ones are almost always SCREENSHOTS of the application, and therefore real
# lab results and genotypes.
_RASTER_URI = re.compile(r"data:image/(?:jpe?g|png|gif|webp|bmp|tiff?|avif|heic)\s*;base64,([A-Za-z0-9+/=\s]+)", re.I)
_IMG_DATA_TAG = re.compile(r"<img\b[^>]*?src=\"data:image/[^\"]*\"[^>]*?>", re.I | re.S)
RASTER_MAX_B64 = 30_000  # base64 characters (~22 KB) — above the threshold it is a screenshot, not an icon

# The allowlist of APPROVED images (sha256 of the decoded blob).
# The presentation screenshots were taken on the synthetic demo profile (not on the
# owner's data) — they have been checked by eye and allowed by name. Any OTHER large
# image fails the audit: a text audit cannot look inside a JPEG, and a new screenshot
# may hold real lab results and genotypes. Add a hash here only after viewing the image.
APPROVED_RASTER_SHA256 = {
    # Presentation shots, retaken on 19.08.2026 for the 0.3.2 refresh: the
    # application on the SYNTHETIC demo profile (an invented person, subject
    # DEMO-0001, `scholion init --demo`), captured via a real headless run of
    # `scholion serve`, one full set per language \u2014 English and Russian now each
    # carry their OWN screenshots, ten tabs each (the Guide tab is new; it did not
    # exist in the previous set). The audit does not see what is drawn inside an
    # image \u2014 so the list is approved by eye, and the hash pins exactly what was
    # looked at. The previous set (nine hashes, English only, Russian reusing the
    # English images) was replaced wholesale rather than extended, for the same
    # reason it was replaced wholesale the time before: a page whose screenshots
    # are stale or in the wrong language reads as carelessness, and keeping old
    # hashes around would let a stale edition pass right alongside the current one.
    #
    # English (docs/presentation.html):
    "fa479e1a2e31e262e9dde323fb14a5673bb98aa3764dad8d7714922c21c3ec40": "presentation (en) \u00b7 Overview: the current task, the live marker and the levers",
    "af63f7f88ee42aaa5784548f56838f8d654b3c06a5e8067d4a60a0c6e3fd0062": "presentation (en) \u00b7 Guide: what every colour, badge and label means",
    "bc401752cdc67fcd2132eeb936a42a388d6489a97b72b193c3164ac36dee885d": "presentation (en) \u00b7 Labs: flags, sparklines and movement for every marker",
    "473f81ff9c25a3a6609ab205868c2b84558c9b60f5986b0c2111f3df981173e5": "presentation (en) \u00b7 Drugs: one drug checked against genome x labs x interactions x ClinVar",
    "84e7d341003e994b7c1072748c0c67005b50883f9f3d35ec0df976bf2598031a": "presentation (en) \u00b7 Genome: findings by tier, polygenic risks and the longevity layer",
    "6d18749e21aef38fd2b3306819cb8f012ac007f503b45039b3f54feb28aeb6d8": "presentation (en) \u00b7 Lifestyle: anthropometry, activity and recovery with their trends",
    "f686265dcd280245a44ee03fb8188ee42a4c029e43b0eb0f3387b4d1a2a391c5": "presentation (en) \u00b7 What to test: entries in steps, tube, preparation, age of last value",
    "1ff87e7c82727636b11ff217890f7ca4704679e628d3e7458f0fc44cf702b719": "presentation (en) \u00b7 Second opinion: summary for the appointment",
    "9f8844744abdddf13af044831e987acf0c316130c0a3c5111ddce91259cbd165": "presentation (en) \u00b7 Prescriptions: the current regimen as single point of truth",
    "5bfb54f7683962813ee8fe219148d54855c9ba875141533d6f6f014f0390b563": "presentation (en) \u00b7 Assistant: the core's self-check",
    # Russian (docs/presentation.ru.html) \u2014 genuinely Russian-interface screenshots,
    # not the English set reused:
    "4f1b92d0d168a2876099b4cf8b43b4c74d7da5eb775fb3469381f5b9b9229953": "presentation (ru) \u00b7 Overview: the current task, the live marker and the levers",
    "d26a0302ae9e689f4bb52384a3296b757a3577681ae5a722ae3e6ad76e23b298": "presentation (ru) \u00b7 Guide: what every colour, badge and label means",
    "f4c2369e14ac950bc2b54471505c25aba7c4200f9c9a9d4d4f94f5f32a24262d": "presentation (ru) \u00b7 Labs: flags, sparklines and movement for every marker",
    "0d2371af0287b6acbcdec4d2784bd6b37681f64b73ca8f6a687dbf553bc24d9d": "presentation (ru) \u00b7 Drugs: one drug checked against genome x labs x interactions x ClinVar",
    "882c05ad3dc8a0387def0a891341a4b96868f555db125b967b6290b87fb8a37e": "presentation (ru) \u00b7 Genome: findings by tier, polygenic risks and the longevity layer",
    "e91cf2b65e5c8c1764fe54c5e877555cf0f37a84395899a751f5f2691b697c3d": "presentation (ru) \u00b7 Lifestyle: anthropometry, activity and recovery with their trends",
    "c2d6ba9f5da21a143ab7843a1052a1ae563056b346803048b9f707d1c2cbb139": "presentation (ru) \u00b7 What to test: entries in steps, tube, preparation, age of last value",
    "e6e87fbf540ee69d73ca7644db6d0e2a86a1ba7124246a987ebe4a3b065ef950": "presentation (ru) \u00b7 Second opinion: summary for the appointment",
    "6c59a8abf98c4a65997fa65eda33255839c15d1efee628ba190fabfc4b795a02": "presentation (ru) \u00b7 Prescriptions: the current regimen as single point of truth",
    "3b0e71142ab3ad3c0bab01c56c178151bc88e57b3979b0e815b7f71e46a94f88": "presentation (ru) \u00b7 Assistant: the core's self-check",
}


# ── what counts as text (for substitutions and the audit) ─────────────────
TEXT_EXT = {".py", ".sh", ".md", ".json", ".html", ".htm", ".txt", ".js", ".css", ".cfg", ".toml", ".yml", ".yaml", ".gitignore"}

#: The file that holds the owner's identifiers. Next to the project, in
#: `.gitignore`, and never in the package — the same file the pre-commit hook
#: reads, so the two gates cannot come to hold different lists.
PATTERNS_FILE = ".personal_patterns"

# What used to stand here: the identifiers themselves, base64-encoded, with a
# comment saying they were encoded "so that THIS script holds no owner
# identifiers and does not fail its own audit". That is not passing an audit, it
# is stepping around one. The script ships INSIDE the package, so eleven personal
# strings — surname in two alphabets, an e-mail handle, a date of birth, a sample
# number, a GitHub account, a home path — travelled into a public archive in a
# form one line of Python reverses. The audit did not see them for exactly the
# reason it was built to catch: it compares substrings, and an encoded string is
# not a substring of anything.
#
# An outside audit read the decoded list back to us on 16.08.2026. The remedy is
# not to document the trace — it is not to have it. Nothing personal is written
# in a file that ships; the list is read at build time from a file that does not.
#
# Consequence, and it is deliberate: with no `.personal_patterns` the identifier
# half of the audit cannot run at all, and a build that cannot check must not
# report a clean one. It stops. A fork with no owner data to protect passes
# `--no-personal-patterns` and says so out loud.
SUBSTITUTIONS: list = []
DENY: list = []


def load_personal(repo: Path, required: bool = True) -> None:
    """Fill SUBSTITUTIONS and DENY from `.personal_patterns`. Fail closed.

    Format, shared with `check_staged.py`:

      * `identifier`            — a case-insensitive substring the package may not contain
      * `re:PATTERN`            — the same, as a regular expression
      * `sub:SOURCE => TARGET`  — replace SOURCE with TARGET in every text file,
                                  AND refuse a package in which SOURCE survives
      * `warn:` / `#`           — a softer level and comments, both read by the hook

    A substitution source is always a denylist entry too: a replacement that
    silently failed to fire is precisely what the audit exists to catch.
    """
    global SUBSTITUTIONS, DENY
    f = repo / PATTERNS_FILE
    if not f.exists():
        if required:
            sys.exit(f"✗ {PATTERNS_FILE} not found next to the project.\n"
                     f"  The identifier half of the audit cannot run without it, and a build\n"
                     f"  that cannot check must not report a clean package.\n"
                     f"  If this is a fork with no owner data to protect, say so:\n"
                     f"    python3 src/tools/make_shareable.py --no-personal-patterns")
        print(f"• {PATTERNS_FILE} is absent and was not required — the package is NOT "
              f"checked against owner identifiers")
        SUBSTITUTIONS, DENY = [], []
        return
    subs, deny = [], []
    for line in f.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("warn:"):
            line = line[5:].strip()
        if line.startswith("sub:"):
            src, _, dst = line[4:].partition("=>")
            src, dst = src.strip(), dst.strip()
            if not src or not dst:
                sys.exit(f"✗ {PATTERNS_FILE}: a `sub:` line without `=> replacement`")
            subs.append((src, dst))
            deny.append(src.lower())
        elif line.startswith("re:"):
            deny.append(re.compile(line[3:], re.IGNORECASE))
        else:
            deny.append(line.lower())
    # One identifier written twice — once plainly, once as a `sub:` source — is the
    # ordinary state of this file, and it used to be reported as two violations.
    # A count that overstates is read as noise, and a check people read past is off.
    seen, unique = set(), []
    for d in deny:
        key = d.pattern if hasattr(d, "pattern") else d
        if key not in seen:
            seen.add(key)
            unique.append(d)
    SUBSTITUTIONS, DENY = subs, unique
    print(f"• owner identifiers loaded from {PATTERNS_FILE}: "
          f"{len(subs)} substitution(s), {len(unique)} denylist entr(ies)")

# ── file types that must NOT be in the package ────────────────────────────
FORBIDDEN_SUFFIXES = (".pdf", ".vcf", ".gz", ".bam", ".bai", ".tbi", ".cram",
                      ".fastq", ".fq", ".bak", ".doc", ".docx", ".zip")
FORBIDDEN_NAME_HINTS = ("clinvar_hits", "prs_results", "longevity_findings",
                        "pharmacogenomics.json.bak", "wearable_trends.json",
                        "telomere_length")

SKIP_DIR = {"__pycache__", ".git", ".cache", "node_modules", ".venv"}

# ── Files that stay ONLY in the personal repository ───────────────────────
# These are not personal data (the audit catches those) but material that belongs to
# a particular owner and is of no use to the package recipient: a personal version
# log with findings, narrow loaders for one specific instrument or application.
# Paths are relative to the repository root, in POSIX form.
# The list is extended by a `.private_files` file at the root (one path per line, `#`
# is a comment) — so that the code need not be edited for one more exception.
# The heading sync_rules.py writes above the owner's qualifications. It is the
# one sign that separates the editions and does not depend on any person:
# tests/test_skill_editions.py asserts from both sides that the personal edition
# HAS it and the shared one does NOT.
OWNER_BLOCK_MARK = "Owner\'s personal refinements"

PRIVATE_DEFAULT = (
    "CHANGELOG.private.md",
    # The development journal from before publication. Its numbering ran to 2.24.0
    # and was retired at 0.1.0; shipping it beside the published changelog would
    # put a larger number next to the current one, and a larger number reads as
    # newer. The commits are kept in the private repository, under `pre-0.1.0/`
    # tags.
    "CHANGELOG.pre-0.1.0.md",
    "src/ingest/cgm_join.py",
    "src/ingest/ingest_cgm_screens.py",
)
_PRIVATE_ABS: set = set()          # filled in build(); consulted in _copytree


def load_private(repo: Path) -> set:
    """Absolute paths of files that are not copied into the package."""
    names = list(PRIVATE_DEFAULT)
    extra = repo / ".private_files"
    if extra.exists():
        for line in extra.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                names.append(line)
    out = set()
    for rel in names:
        p = (repo / rel)
        if p.exists():
            out.add(p.resolve())
    return out


def _is_text(p: Path) -> bool:
    return p.suffix.lower() in TEXT_EXT or p.name == ".gitignore"


def _copytree(src: Path, dst: Path, only_ext=None) -> None:
    """Copy a tree, skipping junk and (optionally) filtering by extension."""
    for p in src.rglob("*"):
        if any(part in SKIP_DIR for part in p.parts) or _quarantined(p):
            continue
        if p.is_dir():
            continue
        if p.suffix == ".pyc" or p.name in {".DS_Store", "Thumbs.db"}:
            continue
        if only_ext is not None and p.suffix.lower() not in only_ext:
            continue
        if p.resolve() in _PRIVATE_ABS:      # personal — does not travel in the package
            continue
        rel = p.relative_to(src)
        out = dst / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, out)


def _substitute_in(root: Path) -> int:
    n = 0
    for p in root.rglob("*"):
        if p.is_file() and _is_text(p):
            try:
                t = p.read_text(encoding="utf-8")
            except (UnicodeDecodeError, PermissionError):
                continue
            new = t
            for a, b in SUBSTITUTIONS:
                new = new.replace(a, b)
            if new != t:
                p.write_text(new, encoding="utf-8")
                n += 1
    return n


# Markers of the personal block. The same ones as in the canon of assistant rules: one
# markup for the whole project — less chance that a new file introduces a third.
_OWNER_BEGIN, _OWNER_END = "<!-- OWNER:BEGIN -->", "<!-- OWNER:END -->"


def _public_bytes(src: Path) -> bytes:
    """The content without the personal block — what may be carried to the recipient."""
    text = src.read_text(encoding="utf-8")
    i, j = text.find(_OWNER_BEGIN), text.find(_OWNER_END)
    if i >= 0 and j > i:
        return (text[:i].rstrip() + "\n" + text[j + len(_OWNER_END):].lstrip("\n")).encode("utf-8")
    if i >= 0 or j >= 0:
        sys.exit(f"✗ {src.name}: an OWNER marker without its pair — the build is stopped")
    return text.encode("utf-8")


QUARANTINE_SUFFIX = "._stale"

# Set by `_clear_or_quarantine` and read by `main`: names of the quarantined
# directories from previous builds. Not a warning that scrolls past — the build's
# final verdict depends on it.
_QUARANTINED: list = []


def quarantine_root(out: Path) -> Path:
    """Where an undeletable previous build is put — OUTSIDE the delivery folder.

    It used to be moved aside in place: `Scholion-SHARE/src` became
    `Scholion-SHARE/src._stale`, still inside the package. That solved the wrong
    half of the problem. The build could no longer confuse old files with new
    ones, but a full copy of the previous package was now sitting inside the
    thing being handed over: zip the folder and you ship two versions; and every
    ignore rule the builder writes is anchored to the delivery folder's own name,
    so `profile._stale3/` — the recipient's filled-in templates — was excluded by
    nothing. Ninety-one such directories had accumulated by the time it was
    noticed, and each build made more, because the build refused to call itself
    ready and the person cleaned up by hand.

    One directory, next to the package and never in it. The package is then
    complete and correct the moment the audit passes, whatever the filesystem
    allowed.
    """
    return out.parent / f"{out.name}{QUARANTINE_SUFFIX}"


def drain_quarantine(qroot: Path) -> int:
    """Try to delete what earlier builds could not. Returns what is left.

    Called once at the start of a build. The filesystem that refused unlink last
    week may allow it today — iCloud finishes evicting, the volume is remounted,
    the copy is no longer open anywhere. Nothing accumulates unless the refusal
    is permanent, and then it accumulates in one named place instead of scattered
    through the delivery folder.
    """
    if not qroot.exists():
        return 0
    shutil.rmtree(qroot, ignore_errors=True)
    if not qroot.exists():
        return 0
    return sum(1 for _ in qroot.iterdir())


def _clear_or_quarantine(d: Path, qroot: Optional[Path] = None) -> None:
    """Empty the build directory — and if it cannot be deleted, move it aside.

    The build folder often lives on a filesystem with no right to unlink: iCloud,
    a network volume, the bridge to the owner's machine. `rmtree(ignore_errors)`
    returns quietly there and THE OLD CONTENT STAYS. As long as the file names do
    not change nobody notices — the new build writes over them. The moment a file
    is renamed or dropped, the old one survives under its old name, and the
    recipient gets it: a document under its pre-rename name, a README that was
    replaced, a file that was removed on purpose.

    Overwriting cannot express "this file is no longer part of the package", so
    the directory is moved out of the way instead — into `qroot`, which is
    outside the package (see `quarantine_root`).
    """
    if not d.exists():
        return
    shutil.rmtree(d, ignore_errors=True)
    if not d.exists():
        return
    qroot = qroot if qroot is not None else quarantine_root(d.parent)
    qroot.mkdir(parents=True, exist_ok=True)
    for n in range(1, 100):
        aside = qroot / (d.name if n == 1 else f"{d.name}-{n}")
        if aside.exists():
            continue
        try:
            d.rename(aside)
        except OSError as e:                                     # noqa: BLE001
            sys.exit(f"✗ {d.name} can be neither deleted nor moved aside ({e}).\n"
                     f"  A build on top of the previous one would carry files that are "
                     f"no longer part of the package.\n"
                     f"  Delete {d} by hand and run the build again.")
        _QUARANTINED.append(aside)
        print(f"  • the previous build could not be deleted (the filesystem forbids it) "
              f"and was moved outside the package: {aside}")
        return
    sys.exit(f"✗ {qroot} holds a hundred quarantined builds — clear them out.")


def _clear_build_root(out: Path) -> None:
    """Empty the build root while keeping `.git`.

    The root is the public repository now, so wiping it wholesale would take the
    history with it. Everything else goes through the same quarantine logic as
    before: on a filesystem that refuses unlink (iCloud, network volumes) a
    directory is renamed aside rather than silently left behind, because
    overwriting cannot say "this file is no longer part of the package".
    """
    qroot = quarantine_root(out)
    left = drain_quarantine(qroot)
    if left:
        print(f"  • {left} leftover(s) from earlier builds are still in {qroot} — "
              f"outside the package, and this build tried to remove them")
    if not out.exists():
        out.mkdir(parents=True, exist_ok=True)
        return
    for p in sorted(out.iterdir()):
        if p.name == ".git" or QUARANTINE_SUFFIX in p.name:
            continue
        if p.is_dir():
            _clear_or_quarantine(p, qroot)
            try:
                if p.exists() and not any(p.iterdir()):
                    p.rmdir()
            except OSError:
                pass
        else:
            try:
                p.unlink()
            except OSError:
                pass                        # will be overwritten by the build


def build(repo: Path, out: Path) -> Path:
    share = repo / "share"
    if not share.is_dir():
        sys.exit("✗ Run this from the ORIGINAL repository (there is no share/ folder with the templates).")
    global _PRIVATE_ABS
    _PRIVATE_ABS = load_private(repo)
    if _PRIVATE_ABS:
        print(f"• personal files excluded from the package: {len(_PRIVATE_ABS)}")
    # The build root IS the public repository. There is no container level above
    # it any more: two copies of LICENSE, VERSION and CHANGELOG in one tree only
    # raise the question of which one is true, and a `pip install` from GitHub
    # wants pyproject.toml at the root, not one level down.
    shared = out
    skillpkg = out / "claude-skill"        # delivered in the archive, excluded from git
    _clear_build_root(out)
    _clear_or_quarantine(skillpkg, quarantine_root(out))

    # ── 1) portable code/knowledge/scripts/plugin ─────────────────────────
    _copytree(repo / "src" / "scholion", shared / "src" / "scholion")
    if (repo / "src" / "ingest").is_dir():
        _copytree(repo / "src" / "ingest", shared / "src" / "ingest")
    if (repo / "src" / "annotate").is_dir():
        _copytree(repo / "src" / "annotate", shared / "src" / "annotate")
    (shared / "src" / "tools").mkdir(parents=True, exist_ok=True)
    shutil.copy2(repo / "src" / "tools" / "make_shareable.py",
                 shared / "src" / "tools" / "make_shareable.py")
    # The brief editor: user-facing in the same sense as the n-of-1 wrapper below.
    # The shared SKILL tells an assistant to edit the lifestyle brief with THIS
    # tool rather than by hand in the JSON — because it makes a backup, sets
    # `reviewed` and validates what was written. An instruction to run a file the
    # package does not carry is not an instruction, and the skill is an executable
    # specification. 183 lines, nothing owner-specific in it.
    _brief = repo / "src" / "tools" / "brief_edit.py"
    if _brief.exists():
        shutil.copy2(_brief, shared / "src" / "tools" / "brief_edit.py")
    # the daily n-of-1 logging wrapper: user-facing, unlike the rest of tools/
    _qlog = repo / "src" / "tools" / "nof1_quick_log.sh"
    if _qlog.exists():
        shutil.copy2(_qlog, shared / "src" / "tools" / "nof1_quick_log.sh")
    # the documents a recipient needs to CONTRIBUTE, not only to run: the runbook
    # of checks (the skill links to it), the development conventions (written for
    # an outside contributor — shipping everywhere except to that contributor
    # would be the four-face defect again), and the versioning rules the
    # conventions point at.
    for _name in ("TESTS-AND-COMPATIBILITY.md", "DEVELOPMENT.md", "VERSIONING.md"):
        _doc = repo / "docs" / _name
        if _doc.exists():
            (shared / "docs").mkdir(parents=True, exist_ok=True)
            shutil.copy2(_doc, shared / "docs" / _name)

    # the compatibility check is part of the public package: the recipient must be
    # able to confirm that their build has not narrowed the contract, without access
    # to our repository.
    # The privacy check travels together with the tests. Without it six tests in the
    # delivery are SKIPPED with the wording "check_staged.py is not in this build":
    # that is, the recipient silently loses exactly the check the package is
    # depersonalised for, while the run still looks green.
    _guard = repo / "src" / "tools" / "check_staged.py"
    if _guard.exists():
        shutil.copy2(_guard, shared / "src" / "tools" / "check_staged.py")

    # …and what both of the checks above import. It is one small module and it was
    # nearly left behind: the build succeeded, and the recipient's `check_staged.py`
    # then failed to import at all — which the test file turned into an error rather
    # than a skip only by luck. A dependency of a shipped tool is shipped.
    _fixgate = repo / "src" / "tools" / "synthetic_fixture.py"
    if _fixgate.exists():
        shutil.copy2(_fixgate, shared / "src" / "tools" / "synthetic_fixture.py")

    _compat = repo / "src" / "tools" / "check_compat.py"
    if _compat.exists():
        shutil.copy2(_compat, shared / "src" / "tools" / "check_compat.py")

    # The language gate, for the same reason as the two above: it is what keeps the
    # project English, and a contributor cannot honour a rule they have no way to
    # check. Without the baseline beside it the tool reports every file as new, so
    # the two travel together or not at all.
    _lang = repo / "src" / "tools" / "check_language.py"
    _lang_base = repo / "src" / "tools" / "language_baseline.json"
    if _lang.exists() and _lang_base.exists():
        shutil.copy2(_lang, shared / "src" / "tools" / "check_language.py")
        shutil.copy2(_lang_base, shared / "src" / "tools" / "language_baseline.json")
    # the demo profile: seeing a working product BEFORE loading one's own data. It is
    # an invented person, not the author of the project, and it is marked as synthetic
    # in every file — otherwise the demo is indistinguishable from someone's medical
    # record.
    # The demo is not kept in git (it is generated by a command), so on a fresh clone
    # it is absent. Building a package without the demo silently is not acceptable:
    # the recipient will not see the product before loading their own data, and the
    # builder will not learn of it. Generation is deterministic (a fixed seed), so a
    # rebuild is safe.
    if not (repo / "demo").is_dir():
        _gen = repo / "src" / "tools" / "make_demo_profile.py"
        if _gen.exists():
            print("• no demo profile — generating one")
            subprocess.run([sys.executable, str(_gen)], cwd=str(repo), check=False)
    if (repo / "demo").is_dir():
        _copytree(repo / "demo", shared / "demo")
    else:
        print("  ⚠ the demo profile is missing and was not generated — the package "
              "travels with no way to look at the product before loading one\'s own data")
    _mkdemo = repo / "src" / "tools" / "make_demo_profile.py"
    if _mkdemo.exists():
        shutil.copy2(_mkdemo, shared / "src" / "tools" / "make_demo_profile.py")

    # the automated tests and the synthetic fixture: without them the public project is unverifiable
    if (repo / "tests").is_dir():
        _copytree(repo / "tests", shared / "tests")
    # the crossread wrapper is a public entry point; without it the package README lies
    if (repo / "bin" / "crossread").exists():
        (shared / "bin").mkdir(parents=True, exist_ok=True)
        shutil.copy2(repo / "bin" / "crossread", shared / "bin" / "crossread")

    _runner = repo / "run_tests.sh"
    if _runner.exists():
        shutil.copy2(_runner, shared / "run_tests.sh")
    _copytree(repo / "ouroboros_plugin", shared / "ouroboros_plugin", only_ext={".py"})
    (shared / "ouroboros_plugin" / "README.md").write_text(
        "# Scholion — an Ouroboros plugin\n\n"
        "The implementation lives inside the package as `scholion/ouroboros_tools.py`,\n"
        "so `pip install scholion` delivers it too. This folder holds a thin re-export\n"
        "for the case where the project is unpacked as a folder and never installed:\n"
        "one implementation, two ways to reach it.\n\n"
        "Ouroboros discovers tools by scanning its own tools package, so the module is\n"
        "copied there once. The contract is `get_tools() -> list[ToolEntry]`.\n\n"
        "## Install\n\n"
        "```bash\n"
        "pip install scholion\n"
        "cp \"$(python3 -c 'import scholion.ouroboros_tools as m; print(m.__file__)')\" \\\n"
        "   <ouroboros>/ouroboros/tools/\n"
        "export SCHOLION_REPO_DIR=~/.local/share/scholion   # where your data lives\n"
        "```\n\n"
        "Without an install, copy `scholion_tools.py` from this folder instead and put\n"
        "the project's `src` on `PYTHONPATH`.\n\n"
        "Self-check outside Ouroboros: `python3 -m scholion.ouroboros_tools` prints the\n"
        "tool list.\n\n"
        "## Tools\n\n"
        "14 tools with the `sch_` prefix: a second opinion on a drug, drug-gene check,\n"
        "lab analysis, suggested tests, locus lookup, ClinVar findings, health metrics,\n"
        "lifestyle, polygenic scores, longevity, goals, biological age, provenance and\n"
        "lab ingest.\n\n"
        "User data (`profile/`, `genome/`) stays local and is not part of the plugin.\n",
        encoding="utf-8")

    # ── 2) the generalised skill instead of the owner's one ───────────────
    (shared / "src" / "skill").mkdir(parents=True, exist_ok=True)
    shutil.copy2(share / "skill" / "INSTRUCTION.md", shared / "src" / "skill" / "INSTRUCTION.md")

    # ── 3) an empty profile (templates) + genome README + docs ────────────
    # The templates moved inside the package (src/scholion/templates): otherwise they
    # do not get into the wheel and the `scholion init` command does not find them.
    # The sanitiser takes them from the same place — one source, no diverging copies.
    _tpl = repo / "src" / "scholion" / "templates"
    _copytree(_tpl / "profile", shared / "profile")
    (shared / "genome").mkdir(parents=True, exist_ok=True)
    shutil.copy2(_tpl / "genome" / "README.md", shared / "genome" / "README.md")
    # One README for everything: the repository, PyPI and the package. Three texts
    # about one product diverge the faster the more rarely they are read together, and
    # the recipient usually sees exactly the one that was edited last.
    shutil.copy2(repo / "README.md", shared / "README.md")
    shutil.copy2(repo / "ASSISTANT-RULES.md", shared / "ASSISTANT-RULES.md")
    # The sync check travels together with the canon: the copy of the rules in the
    # skill asks "edit the canon, not the copy", and the recipient must have something
    # to check that with.
    _sync = repo / "src" / "tools" / "sync_rules.py"
    if _sync.exists():
        shutil.copy2(_sync, shared / "src" / "tools" / "sync_rules.py")
    shutil.copy2(share / "LOADING-DATA.md",
                 shared / "LOADING-DATA.md")
    shutil.copy2(share / "PREPARING-THE-GENOME.md",
                 shared / "PREPARING-THE-GENOME.md")
    # ── licences and legal terms ──────────────────────────────────────────
    # Mandatory in BOTH places: at the root of the package (which is the public
    # repository itself) — one level, one copy, because that folder is what people
    # copy to themselves whole. A package without LICENSE is not "a package missing a
    # file" but code to which no rights are granted by default; NOTICE and ATTRIBUTION
    # meanwhile carry the verbatim terms of the sources (LOINC, HAGR), which may
    # neither be omitted nor paraphrased.
    # VERSION and CHANGELOG.md belong here too, and for the same reason as the
    # licences: without them the package does not lie silently, it lies visibly. They
    # sat at the build root from the previous time and were not updated — the public
    # package declared version 1.1.0 while the repository was at 2.2.0, and carried a
    # log cut off at v1.x. The recipient has no way of learning that they are looking
    # at last year's list of capabilities.
    # One list for copying and for the freshness check: two lists sooner or later drift
    # apart, and a file starts being checked but not copied.
    for _name in _MIRRORED:
        _src = repo / _name
        if _src.exists():
            shutil.copy2(_src, shared / _name)   # one level, one copy
        else:
            print(f"  ⚠ no {_name} — the package travels without the legal terms")

    # The canon of rules gets its own line and travels WITHOUT the personal block. The
    # mirror into the package was already fixed in sync_rules.py, but the sanitiser has
    # its own, independent copying path: having fixed one copier, it is easy to decide
    # the whole class is closed. The leak went out through the second door and again
    # carried an owner's laboratory specifics.
    _canon = repo / "ASSISTANT-RULES.md"
    if _canon.exists():
        (shared / "ASSISTANT-RULES.md").write_bytes(_public_bytes(_canon))

    # Packaging and CI live at the root of the delivery, because the root IS the
    # public repository. There used to be a container level above it, and the
    # comment here claimed a python project could not be rooted there. That was
    # wrong — hatchling builds a correct wheel from a nested package too, given
    # the paths. The reason for removing the level was different and simpler: it
    # forced two copies of LICENSE, VERSION and CHANGELOG into one tree, and
    # `pip install git+https://…` wants pyproject.toml at the root, not one
    # level down behind a `#subdirectory=` nobody guesses.
    # The whole workflows directory, not one file by name. Copying `publish.yml`
    # alone is why `tests.yml` never reached the package: the build carried the
    # publishing workflow and no checks, and an outside audit read that as
    # "the project has no CI".
    _wfdir = repo / ".github" / "workflows"
    if _wfdir.is_dir():
        (shared / ".github" / "workflows").mkdir(parents=True, exist_ok=True)
        for _f in sorted(_wfdir.glob("*.y*ml")):
            shutil.copy2(_f, shared / ".github" / "workflows" / _f.name)

    # The issue templates, for the same reason and one more: they are the only
    # place most people will ever read the rule about not pasting a medical
    # record into a public tracker. A tool nobody is told about protects nobody,
    # and the moment somebody is about to paste is the moment they are looking at
    # the issue form.
    _itdir = repo / ".github" / "ISSUE_TEMPLATE"
    if _itdir.is_dir():
        (shared / ".github" / "ISSUE_TEMPLATE").mkdir(parents=True, exist_ok=True)
        for _f in sorted(_itdir.iterdir()):
            if _f.is_file():
                shutil.copy2(_f, shared / ".github" / "ISSUE_TEMPLATE" / _f.name)

    for _name in ("pyproject.toml",):
        if (repo / _name).exists():
            shutil.copy2(repo / _name, shared / _name)

    # The .gitignore of the package root — and the root is the public repository. It
    # is not a copy of the repository's own: the folder names there are different. It
    # is written here rather than kept in share/ exactly because the build folder name
    # is set in this same file: when the project was renamed, the old .gitignore stayed
    # from the previous build and went on excluding the profile directory under its
    # FORMER name — that is, the recipient's personal data in the folder with the new
    # name was not excluded at all.
    (out / ".gitignore").write_text(
        "# The recipient fills the templates in with their own data — it must not reach git.\n"
        f"/{shared.name}/profile/*\n"
        f"!/{shared.name}/profile/*.md\n"
        f"/{shared.name}/genome/*\n"
        f"!/{shared.name}/genome/README.md\n"
        f"/{shared.name}/raw/\n"
        f"/{shared.name}/work/\n"
        f"/{shared.name}/archive/\n"
        # A quarantined previous build is not part of the package and must not be
        # under version control either. The rules above are anchored to the delivery
        # folder BY NAME, so `Scholion-SHARE._stale3/profile/labs.json` matched none
        # of them: the recipient's own data, in a directory this build created,
        # excluded by nothing.
        "*._stale*/\n"
        "*.vcf*\n*.bam\n*.pdf\n"
        + _fixture_negation(f"{shared.name}/")
        + "__pycache__/\n*.pyc\n.DS_Store\n.cache/\ndist/\n", encoding="utf-8")

    # CLAUDE.md — the shared part travels, the personal part is cut out. The file used
    # not to be copied at all: it held both project rules useful to anyone who forks it
    # and the owner's personal paths. The split is marked by markers, not by memory —
    # an agreement held only in someone's head sooner or later leaks the wrong way.
    _claude = repo / "CLAUDE.md"
    if _claude.exists():
        _txt = _claude.read_text(encoding="utf-8")
        i, j = _txt.find(_OWNER_BEGIN), _txt.find(_OWNER_END)
        if i >= 0 and j > i:
            _txt = (_txt[:i] + _txt[j + len(_OWNER_END):]).rstrip() + "\n"
        elif i >= 0 or j >= 0:
            # A single marker without its pair — the file was edited and left broken.
            # Cutting on half the markup is more dangerous than not cutting at all: one
            # may carry away exactly what was being hidden.
            sys.exit("✗ CLAUDE.md: an OWNER marker without its pair — the build is stopped")
        (shared / "CLAUDE.md").write_text(_txt, encoding="utf-8")

    _shortcuts = repo / "docs" / "SHORTCUTS-macOS.md"
    if _shortcuts.exists():
        shutil.copy2(_shortcuts, shared / "SHORTCUTS-macOS.md")
    (shared / ".gitignore").write_text(
        "# The user\'s personal data — do NOT commit.\n"
        "# profile/*.json and genome/* are deliberately outside git: once you fill them\n"
        "# in, the templates from the package become your own personal data. If you need\n"
        "# a pristine template, take it from the package archive, not from the history\n"
        "# of the repository.\n"
        "profile/*\n!profile/*.md\ngenome/*\n!genome/README.md\n"
        # The data layout: raw/ work/ archive/ are created by `scholion init`
        # next to the profile and hold a person's data in full.
        "raw/\nwork/\narchive/\n"
        "*._stale*/\n"
        "*.vcf*\n*.bam\n*.pdf\n"
        + _fixture_negation()
        + "__pycache__/\n*.pyc\n.cache/\n"
        # The standalone skill package travels in the archive but not in the
        # repository: its SKILL.md is byte for byte the one inside the package
        # (src/scholion/skill/), and a second copy under version control is a
        # question of which one to edit.
        "claude-skill/\n", encoding="utf-8")

    # ── 4) the standalone skill package ───────────────────────────────────
    skillpkg.mkdir(parents=True, exist_ok=True)
    shutil.copy2(share / "skill" / "SKILL.md", skillpkg / "SKILL.md")
    shutil.copy2(share / "skill" / "INSTRUCTION.md", skillpkg / "INSTRUCTION.md")
    shutil.copy2(share / "LOADING-DATA.md",
                 skillpkg / "LOADING-DATA.md")
    shutil.copy2(share / "PREPARING-THE-GENOME.md",
                 skillpkg / "PREPARING-THE-GENOME.md")
    (skillpkg / "README.md").write_text(
        "# Scholion — the skill on its own\n\n"
        "`SKILL.md` is the full instruction for a language model: what the tool can do,\n"
        "which commands to call, and the rules the model must follow. The safety rules\n"
        "in `ASSISTANT-RULES.md` take precedence over everything else it is told.\n\n"
        "The model works through the command line — it asks you to run a command and\n"
        "reads the output. It gets no access to your machine.\n\n"
        "`LOADING-DATA.md` describes the profile file formats, so the model can tell you\n"
        "what to put where.\n\n"
        "The runnable project is the folder this one sits in, or `pip install\n"
        "scholion`.\n",
        encoding="utf-8")

    # ── 5) neutralise personal identifiers ────────────────────────────────
    changed = _substitute_in(shared) + _substitute_in(skillpkg)
    print(f"• substitutions made in files: {changed}")

    # ── 6) the package root README + the presentation (demo data) ─────────
    # Two editions, English first. The Russian one is a sibling rather than a
    # translation buried inside: the pages cross-link to each other by name, so a
    # build that carried only one of them would leave a dead link on the page it
    # did carry.
    pres = share / "presentation.html"
    pres_ru = share / "presentation.ru.html"
    has_pres = pres.exists()
    (shared / "docs").mkdir(parents=True, exist_ok=True)
    if has_pres:
        shutil.copy2(pres, shared / "docs" / "presentation.html")
    has_pres_ru = pres_ru.exists()
    if has_pres_ru:
        shutil.copy2(pres_ru, shared / "docs" / "presentation.ru.html")
    if has_pres != has_pres_ru:
        print("  \u26a0 only one edition of the presentation is present — the language "
              "switcher on the page that shipped points at a file that did not")
    # GitHub Pages, serving straight off docs/ on the main branch: a bare visit to
    # the Pages root has nothing to render without an index.html (a 404, not the
    # presentation), and .nojekyll tells Pages not to run the tree through Jekyll
    # first \u2014 neither file has any other purpose, so both are optional the same way
    # the presentation itself is: added only if present in share/.
    for extra_name in ("index.html", ".nojekyll"):
        extra_src = share / extra_name
        if extra_src.exists():
            shutil.copy2(extra_src, shared / "docs" / extra_name)
    # The guide README that used to live at the container level is gone with the
    # level itself: the root now holds the project README, and that is the page
    # GitHub renders and PyPI links to.

    _check_root_fresh(repo, out, shared)
    return out


# Files at the build root that have a same-named source in the repository.
# Everything listed here must match it byte for byte after the build: the build folder
# cannot be deleted (iCloud, network volumes), so a file that was not copied does not
# disappear but stays from the previous version and looks like the real one.
_MIRRORED = ("VERSION", "CHANGELOG.md", "LICENSE", "LICENSE-DATA", "NOTICE",
             "ATTRIBUTION.md", "DISCLAIMER.md", "CONTRIBUTING.md",
             "SECURITY.md", "CITATION.cff", "THREAT_MODEL.md")


def _check_root_fresh(repo: Path, out: Path, shared: Path) -> None:
    """Whether a file from a previous version has stayed in the build.

    The check is cheap and necessary: this is exactly how the package carried the
    wrong version for half a year.
    """
    # Extra items at the root. The same mechanism as with stale files: the build folder
    # cannot be deleted, so a file that used to be put at the root and is now put
    # elsewhere stays lying there and travels to the recipient. That is how the
    # delivery root acquired a `pyproject.toml` from which an empty wheel is built.
    expected = {".git", ".gitignore", ".DS_Store", ".github", "claude-skill",
                "README.md", "ASSISTANT-RULES.md", "CLAUDE.md",
                "SHORTCUTS-macOS.md", "LOADING-DATA.md", "PREPARING-THE-GENOME.md",
                "pyproject.toml", "run_tests.sh",
                "src", "tests", "docs", "bin", "demo", "profile", "genome",
                "ouroboros_plugin", *_MIRRORED}
    extra = sorted(p.name for p in out.iterdir()
                   if p.name not in expected and QUARANTINE_SUFFIX not in p.name)
    if extra:
        print("  ⚠ unexpected entries in the build root (left over from previous "
              "versions; delete the build folder and rebuild): " + ", ".join(extra))

    stale = []
    for name in _MIRRORED:
        src = repo / name
        if not src.exists():
            continue
        dst = shared / name
        if not dst.exists():
            stale.append(f"{dst.relative_to(out)} — not copied")
        elif dst.read_bytes() != src.read_bytes():
            stale.append(f"{dst.relative_to(out)} — differs from {name} in the repository")
    if stale:
        print("  ⚠ files from the previous version in the build root:")
        for s in stale:
            print("     · " + s)


def _declared_synthetic(path: Path) -> bool:
    """Does the file declare ITSELF invented (_meta.synthetic or a word in the description)?

    Needed where the file name looks like a personal result (`prs_results.json`,
    `longevity_findings.json`) while the content is in fact a demonstration. It is the
    declaration inside the file that is checked, not the path: putting someone's real
    export into `demo/` and bypassing the audit that way will not work — without the
    marking it stays a violation.
    """
    if path.suffix.lower() != ".json":
        return False
    try:
        import json as _json
        d = _json.loads(path.read_text(encoding="utf-8"))
    except Exception:                                     # noqa: BLE001
        return False
    if not isinstance(d, dict):
        return False
    meta = d.get("_meta") or d.get("meta") or {}
    if not isinstance(meta, dict):
        return False
    if meta.get("synthetic"):
        return True
    # Both alphabets are matched, and the Russian stems stay for good: this reads a
    # declaration WRITTEN BY A HUMAN in a free-form `_meta`, so it is input, not
    # printed text. A fixture that declares itself synthetic in Russian must keep being
    # recognised — dropping the Russian stems would not translate the audit, it would
    # make it reject files that are correctly declared.
    txt = " ".join(str(v) for v in meta.values() if isinstance(v, str)).upper()
    return any(w in txt for w in ("СИНТЕТ", "ФИКСТУР", "ВЫМЫШЛ", "SYNTHETIC", "FIXTURE"))


def _exec_bit_candidates(root: Path) -> list:
    """Every script the recipient has to be able to run directly, no `chmod` first.

    Pulled out of `_fix_exec_bits` so that zipping can ask the SAME question
    afterwards: two places computing "which files must be executable"
    independently is exactly how the personal-identifier list and the
    pre-commit hook once drifted apart (see v2.20.0).

    Deduplicated by resolved path: `root.rglob("*.sh")` already matches
    `run_tests.sh` at the root (`rglob` allows the `**` to match zero
    directories), so the explicit entry below would otherwise list it twice —
    harmless for `chmod`, but it would report the same file twice in a zip
    verification failure and read like two separate problems.
    """
    found, seen = [], set()
    for p in list(root.rglob("*.sh")) + list(root.rglob("bin/crossread")) + [root / "run_tests.sh"]:
        key = p.resolve()
        if key not in seen:
            seen.add(key)
            found.append(p)
    return found


def _fix_exec_bits(root: Path) -> int:
    """Restore the execute bit on the package scripts.

    Files are copied over the bridge and through web interfaces, which do not carry the
    `+x` bit, so for the recipient `./run_tests.sh` answers "permission denied" — out of
    nowhere, and in the first minute of acquaintance at that. Restoring the bit at build
    time is cheaper than explaining this in the README.
    """
    n = 0
    for p in _exec_bit_candidates(root):
        if p.is_file() and not (p.stat().st_mode & 0o111):
            p.chmod(p.stat().st_mode | 0o755)
            n += 1
    return n


def _write_zip(out: Path) -> Path:
    """The delivery as one `.zip`, with the execute bit still on inside it.

    `shutil.make_archive` writes each entry through `zipfile.ZipInfo.from_file`,
    which reads `os.stat()` on the source file and carries the mode into
    `external_attr` — the same thing the system `zip` and `tar` do, verified
    against this exact function.

    That is NOT the only way to write a zip, which is the whole reason this
    function exists rather than leaving the last step to whoever needs a file to
    attach. The failure mode it guards against: read a file's bytes into memory,
    write them with `ZipFile.writestr(ZipInfo(name), data)`. That path never
    touches the source file's mode — `external_attr` stays zero — and every
    entry comes out of the archive with NO permission bits at all, not just
    missing `+x`. `unzip` does not warn about a bit it was never told to set, so
    the person on the other end sees "permission denied" and no reason why.

    Written NEXT TO `out`, never inside it: `.zip` is itself in
    `FORBIDDEN_SUFFIXES` — nothing pre-packaged belongs inside a package under
    audit — and an archive of the folder sitting inside that same folder would
    be a stale copy the moment either one changes again.
    """
    # `.git` is skipped, and not for tidiness. The delivery folder BECOMES a git
    # repository the first time `publish_share.sh` runs `git init` in it, and from
    # then on `make_archive` sweeps the whole public history into the handover
    # archive: 506 entries and 3.6 MB of 6.8 on 17.08.2026, plus a remote pointing
    # at the owner's account, in a file meant to be «the package, as one file».
    #
    # The part that matters is not the weight. `audit()` walks this folder looking
    # for strings, and a git object is zlib — of 315 files under `.git` exactly 26
    # read back as text. Whatever a repository's history holds, the audit passes it
    # without seeing it. A folder the audit cannot read has no business inside
    # something the audit signs off.
    made = shutil.make_archive(str(out), "zip", root_dir=str(out.parent), base_dir=out.name,
                               logger=None)
    kept = []
    with zipfile.ZipFile(made) as src:
        for info in src.infolist():
            parts = pathlib.PurePosixPath(info.filename).parts
            if ".git" in parts:
                continue
            kept.append((info, src.read(info.filename)))
    tmp = Path(str(made) + ".tmp")
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as dst:
        for info, data in kept:
            dst.writestr(info, data)          # the ZipInfo carries external_attr over
    tmp.replace(made)
    return Path(made)


def _verify_zip_exec_bits(zip_path: Path, out: Path) -> list:
    """Which of the must-run scripts lost their bit INSIDE the archive.

    Trusting that `_write_zip` did what its docstring claims is exactly the
    posture that let eleven identifiers ship base64-encoded in v2.19.0 — the
    fix there was "read back what was written and check it", not "read the
    code and reason about it". This is the same move: open the zip the way the
    recipient's `unzip` will, and look.
    """
    expected = [p.relative_to(out.parent).as_posix()
               for p in _exec_bit_candidates(out) if p.is_file()]
    lost = []
    with zipfile.ZipFile(zip_path) as z:
        present = {i.filename: i for i in z.infolist()}
        for rel in expected:
            info = present.get(rel)
            if info is None:
                lost.append(f"{rel} (missing from the archive)")
                continue
            mode = info.external_attr >> 16
            if not (mode & 0o111):
                lost.append(rel)
    return lost


def _fixture_negation(prefix: str = "") -> str:
    """The two lines that let the test fixture survive `*.vcf*` in a .gitignore.

    Git has no way to ask about a file's content, so here — and only here — the
    exception is a path. It is written next to the ban rather than left out,
    because the alternative was discovered the hard way: the test that proves an
    unread position is not read as the reference went into the package while its
    fixture was silently ignored, and the recipient would have got a suite with a
    hole in exactly the place that matters most.
    """
    d = "/".join(synthetic_fixture.FIXTURE_DIR)
    return ("# …except the synthetic test fixture: a few invented lines, checked by\n"
            "# content at commit time and at build time (src/tools/synthetic_fixture.py).\n"
            f"!{prefix}{d}/*.vcf.gz\n"
            f"!{prefix}{d}/*.vcf.gz.tbi\n")


#: A base64 literal long enough to be worth decoding. Eight characters is six
#: bytes — shorter than any identifier this project protects, and short enough
#: that nothing real slips under it.
_B64_LITERAL = re.compile(r"[A-Za-z0-9+/]{8,}={0,2}")


def _decoded_texts(raw: str):
    """Every base64 literal in the text that decodes to readable text, lower-cased.

    Deliberately generous about what it tries and strict about what it keeps: a
    blob that is not valid UTF-8, or that decodes to control characters, is a PNG
    or a hash and is dropped. What survives is text somebody chose to write in an
    encoded form, which in a file that ships is exactly the thing worth reading.
    """
    for m in _B64_LITERAL.finditer(raw):
        s = m.group(0)
        try:
            blob = base64.b64decode(s + "=" * (-len(s) % 4), validate=True)
        except Exception:                                         # noqa: BLE001
            continue
        if not blob or len(blob) < 4:
            continue
        try:
            text = blob.decode("utf-8")
        except UnicodeDecodeError:
            continue
        if any(ch < " " and ch not in "\t\n\r" for ch in text):
            continue
        yield text.lower()


def _masked(token) -> str:
    """Name the hit without printing any of it.

    The build log is read in a terminal, pasted into an issue and scrolled past on
    a screen somebody else can see. Printing the identifier that leaked in order to
    report that it leaked is the failure repeating itself one layer up — so the
    line carries a position in `.personal_patterns` and a length, and the owner
    looks the entry up in their own file.
    """
    s = token.pattern if hasattr(token, "pattern") else str(token)
    keys = [d.pattern if hasattr(d, "pattern") else d for d in DENY]
    where = f"#{keys.index(s) + 1}" if s in keys else "?"
    return f"{where} of {PATTERNS_FILE} ({len(s)} chars)"


def _quarantined(p: Path) -> bool:
    """Inside a directory moved aside from a previous build.

    Such a directory is not part of the package — `main` refuses to call the
    build handed-over until it is gone. Auditing it would report the sins of a
    version nobody is shipping and hide the state of the one being built.
    """
    return any(QUARANTINE_SUFFIX in part for part in p.parts)


def audit(root: Path) -> int:
    """Return the number of violations (0 = clean). Prints what was found."""
    violations = 0
    # a) forbidden file types/names
    for p in root.rglob("*"):
        if p.is_dir() or _quarantined(p):
            continue
        low = p.name.lower()
        if low.endswith(FORBIDDEN_SUFFIXES) and low != "readme.md":
            # One exception, cut by content rather than by name: the few-line VCF
            # the test suite needs in order to prove that an unread position is
            # not read as the reference. Everything about why it is safe lives in
            # `synthetic_fixture`; here only the verdict is used, and the reason
            # is printed so that a fixture that ALMOST qualifies says which cap it
            # broke instead of reading as a flat ban.
            ok, why = synthetic_fixture.check(p)
            if not ok:
                print(f"  ✗ forbidden file: {p.relative_to(root)}"
                      + (f" — {why}" if why and "outside" not in why else ""))
                violations += 1
        # a name hinting at personal RESULTS — only for data, not for code/scripts
        if p.suffix.lower() in {".json", ".csv", ".tsv", ".txt"} and any(h in low for h in FORBIDDEN_NAME_HINTS):
            # the exception applies only to a file that declared ITSELF invented and
            # lies in a sandbox (demo/ or tests/): a demo profile must have the same
            # file names as a real one, otherwise it does not demonstrate the product
            if bool({"tests", "demo"} & set(p.parts)) and _declared_synthetic(p):
                continue
            print(f"  ✗ looks like personal data: {p.relative_to(root)}")
            violations += 1
    # b) denylist strings in text files
    for p in root.rglob("*"):
        if not (p.is_file() and _is_text(p)):
            continue
        if any(part in SKIP_DIR for part in p.parts) or _quarantined(p):
            continue
        try:
            raw = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, PermissionError):
            continue
        # strip base64 data-URIs (embedded images) — otherwise tokens match by chance
        stripped = _DATAURI.sub("data:base64", raw)
        # The file is searched as written AND as decoded. Substring matching is what
        # this audit is: an identifier that has been encoded is a substring of
        # nothing, and for a year the builder's own denylist sat in this very file
        # base64-encoded, passing every run. Whoever encodes an identifier next —
        # for the same well-meant reason, to get a file past its own check — is
        # caught by the same rule that failed here.
        for hay in (stripped.lower(), *(_decoded_texts(stripped))):
            for token in DENY:
                hit = (token.search(hay) if hasattr(token, "search") else (token in hay))
                if hit:
                    print(f"  ✗ personal identifier {_masked(token)} in {p.relative_to(root)}")
                    violations += 1
    # c) any profile/labs.json|metrics.json in the tree may only be a template (nearly
    #    empty series). There is exactly one exception: the automated-test fixture, which
    #    MUST declare itself synthetic in _meta. The demand for a declaration here is not
    #    a formality — otherwise "I will put a real profile in tests/, the audit will not
    #    notice" becomes a working way to carry a medical record outside.
    import json
    for f in root.rglob("profile/*.json"):
        if f.name not in ("labs.json", "metrics.json"):
            continue
        # The same skip as in (a), (b) and (d), and it was missing only here: a
        # build directory moved aside because the filesystem refuses unlink is not
        # part of the package. Without this line every build on such a filesystem
        # failed its audit over the PREVIOUS version's demo profile — and an audit
        # that fails for reasons unrelated to what is being shipped teaches people
        # to read past it, which is the one thing a fail-closed check cannot afford.
        if _quarantined(f):
            continue
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        meta = d.get("_meta") or d.get("meta") or {}
        declared = " ".join(str(v) for v in meta.values() if isinstance(v, str)).upper()
        sandbox = bool({"tests", "demo"} & set(f.parts))
        # The same stems in both alphabets as in `_declared_synthetic`, and for the same
        # reason: this is a human-written declaration being read, not text being printed.
        synthetic = bool(meta.get("synthetic")) or any(
            w in declared for w in ("СИНТЕТ", "ФИКСТУР", "SYNTHETIC", "FIXTURE", "ВЫМЫШЛ"))
        if sandbox and not synthetic:
            print(f"  ✗ {f.relative_to(root)}: a file in tests/ or demo/ is not declared "
                  f"synthetic (_meta must say outright that the data is invented)")
            violations += 1
            continue
        if sandbox:
            continue                      # declared synthetic — nothing to check for volume
        cont = d.get("markers") or d.get("metrics") or {}
        total_points = sum(len(m.get("series", [])) for m in cont.values() if isinstance(m, dict))
        if total_points > 3:  # a template must be nearly empty
            print(f"  ✗ {f.relative_to(root)}: {total_points} points — looks like real data, not a template")
            violations += 1
    # d) large raster images inside text files = screenshots of the application.
    #    The audit cannot look inside a JPEG/PNG, and a screenshot holds real lab
    #    results and genotypes. Icons (small blobs) are allowed.
    for p in root.rglob("*"):
        if not (p.is_file() and _is_text(p)):
            continue
        if any(part in SKIP_DIR for part in p.parts) or _quarantined(p):
            continue
        try:
            raw = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, PermissionError):
            continue
        for m in _RASTER_URI.finditer(raw):
            b64 = re.sub(r"\s", "", m.group(1))
            if len(b64) <= RASTER_MAX_B64:
                continue                      # an icon/favicon, not a screenshot
            try:
                blob = base64.b64decode(b64 + "=" * (-len(b64) % 4))
            except Exception:
                print(f"  ✗ broken embedded image in {p.relative_to(root)}")
                violations += 1
                continue
            h = hashlib.sha256(blob).hexdigest()
            if h not in APPROVED_RASTER_SHA256:
                print(f"  ✗ UNAPPROVED screenshot in {p.relative_to(root)}: sha256 {h[:16]}… "
                      f"({len(blob)//1024} KB). The audit cannot see what is in the image — "
                      f"look at it yourself and add the hash to APPROVED_RASTER_SHA256.")
                violations += 1

    # d) build junk. Not a privacy leak — a correctness one, and it appears
    #    precisely because the release gate is obeyed: the order is build → run the
    #    tests INSIDE the package → archive, and it is the test run that creates
    #    __pycache__. So the freshly built package is clean and the one you are
    #    about to hand over is not. The manual "check before archiving" step
    #    existed and was forgotten, which is what a check is for.
    junk = [p for p in root.rglob("*")
            if not _quarantined(p)
            and (p.suffix == ".pyc" or p.name in {".DS_Store", "Thumbs.db"}
                 or (p.is_dir() and p.name == "__pycache__"))]
    if junk:
        dirs = sorted({q for q in junk if q.is_dir()})
        print(f"  ✗ build junk in the package: {len(junk) - len(dirs)} files "
              f"in {len(dirs)} directories — they appear after a test run and must not "
              f"travel to the recipient. Remove and re-audit:")
        print(f"    find {root} \\( -name '__pycache__' -o -name '*.pyc' "
              f"-o -name '.DS_Store' \\) -prune -exec rm -rf {{}} +")
        violations += 1

    # e) the edition of the skill that actually shipped.
    #    Step 2 of the build puts share/skill/INSTRUCTION.md over the owner's
    #    src/skill/INSTRUCTION.owner.md. Nothing else stood behind that one line: the owner's
    #    edition is NOT on the private list (the package needs a file at that
    #    path, so omitting it is not an option), and the identifier audit above
    #    cannot see it either — those 116 KB hold diplotypes, phenotypes and
    #    per-drug caveats, and not one name, e-mail or sample number. A sanitiser
    #    that looks for identifiers has nothing to catch.
    #    So the check is on the property that distinguishes the editions rather
    #    than on the person: the personal block, written by sync_rules.py under a
    #    heading of its own. Two assertions, both from inside the package:
    #    the copies are one edition, and that edition is not the owner's.
    #    Since the split of names, two groups are checked instead of one, and the
    #    check got stronger rather than weaker: `SKILL.md` is everywhere the short
    #    entry, `INSTRUCTION.md` everywhere the long text, and within each group the
    #    copies must be one edition. A file named `*.owner.*` must not be in the
    #    package at all — that is now a property of the name, not of the content.
    for name in ("SKILL.md", "INSTRUCTION.md"):
        group = sorted(q for q in root.rglob(name) if not _quarantined(q))
        digests = {}
        for q in group:
            try:
                blob = q.read_bytes()
            except (OSError, PermissionError):
                continue
            digests.setdefault(hashlib.sha256(blob).hexdigest(), []).append(q)
            if OWNER_BLOCK_MARK.encode("utf-8") in blob:
                print(f"  ✗ the OWNER's edition of the skill shipped: "
                      f"{q.relative_to(root)} carries \"{OWNER_BLOCK_MARK}\". "
                      f"The generalised edition (share/skill/INSTRUCTION.md) was not "
                      f"put over it — check step 2 of build().")
                violations += 1
        if len(digests) > 1:
            print(f"  ✗ the package carries {len(digests)} different editions of "
                  f"{name} where it must carry one:")
            for h, qs in sorted(digests.items()):
                print(f"      {h[:16]}…  " +
                      ", ".join(str(q.relative_to(root)) for q in sorted(qs)))
            violations += 1

    owned = sorted(q for q in root.rglob("*.owner.*") if not _quarantined(q))
    if owned:
        print("  ✗ a file whose name says it belongs to the owner shipped:")
        for q in owned:
            print(f"      {q.relative_to(root)}")
        violations += 1
    return violations


def main(argv=None) -> int:
    argv = list(argv if argv is not None else sys.argv[1:])
    # A fork has no owner identifiers to protect, and for it the missing file is
    # normal rather than a failure. It has to SAY so: an unchecked build that
    # looks exactly like a checked one is how a list stops being maintained.
    required = "--no-personal-patterns" not in argv
    make_zip = "--zip" in argv
    argv = [a for a in argv if a not in ("--no-personal-patterns", "--zip")]
    repo = Path(__file__).resolve().parents[2]

    if argv and argv[0] == "--audit-only":
        if len(argv) < 2:
            sys.exit("Usage: --audit-only <folder> [--no-personal-patterns]")
        load_personal(repo, required)
        target = Path(argv[1]).expanduser().resolve()
        print(f"🔍 Audit of {target} …")
        v = audit(target)
        print("✅ AUDIT OK — no personal data found." if v == 0
              else f"❌ AUDIT FAILED — violations: {v}")
        return 0 if v == 0 else 2

    load_personal(repo, required)
    out = Path(argv[0]).expanduser().resolve() if argv else (repo.parent / "Scholion-SHARE")
    out.mkdir(parents=True, exist_ok=True)
    print(f"📦 Building the depersonalised package from {repo}\n   → {out}")
    build(repo, out)
    _fixed = _fix_exec_bits(out)
    if _fixed:
        print(f"• execute bit restored on scripts: {_fixed}")
    print("🔍 Automatic audit of the built package (the whole package, root included) …")
    total = audit(out)
    if total:
        print(f"\n❌ AUDIT FAILED — violations: {total}. Do NOT hand the package over; fix the source.")
        return 2
    if _QUARANTINED:
        # A note now, not a verdict. This used to return 3 and refuse to call the
        # package ready, because the leftovers were INSIDE the delivery folder and
        # whoever zipped it shipped two versions. They are outside it now, so the
        # package is complete — but a copy of a previous build is still occupying
        # disk somewhere the person did not put it, and the next build will try to
        # remove it again rather than adding to the pile.
        print("\n• a previous build could not be deleted and was moved OUTSIDE the package:")
        for q in _QUARANTINED:
            print(f"     rm -rf {q}")

    zip_path = None
    if make_zip:
        zip_path = _write_zip(out)
        lost = _verify_zip_exec_bits(zip_path, out)
        if lost:
            print(f"\n❌ the zip lost the execute bit on: {', '.join(lost)}. "
                  f"Do NOT hand the archive over.")
            return 2
        print(f"• zipped, execute bits verified INSIDE the archive: {zip_path}")

    print("\n✅ AUDIT OK — no personal data found. The package is ready to hand over:")
    print(f"   {out}")
    if zip_path:
        print(f"   {zip_path}  (single file, same content, +x already correct on arrival)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
