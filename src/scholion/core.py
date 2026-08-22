"""Loading of the profile and the reference data. No business logic — data access only."""
from __future__ import annotations
import datetime
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional


def file_date(path: Path) -> Optional[str]:
    """Date the file was last modified (YYYY-MM-DD), or None if there is no file."""
    try:
        return datetime.date.fromtimestamp(path.stat().st_mtime).isoformat()
    except Exception:
        return None


def json_updated(path: Path) -> Optional[str]:
    """Date from _meta.updated / _meta.catalog_updated of a JSON file (if present)."""
    try:
        d = _read_json(path)
        meta = d.get("_meta", {}) if isinstance(d, dict) else {}
        return meta.get("updated") or meta.get("catalog_updated")
    except Exception:
        return None

_PKG_DIR = Path(__file__).resolve().parent           # .../src/scholion
_KNOWLEDGE_DIR = _PKG_DIR / "knowledge"


def _source_tree_root() -> Optional[Path]:
    """Root of the source tree, if the package is run from it; otherwise None.

    The marker is the VERSION file next to the src/ folder. A package installed
    through pip has no such neighbour, and this is the only reliable way to tell
    the two modes apart. `_PKG_DIR.parents[1]` cannot be taken unconditionally:
    in site-packages it points ABOVE the packages directory, that is, nowhere,
    and the profile starts being looked for there.
    """
    try:
        root = _PKG_DIR.parents[1]
    except IndexError:
        return None
    return root if (root / "VERSION").exists() else None


def user_data_dir() -> Path:
    """User data directory — for the installed-package mode.

    The order accepted for the platform: XDG on Linux, Application Support on
    macOS, ~/.scholion as the fallback for everything else.
    """
    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg:
        return Path(xdg).expanduser() / "scholion"
    home = Path.home()
    if sys.platform == "darwin":
        return home / "Library" / "Application Support" / "Scholion"
    if sys.platform.startswith("linux"):
        return home / ".local" / "share" / "scholion"
    return home / ".scholion"


def is_installed_mode() -> bool:
    """True if the package is installed rather than run from the source tree."""
    return _source_tree_root() is None


def repo_dir() -> Path:
    """Data root. Overridden by SCHOLION_REPO_DIR.

    From the source tree — its root (the previous behaviour). From an installed
    package — the user data directory.
    """
    env = os.environ.get("SCHOLION_REPO_DIR")
    if env:
        return Path(env).expanduser().resolve()
    src = _source_tree_root()
    return src if src is not None else user_data_dir()


def profile_dir() -> Path:
    """Profile directory. Overridden by SCHOLION_PROFILE_DIR."""
    env = os.environ.get("SCHOLION_PROFILE_DIR")
    if env:
        return Path(env).expanduser().resolve()
    return repo_dir() / "profile"


def templates_dir() -> Path:
    """Profile templates that live inside the package (used by `scholion init`)."""
    return _PKG_DIR / "templates"


# ---- layout of the data directory ---------------------------------------
# The slot names are collected here instead of being scattered through the code for a
# concrete reason: at least four independent places know them — `.gitignore`, the audit
# of staged files, the sanitiser and the hygiene test. As long as each of them carries
# the name as its own literal, renaming a directory breaks **nothing**, and that is the
# danger: the checks keep passing, they merely stop catching. This happened already —
# after a rename the old `.gitignore` excluded the profile directory under its former
# name, and personal data in the folder with the new name was not excluded at all.
#
# The layout is described in `docs/DATA-LAYOUT.md`. In short, one
# question per directory: profile/genome — what the application knows; raw — what
# arrived from outside; work — what can be recomputed; archive — what used to be.
DATA_SLOTS = ("profile", "genome", "raw", "work", "archive")
RAW_KINDS = ("lab", "sequencing", "wearables", "reference")

# Slots that are allowed to be kept on another disk. `profile/` is deliberately
# not in the list: it is small, the application writes to it constantly, and it
# is what makes the data directory a data directory.
EXTERNAL_SLOTS = ("genome", "raw", "work")


def slot_dir(name: str) -> Path:
    """Directory of a layout slot, taking external storage into account.

    Resolution order — from the most explicit to the most general:
      1. `SCHOLION_<SLOT>_DIR` — one-off runs and tests;
      2. `profile/sources.json` — the person's permanent setting;
      3. `<data directory>/<slot>` — the default.

    Why a setting in a file and not only an environment variable: the
    application is started by a double click on a shortcut, and variables from
    `.zshrc` do not reach there. A setting that works only from the terminal is
    worse than no setting — it fires every other time, and it is unclear why.
    """
    env = os.environ.get(f"SCHOLION_{name.upper()}_DIR")
    if env:
        return Path(env).expanduser().resolve()
    if name in EXTERNAL_SLOTS:
        folder = (source_config() or {}).get(name)
        if folder:
            return Path(folder).expanduser()
    return repo_dir() / name


def raw_dir(kind: Optional[str] = None) -> Path:
    """Sources: what came from outside and does not change, it is only added to."""
    base = slot_dir("raw")
    return base / kind if kind else base


def work_dir() -> Path:
    """Intermediate results. Everything here must be recomputable by a command.

    This is a definition, not a wish: a file that cannot be restored belongs not
    here but in `raw/` or `profile/`.
    """
    return slot_dir("work")


def archive_dir() -> Path:
    """Retired versions of the profile files."""
    return slot_dir("archive")


def cache_dir() -> Path:
    """Cache of the external reference databases — one for the whole application.

    This expression used to be written out in five files in a row. It takes one
    of them diverging for the cache to end up in the code tree again, where
    nobody expects it and nobody cleans it up.

    The cache does NOT follow external storage, even if `work/` has been moved to
    another disk: a disconnected disk must not break an ordinary lookup in a reference
    database. That is why the path is computed from the data directory directly.
    """
    env = os.environ.get("SCHOLION_CACHE_DIR")
    if env:
        return Path(env).expanduser()
    new_path = repo_dir() / "work" / "cache"
    old_path = repo_dir() / ".cache"
    # A move without losing what has already accumulated: as long as the old directory
    # exists and the new one does not, the old way is kept. Dropping the cache silently
    # means making the person go to the network again for what has already been fetched.
    if old_path.is_dir() and not new_path.is_dir():
        return old_path
    return new_path


def source_status() -> List[Dict[str, Any]]:
    """Where each slot lies and whether it is connected.

    An external disk gets disconnected — that is a normal state, not a failure.
    The answer "the source is not connected, <path> was expected" is one a person
    can check; silent zeros in its place are the only truly bad outcome, because
    conclusions about one's own health are drawn from them.
    """
    cfg = source_config() or {}
    out = []
    for name in DATA_SLOTS:
        path = slot_dir(name)
        # These keys are published: the list goes out as `data_layout` in
        # `scholion assistant --json`, where a reader reaches for it with `jq`. A key is
        # an identifier, and identifiers in this project are English — not because
        # English is better, but because a key nobody can type is a key nobody uses.
        out.append({
            "slot": name,
            "path": str(path),
            "connected": path.is_dir(),
            "external": bool(cfg.get(name)) or bool(os.environ.get(f"SCHOLION_{name.upper()}_DIR")),
        })
    return out


def mkdir_private(path: Path) -> Path:
    """Create a directory closed to outsiders (0700 on POSIX) and return it.

    `mkdir` gives 0755 by default: on a shared machine any other user reads the
    contents. What lies here is the profile, the genome and the query caches —
    that is, derivatives of the same medical data. The permissions are set ONLY
    on creation: an already existing directory is left alone, the person may have
    configured access deliberately.
    """
    path = Path(path)
    if path.exists():
        return path
    path.mkdir(parents=True, exist_ok=True)
    if os.name == "posix":
        try:
            os.chmod(path, 0o700)
        except OSError:
            pass
    return path


import contextlib as _contextlib
import threading as _threading

try:
    import fcntl as _fcntl
except ImportError:                                   # non-POSIX; the owner runs POSIX
    _fcntl = None

_WRITE_TLOCK = _threading.RLock()
_WRITE_DEPTH = _threading.local()


