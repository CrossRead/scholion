#!/usr/bin/env python3
"""Garmin Connect (GDPR export) → yearly trends for the "Lifestyle" section.

The main lifestyle source (replaces Apple Health). Distils a decade of daily
Garmin data into compact yearly averages + workouts by type.

Input: the garmin_export folder (or its DI_CONNECT). Output: profile/wearable_trends.json.
PERSONAL data (the values) go to profile/ (locally); the script itself is impersonal.

    python3 ingest_garmin.py <garmin_export_dir> <out_wearable_trends.json>
"""
from __future__ import annotations
import datetime as _dt
import calendar
import glob, json, os, sys
from collections import defaultdict
from datetime import datetime, timezone


def _month_of(cal):
    """calendarDate 'YYYY-MM-DD' → 'YYYY-MM' (monthly aggregation)."""
    if isinstance(cal, str) and len(cal) >= 7 and cal[:4].isdigit() and cal[5:7].isdigit():
        return cal[:7]
    return None


def _mean(xs):
    xs = [x for x in xs if isinstance(x, (int, float))]
    return round(sum(xs) / len(xs), 1) if xs else None


def _monthly(daily: dict):
    """{'YYYY-MM': [values]} → {'YYYY-MM': mean} (monthly averages)."""
    return {y: _mean(v) for y, v in sorted(daily.items()) if _mean(v) is not None}


def _days_in(month: str) -> int:
    y, m = int(month[:4]), int(month[5:7])
    return calendar.monthrange(y, m)[1]


def _stats(xs, month):
    """What a monthly point is worth: how many days it stands on, and how far apart they were.

    A month is one number in the series, and one number cannot say whether it is a
    measurement or an average of noise. Measured on twelve months of this project's
    own data: for deep sleep the spread WITHIN a month is about 20.6 min while the
    spread BETWEEN monthly means over a year is 4.05 — against 3.90 expected from
    sampling alone. That is 92% of the visible movement of the monthly series being
    the sample, not the sleeper.

    None of that can be recovered later: the daily values exist only here, at the
    moment they are folded into a mean. So the fold keeps its own arithmetic —
    `n` (days that carried a reading), `days` (days the month had), the `median`
    beside the mean, and `sd` — and everything downstream that wants to say
    «this moved» can find out what «moved» is worth.
    """
    xs = sorted(x for x in xs if isinstance(x, (int, float)))
    n = len(xs)
    if not n:
        return None
    mid = xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2
    mean = sum(xs) / n
    # The sample standard deviation. With one day there is no spread to speak of,
    # and 0.0 would read as «perfectly steady» rather than «nothing to compare».
    sd = None
    if n > 1:
        sd = (sum((x - mean) ** 2 for x in xs) / (n - 1)) ** 0.5
    out = {"n": n, "days": _days_in(month), "median": round(mid, 1)}
    if sd is not None:
        out["sd"] = round(sd, 2)
    return out


def _monthly_stats(daily: dict):
    """The same months as `_monthly`, each with what its number stands on."""
    out = {}
    for y, v in sorted(daily.items()):
        st = _stats(v, y)
        if st is not None and _mean(v) is not None:
            out[y] = st
    return out


# grouping of Garmin activity types → human-readable labels
def _wlabel(t: str) -> str:
    t = (t or "").lower()
    for needle, label in (
        # the owner logs HIIT/high-intensity in Garmin as strength — folded into strength
        ("strength", "Strength training"), ("hiit", "Strength training"),
        ("high_intensity", "Strength training"),
        ("run", "Running"), ("swim", "Swimming"),
        ("cycl", "Cycling"), ("bik", "Cycling"), ("walk", "Walking"),
        ("hik", "Hiking"), ("tennis", "Tennis"), ("ski", "Skiing/snowboarding"),
        ("snowboard", "Skiing/snowboarding"), ("yoga", "Yoga"), ("pilates", "Pilates"),
        ("cardio", "Cardio"), ("elliptical", "Elliptical"),
        ("row", "Rowing"), ("golf", "Golf"), ("pickle", "Pickleball"),
    ):
        if needle in t:
            return label
    return "Other"


