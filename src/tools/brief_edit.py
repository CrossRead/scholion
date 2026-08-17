#!/usr/bin/env python3
"""Editing the texts of the "lifestyle brief" (profile/lifestyle_brief.json).

The texts are written by an assistant, but poking at the JSON by hand is not
allowed: it is easy to break the structure, to forget to update reviewed, or to type
a number straight into the text (it will go stale). This tool makes an edit in one
command and checks after itself.

    python3 src/tools/brief_edit.py --list
    python3 src/tools/brief_edit.py --show bone
    python3 src/tools/brief_edit.py --stale
    python3 src/tools/brief_edit.py --set bone --body-file /tmp/bone.md
    python3 src/tools/brief_edit.py --set bone --body-file /tmp/bone.md --title "New heading"
    python3 src/tools/brief_edit.py --touch bone          # only mark it as reviewed
    python3 src/tools/brief_edit.py --add --id newid --section diet --title "…" --body-file f
    python3 src/tools/brief_edit.py --action-add "text"   --action-del 3
    python3 src/tools/brief_edit.py --drop oldid

What it does by itself:
  · a backup before every write;
  · reviewed is set to today (or --reviewed YYYY-MM-DD);
  · TOKEN CHECK: [[lab:key]] and [[life:key]] are matched against the profile;
    unknown keys are an error, not a silent substitution of "[no marker]";
  · WARNING ABOUT NUMBERS: if the text holds a number with a unit of measurement
    where there is no token nearby, the tool says so — most likely the value was
    typed in by hand and will go stale.
"""
import argparse, datetime, json, os, re, shutil, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
P = Path(os.environ.get("SCHOLION_PROFILE_DIR", ROOT / "profile")) / "lifestyle_brief.json"
TOKEN = re.compile(r"\[\[(lab|life|goal):([^\]]+)\]\]")
# Percentages and fractions from prose ("14 % of sleep", "risk rose by 12 %") are
# legitimate text and are not in the list of suspicious units: otherwise the warning
# devalues itself. We catch only the units in which the tracked markers are measured.
# We do not treat the SECOND end of a range as suspicious ("59-71 bpm"): that
# describes the scale, not the current value. We catch only a lone number with a unit.
#
# Both spellings of every unit are listed, and the Russian ones stay for good. This
# is a recognition pattern, not printed text: the brief is written in whatever
# language the owner reads, so a brief composed in Russian must keep raising the
# warning. Dropping the Russian half would not translate the tool — it would switch
# the check off for every profile that already exists.
SUSPECT = re.compile(r"(?<!\[)(?<![\d–\-—]\s)(?<![\d–\-—])\b\d+[,.]?\d*\s?"
                     r"(ммоль/л|мкмоль/л|нг/мл|пг/мл|г/л|мкМЕ/мл|мл/кг/мин|уд/мин|ч/ночь|мин/ночь"
                     r"|mmol/L|µmol/L|umol/L|ng/mL|pg/mL|g/L|µIU/mL|uIU/mL"
                     r"|mL/kg/min|bpm|h/night|min/night)\b")


def load():
    return json.loads(P.read_text(encoding="utf-8"))


def save(d, why):
    b = ROOT / "_backups" / f"lifestyle_brief.json.{datetime.date.today():%Y%m%d}-{why}"
    b.parent.mkdir(exist_ok=True)
    shutil.copy(P, b)
    P.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"written; backup {b.name}")


def check(body):
    """Returns the list of problems with the text."""
    problems = []
    try:
        from scholion import core, engine                      # noqa: F401
        markers = set((core.labs().get("markers") or {}).keys())
        life = {m.get("key") for m in engine.lifestyle().get("metrics", [])}
    except Exception as e:                                           # noqa: BLE001
        problems.append(f"could not check the tokens ({e})")
        markers, life = None, None
    for kind, key in TOKEN.findall(body):
        if kind == "lab" and markers is not None and key not in markers:
            problems.append(f"no such marker in labs.json: [[lab:{key}]]")
        if kind == "life" and life is not None and key not in life:
            problems.append(f"no such lifestyle metric: [[life:{key}]]")
    for m in SUSPECT.finditer(body):
        problems.append(f"looks like a hand-typed number: \"{m.group(0)}\" — "
                        f"replace it with a token, or it will go stale")
    return problems