@_contextlib.contextmanager
def profile_write_lock():
    """Serialize a read-modify-write of the profile across threads AND processes.

    The web server is a ThreadingHTTPServer: two requests that each read a file,
    change one field and write it back run concurrently, and the later writer
    silently drops the earlier one's change — a lost update, reproduced as five
    failures out of eight parallel writes. The same race exists between a CLI
    write and the running server. `write_json` makes a SINGLE write atomic; it
    cannot make a read-and-then-write atomic, which is what this does.

    A process-local RLock covers the server's own threads (and makes the lock
    reentrant, so a mutator that calls another mutator does not deadlock). An
    flock on a lockfile in the profile directory covers a separate CLI process.
    flock is advisory and per-open-description, so a second os.open in the same
    process would contend — the depth counter skips re-locking on reentry.
    """
    depth = getattr(_WRITE_DEPTH, "n", 0)
    with _WRITE_TLOCK:
        if depth or _fcntl is None:
            _WRITE_DEPTH.n = depth + 1
            try:
                yield
            finally:
                _WRITE_DEPTH.n = depth
            return
        try:
            lockpath = profile_dir() / ".write.lock"
            lockpath.parent.mkdir(parents=True, exist_ok=True)
            fd = os.open(str(lockpath), os.O_CREAT | os.O_RDWR, 0o600)
        except OSError:
            # If the lockfile cannot be made, the RLock still serializes this
            # process's own threads — better than nothing, and never a reason to
            # refuse to write somebody's data.
            _WRITE_DEPTH.n = depth + 1
            try:
                yield
            finally:
                _WRITE_DEPTH.n = depth
            return
        _WRITE_DEPTH.n = depth + 1
        try:
            _fcntl.flock(fd, _fcntl.LOCK_EX)
            yield
        finally:
            _WRITE_DEPTH.n = depth
            try:
                _fcntl.flock(fd, _fcntl.LOCK_UN)
            finally:
                os.close(fd)


def write_json(path: Path, data: Any, *, indent: int = 2) -> None:
    """Write JSON so that the file is never left half written.

    A direct rewrite (`write_text`) first truncates the file and only then writes
    the contents. An interruption in the middle — and this is `labs.json` with years
    of history — leaves truncated JSON that will not parse at all on the next read.
    The order here is different: a temporary file is written NEXT TO the target (the
    same directory, therefore the same file system, therefore an atomic rename), the
    buffers are flushed to the kernel, then `os.replace`. At any moment the target
    path holds either the old version whole or the new one whole.

    The `fsync` of the directory is a separate line and a separate `except`: it
    makes the rename resistant to a power cut, but it is not supported everywhere
    (network and synchronised directories are known to respond with a refusal),
    and failing because an ADDITIONAL guarantee is impossible is not acceptable.
    """
    path = Path(path)
    # Everything written INTO the profile carries the version of the shape it was
    # written in. Stamped here rather than at each of the dozen call sites: a
    # number applied by half the writers is worse than none, because then its
    # absence means «old» in one file and «whoever wrote this forgot» in the next.
    # Caches and knowledge files are not the profile and are left alone.
    try:
        # `.resolve()` on both sides, and it is not tidiness. `profile_dir()`
        # resolves; a path handed in by a caller does not have to. On macOS
        # `/var` and `/tmp` are symlinks to `/private/...`, so a profile
        # directory reached the ordinary way compares UNEQUAL to itself, the
        # stamp is skipped, and the file is written with no version at all —
        # silently, which defeats the entire point of having one. Caught by the
        # package's own test run on the owner's machine while the same code was
        # green on Linux, which is the third time this project has paid for that
        # difference.
        if isinstance(data, dict) and path.parent.resolve() == profile_dir():
            data = stamp_profile_schema(data)
    except Exception:                                             # noqa: BLE001
        pass          # a stamp is never a reason to fail a write of somebody's data
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    # A new file is created closed (0600). A plain `open()` would give 0644, that
    # is, after every rewrite the lab history would become readable by any user of
    # the machine. For an existing file the mode is preserved: it is not the
    # business of a write to change the permissions the person set themselves.
    try:
        keep = os.stat(path).st_mode & 0o7777
    except OSError:
        keep = None
    try:
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=indent)
            f.flush()
            os.fsync(f.fileno())
        if keep is not None:
            os.chmod(tmp, keep)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    try:
        dfd = os.open(str(path.parent), os.O_RDONLY)
        try:
            os.fsync(dfd)
        finally:
            os.close(dfd)
    except OSError:
        pass


_JSON_CACHE: Dict[str, Any] = {}   # str(path) -> (mtime, data)


def _read_json(path: Path) -> Dict[str, Any]:
    """Read JSON with invalidation by the file modification time.

    The cache lives as long as the file has not changed on disk. That way the application
    always returns the ACTUAL data of the source (after edits from the UI, from a parallel
    branch or by hand) — without requiring a restart, without re-reading it on every request.
    """
    try:
        mt = path.stat().st_mtime
    except (FileNotFoundError, NotADirectoryError):
        return {}
    key = str(path)
    hit = _JSON_CACHE.get(key)
    if hit is not None and hit[0] == mt:
        return hit[1]
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    _JSON_CACHE[key] = (mt, data)
    return data


# ---- the version of the profile format -----------------------------------
#: The version the code in this build writes and understands.
#:
#: Raised only when a file's SHAPE changes in a way an older build would read
#: wrongly — a renamed field, a changed nesting, a unit that now means something
#: else. Adding a field nobody reads yet is not a new version.
PROFILE_SCHEMA = 1

#: Where the number lives. The prose describing a file's layout used to live
#: under the same key, and the two are not the same thing: one is for a person
#: reading the file, the other is for code deciding whether it may read it at
#: all. The prose moved to `_meta.shape`.
_SCHEMA_FIELD = "schema"


def _profile_meta(data: Dict[str, Any]) -> Dict[str, Any]:
    """The metadata block, under either spelling.

    `pharmacogenomics.json` shipped with `meta` while every other profile file
    used `_meta`. Both are accepted on read — a file already on somebody's disk
    is not going to rename itself — and `_meta` is what gets written.
    """
    for key in ("_meta", "meta"):
        v = data.get(key)
        if isinstance(v, dict):
            return v
    return {}


def profile_meta(data: Dict[str, Any]) -> Dict[str, Any]:
    """The metadata block of a profile file, under either spelling.

    Public because callers outside this module need it and were reaching for
    `data["meta"]` directly — which is the older spelling, so a file written with
    `_meta` came back empty and a missing subject id was printed as «subject ?».
    """
    return _profile_meta(data)


def profile_is_synthetic() -> bool:
    """Is the profile now loaded a fictional person rather than somebody's own data?

    `scholion init --demo` writes `synthetic: true` into every file it lays down.
    Asking any one of them is enough, and pharmacogenomics.json is the file the
    subject id lives in. The answer travels to the interface so that the demo says
    so on every screen: on the first pass the only sign of it was the string
    «DEMO-0001» in the header, which reads like a laboratory accession number, and
    a reader who takes it for their own is exactly who this project must not fail.
    """
    try:
        return bool(_profile_meta(pharmacogenomics()).get("synthetic"))
    except Exception:                                        # noqa: BLE001
        return False


def profile_schema_of(data: Dict[str, Any]) -> int:
    """The version a profile file declares. An undeclared file is version 1.

    Silence means «written before the number existed», which is exactly version
    1 — every file this project has ever written. Treating it as unknown and
    refusing would lock every existing user out of their own data on upgrade.
    """
    v = _profile_meta(data).get(_SCHEMA_FIELD)
    if isinstance(v, bool):          # a stray `true` is not a version
        return 1
    if isinstance(v, int) and v > 0:
        return v
    if isinstance(v, str) and v.strip().isdigit():
        return int(v.strip())
    return 1                          # prose, absent, or nonsense — the original shape


class ProfileFromTheFuture(RuntimeError):
    """A profile file written by a newer build than this one.

    Raised rather than shrugged off. The alternative is reading a shape the code
    does not know with rules that no longer apply — silently, on somebody's
    medical history, with no symptom until a number comes out wrong. Refusing
    names the file and the two versions; the person can update or keep a copy.
    """


def read_profile_json(path: Path) -> Dict[str, Any]:
    """Read one file of the profile, checking that this build may read it.

    Migration forward has nothing to do yet: version 1 is the only shape that
    has ever existed. The point of the check is the other direction — a file
    from a newer build must not be read by an older one. That direction cannot
    be added retroactively: by the time there is a version 2, the builds that
    would need to refuse it are already installed.
    """
    data = _read_json(path)
    if not data:
        return data
    found = profile_schema_of(data)
    if found > PROFILE_SCHEMA:
        raise ProfileFromTheFuture(
            f"{path.name} declares profile schema {found}; this build understands "
            f"{PROFILE_SCHEMA}. It was written by a newer version of Scholion. "
            f"Update, or keep this file aside — reading it here would apply rules "
            f"that no longer describe it.")
    return data


