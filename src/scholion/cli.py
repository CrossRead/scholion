"""The CLI entry point: one entry for the Claude skill (scripts) and for manual checks.

Examples:
  python -m scholion drug clopidogrel
  python -m scholion labs
  python -m scholion suggest-tests
  python -m scholion profile
  # JSON output for machine processing:
  python -m scholion drug statins --json
"""
from __future__ import annotations
import argparse
import json
import os
import sys
from pathlib import Path

from . import core as _core
from . import core, engine, format as fmt
from . import i18n as _i18n
from .i18n import t as _t


def build_parser() -> argparse.ArgumentParser:
    """The parser is pulled out of main() into a separate function so that the parity test
    can ask it for the list of commands instead of parsing the source with regexes."""
    # the shared --json flag works both before and after the subcommand (via a parent parser)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true", help="print raw JSON instead of markdown")
    # The output language. The flag is on EVERY command rather than one global flag: a global
    # one would have to be placed before the subcommand, while the habit is to write flags after it.
    common.add_argument("--lang", choices=_i18n.available(),
                        help=f"output language (default {_i18n.DEFAULT}; "
                             f"also the SCHOLION_LANG variable)")

    # prog is taken from whatever the command was called by: through the wrapper it is
    # `crossread`, through the module — `python3 -m scholion`. Otherwise the help teaches
    # a command the person has not been using.
    import os as _os
    _prog = _os.path.basename(_os.environ.get("SCHOLION_PROG") or sys.argv[0] or "scholion")
    if _prog in ("__main__.py", "-m", "", "cli.py"):
        _prog = "python3 -m scholion"
    p = argparse.ArgumentParser(prog=_prog,
                                description="Assistant: genome + labs + prescriptions (put --json after the subcommand)")
    from . import __version__ as _ver
    p.add_argument("--version", action="version", version=f"scholion {_ver}")
    # NOT required. With `required=True` a bare `scholion` answers with a usage
    # dump of all forty-four commands and the line «error: the following arguments
    # are required: cmd» — to somebody who has just installed it and typed the
    # name to see what happens, that is an error message and a wall of names.
    # It is the first thing a curious person types.
    sub = p.add_subparsers(dest="cmd")

    # The initial set-up. It stands first for a reason: it is the only command needed
    # by a person who does not yet have a single file of their own.
    ini = sub.add_parser("init", parents=[common],
                         help="create the data directory and lay out the profile templates")
    ini.add_argument("--demo", action="store_true",
                     help="lay out a synthetic demo profile instead of empty templates")
    ini.add_argument("--force", action="store_true",
                     help="overwrite files that already exist")
    ini.add_argument("--dir", help="profile directory (the user's one by default)")
    ini.add_argument("--sex", choices=["male", "female"], default=None,
                     help="record the sex now: six reference intervals depend on it")
    ini.add_argument("--birth-year", type=int, default=None, help="record the year of birth now")
    # The external tools are asked about at the end of `init` and nowhere else.
    # There is no post-install hook in a wheel — pip runs no code of ours after
    # unpacking — so «ask at install time» has to mean «ask at first run», and
    # `init` is the first run by definition.
    ini.add_argument("--yes", "-y", action="store_true",
                     help="answer yes to the question about external tools (install them)")
    ini.add_argument("--no-tools", action="store_true",
                     help="do not ask about external tools at all")

    dm = sub.add_parser("demo", parents=[common],
                        help="build a synthetic demo profile (a fictional person)")
    dm.add_argument("--out", help="profile directory (<data>/demo/profile by default)")
    dm.add_argument("--force", action="store_true",
                    help="write even if the directory holds unmarked data")

    # The instruction for an external model. The command is needed precisely because after
    # `pip install` the file lies inside site-packages: naming that path to a person is
    # impossible, while the model needs it in full.
    sk = sub.add_parser("skill", parents=[common],
                        help="the instruction for an external model — the short entry by default, --full for all of it")
    sk.add_argument("--path", action="store_true", help="print only the path to the file")
    sk.add_argument("--full", action="store_true",
                    help="the FULL instruction (INSTRUCTION.md) instead of the short entry")
    sk.add_argument("--rules", action="store_true",
                    help="the canon of the assistant's rules instead of the instruction (ASSISTANT-RULES.md)")

    # The same reason `skill` exists. A `pip install` gets `src/scholion` and
    # nothing else, while the output sends the reader to README nine times, to
    # PREPARING-THE-GENOME four and to DATA-LAYOUT twice — files that are not on
    # a PyPI user's disk, in a repository that is not open yet. `limits` was
    # advising people to read something they had no way to reach.
    dc = sub.add_parser("doc", parents=[common],
                        help="print a document the output refers to (no argument — the list)")
    dc.add_argument("name", nargs="?", help="which document; omit to list them")
    dc.add_argument("--path", action="store_true", help="print only the path to the file")

    d = sub.add_parser("drug", parents=[common], help="check a drug against the pharmacogenetics")
    d.add_argument("name", help="the name of the drug (Russian/English)")

    l = sub.add_parser("labs", parents=[common], help="lab analysis: flags + trends")
    l.add_argument("markers", nargs="*", help="marker keys (all of them by default)")

    sub.add_parser("suggest-tests", parents=[common], help="which tests it makes sense to take")
    prf = sub.add_parser("profile", parents=[common],
                         help="a snapshot of the profile (what is loaded); also sets sex "
                              "and year of birth, which several reference intervals need")
    prf.add_argument("--sex", choices=["male", "female"], default=None,
                     help="six markers keep a sex-specific interval; without this the "
                          "corridor is not shown rather than guessed")
    prf.add_argument("--birth-year", type=int, default=None,
                     help="year of birth — age-banded rows on a lab form need it")
    # The choices come from the build, not from this line: a list typed here goes
    # stale the day a third reader is added, and then the command refuses a device
    # the application can read. `none` is a real answer — «I do not wear one» — and
    # not the same state as never having been asked.
    from . import core as _core
    from .wearables import KINDS as _KINDS
    prf.add_argument("--wearable", choices=[k["source"] for k in _KINDS] + [_core.NO_WEARABLE],
                     default=None,
                     help="which device answers where two of them measured the same thing; "
                          "without it such a metric is shown from both and enters no "
                          f"conclusion. `{_core.NO_WEARABLE}` records that there is no "
                          "wearable, so nothing asks again")
    prf.add_argument("--height-cm", type=float, default=None,
                     help="height in centimetres — the body-mass index is computed from it, "
                          "and without it nothing that needs a height is shown. The page has "
                          "always had this field; the command had not.")
    prf.add_argument("--ancestry", choices=list(_core.ANCESTRIES), default=None,
                     help="the reference superpopulation for polygenic scores; without it a "
                          "percentile is printed with the caveat that it was computed against "
                          "a population that may not be yours")

    g = sub.add_parser("genome", parents=[common], help="look a locus up in the full VCF (rsID or --gene)")
    g.add_argument("rsid", nargs="?", help="rsID (e.g. rs4149056)")
    g.add_argument("--gene", help="look for all the loci of a gene")

    rx = sub.add_parser("prescription", parents=[common],
                        help="a second opinion on a NEW prescription: PGx + interactions + monitoring")
    rx.add_argument("name", help="the name of the drug (Russian/English)")

    sub.add_parser("metrics", parents=[common], help="personal health metrics (sleep/weight/BMI/trends)")
    sub.add_parser("focus", parents=[common],
                   help="the focus of attention: the current task, the live metric, the levers, the journal")
    sub.add_parser("brief", parents=[common],
                   help="the lifestyle brief: live numbers + curated wordings")
    sub.add_parser("lifestyle", parents=[common], help="lifestyle (wearables): monthly trends + body composition")
    sub.add_parser("goal", parents=[common], help="your goal for the metrics, on live data")
    _gs = sub.add_parser("goal-suggest", parents=[common],
                         help="propose a goal from your own series and the published guidelines")
    _gs.add_argument("--write", action="store_true",
                     help="write the proposals into profile/health_goals.json (nothing is "
                          "written without this)")
    sub.add_parser("clinvar", parents=[common], help="clinically significant findings (ClinVar × VCF)")
    sub.add_parser("acmg", parents=[common], help="ACMG SF v3.3 secondary findings (the actionable minimum)")
    sub.add_parser("prs", parents=[common], help="polygenic risks (PGS): percentiles by trait")
    sub.add_parser("longevity", parents=[common], help="the longevity layer (LongevityMap): APOE ε + markers")
    sub.add_parser("lipid-genetics", parents=[common],
                   help="the inherited side of the lipid profile: PCSK9 carriage + Lp(a)")

    ig = sub.add_parser("ingest-labs", parents=[common], help="extract markers from the PDFs in a folder → labs.json")
    ig.add_argument("folder", help="the folder with the laboratory PDFs")
    ig.add_argument("--force", action="store_true", help="reprocess every file (ignore the manifest)")

    ist = sub.add_parser("ingest-studies", parents=[common],
                         help="extract doctors' CONCLUSIONS and instrumental studies "
                              "(ECG/ultrasound/MRI/consultations) from the PDFs in a folder → studies.json")
    ist.add_argument("folder", nargs="?", help="the folder with the PDFs (the studies folder by default)")
    ist.add_argument("--force", action="store_true", help="re-read every file")

    igw = sub.add_parser("ingest-wearable", parents=[common],
                         help="rebuild the lifestyle layer from a wearable export — Garmin or "
                              "WHOOP, recognised by what is inside it (with a backup)")
    igw.add_argument("folder", nargs="?",
                     help="the export folder or zip (looked for in raw/wearables/ by default)")
    igw.add_argument("--device", choices=["garmin", "whoop"], default=None,
                     help="read it only if it is this device; without it the file itself decides")

    igg = sub.add_parser("ingest-garmin", parents=[common],
                         help="rebuild the lifestyle layer from a Garmin export → profile/wearable_trends.json (with a backup)")
    igg.add_argument("folder", nargs="?", help="the garmin_export folder (found automatically next to the project by default)")

    rc = sub.add_parser("reconcile", parents=[common],
                        help="a completeness audit: check every PDF form against labs.json (gaps/discrepancies/unreadable)")
    rc.add_argument("--lab-dir", help="the folder with the forms (../Лабораторные исследования or SCHOLION_LABS_DIR by default)")
    rc.add_argument("--ocr", action="store_true", help="OCR for scans with no text layer (needs pdftoppm+tesseract)")

    sc = sub.add_parser("selfcheck", parents=[common],
                        help="a quick self-check of the labs' integrity (a banner: unreadable/gaps) — runs at start-up")
    sc.add_argument("--lab-dir", help="the folder with the forms (../Лабораторные исследования or SCHOLION_LABS_DIR by default)")

    pa = sub.add_parser("phenoage", parents=[common],
                        help="biological age (PhenoAge, Levine 2018) — STRICTLY from a single panel")
    pa.add_argument("panel", nargs="?", default="latest",
                    help="the panel's month YYYY-MM or latest (latest by default)")
    pa.add_argument("--panels", action="store_true", help="an overview of every panel and its completeness")
    pa.add_argument("--track", action="store_true",
                    help="append the result to profile/biological_age_history.md (a complete panel only)")

    pv = sub.add_parser("provenance", parents=[common],
                        help="the REVERSE check: every point of the profile → its source form (catches typos and wrong indices)")
    pv.add_argument("--refresh", action="store_true", help="rebuild the provenance (run reconcile) before the check")
    pv.add_argument("--marker", help="check a single marker only")
    pv.add_argument("--lab-dir", help="the folder with the forms (for --refresh)")

    sub.add_parser("capabilities", parents=[common],
                   help="what this build can do — every command, what it does, "
                        "whether it writes, and which entry points carry it")
    sub.add_parser("flag-rate", parents=[common],
                   help="on what share of objects each flag fired — the cheap check this "
                        "project asks for before any interpretation")
    sub.add_parser("array", parents=[common],
                   help="a consumer genotyping array: which catalogue loci it carries, "
                        "which failed to call, and which it does not carry at all")
    mkp = sub.add_parser("marker", parents=[common],
                         help="locally added marker entries: list, propose, confirm, drop. "
                              "A proposal describes what a row is CALLED — never a value")
    mkp.add_argument("--propose", metavar="KEY", default="",
                     help="canonical key for a new entry")
    mkp.add_argument("--names", default="",
                     help="printed names that recognise the row, separated by «;»")
    mkp.add_argument("--names-en", default="", help="the same in English, if the form is English")
    mkp.add_argument("--unit", default="", help="the unit as printed on the form")
    mkp.add_argument("--direction", default="", choices=["", "higher_better", "lower_better"])
    mkp.add_argument("--loinc", default="", help="LOINC code, if one is known")
    mkp.add_argument("--confirm", metavar="KEY", default="",
                     help="vouch for an entry — from here it may flag")
    mkp.add_argument("--drop", metavar="KEY", default="", help="remove a local entry")
    mkp.add_argument("--propose-unit", nargs=2, metavar=("MARKER", "UNIT"), default=None,
                     help="propose that a printed unit form belongs to a marker; add "
                          "--factor or --refuse-reason")
    mkp.add_argument("--factor", type=float, default=None,
                     help="conversion factor to the canonical unit — NOT applied until confirmed")
    mkp.add_argument("--refuse-reason", default="",
                     help="propose instead that this form cannot be converted at all")
    mkp.add_argument("--propose-row-rule", metavar="PATTERN", default="",
                     help="propose a rule for a multi-line reference block")
    mkp.add_argument("--rule-kind", choices=["alien", "label"], default="alien")
    mkp.add_argument("--example", default="",
                     help="the SHAPE of the row that produced the pattern (required)")
    ldp = sub.add_parser("lab-draw", parents=[common],
                         help="explain a day that holds two draws: why the repeat, and what "
                              "happened between them")
    ldp.add_argument("--day", required=True, help="the day, YYYY-MM-DD")
    ldp.add_argument("--reason", default="", help="why the test was repeated that day")
    ldp.add_argument("--between", default="", help="what happened between the two draws — "
                                                   "a procedure, a dose, a load")
    ldp.add_argument("--marker", default="", help="apply to one marker only (default: all "
                                                  "markers measured twice that day)")
    srcp = sub.add_parser("sources", parents=[common],
                          help="the external reference sources this build mirrors, "
                               "when each was last imported, and what has to be done by hand")
    srcp.add_argument("--refresh", action="store_true",
                      help="import the sources that can be automated (reaches the network)")
    srcp.add_argument("--only", default="", help="refresh one source by id (e.g. cpic)")
    asi = sub.add_parser("assistant", parents=[common],
                         help="what the application does by itself, what the assistant adds and how to connect it")
    asi.add_argument("--context", action="store_true",
                     help="build the text to paste into ANY model (contains personal data)")
    asi.add_argument("--out", help="save the context to a file instead of printing it")

    # --- parity with the web interface: what used to be available only in the tabs ----
    # No new computations appear here: these are entry points to the same engine functions
    # that the web calls. The project's rule — a capability lands in the engine, the CLI and
    # the web at the same time; a divergence is caught by tests/test_parity.py.
    sub.add_parser("overview", parents=[common],
                   help="the main screen summary: red flags, gaps, counters")
    sub.add_parser("second-opinion", parents=[common],
                   help="a second look before a visit: deviations + the PGx watchlist + what to take")
    sub.add_parser("radar", parents=[common],
                   help="the health index by body system (0–100) and how it moves")
    sub.add_parser("medications", parents=[common], help="the current treatment scheme (a list)")
    sub.add_parser("genome-status", parents=[common],
                   help="the state of the genome base: is the VCF connected, is there an index, gaps")
    sub.add_parser("genome-updates", parents=[common],
                   help="what the latest check against a fresh ClinVar has brought")
    sub.add_parser("limits", parents=[common],
                   help="what cannot be said from this data, why, and what would close it")
    sub.add_parser("markers", parents=[common],
                   help="the catalogue of the profile's markers: key, name, units, reference range")

    al = sub.add_parser("add-lab", parents=[common], help="add a marker point to the profile")
    al.add_argument("marker", help="the marker key (see markers)")
    al.add_argument("date", help="the date of the point: YYYY-MM or YYYY-MM-DD")
    al.add_argument("value", type=float)
    al.add_argument("--name")
    # Required for a marker that is not yet in the profile: a number whose unit is
    # unknown cannot be compared with a threshold, and the thresholds do not name
    # their unit. An unrecognised unit is refused with the list of accepted ones.
    al.add_argument("--unit", help="the unit of the value — required for a new marker; "
                                   "a non-canonical unit is converted (e.g. mg/dL → mmol/L)")
    al.add_argument("--ref-low", type=float); al.add_argument("--ref-high", type=float)
    al.add_argument("--direction", help="higher_worse | lower_worse (if it is known)")
    al.add_argument("--new", action="store_true",
                    help="create a marker the dictionary does not know (a unit is required). "
                         "Without this flag an unrecognised name is refused with suggestions, "
                         "so that a typo cannot open a second series of the same test")

    red = sub.add_parser("redact", parents=[common],
                         help="strip your identifiers out of text before you publish it")
    red.add_argument("path", nargs="?", default="-",
                     help="a file, or - to read standard input")
    red.add_argument("--write", default="",
                     help="write the cleaned text to this file instead of printing it")

    imp = sub.add_parser("import-labs", parents=[common],
                         help="import a panel of results from a CSV/TSV file")
    imp.add_argument("path", help="the file: columns marker,date,value,unit[,ref_low,ref_high,note]. "
                                  "A filled-in example ships as templates/panel-template.csv")
    imp.add_argument("--dry-run", action="store_true",
                     help="check and report, write nothing")

    sub.add_parser("mcp", parents=[common],
                   help="speak the Model Context Protocol over stdin/stdout, so a model can "
                        "call the same tools the plugin registers")

    fhi = sub.add_parser("import-fhir", parents=[common],
                         help="import laboratory results from a FHIR R4 Bundle (a portal export, "
                              "Apple Health clinical records, an EHR download)")
    fhi.add_argument("path", help="the bundle: a .json file whose resourceType is Bundle")
    fhi.add_argument("--dry-run", action="store_true",
                     help="say what it would take and write nothing")

    amt = sub.add_parser("add-metric", parents=[common],
                         help="add a point of a personal metric (weight, sleep, blood pressure…)")
    amt.add_argument("metric", help="the metric key")
    amt.add_argument("date", help="YYYY-MM or YYYY-MM-DD")
    amt.add_argument("value", type=float)
    amt.add_argument("--name"); amt.add_argument("--unit")

    am = sub.add_parser("add-med", parents=[common], help="add a drug to the scheme")
    am.add_argument("name"); am.add_argument("--dose", default=""); am.add_argument("--note", default="")

    rm = sub.add_parser("remove-med", parents=[common], help="remove a drug from the scheme")
    rm.add_argument("name")

    fl = sub.add_parser("focus-log", parents=[common],
                        help="mark an episode for the focus of attention (alcohol, a drug, a late dinner)")
    fl.add_argument("date", help="YYYY-MM-DD")
    fl.add_argument("--alcohol", default=""); fl.add_argument("--atenolol", action="store_true")
    fl.add_argument("--late-meal", action="store_true"); fl.add_argument("--note", default="")

    sf = sub.add_parser("set-folder", parents=[common],
                        help="point at a source folder for the data (in the web — the native macOS dialog)")
    sf.add_argument("domain", help="labs_docs | garmin | apple_health | … "
                                   "(or any name of your own for a personal source)")
    sf.add_argument("path")

    tl = sub.add_parser("tools", parents=[common],
                        help="external command-line tools: what is missing and how to install it")
    tl.add_argument("--install", action="store_true",
                    help="install what is missing (the flag IS the confirmation)")
    tl.add_argument("--set", dest="set_", default="base",
                    help="which set --install acts on: base (default), all, or a name from the report")
    tl.add_argument("--manager", choices=("brew", "mamba", "conda", "pip"),
                    help="force a package manager instead of choosing one")

    s = sub.add_parser("serve", help="start the local web interface")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=1521)
    return p