def build(gdir: str) -> dict:
    C = os.path.join(gdir, "DI_CONNECT")
    if not os.path.isdir(C):
        # in case DI_CONNECT itself was passed
        C = gdir if os.path.isdir(os.path.join(gdir, "DI-Connect-Aggregator")) else C
    W = os.path.join(C, "DI-Connect-Wellness")
    A = os.path.join(C, "DI-Connect-Aggregator")
    M = os.path.join(C, "DI-Connect-Metrics")
    F = os.path.join(C, "DI-Connect-Fitness")

    rhr = defaultdict(list); steps = defaultdict(list); intens = defaultdict(list)
    stress = defaultdict(list); bbhigh = defaultdict(list); bblow = defaultdict(list)
    resp = defaultdict(list); cals = defaultdict(list)

    # --- daily summaries (UDSFile) ---
    for f in glob.glob(os.path.join(A, "UDSFile_*.json")):
        try:
            recs = json.load(open(f))
        except Exception:
            continue
        for r in recs if isinstance(recs, list) else []:
            y = _month_of(r.get("calendarDate"))
            if not y:
                continue
            if r.get("restingHeartRate"):
                rhr[y].append(r["restingHeartRate"])
            if isinstance(r.get("totalSteps"), (int, float)):
                steps[y].append(r["totalSteps"])
            im = (r.get("moderateIntensityMinutes") or 0) + (r.get("vigorousIntensityMinutes") or 0)
            if im:
                intens[y].append(im)
            if isinstance(r.get("totalKilocalories"), (int, float)):
                cals[y].append(r["totalKilocalories"])
            ads = r.get("allDayStress") or {}
            for agg in (ads.get("aggregatorList") or []):
                if agg.get("type") == "TOTAL" and isinstance(agg.get("averageStressLevel"), (int, float)) and agg["averageStressLevel"] >= 0:
                    stress[y].append(agg["averageStressLevel"])
            bb = r.get("bodyBattery") or {}
            for s in (bb.get("bodyBatteryStatList") or []):
                if s.get("bodyBatteryStatType") == "HIGHEST" and isinstance(s.get("statsValue"), (int, float)):
                    bbhigh[y].append(s["statsValue"])
                if s.get("bodyBatteryStatType") == "LOWEST" and isinstance(s.get("statsValue"), (int, float)):
                    bblow[y].append(s["statsValue"])
            rr = r.get("respiration") or {}
            if isinstance(rr.get("avgWakingRespirationValue"), (int, float)) and rr["avgWakingRespirationValue"] > 0:
                resp[y].append(rr["avgWakingRespirationValue"])

    # --- HRV (healthStatusData, ~2025+) ---
    hrv = defaultdict(list)
    for f in glob.glob(os.path.join(W, "*healthStatusData.json")):
        try:
            recs = json.load(open(f))
        except Exception:
            continue
        for r in recs if isinstance(recs, list) else []:
            y = _month_of(r.get("calendarDate"))
            for m in (r.get("metrics") or []):
                if m.get("type") == "HRV" and isinstance(m.get("value"), (int, float)) and y:
                    hrv[y].append(m["value"])

    # --- VO2Max: Garmin changed the format. Older years — ActivityVo2Max_*,
    # from ~2021 — MetricsMaxMetData_* (vo2MaxValue out of MaxMET there). BOTH are read. ---
    vo2 = defaultdict(list)
    vo2_files = (glob.glob(os.path.join(M, "*Vo2Max*.json"))
                 + glob.glob(os.path.join(M, "*MaxMetData*.json")))
    for f in vo2_files:
        try:
            recs = json.load(open(f))
        except Exception:
            continue
        for r in recs if isinstance(recs, list) else []:
            y = _month_of(r.get("calendarDate"))
            v = r.get("vo2MaxValue")
            if y and isinstance(v, (int, float)) and v > 0:
                vo2[y].append(v)

    # --- sleep (sleepData): duration + PHASES + quality ----------------------
    # Phases before 2022 are not comparable: the older device labelled an implausibly
    # large share of the night as "deep sleep". The per-night file is written whole; the
    # monthly phase metrics take only records starting from PHASES_FROM.
    PHASES_FROM = "2022-01-01"
    sleep = defaultdict(list)
    deep = defaultdict(list); rem = defaultdict(list)
    slstress = defaultdict(list); slscore = defaultdict(list); bedt = defaultdict(list)
    nightly = []
    for f in glob.glob(os.path.join(W, "*sleepData.json")):
        try:
            recs = json.load(open(f))
        except Exception:
            continue
        for r in recs if isinstance(recs, list) else []:
            if not isinstance(r, dict):
                continue
            cal = r.get("calendarDate")
            y = _month_of(cal)
            d_ = r.get("deepSleepSeconds") or 0
            l_ = r.get("lightSleepSeconds") or 0
            m_ = r.get("remSleepSeconds") or 0
            secs = d_ + l_ + m_
            if not (y and secs > 0):
                continue
            sleep[y].append(secs / 3600.0)
            # falling-asleep time in minutes from 20:00 local (MSK = GMT+3)
            bed = None
            ts = (r.get("sleepStartTimestampGMT") or "").split(".")[0]
            try:
                s = _dt.datetime.fromisoformat(ts) + _dt.timedelta(hours=3)
                bed = ((s.hour - 20) % 24) * 60 + s.minute
            except Exception:
                bed = None
            sc = (r.get("sleepScores") or {}).get("overallScore")
            nightly.append({
                "date": cal, "deep_min": round(d_ / 60, 1), "light_min": round(l_ / 60, 1),
                "rem_min": round(m_ / 60, 1), "awake_min": round((r.get("awakeSleepSeconds") or 0) / 60, 1),
                "total_min": round(secs / 60, 1), "bedtime_min_from_20": bed,
                "sleep_stress": r.get("avgSleepStress"), "score": sc,
                "awake_count": r.get("awakeCount"), "restless": r.get("restlessMomentCount"),
                "respiration": r.get("averageRespiration"), "naps": len(r.get("napList") or []),
                "confirm": r.get("sleepWindowConfirmationType"),
            })
            if cal and cal >= PHASES_FROM:
                deep[y].append(d_ / 60.0)
                rem[y].append(m_ / 60.0)
                if isinstance(r.get("avgSleepStress"), (int, float)):
                    slstress[y].append(float(r["avgSleepStress"]))
                if isinstance(sc, (int, float)):
                    slscore[y].append(float(sc))
                if bed is not None:
                    bedt[y].append(float(bed))
    nightly.sort(key=lambda x: x["date"] or "")

    # --- body composition (Garmin Index smart scales): weight, BMI, fat, water, muscle ---
    weight = defaultdict(list); bmi = defaultdict(list); bfat = defaultdict(list)
    bwater = defaultdict(list); muscle = defaultdict(list)
    for f in glob.glob(os.path.join(W, "*userBioMetrics.json")):
        try:
            recs = json.load(open(f))
        except Exception:
            continue
        for r in recs if isinstance(recs, list) else []:
            y = _month_of((r.get("metaData") or {}).get("calendarDate"))
            w = r.get("weight") if isinstance(r.get("weight"), dict) else {}
            if not y:
                continue
            wv = w.get("weight")
            if isinstance(wv, (int, float)) and wv > 0:
                weight[y].append(wv / 1000.0)               # grams → kg
            for key, dst in (("bmi", bmi), ("bodyFat", bfat), ("bodyWater", bwater)):
                v = w.get(key)
                if isinstance(v, (int, float)) and v > 0:
                    dst[y].append(v)
            mm = w.get("muscleMass")
            if isinstance(mm, (int, float)) and mm > 0:
                muscle[y].append(mm / 1000.0)               # grams → kg

    # --- workouts (summarizedActivities) ---
    workouts = defaultdict(lambda: defaultdict(lambda: {"count": 0, "hours": 0.0}))
    for f in glob.glob(os.path.join(F, "*summarizedActivities.json")):
        try:
            d = json.load(open(f))
        except Exception:
            continue
        acts = []
        if isinstance(d, list):
            for el in d:
                if isinstance(el, dict) and isinstance(el.get("summarizedActivitiesExport"), list):
                    acts += el["summarizedActivitiesExport"]
                elif isinstance(el, dict) and el.get("activityType"):
                    acts.append(el)
        for a in acts:
            ts = a.get("beginTimestamp") or a.get("startTimeGmt")
            if not ts:
                continue
            y = str(datetime.fromtimestamp(ts / 1000.0, tz=timezone.utc).year)
            lbl = _wlabel(a.get("activityType") or a.get("sportType"))
            workouts[y][lbl]["count"] += 1
            dur = a.get("duration")
            if isinstance(dur, (int, float)):
                workouts[y][lbl]["hours"] += dur / 3600000.0  # ms → h

    wout = {y: {lbl: {"count": v["count"], "hours": round(v["hours"], 1)}
                for lbl, v in sorted(t.items())}
            for y, t in sorted(workouts.items())}

    #: The daily lists each metric was folded from, kept beside the fold so the
    #: same names can produce the same months twice — once as a number, once as
    #: what that number stands on. Typing the pairs twice is how the two lists
    #: drift apart, so they are named once and used twice.
    _sources = {
        "Weight": weight, "BMI": bmi, "BodyFat": bfat, "MuscleMass": muscle,
        "BodyWater": bwater, "RestingHeartRate": rhr, "HRV": hrv, "Stress": stress,
        "BodyBatteryHigh": bbhigh, "BodyBatteryLow": bblow, "Respiration": resp,
        "VO2Max": vo2, "StepsDaily": steps, "IntensityMinutesDaily": intens,
        "SleepHours": sleep, "DeepSleepMin": deep, "RemSleepMin": rem,
        "SleepStress": slstress, "SleepScore": slscore, "Bedtime": bedt,
        "CaloriesDaily": cals,
    }
    metrics = {
        "Weight": _monthly(weight),
        "BMI": _monthly(bmi),
        "BodyFat": _monthly(bfat),
        "MuscleMass": _monthly(muscle),
        "BodyWater": _monthly(bwater),
        "RestingHeartRate": _monthly(rhr),
        "HRV": _monthly(hrv),
        "Stress": _monthly(stress),
        "BodyBatteryHigh": _monthly(bbhigh),
        "BodyBatteryLow": _monthly(bblow),
        "Respiration": _monthly(resp),
        "VO2Max": _monthly(vo2),
        "StepsDaily": {y: int(v) for y, v in _monthly(steps).items()},
        "IntensityMinutesDaily": _monthly(intens),
        "SleepHours": _monthly(sleep),
        "DeepSleepMin": _monthly(deep),
        "RemSleepMin": _monthly(rem),
        "SleepStress": _monthly(slstress),
        "SleepScore": _monthly(slscore),
        "Bedtime": _monthly(bedt),
        "CaloriesDaily": {y: int(v) for y, v in _monthly(cals).items()},
    }
    years = sorted({y[:4] for d in (rhr, steps, stress, sleep, vo2, hrv, workouts) for y in d})
    return {
        "_meta": {
            "source": "Garmin Connect (GDPR export)",
            "primary": True,
            "granularity": "monthly",
            "replaced": "Apple Health (the primary source earlier)",
            "range": f"{years[0]}–{years[-1]}" if years else "—",
            "units": {"RestingHeartRate": "bpm", "HRV": "ms (rMSSD, baseline 23–49)",
                      "Stress": "0–100 (Garmin)", "BodyBattery": "0–100",
                      "Respiration": "breaths/min (at rest)", "VO2Max": "ml/kg/min",
                      "SleepHours": "h/night", "DeepSleepMin": "min/night", "RemSleepMin": "min/night",
                      "SleepStress": "0–100 (Garmin, during sleep)", "SleepScore": "0–100",
                      "Bedtime": "min from 20:00 local", "IntensityMinutesDaily": "min/day (moderate+vigorous)"},
            "note": ("MONTHLY averages from the Garmin daily summaries (key YYYY-MM). The trends are "
                     "smoothed with a 3-month moving average in the engine. Stress, Body Battery, "
                     "respiration and HRV are recovery/autonomic signals. Workouts are yearly totals "
                     "by type."),
        },
        "metrics": {k: v for k, v in metrics.items() if v},
        # Beside the series, never inside it: the value of a point stays a number,
        # so every reader that already knows how to draw this series still does.
        "stats": {k: st for k, st in ((k, _monthly_stats(src))
                                      for k, src in _sources.items()) if st and metrics.get(k)},
        "workouts": wout,
        "nightly_sleep": nightly,
    }


def main():
    gdir = sys.argv[1] if len(sys.argv) > 1 else "."
    out = sys.argv[2] if len(sys.argv) > 2 else "wearable_trends.json"
    data = build(gdir)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    m = data["_meta"]
    print(f"✓ {out}")
    print(f"  range: {m['range']}; metrics: {len(data['metrics'])}; years of workouts: {len(data['workouts'])}")
    for k, v in data["metrics"].items():
        yrs = sorted(v)
        print(f"  {k}: {yrs[0]}..{yrs[-1]}  last={v[yrs[-1]]}")


if __name__ == "__main__":
    main()