def stamp_profile_schema(data: Dict[str, Any]) -> Dict[str, Any]:
    """Put the current version into a structure about to be written to the profile.

    In place and idempotent. Called by the writers rather than left to each of
    them to remember, because a stamp applied by half the writers is worse than
    none: it makes the absence of a number meaningful in one file and accidental
    in the next.
    """
    if not isinstance(data, dict):
        return data
    meta = data.get("_meta")
    if not isinstance(meta, dict):
        legacy = data.get("meta")
        meta = dict(legacy) if isinstance(legacy, dict) else {}
        data["_meta"] = meta
        data.pop("meta", None)
    meta[_SCHEMA_FIELD] = PROFILE_SCHEMA
    return data


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


# ---- multilingual fields in the knowledge base ----------------------------
# A curated field may hold either a plain string or a per-language map:
#
#     "why": "the marker is out of range"
#     "why": {"en": "the marker is out of range", "ru": "показатель вне коридора"}
#
# Resolution falls back to the LANGUAGE OF THE SOURCE rather than to a key or an
# empty string: a phrase that exists only in Russian is printed in Russian inside
# an English report. That is deliberate. The alternative — printing nothing, or an
# identifier — hides a fact from someone reading about their own health, and a
# sentence in the wrong language is a far smaller problem than a missing one.
#
# The same rule scales past two languages: the catalogue of markers is not, and
# cannot be, exhaustive, so entries will keep arriving in whatever language their
# source spoke.
#
# Names of markers, units and other values that came from a person's own document
# are NOT in this list. They are printed as they were written — otherwise the
# report stops matching the paper the person is holding.
# The split is not "which fields hold text" but "who reads them".
#
# A field PRINTED TO THE PERSON is multilingual — it is the project speaking to
# someone about their health, and they should hear it in their language.
#
# A field that is a NOTE TO WHOEVER MAINTAINS THE FILE (`purpose`, `schema`,
# `generated`, `how_to_use`) is a comment that happens to live inside JSON. Like
# any comment in this project it is written in English and stays a plain string:
# making it multilingual would double the upkeep of text no user ever sees.
LOCALIZABLE_FIELDS = {
    # explanations and verdicts
    "note", "why", "reason", "action", "advice", "caveat", "comment",
    "interpretation", "recommendation", "evidence_note", "validity_note",
    "meaning", "effect", "mechanism", "manage", "claim", "effect_size",
    "low_dose_note", "pharmacologic_dose", "verdict_rule", "population_caveat",
    "not_a_cpic_drug_pair", "guidance_gap_reason", "report_rule_note", "units_note",
    "would_close", "why_named_not_taken",
    "assembly_secondary_note", "assembly_secondary_open", "applies_to_sex_note",
    "zygosity_note", "loinc_note", "common_pitfalls", "hypothesis", "evidence",
    "text", "rule", "summary", "description",
    # names and headings shown on screen
    "label", "display_name", "name", "title", "category", "phenotype",
    "suggest", "specialist", "source", "class", "nutritional_dose", "forms",
    "one_line", "melatonin", "metabolic", "pk",
    # `unit` is on this list ONLY because the resolver runs on knowledge files,
    # never on a person's profile. A unit inside `wearable_metrics.json` is ours
    # (we defined the metric); a unit inside someone's `labs.json` came off their
    # form and is printed as written. Same field name, two different owners —
    # which is exactly why the resolver is scoped to the knowledge directory.
    "unit",
}

# Deliberately NOT localizable, even though they are printed. Code compares these
# values literally — `quality_label` is ranked by `_QRANK`, `level` picks an icon,
# `severity` orders interactions. A translated value silently stops matching, and
# the failure is invisible: the ranking simply comes out wrong. A printed string
# that is also a key belongs in the message catalogue as a rendering of the key,
# never as a translation of the value.
COMPARED_NOT_TRANSLATED = {"quality_label", "level", "severity", "cpic_level",
                           "flag", "direction", "status", "verdict"}


def _localized(value: Any, lang: str) -> Any:
    """A per-language map → one string. Anything else is returned untouched."""
    if not isinstance(value, dict) or not value:
        return value
    # A language map is two-letter keys AND text values. Keys alone are not
    # enough: `{"ab": 1, "cd": 2}` is a lookup table that happens to have short
    # keys, and resolving it would replace a structure with one of its numbers.
    if not all(isinstance(k, str) and len(k) == 2 and k.isalpha() and isinstance(v, str)
               for k, v in value.items()):
        return value                      # an ordinary nested object, not a language map
    if lang in value:
        return value[lang]
    from .i18n import DEFAULT
    if DEFAULT in value:
        return value[DEFAULT]
    return next(iter(value.values()))     # the language of the source


# Objects whose KEYS are data and whose VALUES are prose: `alternatives` is keyed
# by the name of the alternative, `confidence_modifiers` by a ClinVar review
# status. A field-name rule cannot reach inside them — the field name is the
# datum. So the container is named instead, and every value inside it is
# resolved. Without this the text renders raw, and the failure is silent for
# whoever added a new alternative.
# `convert_refused` joins them: its keys are the unit surfaces a form may print
# (data — «mg/dL», «мг/дл») and its values are the sentence explaining why that
# unit cannot be converted. A field-name rule cannot reach inside a map keyed by
# data, which is what this set is for.
LOCALIZABLE_CONTAINERS = {"alternatives", "confidence_modifiers", "review_status",
                          "convert_refused"}

# A language map whose values are STRUCTURE, not prose: `labels` in the marker
# dictionary holds, per language, a marker's display name together with the
# substrings that recognise it on a form. It must not go through `_localized` —
# that would collapse the whole per-language object down to one language's, and
# the parser would then look for Russian names only when the output language
# happens to be Russian. Reading it is the job of `marker_rules` (all languages at
# once, because a form does not know what the output language is) and
# `marker_display` (one language, with fallback).
#
# It is named here so that the audit of stray language maps can tell «resolved by
# a dedicated accessor» from «forgotten, and will print raw into a report». Being
# on this list is a claim that something reads the field deliberately.
# A phenotype code is two letters (RM, UM, PM) and so is a language code (en, ru):
# by shape alone they are indistinguishable, and `guidance_gaps`, keyed by
# phenotype, reads to the language audit as a map of translations. It is declared
# structural here — its values are objects, and the audit walks INTO them, so the
# prose inside still has to sit in a curated field.
STRUCTURAL_LANGUAGE_MAPS = {"labels", "guidance_gaps"}


def _localize_tree(node: Any, lang: str) -> Any:
    if isinstance(node, dict):
        out = {}
        for k, v in node.items():
            if k in LOCALIZABLE_FIELDS:
                out[k] = _localized(v, lang)
            elif k in LOCALIZABLE_CONTAINERS and isinstance(v, dict):
                out[k] = {kk: _localized(vv, lang) for kk, vv in v.items()}
            else:
                out[k] = _localize_tree(v, lang)
        return out
    if isinstance(node, list):
        return [_localize_tree(v, lang) for v in node]
    return node


def knowledge_dir_local() -> Path:
    """Where a REFRESHED copy of a knowledge file lives, on this machine.

    The bundled `knowledge/` travels inside the package and is, after a
    `pip install`, usually read-only (site-packages) and replaced wholesale by
    the next upgrade. A catalogue refreshed from its upstream must therefore land
    beside the person's own data, not inside the wheel — otherwise «update the
    reference base» would mean «reinstall the program», and an upgrade would
    silently discard the refresh.
    """
    return repo_dir() / "knowledge"


def knowledge_path(name: str) -> Path:
    """The file that WINS for a knowledge name: a local refresh over the bundle.

    Both are the same shape; the local one is newer by construction, because the
    only thing that writes it is an import from the upstream source. `sources`
    prints which of the two answered, so the precedence is visible rather than
    inferred.
    """
    local = knowledge_dir_local() / name
    try:
        if local.is_file():
            return local
    except OSError:
        pass
    return _KNOWLEDGE_DIR / name


def knowledge_is_local(name: str) -> bool:
    return knowledge_path(name) != _KNOWLEDGE_DIR / name