def _hint_if_empty(cmd) -> None:
    """The new user's first minute: there is no data yet.

    An empty profile is not an error, so the command runs as usual while the hint goes
    to stderr: it spoils neither the JSON nor the text report, but it answers the
    question «and what now». Without it the installed package silently shows zeros, and
    the person concludes that the application is broken.
    """
    # `skill` does not read the profile at all: it prints a file that lies inside the package.
    # A hint about an empty profile next to it is misleading — the person decides that the
    # instruction has to be filled with something too.
    # `tools` says nothing about a profile either: it reports on the machine.
    if cmd in ("init", "demo", "skill", "tools"):
        return
    try:
        d = core.profile_dir()
        if any(d.glob("*.json")):
            return
    except OSError:
        return
    print(_t("init.empty_profile", path=d), _t("init.empty_hint_files"),
          _t("init.empty_hint_demo"), sep="\n", file=sys.stderr)


def _can_ask() -> bool:
    """Whether there is somebody who can answer, not merely a terminal.

    `isatty()` answers the wrong question for automation. A Makefile, a
    provisioning script, a CI job with a pseudo-terminal allocated — all of them
    have a terminal and none of them has a person, and a command that stops to
    ask in one of those hangs a pipeline with no output to explain why. Both
    signals are the conventional ones: `CI` is set by every hosted runner, and
    `SCHOLION_NONINTERACTIVE` is for everyone else. The answers can still be
    given outright with `--sex` and `--birth-year`, which is what a script should
    do when it knows them.
    """
    if os.environ.get("SCHOLION_NONINTERACTIVE") or os.environ.get("CI"):
        return False
    try:
        return bool(sys.stdin) and sys.stdin.isatty()
    except (ValueError, AttributeError):     # a closed or replaced stream
        return False


