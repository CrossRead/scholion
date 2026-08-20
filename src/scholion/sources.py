"""External reference sources: what updates upstream, and how it is imported.

The knowledge base is not one thing. Part of it is curated by this project and
changes when somebody decides it should; part of it mirrors a public source that
changes on its own schedule — CPIC revises a guideline, ClinVar publishes a
weekly release, the PGS Catalog adds models. A mirror with no import path rots
silently: it keeps answering, and the answer drifts away from the source it
claims. This module is the registry of those sources and the machinery that
brings them in.

Three rules it exists to keep.

**A refreshed catalogue lands beside the person's data, never inside the wheel.**
`pip install` puts the bundled copy in site-packages, which is read-only on many
machines and replaced wholesale by the next upgrade. `core.knowledge_path`
prefers a local copy, so «refresh the reference base» does not mean «reinstall».

**An import verifies before it writes.** The CPIC importer compares every allele
function label we carry against the upstream table and reports the differences,
because the finding that started this work was exactly a hand-copied label that
had drifted. An import that only overwrites hides the drift it should surface.

**A source that cannot be automated says so, by name.** LOINC needs a registered
account and an accepted licence; the ACMG secondary-findings list is a paper a
human reads. Those are `auto: False` with the reason recorded, not omissions —
the same rule the four-face contract applies to capabilities.
"""
from __future__ import annotations

import datetime
import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from . import core
from .i18n import t as _t

CPIC_API = "https://api.cpicpgx.org/v1"

#: Upstream functional-status wording → the label our marker definitions carry.
_FUNCTION_LABEL = {
    "no function": "none",
    "decreased function": "decreased",
    "normal function": "normal",
    "increased function": "increased",
    "uncertain function": "uncertain",
    "unknown function": "uncertain",
    "possible decreased function": "decreased",
}

#: Upstream phenotype wording → the short code the engine speaks.
_PHENO_CODE = {
    "normal metabolizer": "NM", "intermediate metabolizer": "IM",
    "poor metabolizer": "PM", "rapid metabolizer": "RM",
    "ultrarapid metabolizer": "UM",
}


def _today() -> str:
    return datetime.date.today().isoformat()


def _star_token(name: str) -> Optional[str]:
    """The `*N` token inside an allele name, however the name is spelled.

    Ours read `*2`, `*3C`, `*2A`, `HapB3 (c.1129-5923C>G)`; CPIC's read `*2`,
    `c.1905+1G>A (*2A)`. Matching on the star token is what makes the two
    vocabularies comparable without a hand-written mapping table per gene.
    """
    import re
    m = re.search(r"\*([0-9]+[A-Za-z]*)", str(name or ""))
    return f"*{m.group(1)}" if m else None


def _fetch_json(url: str) -> Any:
    """Default fetcher: the project's own network layer, so SCHOLION_OFFLINE,
    the TLS policy and the host inventory all apply to an import too."""
    from . import net
    if net.offline():
        raise SourceUnavailable(_t("sources.offline"))
    data = net.get_json(url)
    if data is None:
        raise SourceUnavailable(_t("sources.fetch_failed", url=url))
    return data


class SourceUnavailable(RuntimeError):
    """The upstream could not be read — offline, unreachable, or refused."""