def write_knowledge_local(name: str, data: Any) -> Path:
    """Write a refreshed knowledge file to the LOCAL copy, next to the profile.

    Never into the package: see `knowledge_dir_local`. The write goes through
    `write_json`, so it is atomic — a knowledge file half-written by an
    interrupted import would be a reference base that fails to parse.
    """
    p = knowledge_dir_local() / name
    write_json(p, data)
    _KB_CACHE.clear()
    return p


_KB_CACHE: Dict[str, Any] = {}


def _read_knowledge(name: str) -> Dict[str, Any]:
    """A knowledge file with its curated fields resolved to the current language.

    Resolution happens once, here, rather than at every place that renders a
    field. Two dozen call sites would each have to remember the rule, and the one
    that forgot would print a raw `{'en': …, 'ru': …}` into a report.
    """
    from .i18n import lang as _lang
    path = knowledge_path(name)
    code = _lang()
    try:
        mt = path.stat().st_mtime
    except (FileNotFoundError, NotADirectoryError):
        return {}
    key = f"{path}|{code}"
    hit = _KB_CACHE.get(key)
    if hit is not None and hit[0] == mt:
        return hit[1]
    data = _localize_tree(_read_json(path), code)
    _KB_CACHE[key] = (mt, data)
    return data


# ---- reference data (knowledge/) -----------------------------------------
def cpic_kb() -> Dict[str, Any]:
    return _read_knowledge("cpic_drug_gene.json")


def test_rules() -> Dict[str, Any]:
    return _read_knowledge("test_rules.json")


def med_classes() -> Dict[str, Any]:
    """Public drug→class dictionary (for class-based rules). Not personal."""
    return _read_knowledge("med_classes.json")


def drug_interactions() -> Dict[str, Any]:
    """Public database of drug interactions by class. Not personal."""
    return _read_knowledge("drug_interactions.json")


def goal_targets() -> Dict[str, Any]:
    """Targets a clinical association has published, with the citation attached.

    Separate from `lab_markers.json` on purpose: that file holds reference
    INTERVALS, which say where most of a population sits. A target says where a
    body of physicians has argued a value should be brought, for a named
    population and a stated reason. The two disagree often — LDL-C sits inside
    the laboratory range at values every cardiology guideline calls too high —
    and a file that mixed them would make the difference impossible to show.
    """
    return _read_knowledge("goal_targets.json")


def longevity_directions() -> Dict[str, Any]:
    """Curated directions of longevity alleles — which allele the primary source
    calls favourable. Public reference data; it contains nobody's genotypes."""
    return _read_knowledge("longevity_directions.json")


def loci() -> Dict[str, Any]:
    """rsID → GRCh38 coordinate. The one place in this project where a position
    may be asserted; everything else asks here."""
    return _read_knowledge("loci.json")


def loinc_index() -> Dict[str, str]:
    """LOINC code → marker key, built from what the base actually carries.

    Task 60/21. A FHIR `Observation` names its analyte by LOINC code, so the
    reverse direction is what an import needs — and it did not exist. Built here
    rather than stored, because a second copy of a mapping drifts from the first.

    It is deliberately small: 33 of 408 markers carry a code today. That is the
    honest denominator, and `scholion sources` prints it as a fraction rather
    than letting the presence of an index imply completeness. A code arrives per
    marker with medical verification, or through the local overlay as a proposal
    somebody confirms — never from a guess, because a wrong code silently binds
    an incoming value to the wrong analyte.
    """
    out: Dict[str, str] = {}
    for key, meta in (lab_test_meta().get("tests") or {}).items():
        code = (meta or {}).get("loinc")
        if code:
            out[str(code)] = key
    try:
        from . import markers_local as _ml
        for k, spec in (_ml.confirmed_markers() or {}).items():
            if spec.get("loinc"):
                out.setdefault(str(spec["loinc"]), k)
    except Exception:
        pass
    return out


def loinc_coverage() -> Dict[str, Any]:
    """How much of the dictionary is reachable by LOINC code, as a fraction."""
    markers = lab_markers().get("markers") or {}
    idx = loinc_index()
    return {"coded": len(idx), "markers": len(markers),
            "pct": round(100.0 * len(idx) / len(markers), 1) if markers else 0.0}


def lab_test_meta() -> Dict[str, Any]:
    """Per-test metadata: biomaterial, tier, whether the test is taken fasting, LOINC.

    Read by the laboratory engine to know what a threshold PRESUMES about the
    draw. The base recorded «fasting: true» for years while the engine applied
    fasting thresholds to any measurement whatever the hour — the fact was held
    and never compared.
    """
    return _read_knowledge("lab_test_meta.json")


def markers_overlay_path() -> Path:
    """Where locally added marker entries live: <data>/knowledge/lab_markers.local.json.

    A separate file, never the shipped one. The overlay is how the dictionary
    grows from the person in front of it without the build lying about what it
    ships: an entry here is theirs until somebody reviews it, and an upgrade
    cannot silently overwrite or silently keep it.
    """
    return knowledge_dir_local() / "lab_markers.local.json"


def lab_markers() -> Dict[str, Any]:
    """Public dictionary for recognising lab markers, plus locally added entries.

    The overlay is MERGED, not substituted: a local file replacing the shipped
    dictionary would quietly drop four hundred markers to add one. Each merged
    entry keeps its `status` — `proposed` or `confirmed` — and every consumer that
    makes a claim about a value has to look at it.

    `proposed` exists because of what it prevents. When a row on a form matches no
    marker, the honest repair is a new dictionary entry; but an entry drafted from
    a single form, by a model or by a person in a hurry, is a guess about what the
    row means and what corridor belongs to it. Until a person confirms it the
    value is READ, STORED and SHOWN — it is not lost, which was the defect — and
    no statement of «above normal» is made on it. The same shape as
    `ref_sex_unknown`: keep the number, withhold the claim.
    """
    base = _read_knowledge("lab_markers.json")
    p = markers_overlay_path()
    try:
        if not p.is_file():
            return base
        extra = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return base
    from .i18n import lang as _lang
    merged = dict(base)
    markers = dict(base.get("markers") or {})
    for key, spec in (extra.get("markers") or {}).items():
        if key in markers:
            # A local entry never overwrites a shipped one. The shipped
            # dictionary is reviewed; silently shadowing it from a file nobody
            # reviewed is how a curated base stops being curated.
            continue
        spec = _localize_tree(spec, _lang())
        spec.setdefault("status", "proposed")
        markers[key] = spec
    merged["markers"] = markers
    return merged


def proposed_markers() -> Dict[str, Any]:
    """Locally added entries that no person has confirmed yet."""
    return {k: v for k, v in (lab_markers().get("markers") or {}).items()
            if isinstance(v, dict) and v.get("status") == "proposed"}


def marker_rules(spec: Dict[str, Any], field: str) -> List[str]:
    """One recognition rule of a marker, gathered across every language it has.

    A form is printed in one language, so the other language's substrings simply
    do not occur in it — which is why matching all of them at once is safe and why
    it is also the only thing that works: the dictionary does not know in advance
    which language the next form will arrive in, and asking the caller to guess
    would put a language detector in front of every parse.

    Order is preserved per language so that the longest-name rule downstream keeps
    behaving the way it did when the lists were flat.
    """
    labels = spec.get("labels") or {}
    out: List[str] = []
    for lang in labels:
        vals = (labels.get(lang) or {}).get(field) or []
        out.extend(v for v in vals if isinstance(v, str))
    return out


def unit_table() -> Dict[str, Any]:
    """Labels for units, keyed by UCUM code (knowledge/units.json)."""
    return _read_knowledge("units.json").get("units", {})


def unit_label(code: str, default: str = "") -> str:
    """What to print for a UCUM code, in the current output language.

    The code is the identity and the label is the rendering — which is why a
    marker's `unit` is `mmol/L` in every language and reads «ммоль/л» only on the
    way to a Russian screen. An unknown code prints as itself: a bare code beside
    a number is ugly and obvious, whereas an empty string is a number with no unit
    at all, and that is a number nobody can check.
    """
    entry = unit_table().get(code) or {}
    lbl = entry.get("label")
    if isinstance(lbl, str) and lbl:
        return lbl                       # already resolved by _read_knowledge
    return code or default


