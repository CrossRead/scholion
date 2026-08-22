# Loading data: what to prepare, where to put it, and the privacy guarantee

This package is a **de-identified engine**: code, knowledge base, application, skill and plugin. It contains **nobody's personal data**. Each user drops THEIR OWN files into the `profile/` and `genome/` folders and gets their own analysis. Never pass anything personal out of your own copy.

---

## 0. Privacy guarantee (for whoever hands the package on)

The package is assembled by the sanitiser script `src/tools/make_shareable.py`, which:

1. **Copies only what is portable** — `src/` (code + application), `knowledge/` (public databases), `ouroboros_plugin/`, the generalised `skill/SKILL.md`, templates and documentation.
2. **Excludes everything personal** — `profile/` (labs, prescriptions, genotypes, metrics), `genome/` (VCF), any `*.vcf*`, `*.bam*`, `*.pdf`, `*.fastq*`, caches, raw exports.
3. **Substitutes neutral placeholders** for personal identifiers (for example, sample ID → `SAMPLE1`).
4. **Runs an automatic audit** of the result: it searches recursively for traces of personal data (owner's name, sample ID, e-mail, date of birth, home directory path, genotypes, lab values). If anything is found, the build fails with an error and prints exactly what was found and where.

To check a package you have been given: `python3 src/tools/make_shareable.py --audit-only <package_folder>` → the output must be `AUDIT OK`.

---

## 1. Genetic data → `genome/`
A full VCF on GRCh38 (`genome/*.vcf.gz` + `.tbi`). The detailed preparation is described in **`genome/README.md`** — two routes: full sequencing (WGS/WES), or a consumer array converted to a VCF and lifted over to GRCh38 with external tools. The array route is a conversion you run yourself; the application does not read a raw export, and on an array a position with no variant is treated as unread rather than as reference, which is the safe reading and a coarse one. Without a VCF the genomic functions honestly report "database not connected"; everything else keeps working.

If what you have on hand is **raw sequencing** (FASTQ from the laboratory), the whole path to a finished VCF is laid out step by step in **`PREPARING-THE-GENOME.md`** (tools, alignment to GRCh38, variant calling, indexing, ClinVar, verifying the result).


**No genome of your own yet?** There is one anybody may look at — a Genome in a Bottle reference material, made and consented to be published. `python3 src/tools/fetch_demo_genome.py --list` says what it would fetch, how big it is, and fetches nothing; without the flag it downloads into `genome-demo/`, and the command it prints at the end points the product at it. It is the one tool here that goes out to the network on purpose, and `SCHOLION_OFFLINE=1` stops it.

That genome belongs to somebody — a real, published person, not you. The tool writes `SUBJECT.json` beside the file saying so, and the product then refuses to read it beside anybody else's history: a genotype of one person under the laboratory series of another is a case about nobody. So it gets a profile of its own, which the tool prints the commands for. The refusal is not a warning you can read past; the genomic layer simply does not answer while the two are in one place.

## 2. Activity data (wearables) → `profile/wearable_trends.json`
Two exports are read, and which one you brought is decided by **what is inside the folder**, not by what it is called.

**Garmin** — the GDPR export from Garmin Connect (Account Settings → "Export Your Data"; a zip arrives by email). Unpack it into a folder holding `DI_CONNECT`.

**WHOOP** — in the app: More → App Settings → Data Export → Create Export. A link arrives by email, and WHOOP allows one request per 24 hours. The zip holds `physiological_cycles.csv`, `sleeps.csv`, `workouts.csv` and `journal_entries.csv`; either the zip itself or the folder you unpacked it into works.

Put either into `raw/wearables/`, or pass the path:
```
python3 -m scholion ingest-wearable                            # looks in raw/wearables/
python3 -m scholion ingest-wearable "/path/to/export-or.zip"   # or say where it is
python3 -m scholion ingest-wearable "/path" --device whoop     # read it only if it IS that one
```
The command prints which device it recognised. It never opens a folder it was not offered: an export sitting somewhere else is named in a sentence and left alone until you pass it as an argument.

### Which source a number came from
Every number carries the device that measured it, in the file and on screen. In the web interface the strip above the "Lifestyle" section names the devices in the profile rather than the file they are kept in, and each metric card says `measured by …` underneath the value.

**With two devices this stops being cosmetic.** A Garmin and a WHOOP both report resting heart rate, heart rate variability, respiration and sleep — and they do not measure them the same way: different window, different algorithm, different place on the body. Averaging the two would invent a number nobody measured; picking one silently would make the answer depend on which export was loaded last. So:

* both series are kept and both are shown;
* neither is used for a conclusion, a trend arrow or the fitness score until you say which device answers;
* the page says so, at the top of the section and on each affected card.

Name the device once — in the web interface with the button in that notice, or:
```
python3 -m scholion profile --wearable whoop      # or garmin
```
With a single device none of this appears and nothing changes.

### Columns this does not know
WHOOP does not publish the layout of its export, so the header row decides what is read: each column is looked up in a table that ships as **data**, not code. A column that is not in the table is **listed by name** and nothing is read from it — an export carrying something new says so instead of dropping a measurement in silence.

If one of those columns is a measurement you want, name it yourself in `profile/wearable_metrics.local.json` and read the export again:
```json
{"sources": {"whoop": {"columns": {"Fatigue score %": {"metric": "Recovery"}}}}}
```
Additions are merged per column, so yours cannot delete what already works.

### The file
`profile/wearable_trends.json` is assembled on its own, one block per device: monthly trends (weight / BMI / fat / muscle / water from a smart scale, VO₂max, heart rate, HRV, respiration, sleep and its stages, recovery, strain, steps, activity) plus workouts by year, and a night-by-night file beside it. Running it again backs up the previous file, and a month the fresh export does not carry survives from the old one — an export that did not download in full cannot erase history. A file written by an earlier version is brought to the per-device layout when it is read; if it does not say which device produced it, it is filed as **`device not recorded`** rather than assigned to one.

## 2a. The demonstration profile and your own data

`scholion init --demo` lays down a complete profile of a **fictional person** so that the product can be looked at before any of your files exist. Everything in it is generated; it belongs to nobody.

**The first measurement of your own erases it.** Adding a lab point, a metric or a prescription — from the command line, from the web page, or by importing a file — removes the demonstration and writes your datum into an empty profile. The command says so before it says anything else, and names every file it removed.

This is deliberate and it is not destructive: the demonstration is generated from a fixed seed, so `scholion init --demo --dir <folder>` builds it again exactly as it was. What cannot be rebuilt is a series in which invented numbers and your own sit side by side, indistinguishable — which is what happened before, quietly, while the file went on calling itself synthetic.

The rule underneath is **one profile, one person**. Every datum written now records whose it is, and data of two different people never meet in one profile — your own, the demonstration's, or a published reference sample's. If you want two of them at once, give each its own folder:

```bash
scholion init --dir ~/scholion-demo && SCHOLION_PROFILE_DIR=~/scholion-demo scholion init --demo --dir ~/scholion-demo
```

## 3. Laboratory tests → `profile/labs.json`
Put the laboratory's PDF reports into a folder and run:
```
python3 -m scholion ingest-labs "/path/to/folder with PDFs"
```
This extracts the markers together with their dates (using the recognition dictionary `knowledge/lab_markers.json`), incrementally and idempotently. Scanned PDFs with no text layer cannot be read — enter those points by hand (the Labs tab). For the `labs.json` schema and manual entry, see the `profile/labs.json` template and the `_meta` block inside it.

## 4. Doctor's prescriptions → `profile/medications.json`
Either the Prescriptions tab in the application, or edit the file directly. Schema: `medications: [{name, dose, note}]`. Adding the same drug again updates the existing entry.

## 5. Profile and metrics → `profile/metrics.json`
Sex / year of birth / height (for BMI and age) plus manual metrics (waist). The Lifestyle tab.

## 6. Target values for your markers (optional) → `profile/health_goals.json`
A curated goal; current values and charts are pulled live from `labs.json` + `wearable_trends.json`. Edit the template to match your own goal (see `_meta.how_to_fill`). It is displayed by the dashboard on the Overview tab.

---

All templates, with comments, live in `profile/` (they are example stubs — replace them with your own data). Once the data is loaded, start the application (see `README.md`).