# ---------------------------------------------------------------- importers
def _import_cpic(fetch: Callable[[str], Any]) -> Dict[str, Any]:
    """Refresh the CPIC-derived parts of cpic_drug_gene.json, and report drift.

    What is imported is what CPIC publishes as data: the functional status of
    each star allele, and the activity-score→phenotype bands. What is NOT
    imported is the recommendation prose — CPIC's own wording lives in guideline
    documents, and copying a sentence is a different act from mirroring a table;
    the file records that mixed provenance rather than implying the whole of it
    is verbatim.
    """
    name = "cpic_drug_gene.json"
    data = json.loads(core.knowledge_path(name).read_text(encoding="utf-8"))
    genes = data.get("genes", {})
    changes: List[Dict[str, Any]] = []
    checked = 0

    for gene, gdef in genes.items():
        markers = gdef.get("markers") or []
        if not markers:
            continue
        alleles = fetch(f"{CPIC_API}/allele?genesymbol=eq.{gene}"
                        f"&select=name,activityvalue,clinicalfunctionalstatus")
        by_star: Dict[str, Dict[str, Any]] = {}
        for a in alleles or []:
            tok = _star_token(a.get("name"))
            if tok:
                by_star.setdefault(tok, a)
        for m in markers:
            tok = _star_token(m.get("star"))
            up = by_star.get(tok) if tok else None
            if not up:
                continue
            checked += 1
            want = _FUNCTION_LABEL.get(
                str(up.get("clinicalfunctionalstatus") or "").strip().lower())
            if want and want != m.get("function"):
                changes.append({"gene": gene, "star": m.get("star"), "rsid": m.get("rsid"),
                                "field": "function", "was": m.get("function"), "now": want,
                                "upstream": up.get("clinicalfunctionalstatus")})
                m["function"] = want

        if gdef.get("model") == "activity_score":
            rows = fetch(f"{CPIC_API}/diplotype?genesymbol=eq.{gene}"
                         f"&select=generesult,totalactivityscore")
            bands = _bands_from_diplotypes(rows or [])
            if bands:
                # CPIC publishes the boundaries, not our wording. Carry the
                # existing label across by phenotype code: an import that dropped
                # them would leave the phenotype printed with no name at all,
                # and in the language catalogues' place a blank.
                old_bands = gdef.get("activity_bands") or []
                labels = {b.get("phenotype"): b.get("label") for b in old_bands}
                for b in bands:
                    lab = labels.get(b["phenotype"])
                    if lab:
                        b["label"] = lab
                # Compare on the numbers only — re-deriving identical boundaries
                # is not a change worth reporting.
                def _shape(bs):
                    return [(b["min"], b["max"], b["phenotype"]) for b in bs]
                if _shape(bands) != _shape(old_bands):
                    changes.append({"gene": gene, "field": "activity_bands",
                                    "was": _shape(old_bands), "now": _shape(bands)})
                gdef["activity_bands"] = bands

    _import_cpic_recommendations(fetch, data, changes)
    _import_cpic_pairs(fetch, changes)

    data.setdefault("_meta", {})["imported"] = {
        "source": "cpic", "fetched": _today(), "endpoint": CPIC_API,
        "license": "CC0 1.0 (CPIC content is public domain)",
        "covers": "allele functional status, activity-score bands, and the verbatim "
                  "recommendation wording of every pair that already carries a quote; "
                  "the patient-facing notes stay project-written",
        "alleles_checked": checked,
    }
    core.write_knowledge_local(name, data)
    return {"source": "cpic", "file": name, "checked": checked, "changes": changes}


#: Our guidance keys are the engine's vocabulary; CPIC's are its phenotype
#: strings. The map is written out rather than guessed, because a wrong guess
#: would attach the wrong guideline sentence to a phenotype — the worst failure
#: this file can produce.
_GUIDANCE_KEY_TO_CPIC = {
    "PM": "Poor Metabolizer", "IM": "Intermediate Metabolizer",
    "NM": "Normal Metabolizer", "RM": "Rapid Metabolizer",
    "UM": "Ultrarapid Metabolizer",
    "low_function": "Poor Function", "intermediate_function": "Decreased Function",
    "normal_function": "Normal Function",
    "deficient": "Poor Metabolizer", "intermediate": "Intermediate Metabolizer",
    "normal": "Normal Metabolizer",
}