def _norm_unit(s: str) -> str:
    """A unit string as written by a human, made comparable.

    Case and spacing vary between labs and between keyboards; the identity of the
    unit does not. µ and мк are NOT folded together — one is a Greek letter in a
    Latin string and the other two Cyrillic letters, and both appear in real
    forms, so both are listed instead of being guessed at.
    """
    for sp in (" ", " ", " ", " "):
        s = s.replace(sp, "")
    return s.strip().casefold()


def resolve_unit(spec: Dict[str, Any], given: str) -> Dict[str, Any]:
    """Can this value be stored under this marker, and multiplied by what?

    Returns `{"ok": True, "factor": …, "canonical": …}`, or `{"ok": False}` with
    the units that WOULD be accepted. The list matters as much as the refusal: an
    error that says only «unknown unit» leaves a person guessing at spelling,
    which is how a wrong unit gets typed a second time and accepted.

    The reason this exists at all: thresholds are stored in the canonical unit
    without naming it — glucose ≥ 5.6 means mmol/L — so a value arriving in mg/dL
    and stored as written is compared against arithmetic that belongs to somebody
    else. Nothing errors; the person is simply told the wrong thing, in a document
    that goes to their doctor.
    """
    canonical = spec.get("unit") or ""
    units = dict(spec.get("units") or {})
    # A CONFIRMED local unit form joins the gate; a proposed one deliberately
    # does not. A wrong marker entry costs a wrong corridor; a wrong factor costs
    # a wrong NUMBER, so nothing multiplies a value until a person has vouched
    # for the multiplier. The proposal travels in the refusal instead.
    try:
        from . import markers_local as _ml
        units.update(_ml.confirmed_units(spec.get("key") or spec.get("_key") or ""))
    except Exception:
        pass
    g = _norm_unit(given or "")
    if not g:
        return {"ok": False, "canonical": canonical, "accepted": _accepted_units(spec),
                "reason": "no unit given"}

    # A unit refused deliberately answers with its reason. Silence here would send
    # the person looking for a spelling mistake in a spelling that is correct —
    # HbA1c in mmol/mol is a real unit, it simply cannot be converted by a factor.
    for surface, why in (spec.get("convert_refused") or {}).items():
        if _norm_unit(surface) == g:
            return {"ok": False, "canonical": canonical, "accepted": _accepted_units(spec),
                    "reason": why}

    # A unit that converts by a FORMULA rather than by a factor. HbA1c is the
    # case: the IFCC scale (mmol/mol) and the NGSP scale (%) are related by
    # `% = 0.09148 × mmol/mol + 2.152`, the NGSP master equation — affine, not
    # proportional. Multiplying 48 mmol/mol by anything gives the wrong number;
    # the right one is 6.5 %.
    #
    # It carries an `offset`, and every caller has to apply it. That «has to» is
    # the dangerous part: a caller reading only `factor` would store 48 as 48 %,
    # which is not a refusal but a silently wrong diabetic reading. So nothing
    # calls this and does the arithmetic itself any more — `convert_to_canonical`
    # below is the one place the law lives, and both entry points go through it.
    for surface, rule in (spec.get("convert_affine") or {}).items():
        if _norm_unit(surface) == g:
            return {"ok": True, "factor": float(rule["k"]), "offset": float(rule["b"]),
                    "affine": True, "canonical": canonical,
                    "note": rule.get("source")}

    # `convert` first, then `units`: the conversion table is written for typed
    # input and carries the full constants, while `units` exists for the parser
    # and rounds where a form's own precision makes rounding harmless.
    for source in (spec.get("convert") or {}, units):
        for surface, factor in source.items():
            if _norm_unit(surface) == g:
                return {"ok": True, "factor": float(factor), "offset": 0.0,
                        "canonical": canonical}

    if canonical and g == _norm_unit(canonical):
        return {"ok": True, "factor": 1.0, "offset": 0.0, "canonical": canonical}
    entry = (_read_knowledge_raw("units.json").get("units", {}).get(canonical) or {})
    labels = entry.get("label") or {}
    if isinstance(labels, dict) and any(_norm_unit(v) == g for v in labels.values()
                                        if isinstance(v, str)):
        return {"ok": True, "factor": 1.0, "offset": 0.0, "canonical": canonical}

    return {"ok": False, "canonical": canonical, "accepted": _accepted_units(spec),
            "reason": "unit not recognised"}


def convert_to_canonical(spec: Dict[str, Any], given: str, value: float) -> Dict[str, Any]:
    """A value in whatever unit it arrived in → the marker's canonical unit.

    THE ONE PLACE THE ARITHMETIC LIVES, and it exists because there are now two
    laws instead of one. Almost every unit converts by a factor; HbA1c in mmol/mol
    converts by `% = 0.09148 × mmol/mol + 2.152`, which is affine. A caller that
    knew only about factors and met the second law would multiply 48 by 1.0 and
    store 48 %, and nothing would error — the person would simply be told they
    have a catastrophic HbA1c. That is not a hypothetical failure mode; it is the
    same shape as the mg/dL glucose defect this gateway was built after.

    So the callers no longer multiply. They ask here, for the value and for each
    end of the reference range separately — a corridor printed on a form is in the
    same unit as the result, and converting one without the other reproduces the
    original defect one level down.

    Rounded to four decimals, as elsewhere: below every unit's reporting precision
    and above every threshold in the knowledge base, so it neither invents digits
    nor loses a comparison.
    """
    res = resolve_unit(spec, given)
    if not res.get("ok"):
        return res
    k, b = float(res.get("factor", 1.0)), float(res.get("offset", 0.0))
    if k == 1.0 and b == 0.0:
        return {**res, "value": value}
    return {**res, "value": round(value * k + b, 4)}


def _accepted_units(spec: Dict[str, Any]) -> List[str]:
    """Every spelling this marker would take, for the refusal message."""
    out: List[str] = []
    canonical = spec.get("unit") or ""
    if canonical:
        out.append(canonical)
        labels = ((_read_knowledge_raw("units.json").get("units", {}).get(canonical) or {})
                  .get("label") or {})
        if isinstance(labels, dict):
            out.extend(v for v in labels.values() if isinstance(v, str) and v not in out)
    for source in (spec.get("convert") or {}, spec.get("units") or {},
                   spec.get("convert_affine") or {}):
        for surface in source:
            if surface not in out:
                out.append(surface)
    return out


def _read_knowledge_raw(name: str) -> Dict[str, Any]:
    """The knowledge file WITHOUT language resolution.

    `_read_knowledge` collapses every per-language map to the output language,
    which is right for printing and wrong here: a unit typed by a Russian-speaking
    user must be recognised while the output language is English, and vice versa.
    Recognition reads all languages; rendering reads one.
    """
    path = knowledge_path(name)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def marker_display(spec: Dict[str, Any], lang: str, default: str = "") -> str:
    """The marker's name for the screen, in `lang`, falling back to any language.

    Fallback rather than blank: a label that exists in one language only — a
    species name, a panel nobody has translated yet — must still be printed. The
    project's rule for multilingual fields is fallback to the source language, not
    replacement by silence.
    """
    labels = spec.get("labels") or {}
    got = (labels.get(lang) or {}).get("display")
    if got:
        return got
    for other in labels.values():
        if isinstance(other, dict) and other.get("display"):
            return other["display"]
    return default


def drug_lab_monitoring() -> Dict[str, Any]:
    """Public map class→monitored lab tests. Not personal."""
    return _read_knowledge("drug_lab_monitoring.json")


def dose_evidence() -> Dict[str, Any]:
    """Public dose/critical-claim layer: dose thresholds, effect sizes, formulations.
    Not personal — the comparison with the patient's numbers is done by the engine."""
    return _read_knowledge("dose_evidence.json")


def clinical_thresholds() -> Dict[str, Any]:
    """Public map of CLINICAL ACTION THRESHOLDS (not of reference intervals). Not personal."""
    return _read_knowledge("clinical_thresholds.json")


def external_tools() -> Dict[str, Any]:
    """Command-line tools the data preparation needs: sets, reasons, package names.

    Public reference data like every other file here — the mapping from a binary
    (`bgzip`) to the package that carries it (`htslib`) is not something to keep
    in code, because it is corrected by whoever notices a manager renamed one.
    """
    return _read_knowledge("external_tools.json")


def wearable_metrics() -> Dict[str, Any]:
    """Public reference for interpreting wearable-device metrics. Not personal."""
    return _read_knowledge("wearable_metrics.json")


