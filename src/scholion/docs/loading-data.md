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

## 2. Activity data (wearables) → `profile/wearable_trends.json`
The source is the **GDPR export from Garmin Connect** (Account Settings → "Export Your Data"; you will receive a zip). Unpack it into a folder called `garmin_export` (which contains a `DI_CONNECT` folder) next to the project and run:
```
python3 -m scholion ingest-garmin           # auto-discovers the garmin_export folder
# or give the path explicitly:  python3 -m scholion ingest-garmin "/path/to/garmin_export"
```
The file `profile/wearable_trends.json` is assembled on its own (monthly trends: weight / BMI / fat / muscle / water from Garmin Index smart scales, VO₂max, heart rate, HRV, stress, Body Battery, steps, activity, workouts). Running it again backs up the previous file. (Other devices: bring the data into the same structure — metric → {`YYYY-MM`: value}.)

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