def main(argv=None) -> int:
    """The command line, with one class of failure caught before it reaches a person.

    A profile file written by a newer build cannot be read by this one, and the
    refusal is deliberate (`core.ProfileFromTheFuture`). What must not happen is
    that the refusal arrives as a Python traceback: the first thing somebody sees
    about their own medical history should not look like a crash. The message
    already says which file, which two versions, and what to do — it only needed
    somewhere to be printed instead of raised.
    """
    try:
        return _main(argv)
    except _core.ProfileFromTheFuture as e:
        print(f"⚠️  {e}", file=sys.stderr)
        return 3


def _main(argv=None) -> int:
    # `scholion skill | head` is a natural command, and its output runs to nearly a hundred
    # kilobytes. Without this, head closes the pipe and the person gets a BrokenPipeError
    # traceback instead of text: it looks like a breakage even though everything worked.
    # SIG_DFL gives the same behaviour as ordinary command-line utilities.
    try:
        import signal as _sig
        _sig.signal(_sig.SIGPIPE, _sig.SIG_DFL)
    except (ImportError, AttributeError, ValueError):
        pass                      # Windows and a non-main thread: there is no SIGPIPE there

    p = build_parser()
    args = p.parse_args(argv)
    if not getattr(args, "cmd", None):
        # Three lines and a way in, not a catalogue. `--help` is one keystroke
        # away and lists everything; what a bare `scholion` owes the reader is a
        # first move.
        print(_t("cli.bare_hint"))
        return 0
    # An explicit flag beats the environment, the environment beats the default.
    if getattr(args, "lang", None):
        _i18n.set_lang(args.lang)
    _hint_if_empty(getattr(args, "cmd", None))

    if args.cmd == "init":
        from . import store as _st
        r = _st.init_profile(target=args.dir, force=args.force, demo=args.demo)
        if args.json:
            print(json.dumps(r, ensure_ascii=False, indent=2))
            return 0 if r.get("ok") else 1
        if not r.get("ok"):
            print(f"✗ {r.get('error')}", file=sys.stderr)
            return 1
        print(_t("init.dir_created", path=r['dir']))
        if r["written"]:
            print(_t("init.written", files=', '.join(r['written'])))
        if r["skipped"]:
            print(_t("init.skipped", files=', '.join(r['skipped'])))
        print()
        if r.get("mode") == "demo":
            print(_t("init.demo_notice"))
            print(_t("init.demo_next"))
        else:
            print(_t("init.next_steps"))
        # Setting the tool up includes knowing what reference data it carries and
        # how that data is refreshed. Printed for both modes and before the tool
        # check, because it is true of every install: the catalogues are mirrors
        # of sources that move, and a mirror without a named import path is the
        # defect this line exists to prevent. Nothing is fetched here — the line
        # names the command, the person runs it.
        # Sex and year of birth, at the one moment the person is already setting
        # the tool up. Task 72: without them six reference intervals fall back to
        # the male range and every age-banded row on a lab form is unreachable —
        # one unasked question is the precondition for a whole family of wrong
        # flags. Asked only for a real profile (the demo has its own person), only
        # when there is a terminal to answer from, and never blocking: a person
        # who presses Enter twice gets the same honest «not recorded» as before,
        # now with the command that fixes it.
        if r.get("mode") != "demo":
            from . import store as _st
            fields = {}
            if args.sex:
                fields["sex"] = args.sex
            if args.birth_year:
                fields["birth_year"] = args.birth_year
            if not fields and _can_ask():
                print()
                print(_t("init.why_sex_asked"))
                try:
                    a = input(_t("init.ask_sex")).strip().lower()
                    if a in ("m", "male", "м", "мужской"):
                        fields["sex"] = "male"
                    elif a in ("f", "female", "ж", "женский"):
                        fields["sex"] = "female"
                    b = input(_t("init.ask_birth_year")).strip()
                    if b.isdigit() and 1900 < int(b) <= 2026:
                        fields["birth_year"] = int(b)
                except (EOFError, KeyboardInterrupt):
                    fields = {}
            if fields:
                _st.update_metric_profile(fields)
                print(_t("profile.recorded",
                         fields=", ".join(f"{k} = {v}" for k, v in sorted(fields.items()))))
            else:
                print()
                print(_t("init.sex_not_recorded"))
        print()
        print(_t("sources.init_hint"))
        # Last, deliberately. Whatever happens with brew, the profile is already
        # created and the person has already been told what to do next: a failed
        # installation must not be able to make a successful init look failed.
        from . import tools as _tools
        # Not after a demo. The demo needs none of these — it is synthetic data
        # already on disk — and four ✗ printed directly under «Have a look» read
        # as «installed halfway», which is the wrong thing to tell somebody in
        # the first thirty seconds. For a real profile the offer stays: there the
        # genome layer does not work without them, and the moment to say so is
        # before the person goes looking for a VCF.
        if r.get("mode") == "demo":
            print(_t("tools.see_later"))
        else:
            # One line before the four crosses. Without it the list reads as «this
            # is not installed yet», which is false for everything most people
            # arrive with — lab PDFs, a prescription list, a consumer-array file.
            # These four are the genome track alone.
            print(_t("tools.only_for_genome"))
            _tools.offer_after_init(assume_yes=args.yes, skip=args.no_tools)
        return 0

    if args.cmd == "tools":
        from . import tools as _tools
        st = _tools.status(args.manager)
        if not args.install:
            if args.json:
                print(json.dumps(st, ensure_ascii=False, indent=2))
                return 0
            print(_tools.report(st), end="")
            return 0
        names = _tools.set_names(st) if args.set_ == "all" else [args.set_]
        unknown = [x for x in names if x not in _tools.set_names(st)]
        if unknown:
            print(f"✗ unknown set: {', '.join(unknown)} "
                  f"(available: {', '.join(_tools.set_names(st))})", file=sys.stderr)
            return 2
        missing = _tools.tools_of(names, st)
        if not missing:
            if args.json:
                print(json.dumps({"ok": True, "installed": [], "still_missing": [],
                                  "sets": names, "message": _t("tools.all_present")},
                                 ensure_ascii=False, indent=2))
            else:
                print(_t("tools.all_present"))
            return 0
        # --install is the answer to the question, so confirm=True here is not a
        # rubber stamp: the person typed the flag. Everywhere else the flag is
        # absent and tools.install refuses.
        r = _tools.install(missing, st["manager"], confirm=True)
        if args.json:
            print(json.dumps(r, ensure_ascii=False, indent=2))
            return 0 if r.get("ok") else 1
        if r.get("message"):
            print(r["message"], file=sys.stderr)
        if r.get("installed"):
            print(_t("tools.installed_ok", tools=", ".join(r["installed"])))
        if r.get("still_missing"):
            print(_t("tools.install_failed", tools=", ".join(r["still_missing"])), file=sys.stderr)
        return 0 if r.get("ok") else 1

    if args.cmd == "demo":
        from . import demo as _demo
        argv2 = []
        if args.out:
            argv2 += ["--out", args.out]
        if args.force:
            argv2 += ["--force"]
        # --json must give a parseable object for EVERY command: the assistant picks a
        # command from the list, not by which of them happens to be «the textual one».
        if args.json:
            argv2 += ["--quiet"]
        code = _demo.main(argv2)
        if args.json:
            out = Path(args.out).expanduser().resolve() if args.out else _demo._default_out()
            files = sorted(f.name for f in out.glob("*") if f.is_file()) if code == 0 else []
            print(json.dumps({"ok": code == 0, "dir": str(out), "seed": _demo.SEED,
                              "written": files, "synthetic": True},
                             ensure_ascii=False, indent=2))
        return code

    if args.cmd == "doc":
        from . import docs as _docs
        if not args.name:
            avail = _docs.available()
            if args.json:
                print(json.dumps({"documents": [{"name": k, "bytes": b} for k, b in avail]},
                                 ensure_ascii=False, indent=2))
                return 0
            print(_t("doc.list_header"))
            for k, b in avail:
                print(f"  {k:24} {b // 1024} KB")
            print()
            print(_t("doc.list_hint"))
            return 0
        path = _docs.path_of(args.name)
        if path is None:
            print(_t("doc.unknown", name=args.name,
                     known=", ".join(k for k, _ in _docs.available())), file=sys.stderr)
            return 1
        text = path.read_text(encoding="utf-8")
        if args.json:
            print(json.dumps({"name": args.name, "path": str(path),
                              "bytes": len(text.encode()),
                              "text": None if args.path else text},
                             ensure_ascii=False, indent=2))
            return 0
        print(str(path) if args.path else text, end="" if not args.path else "\n")
        return 0

    if args.cmd == "skill":
        # SKILL.md is the entry a model loads first; INSTRUCTION.md is the long text.
        # Printing seventy kilobytes at somebody who typed `scholion skill` to see what
        # this is was the old behaviour, and it was the wrong default.
        name = ("ASSISTANT-RULES.md" if args.rules
                else "INSTRUCTION.md" if args.full else "SKILL.md")
        path = Path(__file__).resolve().parent / "skill" / name
        if not path.exists():
            # The build is incomplete. Staying silent is not an option: a command that
            # prints emptiness here reads as «the project has no instruction».
            print(_t("skill.file_missing", path=path), file=sys.stderr)
            return 1
        text = path.read_text(encoding="utf-8")
        if args.json:
            print(json.dumps({"file": name, "path": str(path), "bytes": len(text.encode()),
                              "text": None if args.path else text},
                             ensure_ascii=False, indent=2))
            return 0
        print(str(path) if args.path else text)
        return 0

    if args.cmd == "serve":
        from .server import serve
        serve(args.host, args.port)
        return 0

    if args.cmd == "assistant":
        from . import assistant as _as
        if args.context:
            txt = _as.context_bundle()
            if args.out:
                Path(args.out).expanduser().write_text(txt, encoding="utf-8")
                print(_t("assistant.context_saved", path=args.out, chars=len(txt)))
                print(_t("assistant.context_personal"))
                return 0
            print(txt)
            return 0
        res, render = _as.status(), _as.format_status
    elif args.cmd == "overview":
        res, render = engine.overview(), fmt.overview_report
    elif args.cmd == "second-opinion":
        res, render = engine.second_opinion(), fmt.second_opinion_report
    elif args.cmd == "radar":
        res, render = engine.health_radar(), fmt.radar_report
    elif args.cmd == "medications":
        from . import store as _st
        res, render = {"medications": _st.list_medications()}, fmt.medications_report
    elif args.cmd == "genome-status":
        res = {**engine.genome_status(), "gaps": core.genome_gaps()}
        render = fmt.genome_status_report
    elif args.cmd == "genome-updates":
        res, render = engine.genome_updates(), fmt.genome_updates_report
    elif args.cmd == "limits":
        from . import limits as _lim
        res, render = _lim.report(), fmt.limits_report
    elif args.cmd == "markers":
        res, render = {"markers": core.marker_catalog()}, fmt.markers_report
    elif args.cmd == "add-lab":
        from . import store as _st
        res = _st.add_lab_point(args.marker, args.date, args.value, name=args.name, new=args.new,
                                unit=args.unit, ref_low=args.ref_low, ref_high=args.ref_high,
                                direction=args.direction, date_source="manual",
                                subject="owner")
        render = fmt.write_result
    elif args.cmd == "redact":
        from . import redact as _red
        res, render = _red.run(args.path, write=args.write), fmt.redact_report
    elif args.cmd == "import-labs":
        from . import import_csv as _imp
        res, render = _imp.run(args.path, dry_run=args.dry_run), fmt.import_report
    elif args.cmd == "mcp":
        # A protocol dialogue, not a report: it owns stdout for its whole run, so
        # it returns straight from here rather than going through the renderer.
        from . import mcp_server as _mcp
        raise SystemExit(_mcp.serve())
    elif args.cmd == "import-fhir":
        from . import ingest_fhir as _fhir
        res, render = _fhir.ingest(args.path, dry_run=args.dry_run), fmt.fhir_report
    elif args.cmd == "add-metric":
        from . import store as _st
        res = _st.add_metric_point(args.metric, args.date, args.value,
                                   name=args.name, unit=args.unit, subject="owner")
        render = fmt.write_result
    elif args.cmd == "add-med":
        from . import store as _st
        res, render = (_st.add_medication(args.name, args.dose, args.note, subject="owner"),
                       fmt.write_result)
    elif args.cmd == "remove-med":
        from . import store as _st
        res, render = _st.remove_medication(args.name), fmt.write_result
    elif args.cmd == "focus-log":
        from . import store as _st
        res = _st.add_focus_entry(args.date, alcohol=args.alcohol, atenolol=args.atenolol,
                                  late_meal=args.late_meal, note=args.note)
        render = fmt.write_result
    elif args.cmd == "set-folder":
        from . import store as _st
        res, render = _st.set_source_folder(args.domain, args.path), fmt.write_result
    elif args.cmd == "drug":
        res, render = engine.check_drug_gene(args.name), fmt.drug_check
    elif args.cmd == "labs":
        res, render = engine.analyze_labs(args.markers or None), fmt.labs_report
    elif args.cmd == "suggest-tests":
        res, render = engine.suggest_tests(), fmt.tests_report
    elif args.cmd == "genome":
        res, render = engine.genome_lookup(rsid=args.rsid, gene=args.gene), fmt.genome_report
    elif args.cmd == "prescription":
        res, render = engine.check_new_prescription(args.name), fmt.prescription_check
    elif args.cmd == "metrics":
        res, render = engine.metrics_summary(), fmt.metrics_report
    elif args.cmd == "focus":
        res, render = engine.focus_dashboard(), fmt.render_focus
    elif args.cmd == "brief":
        res, render = engine.lifestyle_brief(), fmt.render_brief
    elif args.cmd == "lifestyle":
        res, render = engine.lifestyle(), fmt.lifestyle_report
    elif args.cmd == "goal":
        res, render = engine.goal_dashboard(), fmt.goal_report
    elif args.cmd == "goal-suggest":
        res = engine.suggest_goal_targets()
        if args.write:
            from . import store as _st
            res = {**res, "written": _st.write_goal_targets(res["proposals"])}
        render = fmt.goal_suggest_report
    elif args.cmd == "clinvar":
        res, render = engine.clinvar_findings(), fmt.clinvar_report
    elif args.cmd == "acmg":
        res, render = engine.acmg_findings(), fmt.acmg_report
    elif args.cmd == "prs":
        res, render = engine.prs_findings(), fmt.prs_report
    elif args.cmd == "longevity":
        res, render = engine.longevity_findings(), fmt.longevity_report
    elif args.cmd == "capabilities":
        from . import contract as _c
        res, render = _c.capabilities(), fmt.capabilities_report
    elif args.cmd == "flag-rate":
        from . import prevalence as _pv
        res, render = _pv.report(), fmt.prevalence_report
    elif args.cmd == "array":
        from . import array_genome as _arr
        res, render = _arr.catalogue_coverage(), fmt.array_report
    elif args.cmd == "marker":
        from . import markers_local as _ml
        if args.propose_unit:
            res = _ml.propose_unit(args.propose_unit[0], args.propose_unit[1],
                                   factor=args.factor, refuse_reason=args.refuse_reason,
                                   by="person")
        elif args.propose_row_rule:
            res = _ml.propose_row_rule(args.propose_row_rule, kind=args.rule_kind,
                                       example=args.example, by="person")
        elif args.propose:
            res = _ml.propose(args.propose, unit=args.unit,
                              names_ru=[x for x in args.names.split(";") if x.strip()],
                              names_en=[x for x in args.names_en.split(";") if x.strip()],
                              direction=args.direction, loinc=args.loinc, by="person")
        elif args.confirm:
            res = _ml.confirm(args.confirm)
        elif args.drop:
            res = _ml.drop(args.drop)
        else:
            res = _ml.listing()
        render = fmt.markers_local_report
    elif args.cmd == "lab-draw":
        from . import store as _st
        res = _st.set_draw_context(args.day, args.reason, args.between,
                                   marker=args.marker or None)
        render = fmt.draw_context_report
    elif args.cmd == "sources":
        from . import sources as _src
        results = []
        if getattr(args, "refresh", False):
            try:
                ids = [args.only] if getattr(args, "only", "") else list(_src.SOURCES)
                results = [_src.refresh(i) for i in ids]
            except _src.SourceUnavailable as e:
                results = [{"source": args.only or "all", "skipped": True, "reason": str(e)}]
            except KeyError:
                results = [{"source": args.only, "skipped": True,
                            "reason": f"no such source: {args.only}"}]
        res = {"sources": _src.state(), "results": results}
        render = fmt.sources_report
    elif args.cmd == "lipid-genetics":
        res, render = engine.lipid_genetics(), fmt.lipid_genetics_report
    elif args.cmd == "ingest-labs":
        from . import ingest_labs
        res = ingest_labs.ingest(args.folder, force=args.force)
        render = fmt.ingest_labs_report
    elif args.cmd == "ingest-studies":
        from . import ingest_studies
        folder = args.folder or core.source_config().get("labs_docs")
        if not folder:
            res, render = ({"ok": False, "error": _t("ingest.no_folder")},
                           lambda r: f"⚠️ {r['error']}")
        else:
            res = ingest_studies.ingest(folder, force=args.force)
            render = fmt.ingest_studies_report
    elif args.cmd == "ingest-wearable":
        from . import wearables as _wear
        res = _wear.reingest(args.folder, source=getattr(args, "device", None))
        render = fmt.wearable_ingest_report
    elif args.cmd == "ingest-garmin":
        from . import garmin
        res = garmin.reingest(args.folder)
        render = lambda r: (_t("ingest.garmin_done", metrics=r.get('metrics'),
                               range=r.get('range'), out=r.get('out'))
                            + (_t("ingest.garmin_backup", path=r.get('backup')) if r.get('backup') else "")
                            if r.get("ok") else f"⚠️ {r.get('error')}")
    elif args.cmd == "reconcile":
        from . import reconcile as _rec
        res, render = _rec.reconcile(args.lab_dir, ocr=args.ocr), fmt.reconcile_report
    elif args.cmd == "selfcheck":
        from . import reconcile as _rec
        res = _rec.reconcile(args.lab_dir)
        render = _rec.selfcheck_summary
    elif args.cmd == "phenoage":
        from . import phenoage as _pa
        if args.panels:
            res, render = _pa.panels_overview(), _pa.format_panels
        else:
            res = _pa.compute_panel(args.panel, track=args.track)
            render = _pa.format_result
    elif args.cmd == "provenance":
        from . import provenance as _pv
        res = _pv.audit(refresh=args.refresh, lab_dir=args.lab_dir, marker=args.marker)
        render = _pv.format_report
    elif args.cmd == "profile" and (getattr(args, "sex", None)
                                    or getattr(args, "birth_year", None)
                                    or getattr(args, "height_cm", None)
                                    or getattr(args, "wearable", None)
                                    or getattr(args, "ancestry", None)):
        from . import store as _st
        fields = {}
        if args.sex:
            fields["sex"] = args.sex
        if args.birth_year:
            fields["birth_year"] = args.birth_year
        if getattr(args, "height_cm", None):
            fields["height_cm"] = args.height_cm
        if getattr(args, "wearable", None):
            fields["wearable_primary"] = args.wearable
        if getattr(args, "ancestry", None):
            fields["ancestry"] = args.ancestry
        res = _st.update_metric_profile(fields)
        render = fmt.profile_set_report
    elif args.cmd == "profile":
        res, render = engine.load_profile(), lambda r: json.dumps(r, ensure_ascii=False, indent=2)
    else:
        p.print_help()
        return 2

    print(json.dumps(res, ensure_ascii=False, indent=2) if args.json else render(res))
    return 0


if __name__ == "__main__":
    sys.exit(main())