def wearable_trends() -> Dict[str, Any]:
    """PERSONAL historical lifestyle data (wearable devices): wearable_trends.json.
    Yearly trends: metric → {year: value}. Personal, only on the owner's machine."""
    p = profile_dir() / "wearable_trends.json"
    if not p.exists():
        return {}
    from . import wearables                      # local: wearables imports core
    return wearables.migrate(read_profile_json(p))


def wearable_primary() -> Optional[str]:
    """Which device answers, when two of them measured the same thing.

    A person's own setting (`scholion profile --wearable whoop`), never a
    default: picking one silently is how a chart ends up showing a change of
    watch as a change of health.
    """
    v = (metrics_json().get("profile") or {}).get("wearable_primary")
    return (v or "").strip() or None


def lifestyle_brief_src() -> Dict[str, Any]:
    """PERSONAL curated lifestyle brief (profile/lifestyle_brief.json).
    The wording is written by the assistant, the numbers are substituted by the engine from tokens. Personal."""
    p = profile_dir() / "lifestyle_brief.json"
    return read_profile_json(p) if p.exists() else {}


def studies() -> Dict[str, Any]:
    """PERSONAL instrumental studies (profile/studies.json): ECG, echocardiography, ultrasound, MRI.

    Introduced on 2026-08-14 after a failure: the conclusions lay only as prose in labs.md, the
    engine did not see them, and a study that had been done was twice called not done.
    """
    p = profile_dir() / "studies.json"
    return read_profile_json(p) if p.exists() else {}


def focus_src() -> Dict[str, Any]:
    """PERSONAL focus of attention (profile/focus.json): the one task the owner is
    concentrated on right now. Curated wording and levers; the numbers the engine takes live."""
    p = profile_dir() / "focus.json"
    return read_profile_json(p) if p.exists() else {}


def focus_log() -> Dict[str, Any]:
    """PERSONAL journal of episodes for the focus (profile/focus_log.json): alcohol, drugs, dinner.
    Needed in order to separate factors that are superimposed on one another in passive data."""
    p = profile_dir() / "focus_log.json"
    return read_profile_json(p) if p.exists() else {}


def sleep_nightly() -> Dict[str, Any]:
    """PERSONAL per-night sleep data (profile/sleep_nightly.json): phases, falling asleep,
    awakenings. The granularity is one night, for n-of-1 analyses."""
    p = profile_dir() / "sleep_nightly.json"
    return read_profile_json(p) if p.exists() else {}


def prs_results() -> Dict[str, Any]:
    """PERSONAL aggregated polygenic scores (profile/prs_results.json). Personal."""
    p = profile_dir() / "prs_results.json"
    return read_profile_json(p) if p.exists() else {}


def longevity_data() -> Dict[str, Any]:
    """PERSONAL longevity findings (profile/longevity_findings.json). Personal."""
    p = profile_dir() / "longevity_findings.json"
    return read_profile_json(p) if p.exists() else {}


def health_goals() -> Dict[str, Any]:
    """PERSONAL goal for the metrics (profile/health_goals.json): the wording, the anchor points,
    the reference values and the chart parameters. Current values/series are taken live from labs+wearable."""
    p = profile_dir() / "health_goals.json"
    return read_profile_json(p) if p.exists() else {}


def genome_dir() -> Path:
    """Directory with the personal genome database (genome/).

    `SCHOLION_GENOME_DIR` overrides the search. It is needed in exactly the same place as
    `SCHOLION_PROFILE_DIR`: otherwise a run on a synthetic profile would still mix in the
    REAL genome database of the owner that lies next to the repository, and the result would
    depend on whose machine it was run on.
    """
    env = os.environ.get("SCHOLION_GENOME_DIR")
    if env:
        return Path(env).expanduser()
    for base in (slot_dir("genome"), repo_dir() / "genome"):
        if base.exists():
            return base
    return slot_dir("genome")


def genome_bases() -> List[Path]:
    """Where to look for the files of the genome database, in order of priority.

    If `SCHOLION_GENOME_DIR` is set, the list consists ONLY of it: an explicit setting
    must switch off the search among the neighbours, otherwise an "empty" test folder is
    silently substituted by the owner's real database that lies next to the repository — and
    a run on synthetic data stops being synthetic.
    """
    env = os.environ.get("SCHOLION_GENOME_DIR")
    if env:
        return [Path(env).expanduser()]
    # `slot_dir` first: it is the declared location and honours external storage.
    # This used to end in `profile_dir().parent / "genome"` — a path built by
    # walking UP from where the profile is, the same shape that let the lab and
    # wearable searches reach into somebody's documents. Harmless here in
    # practice, because the parent is normally the data root anyway; removed
    # because "harmless in practice" is what the other two were until a
    # directory moved.
    return [slot_dir("genome"), repo_dir() / "genome"]


def whats_new() -> Dict[str, Any]:
    """Result of the last check for database updates (genome/whats_new.json).
    NOT cached — it is updated after every check."""
    p = genome_dir() / "whats_new.json"
    return read_profile_json(p) if p.exists() else {}


_CYR = "\u0430-\u044f"          # Russian lower case (after the yo→ye normalisation)
_WORD = _CYR + "a-z0-9"


def _norm_drug(s: str) -> str:
    """Normalisation of a drug name: lower case, yo→ye, any non-alphanumeric
    character (hyphen, bracket, comma, = sign) → space, collapsing of spaces.
    That way "Sea-Iodine 1000" and "sea iodine 1000" become one and the same."""
    s = (s or "").lower().replace("\u0451", "\u0435")
    s = re.sub(r"[^" + _WORD + r"]+", " ", s)
    return " ".join(s.split())


def _pattern_hits(text: str, pat: str) -> bool:
    """Whether the pattern occurs in the text as a WHOLE word (or phrase).

    On the left a boundary is always required. On the right: for a pattern ending in Cyrillic, up to
    three letters of Russian case inflection are allowed, so a name in its dictionary form still matches
    its inflected forms in the text; for Latin letters and digits an exact boundary is required — that
    is what separates "niacin" from "niacinamide", "b6" from "b60", "mk 7" from "mk 677"."""
    if not pat:
        return False
    tail = "[" + _CYR + "]{0,3}" if re.search("[" + _CYR + "]$", pat) else ""
    rx = r"(?<![" + _WORD + r"])" + re.escape(pat).replace(r"\ ", r"\s+") + tail + r"(?![" + _WORD + r"])"
    return re.search(rx, text) is not None


def classify_drug(name: str) -> List[str]:
    """Classes of a drug by its name (public dictionary). For checking a new prescription.

    The matching is word by word and not by substring occurrence: previously "Niacinamide" was
    determined to be niacin, and any name containing the word for a statin inside another word was
    determined to be a statin. The reverse direction (a short query → a long class name) is kept but
    narrowed: only for a single-word query at least three characters long and only as a PREFIX of a
    word in the pattern, so that a three-letter query for iodine still finds a brand name starting with it."""
    n = _norm_drug(name)
    if not n:
        return []
    single = n if " " not in n and len(n) >= 3 else None
    out = []
    for cls, spec in med_classes().get("classes", {}).items():
        pats = [_norm_drug(c) for c in spec.get("names", [])]
        hit = any(_pattern_hits(n, p) for p in pats)
        if not hit and single:
            hit = any(tok.startswith(single) for p in pats for tok in p.split())
        if hit:
            out.append(cls)
    return out


# ---- source folders selected by the user (profile/sources.json) ----------
_DOMAIN_FILE = {"labs": "labs.json", "medications": "medications.json", "metrics": "metrics.json"}


def source_config() -> Dict[str, str]:
    """User folders for the data domains (labs/medications/metrics/genome/…) and for
    personal external sources set under a name of the user's own choosing (see
    store.set_source_folder). Both live in profile/sources.json, under "folders" and
    "external_sources" respectively, and are merged here — the split between the two
    only matters when a folder is being SET, never when one is being read back.
    Empty = the data lies in the profile by default. Personal (in profile/sources.json)."""
    p = profile_dir() / "sources.json"
    if p.exists():
        try:
            cfg = _read_json(p)
            return {**(cfg.get("external_sources") or {}), **(cfg.get("folders") or {})}
        except Exception:
            return {}
    return {}


def source_path(domain: str) -> Path:
    """Data file of a domain: <selected folder>/<file> if a folder is set, otherwise profile/<file>."""
    fname = _DOMAIN_FILE.get(domain)
    if not fname:
        return profile_dir()
    folder = source_config().get(domain)
    if folder:
        return Path(folder).expanduser() / fname
    return profile_dir() / fname


