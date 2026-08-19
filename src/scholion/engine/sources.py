"""Origin and freshness of the data, by domain.

engine.provenance() answers "where does each tab's data come from and when was
it updated" -- local personal files vs public references. Distinct from the
top-level scholion/provenance.py, which is the REVERSE check (every profile
value -> its source report); the two share a word, not a purpose, which is why
this module is named sources.
"""
from __future__ import annotations

from typing import Any, Dict
from .. import core
from ..i18n import t as _t


def provenance() -> Dict[str, Any]:
    """Origin and freshness of the data by domain — for the "source/updated" marks on the tabs.

    kind: 'local' — personal files on the owner's machine; 'public' — open international
    bases / curated references. updated — the _meta.updated date or the mtime.
    """
    from .. import genome
    prof = core.profile_dir()
    kn = core._KNOWLEDGE_DIR

    cfg = core.source_config()

    def loc(name: str, label: str, domain: str) -> Dict[str, Any]:
        p = core.source_path(domain)
        folder = cfg.get(domain)
        origin = (_t("sources.chosen_folder", path=folder) if folder
                  else _t("sources.local_folder", path=f"profile/{name}"))
        return {"kind": "local", "label": label, "origin": origin, "domain": domain,
                "folder": folder, "custom": bool(folder),
                "updated": core.json_updated(p) or core.file_date(p), "present": p.exists()}

    def pub(name: str, label: str, origin: str) -> Dict[str, Any]:
        p = kn / name
        return {"kind": "public", "label": label, "origin": origin,
                "updated": core.json_updated(p) or core.file_date(p), "present": p.exists()}

    # the genome (full VCF) — local
    vp = genome.vcf_path()
    gfolder = cfg.get("genome")
    genome_vcf = {"kind": "local", "label": _t("sources.genome_vcf"), "domain": "genome",
                  "folder": gfolder, "custom": bool(gfolder),
                  "origin": (_t("sources.chosen_folder", path=gfolder) if gfolder
                             else _t("sources.local_folder",
                                     path=vp.parent if vp else "genome/*.vcf.gz")),
                  "updated": core.file_date(vp) if vp else None, "present": vp is not None}

    # ClinVar findings — an international base (NCBI), synchronisation = the mtime of the file/meta
    cv_meta = None
    for base in core.genome_bases():
        mf = base / "clinvar_meta.json"
        hf = base / "clinvar_hits.tsv"
        if mf.exists():
            try:
                cv_meta = core._read_json(mf)
            except Exception:
                cv_meta = None
        if hf.exists():
            clinvar_synced = core.file_date(hf)
            break
    else:
        hf = None
        clinvar_synced = None
    clinvar = {"kind": "public", "label": _t("sources.clinvar"),
               "origin": _t("sources.clinvar_origin"),
               "release": (cv_meta or {}).get("clinvar_date"),
               "updated": (cv_meta or {}).get("synced") or clinvar_synced,
               "present": hf is not None and (hf.exists() if hf else False)}

    # live resolution of rsIDs — Ensembl REST
    cache = core.cache_dir() / "rsid_cache.json"
    ensembl = {"kind": "public", "label": _t("sources.ensembl"),
               "origin": _t("sources.ensembl_origin"),
               "updated": core.file_date(cache), "present": cache.exists()}

    p_life = prof / "wearable_trends.json"
    lifestyle_src = {"kind": "local", "label": _t("sources.lifestyle"),
                     "origin": _t("sources.local_folder",
                                  path="profile/wearable_trends.json"),
                     "updated": core.file_date(p_life), "present": p_life.exists()}
    return {
        "labs": loc("labs.json", _t("sources.labs"), "labs"),
        "medications": loc("medications.json", _t("sources.medications"), "medications"),
        "metrics": loc("metrics.json", _t("sources.metrics"), "metrics"),
        "lifestyle": lifestyle_src,
        "pgx": pub("cpic_drug_gene.json", _t("sources.pgx"), _t("sources.pgx_origin")),
        "interactions": pub("drug_interactions.json", _t("sources.interactions"),
                            _t("sources.interactions_origin")),
        "catalog": pub("loci.json", _t("sources.catalog"), _t("sources.catalog_origin")),
        "test_rules": pub("test_rules.json", _t("sources.test_rules"),
                          _t("sources.test_rules_origin")),
        "genome_vcf": genome_vcf,
        "clinvar": clinvar,
        "ensembl": ensembl,
    }
