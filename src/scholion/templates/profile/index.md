# Profile (personal data) — filled in by the user

This folder is the **user's personal memory**. It is NOT part of the package that is handed over (everyone fills its contents with their own data). Do not pass anything from here to anyone else.

What goes here (for the structures see `LOADING-DATA.md` in the package root):

- `labs.json` — laboratory results (can be auto-ingested from PDFs).
- `medications.json` — current prescriptions.
- `metrics.json` — the profile (sex/year of birth/height) plus manual metrics (waist).
- `pharmacogenomics.json` — pharmacogenomic genotypes (or empty, if a full VCF is present).
- `wearable_trends.json` — lifestyle; created automatically by the `ingest-garmin` command from a Garmin export.
- `health_goals.json` — your target for the indicators (optional).

The full VCF goes into the neighbouring `genome/` folder — see `genome/README.md`.