def medication_names() -> List[str]:
    """Names of the prescriptions from the STRUCTURED source profile/medications.json (in lower case).

    Only real prescriptions — NOT the prose of medications.md (drug names occur there inside
    explanations, and the patient does not take those). This is a clean personal source of prescriptions.
    """
    return [m.get("name", "").strip().lower()
            for m in medications_json().get("medications", []) if m.get("name")]


def active_med_classes() -> List[str]:
    """Therapeutic classes among the patient's prescriptions (by the structured list + the dictionary)."""
    names = medication_names()
    out = []
    for cls, spec in med_classes().get("classes", {}).items():
        cnames = [n.lower() for n in spec.get("names", [])]
        if any(any(cn in mn or mn in cn for cn in cnames) for mn in names):
            out.append(cls)
    return out


# ---- profile -------------------------------------------------------------
def star_alleles_tsv() -> Dict[str, Any]:
    """`profile/pgx_star_alleles.tsv` → {gene: {diplotype, phenotype, cnv}}.

    This file is written by `src/ingest/pgx_star_alleles.sh` (PyPGx over a BAM:
    pileup, CNV model, 1KGP phasing) and, until now, was read by nothing. Star
    alleles for eighteen genes were computed and sat on disk while the engine
    answered from tag SNPs, because the only path into the engine was a hand
    edit of `pharmacogenomics.json` that nothing told the person to make.

    A row whose diplotype is `ERROR` or empty is skipped rather than carried: the
    pipeline writes that when a gene failed, and a failure is not a call.
    """
    p = profile_dir() / "pgx_star_alleles.tsv"
    if not p.is_file():
        return {}
    out: Dict[str, Any] = {}
    try:
        import csv as _csv
        with p.open(encoding="utf-8") as fh:
            for row in _csv.DictReader(fh, delimiter="\t"):
                gene = (row.get("gene") or "").strip().upper()
                dip = (row.get("diplotype") or "").strip()
                if not gene or not dip or dip.upper() == "ERROR":
                    continue
                out[gene] = {"diplotype": dip,
                             "phenotype": (row.get("phenotype") or "").strip(),
                             "cnv": (row.get("cnv") or "").strip() or None,
                             "source": "pgx_star_alleles.tsv"}
    except (OSError, ValueError):
        return {}
    return out


def pharmacogenomics() -> Dict[str, Any]:
    """The pharmacogenomic profile, with the star-allele TSV merged in.

    `pharmacogenomics.json` wins wherever it has a gene: it is what a person or
    another tool wrote deliberately. The TSV fills the rest, so an artefact the
    ingest layer produced reaches the reasoning layer without anyone having to
    know it exists. The two were connected by the filesystem and by convention,
    and the convention was checked nowhere — which is the single architectural
    cause the audit found behind four separate defects.
    """
    data = read_profile_json(profile_dir() / "pharmacogenomics.json")
    from_tsv = star_alleles_tsv()
    if not from_tsv:
        return data
    merged = dict(data or {})
    known = dict(merged.get("star_alleles") or {})
    for gene, call in from_tsv.items():
        known.setdefault(gene, call)
    merged["star_alleles"] = known
    return merged


def labs() -> Dict[str, Any]:
    p = source_path("labs")
    return read_profile_json(p) if p.exists() else {"markers": {}}


def marker_catalog() -> List[Dict[str, Any]]:
    """Catalogue of the profile markers: key, name, unit, reference corridor.

    It lives here and not in the server: the CLI (`markers`) uses the same list,
    and duplicating it in two places is a sure way to get two different answers to
    one question. The corridor is taken from the user's lab form; the absence of
    bounds is a normal state, not an error (such a marker will carry no flag).
    """
    from .i18n import lang as _lang
    known = lab_markers().get("markers", {})
    out = []
    for k, m in labs().get("markers", {}).items():
        spec = known.get(k) or {}
        # The dictionary's label wins over the name stored in the profile: the
        # stored one was captured off a form years ago, in that form's language and
        # that lab's casing, and it does not change when the output language does.
        # The profile's own name survives for a marker the dictionary has never
        # heard of — one somebody added by hand, which has no other label.
        name = marker_display(spec, _lang()) or m.get("name", k)
        out.append({"key": k, "name": name, "unit": m.get("unit", ""),
                    "canonical_unit": spec.get("unit", ""),
                    "unit_label": unit_label(spec.get("unit", "")) if spec.get("unit") else "",
                    "ref_low": m.get("ref_low"), "ref_high": m.get("ref_high")})
    out.sort(key=lambda x: x["name"])
    return out


def resolve_marker(query: str) -> Dict[str, Any]:
    """A marker key from whatever a person typed, or the near misses.

    Returns `{"key": …}` on a single confident match, otherwise
    `{"key": None, "candidates": [{key, name}, …]}`.

    Matching goes exact key → exact label or name in ANY language → substring, and
    the «any language» is the point: somebody may know the marker as `glucose` or
    as «глюкоза», and which one they type has nothing to do with the language they
    have asked the output to be in.

    What this exists to prevent is not the typo but what used to follow it.
    `add-lab glocose …` created a marker called `glocose` with an empty history,
    and from then on one analyte had two series under two spellings — visible to
    nobody, because each looks perfectly ordinary on its own.
    """
    q = (query or "").strip().casefold()
    if not q:
        return {"key": None, "candidates": []}
    markers = lab_markers().get("markers", {})
    if query in markers:
        return {"key": query}
    if q in markers:
        return {"key": q}

    exact, partial = [], []
    for key, spec in markers.items():
        labels = spec.get("labels") or {}
        shown = [b.get("display", "") for b in labels.values() if isinstance(b, dict)]
        names = marker_rules(spec, "names")
        if any(s.casefold() == q for s in shown if s) or any(n.casefold() == q for n in names):
            exact.append(key)
        elif any(q in s.casefold() for s in shown if s) or any(q in n for n in names):
            partial.append(key)

    if len(exact) == 1:
        return {"key": exact[0]}
    hits = exact or partial
    if len(hits) == 1:
        return {"key": hits[0]}
    from .i18n import lang as _lang
    lang = _lang()
    if not hits:
        # Nothing contains the query: it is a misspelling rather than a vague
        # request. A refusal with no suggestion is the point at which a person
        # reaches for `--new`, and `--new` on a typo is exactly the second series
        # this gate exists to prevent — so the near misses are worth computing.
        import difflib
        pool: Dict[str, str] = {}
        for key, spec in markers.items():
            pool[key] = key
            for block in (spec.get("labels") or {}).values():
                if isinstance(block, dict) and block.get("display"):
                    pool[block["display"].casefold()] = key
                for n in (block or {}).get("names") or []:
                    pool[n] = key
        near = difflib.get_close_matches(q, list(pool), n=12, cutoff=0.75)
        seen: List[str] = []
        for n in near:
            if pool[n] not in seen:
                seen.append(pool[n])
        hits = seen[:5]
    return {"key": None,
            "candidates": [{"key": k, "name": marker_display(markers[k], lang, k)}
                           for k in sorted(hits)[:8]]}


def medications_json() -> Dict[str, Any]:
    """Editable list of prescriptions (medications.json). Added to through the UI."""
    p = source_path("medications")
    return read_profile_json(p) if p.exists() else {"medications": []}


def profile_ancestry() -> Optional[str]:
    """The reference superpopulation the person stated, or None.

    None is the important value: it means a percentile printed for them was
    computed against a default, and the report has to say so rather than let the
    number stand as if the question had been asked.
    """
    v = (metrics_json().get("profile") or {}).get("ancestry")
    return v if v in ("EUR", "AFR", "EAS", "SAS", "AMR") else None


def profile_sex() -> Optional[str]:
    """The person's sex as 'male'/'female', or None if not set or unrecognised.

    Lives in metrics.json → profile.sex. Read here, once, because the reference
    intervals for a dozen markers differ by sex (haemoglobin, ferritin, creatinine,
    testosterone…) and applying the male range to a woman prints false anaemia and
    false-normal testosterone. An unrecognised value is None, not a guess: a
    silent default to one sex is exactly the failure this exists to prevent.
    """
    raw = str((metrics_json().get("profile") or {}).get("sex") or "").strip().lower()
    if raw in ("m", "male", "man", "муж", "мужской", "м"):
        return "male"
    if raw in ("f", "female", "woman", "жен", "женский", "ж"):
        return "female"
    return None