def main():
    a = argparse.ArgumentParser()
    a.add_argument("--list", action="store_true")
    a.add_argument("--stale", action="store_true", help="show the blocks that need reviewing")
    a.add_argument("--show")
    a.add_argument("--set")
    a.add_argument("--touch")
    a.add_argument("--drop")
    a.add_argument("--add", action="store_true")
    a.add_argument("--id"); a.add_argument("--section"); a.add_argument("--title")
    a.add_argument("--body-file"); a.add_argument("--weight", type=int)
    a.add_argument("--watch", help="marker keys, comma-separated")
    a.add_argument("--hint", help="what to review when new data arrives")
    a.add_argument("--reviewed")
    a.add_argument("--action-add"); a.add_argument("--action-del", type=int)
    a.add_argument("--force", action="store_true", help="write despite the warnings")
    n = a.parse_args()
    d = load()
    today = n.reviewed or datetime.date.today().isoformat()
    blocks = d["blocks"]
    by = {b["id"]: b for b in blocks}

    if n.list:
        for b in blocks:
            print(f"{b['id']:14s} [{b.get('section',''):8s}] w{b.get('weight',5):<2} "
                  f"reviewed {b.get('reviewed','—')}  {b.get('title','')[:60]}")
        return 0
    if n.stale:
        from scholion import engine
        r = engine.lifestyle_brief()
        if not r.get("needs_review"):
            print("everything is current")
            return 0
        for s in r["stale_blocks"]:
            print(f"⚠ {s['id'] if 'id' in s else ''} {s['title']}\n   text from {s['reviewed']}, "
                  f"data from {s['newest_data']}\n   {s.get('review_hint','')}")
        return 0
    if n.show:
        print(json.dumps(by[n.show], ensure_ascii=False, indent=1))
        return 0
    if n.drop:
        d["blocks"] = [b for b in blocks if b["id"] != n.drop]
        save(d, f"drop-{n.drop}")
        return 0
    if n.action_add or n.action_del is not None:
        if n.action_del is not None:
            removed = d["actions"].pop(n.action_del - 1)
            print("removed:", removed[:70])
        if n.action_add:
            p = check(n.action_add)
            for x in p:
                print("  ! ", x)
            if p and not n.force:
                return 2
            d["actions"].append(n.action_add)
        save(d, "actions")
        return 0

    body = Path(n.body_file).read_text(encoding="utf-8").strip() if n.body_file else None
    if body:
        problems = check(body)
        for x in problems:
            print("  ! ", x)
        if problems and not n.force:
            print("not written. Fix it, or run with --force if you are sure.")
            return 2
    if n.set:
        b = by[n.set]
        if body:
            b["body"] = body
        if n.title:
            b["title"] = n.title
        if n.weight is not None:
            b["weight"] = n.weight
        if n.watch:
            b["watch"] = [{"kind": "lab", "key": k.strip()} for k in n.watch.split(",") if k.strip()]
        if n.hint:
            b["review_hint"] = n.hint
        b["reviewed"] = today
        save(d, f"set-{n.set}")
        return 0
    if n.touch:
        by[n.touch]["reviewed"] = today
        save(d, f"touch-{n.touch}")
        return 0
    if n.add:
        blocks.append({"id": n.id, "section": n.section or "other", "title": n.title or "",
                       "body": body or "", "weight": n.weight or 5,
                       "watch": [{"kind": "lab", "key": k.strip()}
                                 for k in (n.watch or "").split(",") if k.strip()],
                       "reviewed": today, "review_hint": n.hint or ""})
        save(d, f"add-{n.id}")
        return 0
    a.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
