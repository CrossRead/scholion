# Attribution and third-party licenses

This file records where every non-original piece of data in this repository
comes from, under what licence, and what the licence requires of anyone who
redistributes it. It is part of the licence conditions, not documentation.

Two rules govern the whole repository:

1. **Nothing enters `knowledge/` without a source.** A file with no
   `_meta.source` is a defect.
2. **Nothing enters the repository whose licence forbids commercial use,
   modification, or redistribution.** The code is Apache-2.0 and the data is
   CC BY 4.0; both permit commercial use, so anything more restrictive is
   incompatible by construction and is fetched at run time instead.

---

## Data included in this repository

### LongevityMap — Human Ageing Genomic Resources (HAGR)

* File: `src/scholion/knowledge/longevitymap.json` (2 859 variants, 162 genes)
* Source: https://genomics.senescence.info/longevity/
* Licence: **Creative Commons Attribution 3.0 Unported** — free for all
  purposes including commercial, citation required
  (https://genomics.senescence.info/legal.html)
* Required citation — HAGR asks for both the resource and the specific database.
  Check the site for the currently preferred references before publication:
  * Tacutu R, Thornton D, Johnson E, et al. *Human Ageing Genomic Resources:
    new and updated databases.* Nucleic Acids Research, 2018.
  * Budovsky A, Craig T, Wang J, et al. *LongevityMap: a database of human
    genetic variants associated with longevity.* Trends in Genetics, 2013.
* Note: CC BY **3.0** does not expressly address the European sui generis
  database right, unlike CC BY 4.0. For EU users this is a grey area inherited
  from the upstream source, not something this project can resolve.

### Pharmacogenomic gene–drug reference

* File: `src/scholion/knowledge/cpic_drug_gene.json`
* Written by hand from the published principles of CPIC guidelines. **No CPIC
  table is copied.** CPIC content is dedicated to the public domain under CC0
  (https://www.clinpgx.org/page/dataUsagePolicy).
* The CPIC® name is a registered mark and the CPIC logo belongs to NIH; neither
  is used in this project's branding or promotion.
* PharmGKB content is licensed CC BY-SA 4.0, whose ShareAlike term would
  propagate to any derivative file. **No PharmGKB table is copied**, and no
  file here is derived from one.

### LOINC — Regenstrief Institute

* File: `src/scholion/knowledge/lab_test_meta.json` (34 verified codes)
* Source: https://loinc.org — free of charge under the LOINC license
* Licence condition: redistribution requires the verbatim notice reproduced in
  `NOTICE`. It is not optional and not paraphrasable; section 10(a) of the
  licence fixes its wording.
* Each code is stored next to the test it identifies and its LOINC long common
  name, as the licence requires. Codes that could not be verified against the
  LOINC search service are marked `loinc_status` and left empty — an unverified
  code is worse than none, because it silently maps a test to the wrong concept.

### PGS Catalog model registry

* File: `src/scholion/knowledge/prs_models.json`
* Contains **only public PGS identifiers** (e.g. `PGS000123`) and this project's
  own notes about why a model was pinned. **No scoring weights are included.**
* This is a deliberate constraint: the PGS Catalog sets no single licence, each
  scoring file carries its own, and some are CC BY-NC-ND — incompatible with
  this repository. Weights are downloaded by the user from
  https://www.pgscatalog.org/ under the terms of each individual score.

### Everything else in `knowledge/`

`acmg_sf.json`, `clinical_thresholds.json`, `dose_evidence.json`,
`drug_interactions.json`, `drug_lab_monitoring.json`, `lab_markers.json`,
`lab_test_meta.json`, `loci.json`, `longevity_directions.json`,
`med_classes.json`, `penetrance.json`, `prs_traits.json`, `test_rules.json`,
`experiment_templates.json`, `wearable_metrics.json` are original compilations
written for this project. Individual entries cite primary literature, clinical
guidelines and genome coordinates verified against Ensembl; citing a fact is
not redistributing a database. Where an entry reflects a specific guideline,
the guideline is named in the entry itself.

The ACMG Secondary Findings gene list reflects the recommendations of the
American College of Medical Genetics and Genomics (SF v3.3); the list of gene
symbols is factual, the reporting rules are implemented in this project's own
code.

---

## Resources used at run time and NOT redistributed here

The user obtains each of these directly from its provider, under that
provider's terms. This project only calls them.

| Resource | Provider | Terms |
|---|---|---|
| ClinVar | NCBI / NLM | Redistribution permitted; attribution requested. NCBI asks that ClinVar data be accompanied by the note that it is *not intended for direct diagnostic use or medical decision-making without review by a genetics professional* — this project reproduces that position in DISCLAIMER.md. https://www.ncbi.nlm.nih.gov/clinvar/docs/maintenance_use/ |
| dbSNP | NCBI / NLM | rsIDs used as identifiers. NCBI policies apply. |
| Ensembl REST (incl. 1000 Genomes and gnomAD allele frequencies) | EMBL-EBI | Queried at run time for coordinates and population frequencies. EMBL-EBI terms of use; IGSR notes that rights vary between constituent datasets. |
| PGS Catalog scoring files | EMBL-EBI / PGS Catalog | Licence declared per score inside each file. |
| RxNorm and RxClass, including ATC codes | NLM | Queried at run time. **ATC codes are never stored in this repository:** the WHO Collaborating Centre prohibits copying and distribution for commercial purposes, which is incompatible with a permissively licensed repository. |
| SNOMED CT | SNOMED International | **Not used.** Requires an Affiliate licence; incompatible with open redistribution. |
| LOINC | Regenstrief Institute | **Used and redistributed** — see the dedicated section below. |

## External tools invoked, not bundled

Installed by the user; this project executes them and reads their output.

| Tool | Licence |
|---|---|
| PharmCAT | Mozilla Public License 2.0 |
| PyPGx | MIT |
| T1K | MIT |
| bcftools, samtools (HTSlib) | MIT/Expat |
| Ensembl VEP | Apache-2.0 |
| BWA | GPL-3.0 (invoked as a separate process; no code is linked or copied) |
| telomerecat | as published by its authors |
| DeepVariant | BSD-3-Clause |

---

## Reporting a licensing problem

If you believe something here is misattributed or should not be redistributed,
open an issue titled `licensing:` or write to the maintainer. Data whose status
is unclear is removed first and discussed second.