def metrics_json() -> Dict[str, Any]:
    """Personal health metrics (metrics.json): sleep, weight, height, mobility and so on.
    Added to through the UI. Personal. The structure is time series, as in labs.json."""
    p = source_path("metrics")
    return read_profile_json(p) if p.exists() else {"profile": {}, "metrics": {}}


def medications_text() -> str:
    """Text of the prescriptions (medications.md + medications.json). For drug triggers."""
    md = _read_text(profile_dir() / "medications.md").lower()
    js = " ".join(f"{m.get('name', '')} {m.get('note', '')}"
                  for m in medications_json().get("medications", [])).lower()
    return f"{md} {js}"


def _any_locus_called(rsids: List[str]) -> bool:
    """Was at least one of this gene's positions actually read?

    The condition used to be "the VCF file exists and the coordinates are in the
    catalogue" — which is a statement about two files, not about the person. With
    a VCF connected, every target gene left the gap list whether or not a single
    one of its positions had been called, and the report then said the gene was
    covered.

    `assumed_ref` does not count: it means there is no row at the position, which
    is either the reference or no coverage, and the file cannot tell them apart.
    """
    for rs in rsids:
        st = genotype_status(rs)
        if st and st.get("genotype") and st.get("confidence") != "assumed_ref":
            return True
    return False


def _genotyped_for(gene: str) -> bool:
    """Does the profile carry a genotype at any of this gene's model positions?

    The mapping rsID → gene lives in the pharmacogenetic catalogue, so a writer
    does not have to repeat it: requiring the gene name beside every genotype is
    a second source of truth for something the base already knows.
    """
    model = {m.get("rsid") for m in
             (((cpic_kb().get("genes") or {}).get(gene) or {}).get("markers") or [])
             if m.get("rsid")}
    if not model:
        return False
    for g in pharmacogenomics().get("genotypes", []) or []:
        if g.get("rsid") in model and g.get("genotype"):
            return True
    return False


def genome_gaps() -> List[str]:
    """Target genes not yet covered by the patient's data.

    Depersonalised: the list of targets is in the shared database (track2_targets). Covered
    or not is by the patient's data: first the Evogen profile, then the personal full VCF
    (if connected). A gene stops being a gap as soon as its loci become available in the VCF.
    """
    from . import genome  # lazy import (genome imports core)
    vcf_ready = genome.available()["ready"]
    gene_loci = {}
    for _rs, l in genome.loci().get("loci", {}).items():
        gene_loci.setdefault(l.get("gene", "").upper(), []).append(_rs)

    targets = cpic_kb().get("track2_targets", {})
    gaps = []
    for gene, meta in targets.items():
        if meta.get("needs_full_diplotype"):
            gaps.append(gene)                       # e.g. CYP2D6 — PyPGx is needed even with a VCF
        elif markers_for_gene(gene) or _genotyped_for(gene):
            # «Already in the report» OR «the profile carries a genotype at one of
            # this gene's model positions». The second half was missing, and it
            # cost a whole class of test its independence: an entry in
            # `genotypes` that does not repeat the gene NAME was invisible here,
            # even though the catalogue already knows which gene each rsID
            # belongs to. On the author's machine the gene was covered by his own
            # VCF, so the omission never showed; with the genome pointed at an
            # empty fixture — that is, on anybody else's machine — a gene with
            # explicit genotypes in the profile came back «not covered».
            continue
        elif vcf_ready and _any_locus_called(gene_loci.get(gene.upper()) or []):
            continue                                # closed by an actual reading at its positions
        else:
            gaps.append(gene)
    return gaps


def markers_for_gene(gene: str) -> List[Dict[str, str]]:
    """Markers found in the patient for a gene — from profile/pharmacogenomics.json (deduplicated by rsid)."""
    out, seen = [], set()
    for g in pharmacogenomics().get("genotypes", []):
        if g.get("gene", "").upper() != gene.upper():
            continue
        key = (g.get("rsid", ""), g.get("genotype", ""))
        if key in seen:
            continue
        seen.add(key)
        out.append({"rsid": g.get("rsid", ""), "genotype": g.get("genotype", ""),
                    "interpretation": g.get("interpretation", ""), "drug": g.get("drug", "")})
    return out


def genotype_status(rsid: str) -> Optional[Dict[str, Any]]:
    """The genotype at an rsID TOGETHER with how it is known.

    The companion this module was missing. `genotype_at` returns the string and
    drops everything that says what the string is worth — and one of the values
    it drops is `assumed_ref`, which does not mean "reference" but "there is no
    row at this position: either the reference, or nothing was read there".

    That distinction is the whole of the strongest failure the audit found. With
    a VCF connected and the DPYD positions never called, the string came back
    "CC", counted as zero variant copies, and a possible carrier of `*2A` was
    told the drug looked normal — while the same person WITHOUT a genome was told
    the status was unknown and the test was required. Connecting more data made
    the answer less cautious.

    `source` is `profile` for a genotype typed in from a laboratory report,
    `vcf` for one resolved from the person's own file.

    WHICH SOURCE WINS, and why it is not the one that used to (task 64). This
    function returned the profile entry the moment it found one and never reached
    the VCF. So `rs4988235`, `rs1801133` and `rs429358` came back as
    `reported/profile/depth=None` — copied off a laboratory's summary sheet —
    while the person's own aligned reads sat unread in a file on the same disk.
    `scholion genome rs4988235` meanwhile read the VCF and answered «reference
    confirmed by a call (0/0), coverage 32». Two routes to one fact, disagreeing.

    A read outranks a report: it carries a depth, it can be re-examined, and it
    is the thing the report was made from. But only a GENUINE read does. A
    missing row in a -mv VCF comes back as `assumed_ref`, which does not mean
    reference — it means «either the reference, or nothing was looked at there» —
    and letting that overrule a laboratory's positive finding would be the
    project's oldest defect wearing new clothes: more data producing a less
    cautious answer.

    A disagreement is never resolved silently. Both values travel in `conflict`,
    so the layer above can say that the report and the reads do not agree rather
    than quietly print one of them.

    Why this was not caught by the seventeen known disagreements between the
    Evogen report and the reads: `genotype_status` answered `None` for all of
    them — those rsIDs are not in the catalogue, so the priority was never
    exercised where it is dangerous. The absence of an error there proved nothing,
    and the test below builds the collision by hand rather than waiting for one.
    """
    reported = None
    for g in pharmacogenomics().get("genotypes", []):
        if g.get("rsid", "").lower() == rsid.lower():
            reported = {"genotype": g.get("genotype", ""), "confidence": "reported",
                        "source": "profile"}
            break

    from . import genome  # lazy import
    try:
        called = genome.genotype_from_vcf(rsid)
    except Exception:                                        # noqa: BLE001
        called = None

    if reported is None:
        return called
    # A row that was never read cannot overrule a laboratory that did read it.
    if not called or not called.get("genotype") or called.get("confidence") != "called":
        return reported

    if _same_genotype(called.get("genotype"), reported.get("genotype")):
        # Agreement is worth saying: two independent routes to the same call is a
        # stronger statement than either of them alone.
        return {**called, "confirmed_by": "profile",
                "also_reported": reported.get("genotype")}
    return {**called, "conflict": {"reported": reported.get("genotype"),
                                   "called": called.get("genotype"),
                                   "resolved_to": "called"}}


def _same_genotype(a: Optional[str], b: Optional[str]) -> bool:
    """Two genotype strings for the same call, phase and separators aside.

    «A/G», «AG» and «GA» are one genotype written three ways; a comparison that
    treated them as three would report a disagreement on every second marker and
    train the reader to ignore the flag.
    """
    def norm(x):
        x = (x or "").replace("|", "").replace("/", "").strip().upper()
        return "".join(sorted(x))
    return bool(norm(a)) and norm(a) == norm(b)


def genotype_at(rsid: str) -> Optional[str]:
    """The genotype as a bare string. Kept for the published contract.

    Prefer `genotype_status`: a caller that decides anything must see the
    confidence, and this function cannot show it.
    """
    st = genotype_status(rsid)
    return st.get("genotype") if st else None


def reset_cache() -> None:
    """Reset the file-reading cache (after a write from the UI/the ingest).
    Readers are now invalidated by mtime automatically — this is a forced reset just in case."""
    _JSON_CACHE.clear()
    _KB_CACHE.clear()