def _import_cpic_recommendations(fetch, data, changes):
    """Re-read CPIC's own recommendation wording for every pair that carries a quote.

    Only pairs that ALREADY have a `cpic` block are refreshed. Attaching a quote
    to a pair that has none is a judgement — which of several population- or
    age-specific rows applies, and whether the phenotype vocabularies really
    correspond — and a judgement belongs to a person reading the guideline, not
    to an unattended refresh. What the refresh does is keep an existing quote
    true, and say so loudly when the upstream sentence has changed.
    """
    for drug in data.get("drugs", []):
        cpic_name = drug.get("cpic_drug")
        if not cpic_name:
            continue
        guidance = drug.get("guidance") or {}
        if not any(isinstance(g, dict) and g.get("cpic") for g in guidance.values()):
            continue
        rows = fetch(f"{CPIC_API}/recommendation?select=classification,drugrecommendation,"
                     f"implications,phenotypes,drug!inner(name)&drug.name=eq.{cpic_name}") or []
        gene = drug.get("gene")
        by_pheno = {}
        for row in rows:
            ph = (row.get("phenotypes") or {}).get(gene)
            if ph and ph not in by_pheno:
                by_pheno[ph] = row
        for key, g in guidance.items():
            cp = g.get("cpic") if isinstance(g, dict) else None
            if not cp:
                continue
            want = cp.get("phenotype") or _GUIDANCE_KEY_TO_CPIC.get(key)
            row = by_pheno.get(want)
            if not row:
                continue
            upstream = row.get("drugrecommendation")
            if upstream and upstream != cp.get("recommendation"):
                changes.append({"gene": gene, "drug": cpic_name, "field": "recommendation",
                                "phenotype": want, "was": cp.get("recommendation"),
                                "now": upstream})
                cp["recommendation"] = upstream
            impl = (row.get("implications") or {}).get(gene)
            if impl and impl != cp.get("implication"):
                cp["implication"] = impl
            cls = row.get("classification")
            if cls and cls != cp.get("classification"):
                changes.append({"gene": gene, "drug": cpic_name, "field": "classification",
                                "phenotype": want, "was": cp.get("classification"), "now": cls})
                cp["classification"] = cls


def _import_cpic_pairs(fetch, changes):
    """Refresh the level-A pair list — the denominator coverage is measured against.

    This list is what makes «we carry 16 of 78» a fact instead of a feeling, and
    it is what would have named NUDT15 before a person did. Left unrefreshed it
    would rot in the same way as everything else here: CPIC adds pairs, and a
    stale denominator quietly reports better coverage than the build has.
    """
    rows = fetch(f"{CPIC_API}/pair?select=genesymbol,cpiclevel,drug!inner(name)"
                 f"&cpiclevel=eq.A&removed=is.false&order=genesymbol") or []
    pairs = sorted({(r["genesymbol"], (r.get("drug") or {}).get("name"))
                    for r in rows if r.get("genesymbol") and (r.get("drug") or {}).get("name")})
    if not pairs:
        return
    name = "cpic_pairs.json"
    doc = json.loads(core.knowledge_path(name).read_text(encoding="utf-8"))
    before = {(p["gene"], p["drug"]) for p in doc.get("pairs", [])}
    added = [f"{g}/{d}" for g, d in pairs if (g, d) not in before]
    dropped = [f"{g}/{d}" for g, d in sorted(before) if (g, d) not in set(pairs)]
    if added or dropped:
        changes.append({"gene": "—", "field": "cpic_level_A_pairs",
                        "was": f"{len(before)} pairs", "now": f"{len(pairs)} pairs"
                                + (f"; added {', '.join(added[:8])}" if added else "")
                                + (f"; no longer level A: {', '.join(dropped[:8])}" if dropped else "")})
    doc["pairs"] = [{"gene": g, "drug": d} for g, d in pairs]
    doc.setdefault("_meta", {})["count"] = len(pairs)
    doc["_meta"]["fetched"] = _today()
    core.write_knowledge_local(name, doc)


