#!/usr/bin/env python3
"""Aggregator for the Apple Health / Garmin export → yearly/monthly trends.
Source: Garmin Fenix 8 → Garmin Connect → Health (+ iPhone steps).
Keeps no per-record data — only the aggregates needed for trends.
Usage: python3 parse_health_export.py <export.xml> [out.json]
"""
import sys, re, json
from collections import defaultdict
from datetime import datetime, timedelta

if len(sys.argv) < 2:
    sys.exit("Usage: python3 parse_health_export.py <export.xml> [out.json]")
SRC = sys.argv[1]; OUT = sys.argv[2] if len(sys.argv) > 2 else None
POINT  = ["RestingHeartRate","HeartRateVariabilitySDNN","WalkingHeartRateAverage","VO2Max","BodyMassIndex","BodyFatPercentage"]
WEIGHT = "BodyMass"; DAYSUM = ["StepCount","AppleExerciseTime"]

# The relevant lines are selected INSIDE the process, not through an external grep.
#
# This used to assemble a shell command string with the path substituted from argv and a
# temporary file from mktemp. Two defects in two lines: a quote in the file name closed
# the string and turned the rest of the path into a command, and a predictable name in
# the shared /tmp opened the way to a symlink swap. Both are removed by there being no
# external process and no temporary file at all any more: the export is read as a stream.
#
# One compiled regular expression per line instead of nine substring checks: the parsing
# happens on the C side, and on an export of millions of lines the difference is
# noticeable.
_WANTED = re.compile("|".join(
    [re.escape(f'HKQuantityTypeIdentifier{k}"') for k in POINT + [WEIGHT] + DAYSUM]
    + [re.escape("HKCategoryTypeIdentifierSleepAnalysis"), re.escape("<Workout ")]
))


def _records(path):
    """The export lines that are relevant. The file is not loaded into memory whole:
    a Health export spanning several years runs to gigabytes."""
    try:
        f = open(path, encoding="utf-8", errors="ignore")
    except OSError as e:
        sys.exit(f"Could not open the export: {e}")
    with f:
        for ln in f:
            if _WANTED.search(ln):
                yield ln

rT=re.compile(r'Identifier(\w+)"'); rV=re.compile(r'value="([\d.]+)"')
# The value of a sleep record is TEXT, not a number: HKCategoryValueSleepAnalysisAsleepCore
# and the like. The numeric expression rV never matches it, so the sleep branch silently
# never fired once: the sleep column always stayed empty, and that looked like "there is
# no data" rather than "the parsing is broken".
rCV=re.compile(r'value="(HKCategoryValueSleepAnalysis\w+)"')
rS=re.compile(r'startDate="([\d\- :]+)'); rE=re.compile(r'endDate="([\d\- :]+)')
rC=re.compile(r'sourceName="([^"]+)"'); rW=re.compile(r'workoutActivityType="HKWorkoutActivityType(\w+)"')
def pdt(s):
    try: return datetime.strptime(s[:19],"%Y-%m-%d %H:%M:%S")
    except: return None

pt=defaultdict(lambda:defaultdict(list)); wt=defaultdict(list)
day=defaultdict(lambda:defaultdict(dict)); slp=defaultdict(dict); wko=defaultdict(lambda:defaultdict(int))
for ln in _records(SRC):
    if "<Workout " in ln:
        m=rW.search(ln); sd=rS.search(ln)
        if m and sd: wko[m.group(1)][sd.group(1)[:4]]+=1
        continue
    if "SleepAnalysis" in ln:
        v=rCV.search(ln)
        # InBed is time in bed, Awake are the awakenings inside the night. Neither
        # is sleep; adding them to sleep would overstate the duration for someone
        # who lies awake for a long time before falling asleep.
        if not v or "Asleep" not in v.group(1): continue
        sd=rS.search(ln); ed=rE.search(ln); sc=rC.search(ln)
        a=pdt(sd.group(1)) if sd else None; b=pdt(ed.group(1)) if ed else None
        if not(a and b): continue
        h=(b-a).total_seconds()/3600
        # A segment, not a night: since 2022 recording is by phases, and one night is
        # dozens of segments a few minutes long. The upper bound is therefore on a SEGMENT,
        # while the plausibility of the night's total is checked below.
        if 0<h<=16:
            s=sc.group(1) if sc else "?"
            # A night is named after the date it BEGAN, not the date of the segment:
            # otherwise segments before midnight fall into one day and those after
            # midnight into the next, and one night counts as two short ones. A shift
            # of 12 hours assigns everything started from noon to noon to one night.
            n=(a-timedelta(hours=12)).date().isoformat()
            slp[n][s]=slp[n].get(s,0)+h
        continue
    t=rT.search(ln); v=rV.search(ln); sd=rS.search(ln)
    if not(t and v and sd): continue
    t=t.group(1); val=float(v.group(1)); yr=sd.group(1)[:4]; dt=sd.group(1)[:10]
    if t in POINT:
        if t=="BodyFatPercentage":
            if val<=0: continue
            val=val*100 if val<1 else val
        if t=="BodyMassIndex" and not(18<=val<=45): continue
        pt[t][yr].append(val)
    elif t==WEIGHT:
        if 80<=val<=130: wt[yr].append(val)   # artefact filter (other people's scales/people)
    elif t in DAYSUM:
        sc=rC.search(ln); s=sc.group(1) if sc else "?"
        day[t].setdefault(dt,{}); day[t][dt][s]=day[t][dt].get(s,0)+val

def ym(d): return {y:round(sum(v)/len(v),1) for y,v in sorted(d.items())}
res={t:ym(pt[t]) for t in POINT}
res["BodyMass"]=ym(wt)
for t in DAYSUM:
    yr=defaultdict(list)
    for dt,src in day[t].items(): yr[dt[:4]].append(max(src.values()))  # dedup: max source per day
    res[t]={y:round(sum(v)/len(v)) for y,v in sorted(yr.items())}
# One night can have several sources (the watch and the phone record the same thing).
# The largest total is taken rather than a sum: adding them would double the night.
yr=defaultdict(list)
for n,src in slp.items():
    best=max(src.values())
    if 0<best<=16: yr[n[:4]].append(best)
res["Sleep"]={y:round(sum(v)/len(v),1) for y,v in sorted(yr.items())}
res["SleepNights"]={y:len(v) for y,v in sorted(yr.items())}
res["Workouts"]={t:dict(sorted(y.items())) for t,y in wko.items()}

yrs=sorted({y for k in ["RestingHeartRate","BodyMass","Sleep","VO2Max"] for y in res[k]})
print("YEAR|RestHR|HRV|VO2max|Weight|BMI|Fat%|Sleep|Steps*|ActiveMin")
for y in yrs:
    g=lambda k:res[k].get(y,"—")
    print(f"{y}|{g('RestingHeartRate')}|{g('HeartRateVariabilitySDNN')}|{g('VO2Max')}|{g('BodyMass')}|{g('BodyMassIndex')}|{g('BodyFatPercentage')}|{g('Sleep')}|{g('StepCount')}|{g('AppleExerciseTime')}")
print("\nWorkouts (type: year:count):")
for t,y in sorted(res["Workouts"].items(),key=lambda x:-sum(x[1].values())):
    print(f"  {t}: "+" ".join(f"{a}:{b}" for a,b in y.items()))
if OUT:
    json.dump(res,open(OUT,"w",encoding="utf-8"),ensure_ascii=False,indent=1)
    print("\n[saved]",OUT)
