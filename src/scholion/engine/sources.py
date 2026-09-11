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


#: A build older than this is worth checking for a newer one. Not a
#: correctness threshold — releases here have come days apart — only the
#: point past which silence stops being informative.
AGEING_AFTER_DAYS = 21


def build_freshness() -> Dict[str, Any]:
    """How old this build is — asked of the build, not of a server.

    The product already says when a reference database went stale and said
    nothing at all about ITSELF. A physician ran a version one release behind for
    four days, and the release she was missing fixed the very thing she spent
    most of her session on; nothing anywhere told her. The same defect this
    project keeps finding inside itself, pointed outwards: a stale thing that
    does not announce that it is stale.

    The first attempt asked PyPI, and the privacy guard refused it — correctly.
    A product whose whole claim is that the profile never leaves the disk should
    not acquire a fifth outbound host to deliver a convenience, and «this machine
    asked about scholion» is a fingerprint of a machine running scholion. The
    build's own release date answers the useful half of the question without
    anybody being contacted: it cannot say WHAT is new, and it can say that
    something probably is.

    `days` is the whole content; the threshold only chooses a word for it.
    """
    from datetime import date
    import re as _re
    import scholion
    out: Dict[str, Any] = {"installed": getattr(scholion, "__version__", ""),
                           "released": None, "days": None, "status": "unknown"}
    try:
        from .. import docs as _docs
        p = _docs.path_of("changelog")
        text = p.read_text(encoding="utf-8") if p else ""
        m = _re.search(r"^##\s*v(\S+)\s+—\s*(\d{2})\.(\d{2})\.(\d{4})\s*$",
                       text, _re.M)
        if not m:
            # `unknown` with no reason is what a build with no journal says;
            # a journal whose heading drifted from `## vX — DD.MM.YYYY` says
            # the same word, and the drift is then found by nobody.
            out["reason"] = "no_dated_heading" if text else "no_changelog"
            return out
        out["released"] = f"{m.group(4)}-{m.group(3)}-{m.group(2)}"
        d = date(int(m.group(4)), int(m.group(3)), int(m.group(2)))
        out["days"] = (date.today() - d).days
    except Exception as exc:                                         # noqa: BLE001
        out["reason"] = type(exc).__name__
        return out
    if out["days"] is None:
        return out
    out["status"] = "ageing" if out["days"] >= AGEING_AFTER_DAYS else "fresh"
    return out


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
    # A genome refused because it belongs to somebody else is NOT «no genome» on
    # this strip either: the folder is full, the file is readable, and the reason
    # the layer is silent has to be readable from the same place the reader looks
    # to find out where a number came from.
    _not_ours = genome.not_ours()
    if _not_ours:
        genome_vcf["not_ours"] = _not_ours
        genome_vcf["origin"] = _not_ours.get("message") or genome_vcf["origin"]

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

    # The lifestyle strip names the DEVICES, not the file. A path tells a reader
    # where the numbers are kept; it does not tell them what measured the numbers,
    # and with two devices in one profile that is the only question that matters.
    p_life = prof / "wearable_trends.json"
    devices, shared = [], []
    from .. import wearables as _wear
    try:
        # Asked of the DATA and not of the file: a caller that supplied the layer
        # some other way still gets an honest strip, and «which devices» is a
        # question about the numbers rather than about where they happen to sit.
        _data = _wear.migrate(core.wearable_trends() or {})
        devices = sorted(_data.get("sources") or {})
        shared = sorted(_wear.shared_metrics(_data))
    except Exception:                                            # noqa: BLE001
        devices, shared = [], []
    lifestyle_src = {"kind": "local", "label": _t("sources.lifestyle"),
                     "origin": (", ".join(_wear.device_label(d) for d in devices)
                                if devices else
                                _t("sources.local_folder",
                                   path="profile/wearable_trends.json")),
                     "devices": devices,
                     "shared_metrics": shared,
                     "primary": core.wearable_primary(),
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