def _bands_from_diplotypes(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Collapse CPIC's diplotype table into score→phenotype bands.

    The table is per diplotype; the model needs the interval. Scores that map to
    one phenotype become one band, and a phenotype that is not contiguous is
    dropped rather than guessed — a non-contiguous band would silently
    misclassify everything between its ends.
    """
    seen: Dict[str, List[float]] = {}
    for r in rows:
        try:
            score = float(r.get("totalactivityscore"))
        except (TypeError, ValueError):
            continue
        code = _PHENO_CODE.get(str(r.get("generesult") or "").strip().lower())
        if not code:
            continue
        seen.setdefault(code, []).append(score)
    bands = []
    for code, scores in seen.items():
        lo, hi = min(scores), max(scores)
        others = [s for c, ss in seen.items() if c != code for s in ss]
        if any(lo < s < hi for s in others):
            continue                      # not contiguous — do not guess
        bands.append({"min": lo, "max": hi, "phenotype": code})
    return sorted(bands, key=lambda b: -b["min"])


# ----------------------------------------------------------------- registry
SOURCES: Dict[str, Dict[str, Any]] = {
    # ── mirrors: data this build CARRIES, and that changes upstream ──────────
    "cpic": {
        "kind": "mirror",
        "title": "CPIC — pharmacogenetic allele functions and phenotype bands",
        "license": "CC0 1.0 (public domain)",
        "homepage": "https://cpicpgx.org",
        "endpoint": CPIC_API,
        "feeds": ["cpic_drug_gene.json", "cpic_pairs.json"],
        "cadence": "guidelines are revised a few times a year",
        "auto": True,
        "importer": _import_cpic,
    },
    "acmg_sf": {
        "kind": "mirror",
        "title": "ACMG SF — secondary findings gene list",
        "license": "the gene list is factual; published in a paper",
        "homepage": "https://www.acmg.net",
        "feeds": ["acmg_sf.json"],
        "cadence": "roughly annual (v3.0 → v3.3)",
        "auto": False,
        "why_manual": "sources.manual.acmg",
    },
    "loinc": {
        "kind": "mirror",
        "title": "LOINC — laboratory observation codes",
        "license": "free, requires a registered account and accepting the terms",
        "homepage": "https://loinc.org",
        "feeds": ["lab_markers.json"],
        "cadence": "two releases a year",
        "auto": False,
        "why_manual": "sources.manual.loinc",
    },
    "pgs_catalog": {
        "kind": "mirror",
        "title": "PGS Catalog — polygenic score models",
        "license": "CC BY 4.0 (attribution)",
        "homepage": "https://www.pgscatalog.org",
        "feeds": ["prs_models.json", "prs_traits.json"],
        "cadence": "models added continuously",
        "auto": False,
        "why_manual": "sources.manual.pgs",
    },
    "longevitymap": {
        "kind": "mirror",
        "title": "LongevityMap (HAGR) — longevity association variants",
        "license": "free for non-commercial use — NOT bundled, fetched into your copy",
        "homepage": "https://genomics.senescence.info/longevity/",
        "feeds": ["longevitymap.json"],
        "cadence": "infrequent",
        "auto": False,
        "why_manual": "sources.manual.longevitymap",
        "command": "python3 src/ingest/build_longevitymap.py",
    },

    "eflm_biological_variation": {
        "kind": "mirror",
        "title": "EFLM Biological Variation Database — within-person variation per analyte",
        "license": "free for non-commercial use; registration required",
        "homepage": "https://biologicalvariation.eu",
        "feeds": [],
        "cadence": "updated as new meta-analyses are accepted",
        "auto": False,
        "why_manual": "sources.manual.eflm",
    },

    # ── pipeline: large downloads the genome track needs (source tree only) ──
    "clinvar": {
        "kind": "pipeline",
        "title": "ClinVar — clinically significant variants (annotates your genome)",
        "license": "public domain (NCBI)",
        "homepage": "https://www.ncbi.nlm.nih.gov/clinvar/",
        "endpoint": "https://ftp.ncbi.nlm.nih.gov/pub/clinvar/",
        "feeds": [],
        "cadence": "weekly releases",
        "auto": False,
        "why_manual": "sources.manual.clinvar",
        "command": "bash src/ingest/update_check.sh",
    },
    "mane_select": {
        "kind": "pipeline",
        "title": "MANE Select — one agreed transcript per gene (NCBI/EMBL-EBI)",
        "license": "public domain (NCBI/EMBL-EBI)",
        "homepage": "https://www.ncbi.nlm.nih.gov/refseq/MANE/",
        "endpoint": "https://ftp.ncbi.nlm.nih.gov/refseq/MANE/MANE_human/current/",
        "feeds": [],
        "cadence": "a release every few months, tied to RefSeq/Ensembl",
        "auto": False,
        "why_manual": "sources.manual.mane",
        "command": "bash src/ingest/qc_callability.sh",
    },
    "reference_genome": {
        "kind": "pipeline",
        "title": "Reference genome and annotation (UCSC / Ensembl FTP)",
        "license": "open data",
        "homepage": "https://hgdownload.soe.ucsc.edu",
        "endpoint": "https://ftp.ensembl.org/pub/",
        "feeds": [],
        "cadence": "assembly-stable; annotation releases a few times a year",
        "auto": False,
        "why_manual": "sources.manual.reference",
        "command": "bash src/ingest/fastq_to_vcf.sh",
    },

    # ── live: asked at query time, nothing is stored, nothing to import ──────
    "rxnorm": {
        "kind": "live",
        "title": "RxNorm / RxClass (NLM) — drug identity and class, for a drug not in the local base",
        "license": "public domain (NLM)",
        "homepage": "https://rxnav.nlm.nih.gov",
        "feeds": [],
        "cadence": "queried live, nothing stored",
        "auto": False,
        "why_manual": "sources.manual.live",
    },
    "ensembl_rest": {
        "kind": "live",
        "title": "Ensembl REST — rsID lookup for a locus not in the local catalogue",
        "license": "open (EMBL-EBI)",
        "homepage": "https://rest.ensembl.org",
        "feeds": [],
        "cadence": "queried live, nothing stored",
        "auto": False,
        "why_manual": "sources.manual.live",
    },
    "translation": {
        "kind": "live",
        "title": "Translation services — a Russian drug name to its English ingredient",
        "license": "public APIs; only the drug NAME is sent, never profile data",
        "homepage": "https://mymemory.translated.net",
        "feeds": [],
        "cadence": "queried live, nothing stored",
        "auto": False,
        "why_manual": "sources.manual.live",
    },
}


def state() -> List[Dict[str, Any]]:
    """Every external source, what it feeds, and when it was last brought in.

    «Last updated» has two honest meanings and both are reported: the date this
    machine imported the source, and — when it never did — the stamp the bundled
    copy carries from whoever curated it. A source that stores nothing (a live
    lookup) says so instead of showing a date it does not have.
    """
    out = []
    for sid, s in SOURCES.items():
        files = []
        for f in s.get("feeds", []):
            if not f.endswith(".json"):
                continue
            meta = {}
            try:
                meta = (json.loads(core.knowledge_path(f).read_text(encoding="utf-8"))
                        .get("_meta") or {})
            except (OSError, ValueError):
                pass
            imported = (meta.get("imported") or {}).get("fetched")
            files.append({"file": f,
                          "local": core.knowledge_is_local(f),
                          "imported": imported,
                          "bundled_stamp": meta.get("updated") or meta.get("version"),
                          "tier": meta.get("source_tier")})
        out.append({"id": sid, "kind": s.get("kind", "mirror"), "title": s["title"],
                    "license": s["license"], "homepage": s.get("homepage"),
                    "endpoint": s.get("endpoint"), "cadence": s.get("cadence"),
                    "auto": bool(s.get("auto")), "files": files,
                    "why_manual": s.get("why_manual"), "command": s.get("command")})
    return out


def refresh(source_id: str, fetch: Optional[Callable[[str], Any]] = None) -> Dict[str, Any]:
    """Import one source. Returns what changed; raises SourceUnavailable offline."""
    s = SOURCES.get(source_id)
    if not s:
        raise KeyError(source_id)
    if not s.get("auto"):
        return {"source": source_id, "skipped": True,
                "reason": _t(s.get("why_manual") or "sources.manual.generic"),
                "command": s.get("command")}
    return s["importer"](fetch or _fetch_json)


def refresh_all(fetch: Optional[Callable[[str], Any]] = None) -> List[Dict[str, Any]]:
    return [refresh(sid, fetch) for sid in SOURCES if SOURCES[sid].get("auto")]
