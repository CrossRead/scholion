"""The third entry: a body system of the radar, read as one subject.

The radar already computes the laboratory half of a system — score, deviations,
how much of the panel was measured, how it moved. What it did not hold was the
other half of the same subject: what in the genome bears on the working of this
system, how much of that was actually read, and — the half of the value — the
questions that follow for a clinician. This module assembles the seven layers
of a system's card around one key and never computes the first two again.

The genetic half has two sources, merged and never confused:

  base     the monogenic composition GENERATED from a curated base with a
           version (`gencc_gene_disease.json`): per gene, every submitter's
           assertion side by side — disease, classification, mode of
           inheritance, submitter, date. Nobody wrote this list; a tool read it
           out of the base, and the answer says which export it came from.
  curated  positions a clinician authored (`system_gene_panels.json`): rsID and
           HGVS, the risk allele she named, the phrase for each genotype STATE,
           an expectation on a marker, a next step — and her exclusions of base
           genes, signed with a reason. Composition comes from the base; the
           clinician signs exceptions.

Four rules decide what may be printed, and they are the acceptance of task 168:
every row carries its evidence mode (monogenic / common_variant / pgx) and the
three never print alike; Limited, Disputed and Refuted assertions are never a
finding in any register; for a recessive gene one copy is carriership, printed
as a carrier and raised as a question, never as a risk line; common variation
is shown as a score, and a single common variant only with an effect size from
a named study. The engine speaks for itself only about the completeness of the
data — a gap, staleness, coverage, a value's place in a corridor. Everything
said about the person is either a rule with a source or an author's sentence.

Genetics does not enter the 0–100 score. The score is refuted by the next draw;
a genotype never changes; one number made of both could not be refuted by any
measurement and would drag a system down for years.

JSON shape of `system(key, register)` — two other streams render it:

    status          "ok" | "unknown_system"
    key, label, register, source ("labs" | "wearables"), genetic_half (bool)
    labs            layer 1: status ok|nodata|absent, source, score, level,
                    ok, abnormal[], measured, total, missing[], stale[]
    dynamics        layer 2: status ok|no_previous|absent, prev_score,
                    compared_score, delta, prev_date, compared, moved[]
    genetics        layer 3: status composed|not_composed|no_genetic_half,
                    why_empty, base {source, version, downloaded, filter_version,
                    genes}, curated {status, source, positions}, rows[],
                    excluded[], refused {total, by_reason}, read_count,
                    unread_count, read_genes, read_positions,
                    finding_count, carrier_count, pending_count,
                    signature_open_count, signature_author_count, signature_author_date,
                    withheld_by_classification, verdict, verdict_line, scan,
                    polygenic {status ok|no_scores|no_map|no_genetic_half,
                    rows[] ({trait, label, pgs_id, percentile, evidence,
                    reliable, validity_note?, integrity_note?,
                    model_changed_from?}), high[], mapped, scored, unscored[],
                    why?, caveat} — the common variation of the system AS
                    SCORES (task 178): the pinned models `prs_system_map.json`
                    places on this system, each with the person's percentile
                    from `prs_findings`. Never in the verdict, never in the score.
    medications     layer 4: status ok|empty, rows[] — the person's CURRENT
                    prescriptions whose class maps to this system through
                    `drug_class_systems.json` ({name, dose, status, classes,
                    via, map_status "mapped"}); unmapped[] — current
                    prescriptions whose class has no row in the map, each with
                    map_status "no_map" (never silently absent); unclassified[]
                    — prescriptions no class recognised; empty_why, map
    target          layer 5: status ok|empty, rows[] — the clinician's targets
                    (task 170) on this system's markers, each with the figures,
                    who set it and when, the current value, outside_target and
                    in_corridor; empty_why
    tests           layer 6: status, rows[] (suggest_tests rows whose rule
                    touches a marker of this system), empty_why
    questions       layer 7: status, rows[] ({origin, text, gene?, rsid?,
                    marker?, data}), empty_why — origins: expect, expect_gap,
                    pending, risk_allele, moi, gap, target, polygenic
    verdict, verdict_line   the four-state reading verdict of the genetic half
    next            {lab, genome, ask}: each {rows[], empty_why|null} — never
                    silently empty: an empty basket names one of the reasons;
                    `genome` also carries `full_genome` — when the input is no
                    genome, an array, an exome or a panel, what a full genome
                    would close for THIS system (the genes not read, the
                    polygenic scores), or null when the input is a full genome
    disclaimer

A row of `genetics.rows` (clinician register; the patient register keeps the
rows that say something — finding, carrier, pending — and the counts):

    unit "gene"|"position", origin "base"|"curated", gene, mode, kind?, source,
    text|null, pending, pending_why?, findings (int), carrier (bool), read,
    read_why?, variant_state, coverage,
    base rows:      assertions[] {disease, disease_id, classification, moi,
                    moi_code, submitter, curated_on}, classifications[],
                    finding_grade, recessive_only, weaker_assertions,
                    other_assertions, clinvar {status, hits, withheld}
    position rows:  rsid, hgvs, protein?, risk_allele, classification?, moi?,
                    disease?, effect_size?, study?, genotype {state, genotype,
                    confidence, depth, why?}, expect_check?, next_step?
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from .. import core
from ..i18n import CATALOGUES, plural as _plural, t as _t
from ._helpers import DISCLAIMER, _recent
from . import panel_form, panel_gate, panel_labs
from . import panel_genotype as _pg
from .panel_genotype import _genotype, _has_alignment  # noqa: F401
from .panel_book import (_attach_local_notes, _groups, _on_demand, _on_demand_card,  # noqa: F401
                         on_demand_panels, positions_by_marker)
from .panel_form import KINDS, verdict, verdict_line  # noqa: F401 -- the form's, re-exported

#: The three evidence modes, and they never print alike (brief §5.0).
MODES = panel_gate.MODES
#: Classifications that may turn a row into a finding; Moderate carries a caveat.
FINDING_GRADE = ("Definitive", "Strong", "Moderate")
#: Never a finding, in any register, whatever the genotype (brief §5.0, rule 1).
NOT_A_FINDING = ("Limited", "Disputed", "Refuted", "No Known Disease Relationship")
#: Modes of inheritance where one copy is carriership, not risk.
RECESSIVE = ("AR",)
#: A measurement older than this is stale for the purpose of a system's card —
#: the same window `health_radar` uses for its deviations.
STALE_MONTHS = 18
REGISTERS = ("patient", "clinician")
BASKETS = ("lab", "genome", "ask")
#: The origins of a question (brief §6.2). `target` arrived with task 170: a
#: value the corridor calls normal and the clinician's target does not.
QUESTION_ORIGINS = ("expect", "expect_gap", "pending", "risk_allele", "moi", "gap", "target",
                    "polygenic")
#: A reliable polygenic score at or above this percentile becomes ONE question
#: (task 178) — the same line `prs_findings` draws its `high` list at.
POLYGENIC_HIGH_PERCENTILE = 80


# ---- the three files -------------------------------------------------------
def domains() -> List[Dict[str, Any]]:
    """The systems as `radar_domains.json` declares them — the same file
    `lifestyle._RADAR_DOMAINS` is built from, so the two halves cannot drift."""
    out = []
    for d in (core._read_knowledge("radar_domains.json") or {}).get("domains") or []:
        if isinstance(d, dict) and d.get("key"):
            out.append({"key": str(d["key"]), "source": d.get("source") or "labs",
                        "genetic_half": bool(d.get("genetic_half")),
                        "markers": list(d.get("markers") or []), "why": d.get("why"),
                        "panel_markers": list(d.get("panel_markers") or []),
                        "derived": list(d.get("derived") or []),
                        # task 205 D, E: how the panel author reads the panel
                        "display_only": list(d.get("display_only") or []),
                        "panel_groups": list(d.get("panel_groups") or []),
                        "interpret_with": dict(d.get("interpret_with") or {})})
    return out


def _domain(key: str) -> Optional[Dict[str, Any]]:
    q = (key or "").strip().lower()
    for d in domains():
        if d["key"] == q:
            return d
    return None


def _curated() -> Dict[str, Any]:
    try:
        return core._read_knowledge("system_gene_panels.json") or {}
    except Exception:                                                # noqa: BLE001
        return {}


def _base() -> Dict[str, Any]:
    try:
        return core._read_knowledge("gencc_gene_disease.json") or {}
    except Exception:                                                # noqa: BLE001
        return {}


def _terms() -> Dict[str, Any]:
    try:
        return core._read_knowledge("system_disease_terms.json") or {}
    except Exception:                                                # noqa: BLE001
        return {}


def _labels(key: str) -> Dict[str, str]:
    return {code: CATALOGUES[code].get("radar.domain." + key, key)
            for code in ("en", "ru") if code in CATALOGUES}


def marker_systems() -> Dict[str, str]:
    """marker key → the first system whose score holds it, from the one domain file.

    A marker may count in two systems since 17.09.2026 (homocysteine in
    inflammation and in amino acids); the first in the file is its home, and
    `marker_systems_all` names every one.
    """
    out: Dict[str, str] = {}
    for d in domains():
        for m in d["markers"]:
            out.setdefault(m, d["key"])
    return out


def marker_systems_all() -> Dict[str, List[str]]:
    """marker key → every system whose score holds it, in the file's order."""
    out: Dict[str, List[str]] = {}
    for d in domains():
        for m in d["markers"]:
            out.setdefault(m, []).append(d["key"])
    return out


# ---- the class → system map (layer 4, and the prescription entry's join) ----
def class_systems() -> Dict[str, Any]:
    """Which system each class of prescription acts on, gated against the domains.

    A row naming a system the domain file does not hold is dropped and COUNTED:
    a typo in a system key would otherwise make a class act on nothing, in
    silence, which is the same defect as an unmapped class wearing a map.
    """
    try:
        book = core._read_knowledge("drug_class_systems.json") or {}
    except Exception:                                                # noqa: BLE001
        return {"classes": {}, "refused": 0, "source": None, "updated": None}
    known = {d["key"] for d in domains()}
    out: Dict[str, List[str]] = {}
    refused = 0
    for cls, spec in (book.get("classes") or {}).items():
        keys = [str(s) for s in (spec or {}).get("systems") or []] if isinstance(spec, dict) else []
        good = [k for k in keys if k in known]
        refused += len(keys) - len(good)
        if good:
            out[str(cls)] = good
    meta = book.get("_meta") or {}
    return {"classes": out, "refused": refused,
            "source": meta.get("purpose"), "updated": meta.get("updated")}


def prescriptions() -> List[Dict[str, Any]]:
    """The person's CURRENT prescriptions, each with its classes and the systems
    those classes act on — `map_status` says whether the map answered at all.

    Three states and none of them is an empty list: mapped (at least one class
    has a row), no_map (classes recognised, none of them in the map) and
    no_class (the dictionary recognised no class). The medications listing and
    the system card both read this, so a prescription is placed the same way
    on every face.
    """
    cmap = class_systems()["classes"]
    rows = []
    for m in core.active_medications():
        classes = core.classify_drug(m.get("name") or "")
        via = {c: cmap[c] for c in classes if c in cmap}
        systems_ = sorted({s for keys in via.values() for s in keys})
        rows.append({"name": m.get("name"), "dose": m.get("dose"), "status": m.get("status"),
                     "classes": classes, "via": via, "systems": systems_,
                     "map_status": ("mapped" if systems_ else
                                    "no_map" if classes else "no_class")})
    return rows


# ---- the base-generated monogenic half -------------------------------------
def _base_rows(key: str) -> Dict[str, Any]:
    """One row per gene the base composed for this system, every submitter kept.

    GenCC does not re-check its submitters, so two of them disagreeing on one
    gene are shown side by side and never averaged: `classifications` is the
    set, `finding_grade` says whether ANY assertion is strong enough to turn a
    finding, `recessive_only` whether every such assertion is recessive — the
    fact that decides what a heterozygous call means.
    """
    book = _base()
    meta = book.get("_meta") or {}
    spec = (book.get("systems") or {}).get(key)
    version = {"source": "GenCC", "version": meta.get("export_last_modified"),
               "downloaded": meta.get("downloaded"),
               "filter_version": meta.get("filter_version")}
    if not isinstance(spec, dict) or not spec.get("genes"):
        return {"status": "not_composed", "rows": [], **version}
    rows = []
    for gene, g in sorted((spec.get("genes") or {}).items()):
        subs = [s for s in (g or {}).get("submissions") or [] if isinstance(s, dict)]
        assertions = [{"disease": s.get("disease"), "disease_id": s.get("disease_id"),
                       "classification": s.get("classification"), "moi": s.get("moi"),
                       "moi_code": s.get("moi_code") or "unknown",
                       "submitter": s.get("submitter"), "curated_on": s.get("curated_on")}
                      for s in subs]
        grade = [a for a in assertions if a["classification"] in FINDING_GRADE]
        weaker = sum(1 for a in assertions if a["classification"] in NOT_A_FINDING)
        codes = sorted({a["moi_code"] for a in (grade or assertions)})
        rows.append({"unit": "gene", "origin": "base", "gene": gene.upper(),
                     "mode": "monogenic", "kind": None,
                     "source": f"GenCC {version['version'] or ''}".strip(),
                     "text": None, "pending": False,
                     "assertions": assertions,
                     "classifications": sorted({a["classification"] for a in assertions
                                                if a["classification"]}),
                     "finding_grade": bool(grade),
                     "moi_codes": codes,
                     "recessive_only": bool(grade) and all(c in RECESSIVE for c in codes),
                     "weaker_assertions": weaker,
                     "other_assertions": len(assertions) - len(grade) - weaker})
    return {"status": "composed", "rows": rows, "genes": len(rows),
            "source_text": spec.get("source"), **version}


def _clinvar_by_gene(scan: Dict[str, Any]) -> Dict[str, Any]:
    """Pathogenic-tier ClinVar hits of the person's file, grouped by gene, or the
    reason there are none to group."""
    if scan.get("status") != "ok":
        return {"status": scan.get("status"), "reason": scan.get("reason"), "by_gene": {}}
    from .genomics import clinvar_findings
    try:
        cv = clinvar_findings() or {}
    except Exception as exc:                                         # noqa: BLE001
        cv = {"status": "unavailable", "reason": type(exc).__name__}
    by: Dict[str, List[Dict[str, Any]]] = {}
    if cv.get("status") == "ok":
        for h in cv.get("hits") or []:
            if isinstance(h, dict) and h.get("tier") == "pathogenic":
                by.setdefault(str(h.get("gene") or "").upper(), []).append(h)
        return {"status": "ok", "reason": cv.get("reason"), "by_gene": by, "scanned": cv.get("scanned")}
    # The wide annotation is a pipeline step (bcftools) the person may not
    # have run; the product's own ACMG scan puts the file through ClinVar for
    # its 84 genes without either. On a full genome with only that scan, the
    # cards said «not put through ClinVar» of APOB and LDLR too — found
    # 13.09.2026 on a reference genome. For those genes the scan IS the
    # annotation; for every other gene the answer stays «not run».
    from .genomics import acmg_findings
    try:
        ac = acmg_findings() or {}
    except Exception as exc:                                         # noqa: BLE001
        ac = {"status": "unavailable", "reason": type(exc).__name__}
    if ac.get("status") == "ok":
        genes = {str(g).upper() for g in (core._read_knowledge("acmg_sf.json").get("genes") or {})}
        for h in ac.get("hits") or []:
            if not isinstance(h, dict):
                continue
            sig = str(h.get("clnsig") or "").lower()
            if h.get("reportable") or "pathogenic" in sig:
                by.setdefault(str(h.get("gene") or "").upper(), []).append(h)
        return {"status": "acmg_scan", "reason": cv.get("reason"), "by_gene": by,
                "genes": genes, "scanned": ac.get("scanned")}
    return {"status": cv.get("status") or "not_run", "reason": cv.get("reason"),
            "by_gene": by, "scanned": cv.get("scanned")}


def _finish_base_row(row: Dict[str, Any], scan: Dict[str, Any],
                     clinvar: Dict[str, Any]) -> Dict[str, Any]:
    """The person's file against one base gene: read, findings, carriership.

    «Read» for a base gene means two things at once — its bases were covered
    (the coverage table, judged against the file's own middle) AND its variants
    were put through ClinVar. Either missing, the gene is not read for this
    purpose, and `read_why` says which. A pathogenic heterozygote in a gene
    whose strong assertions are all recessive is a CARRIER, not a finding.
    """
    row = panel_form.gene_row(row["gene"], row, scan)
    if scan.get("status") != "ok":
        row["clinvar"] = {"status": clinvar.get("status"), "hits": 0, "withheld": 0}
        return row
    cov = row.get("coverage") or {}
    through_clinvar = clinvar.get("status") == "ok" or (
        clinvar.get("status") == "acmg_scan" and row["gene"] in (clinvar.get("genes") or set()))
    if not through_clinvar:
        code = clinvar.get("status") or "not_run"
        row["read"], row["read_why"] = False, "clinvar_" + ("not_run" if code == "acmg_scan" else str(code))
    else:
        row["read"], row["read_why"] = panel_form.bases_read(row["gene"], cov)
    hits = clinvar.get("by_gene", {}).get(row["gene"]) or []
    findings, carrier, withheld = 0, False, 0
    for h in hits:
        if not row["finding_grade"]:
            withheld += 1
        elif row["recessive_only"] and (h.get("zygosity") or "") != "hom":
            carrier = True
        else:
            findings += 1
    # Two different pathogenic variants in a gene whose disease needs two copies
    # (task 205 B): whether they sit on the two copies or on one cannot be told
    # from short reads, so the pair is a clinically significant result to be
    # phased, not two carriers' worth of «nothing to see».
    het_sites = {(h.get("chrom"), h.get("pos"), h.get("alt")) for h in hits
                 if row["finding_grade"] and (h.get("zygosity") or "") != "hom"}
    if row["recessive_only"] and len(het_sites) >= 2:
        carrier, findings = False, max(findings, 1)
        row["two_variants_text"] = _t("system.row.two_variants", gene=row["gene"])
    row["findings"], row["carrier"] = findings, carrier
    row["clinvar"] = {"status": ("ok" if through_clinvar and clinvar.get("status") == "acmg_scan"
                                 else clinvar.get("status")),
                      "via": "acmg_scan" if clinvar.get("status") == "acmg_scan" and through_clinvar else None,
                      "hits": len(hits), "withheld": withheld}
    row["read_state"] = panel_form.read_state(bool(row["read"]), row.get("read_why"))
    if row["read_state"] == "file_only":
        # The file read the gene; what is missing is the MEASUREMENT of how
        # deeply. Calling that «not read» said something false about the file
        # (owner, 17.09.2026), and the row says the true half instead.
        row["read"] = True
    row["read_why_text"] = _read_why_text(row.get("read_why"))
    # A gene whose bases were never measured is not read — and the file still
    # said something about it. Until 17.09.2026 the row printed the gap and
    # dropped the answer: after a base grew, a gene waited for a coverage table
    # (and therefore for an alignment, which not everybody has) before it would
    # say that the file holds nothing pathogenic in it. What the file says is
    # said now, with what settles it named beside it — never as «read».
    if through_clinvar and row["read_state"] == "file_only":
        row["file_says"] = {"variants": len(hits), "findings": findings, "carrier": carrier}
        row["file_says_text"] = _t(
            "system.row.file_says_found" if findings else
            "system.row.file_says_carrier" if carrier else "system.row.file_says_clear",
            gene=row["gene"], variants=_plural(findings or len(hits), "count.variants"))
    return row


# ---- the curated positions -------------------------------------------------
_HGVS = panel_gate.HGVS


def _loc_from_hgvs(hgvs: str, rsid: str, gene: str) -> Optional[Dict[str, Any]]:
    """A locus the genome reader can take, from a RefSeq g. HGVS — SNVs only.

    The curated catalogue holds pharmacogenetic loci, not a gene index, and a
    panel a clinician sends is addressed by rsID and HGVS. When the rsID is not
    in the catalogue the coordinate in the HGVS is what there is, and it is
    GRCh38 by the accession. An indel HGVS returns None here on purpose: the
    reader's indel handling is task 172's, and a wrong coordinate is worse than
    an unread position.
    """
    m = _HGVS.match((hgvs or "").strip())
    if not m:
        return None
    acc, pos, ref, alt = m.groups()
    n = int(acc[3:])
    chrom = {23: "X", 24: "Y"}.get(n, str(n)) if acc != "NC_012920" else "MT"
    return {"rsid": rsid, "gene": gene, "chrom": chrom, "pos": int(pos),
            "ref": ref, "alt": alt, "source": "hgvs"}


def _fill_absent(row: Dict[str, Any], geno: Dict[str, Any]) -> str:
    tpl = ((_curated().get("_meta") or {}).get("absent_template") or {}).get("text")
    tpl = panel_form.one_language(tpl) or "{gene} {rsid}: absent ({confidence}, {depth})"
    try:
        return tpl.format(gene=row.get("gene"), rsid=row.get("rsid"),
                          confidence=geno.get("confidence") or "—",
                          depth=geno.get("depth") if geno.get("depth") is not None else "—")
    except (KeyError, IndexError):
        return tpl


def _corridor(low, high) -> str:
    """The reference interval as a person writes it, with one bound missing.

    «выше коридора —–3.0» stood on the lipid card: an em dash for the absent
    lower bound, then the en dash of the interval, then the number. A corridor
    open at one end is written by naming the end it has.
    """
    if low is not None and high is not None:
        return f"{low}–{high}"
    if high is not None:
        return _t("system.corridor.up_to", high=high)
    if low is not None:
        return _t("system.corridor.from", low=low)
    return "—"


def _expect_check(exp: Dict[str, Any], by_key: Dict[str, Any]) -> Dict[str, Any]:
    """The author's expectation next to the person's numbers — a question's data.

    Arithmetic only: the last value, its corridor, where the value sits in it,
    and the movement from the previous point. Whether that agrees with the
    expectation is not decided here; the origin of the sentence is the author,
    and the engine fills in the numbers. A marker never taken is a GAP.
    """
    marker = str(exp.get("marker") or "")
    m = by_key.get(marker)
    out = {"marker": marker, "direction": exp.get("direction"),
           "note": panel_form.one_language(exp.get("note")) or None}
    if not m:
        return {**out, "gap": True}
    lo, hi, v = m.get("ref_low"), m.get("ref_high"), m.get("value")
    position = "unknown"
    if isinstance(v, (int, float)):
        if isinstance(lo, (int, float)) and v < lo:
            position = "below"
        elif isinstance(hi, (int, float)) and v > hi:
            position = "above"
        elif isinstance(lo, (int, float)) or isinstance(hi, (int, float)):
            position = "within"
    series = m.get("series") or []
    prev = series[-2] if len(series) >= 2 else None
    return {**out, "gap": False, "name": m.get("name"), "value": v, "unit": m.get("unit"),
            "date": m.get("date"), "ref_low": lo, "ref_high": hi, "position": position,
            "from_value": prev.get("value") if prev else None,
            "from_date": prev.get("date") if prev else None}


def _level_counts(rows: List[Dict[str, Any]]) -> Dict[str, int]:
    """How many positions stand at each level, and how many have none yet."""
    out: Dict[str, int] = {}
    for r in rows:
        if r.get("unit") == "position":
            k = r.get("level") or "none"
            out[k] = out.get(k, 0) + 1
    return out


def _levels() -> Optional[Dict[str, Any]]:
    """The legend of evidence levels, when the build carries one (task 199)."""
    return {x["level"]: x for x in panel_gate.legend().get("levels") or []} or None


def _curated_rows(key: str, spec: Dict[str, Any], markers: List[str],
                  scan: Dict[str, Any], by_key: Dict[str, Any]) -> Dict[str, Any]:
    """The clinician's positions through the gate, each with the person's state.

    Every refusal is counted BY REASON: a row dropped for lacking a mode and a
    row dropped for naming a marker outside the panel are different mistakes,
    and one number for both would send the author to the wrong field.
    """
    refused: Dict[str, int] = {}
    rows: List[Dict[str, Any]] = []
    sys_source = panel_form.one_language(spec.get("source"))
    levels = _levels()
    has_bam = _has_alignment() if scan.get("status") == "ok" else False
    for p in spec.get("positions") or []:
        source = (panel_form.one_language(p.get("source")) if isinstance(p, dict) else "") or sys_source
        why = panel_gate.refusal(p, markers, sys_source, source, levels,
                                 links=spec.get("links"))
        if why:
            refused[why] = refused.get(why, 0) + 1
            continue
        mode, kind = p.get("mode"), p.get("kind")
        exp = p.get("expect") if isinstance(p.get("expect"), dict) else None
        gene = str(p.get("gene") or "").upper()
        geno = _genotype(str(p["rsid"]), str(p.get("hgvs") or ""), gene,
                         panel_gate.risk_on_plus(p), scan, panel_gate.locus(p), has_bam=has_bam)
        x_one = _pg.on_x(p)
        if x_one:
            # A man's X is one copy: «one copy» there is all of it (task 205 B).
            geno = _pg.as_hemizygous(geno, core.profile_sex())
        state = geno.get("state")
        texts = p.get("text") if isinstance(p.get("text"), dict) else {}
        text = None
        pending, pending_why = False, None
        if state in ("het", "hom", "hemi"):
            text = panel_form.one_language(texts.get(state)) or None
            if not text:
                pending, pending_why = True, "no_text_for_state"
        elif state == "absent" and geno.get("presumed"):
            # A presumption about the reference is a presumption about the
            # absence of a risk: it always turns «unknown» into good news. So the
            # caveat stands inside the sentence — a footnote is read once, a
            # conclusion every time (task 201).
            text = _t("system.row.presumed_absent", gene=gene, rsid=p["rsid"])
        elif state == "absent":
            text = _fill_absent({"gene": gene, "rsid": p["rsid"]}, geno)
        elif state == "risk_allele_not_declared":
            pending, pending_why = True, "risk_allele"
        cls, moi = p.get("classification"), p.get("moi")
        carrier = (mode == "monogenic" and state == "het" and moi in RECESSIVE)
        finding = 0
        not_why = None
        presumed = bool(geno.get("presumed"))
        if presumed and state in ("hom", "hemi"):
            text = _t("system.row.presumed_" + state, gene=gene, rsid=p["rsid"])
        lv = panel_gate.level_of(p, levels)
        confirm = state in ("het", "hom", "hemi") and panel_gate.needs_confirmation(p, scan.get("input_profile"))
        if confirm:
            # The author's sentence describes a variant that is there; off a chip
            # it most often is not, so the row says what to do first instead.
            not_why, text, pending, pending_why = "needs_confirmation", _t(
                "system.row.needs_confirmation_text", gene=gene, rsid=p["rsid"],
                input=scan.get("input_profile") or "—"), False, None
        elif presumed:
            # A value the reference implies is not a reading: it is shown, and
            # it is never a finding or a carriership.
            not_why, carrier = "presumed", False
        elif state in ("het", "hom", "hemi") and text:
            if mode == "monogenic":
                if cls in NOT_A_FINDING or cls not in FINDING_GRADE:
                    not_why = "classification"
                elif carrier:
                    not_why = "carrier"
                else:
                    finding = 1
            elif kind in ("asked_about", "no_variant", "mechanism"):
                # The author's own kind of link says nothing follows: the row is
                # printed with its sentence and is not a finding. COMT Val/Met on
                # a reference genome read as «something reportable was found»
                # until 13.09.2026 — the sentence beside it said the opposite.
                not_why = "kind"
            else:
                finding = 1
            if finding and not lv["verdict_allowed"]:
                # A conclusion is printed at A and B only; a row with no level,
                # or a lower one, keeps its value and loses the verdict (task 199).
                finding, not_why = 0, "level"
        row = {"unit": "position", "origin": "curated", "gene": gene, "state": state,
               **lv, "evidence": p.get("evidence"),
               "ladder": (_pg.hemizygous_ladder(panel_gate.ladder(p)) if geno.get("hemizygous")
                          else panel_gate.ladder(p)),
               "ladder_refused": p.get("ladder") == "refused",
               "hemizygous": bool(geno.get("hemizygous")), "on_x": x_one,
               "rsid": p["rsid"], "hgvs": p.get("hgvs"), "strand": p.get("strand") or "+", "protein": p.get("protein"),
               "link": p.get("link"), "link_text": _link_text(p.get("link"), spec.get("links")),
               "under_load": _under_load(p.get("under_load"), spec.get("load_tests")),
               "route": _route(p.get("route"), spec.get("routes")),
               "risk_allele": p.get("risk_allele"), "mode": mode, "kind": kind,
               "classification": cls, "moi": moi, "disease": p.get("disease"),
               "effect_size": p.get("effect_size"), "study": p.get("study"),
               "source": source, "submitter": p.get("submitter"),
               "curated_on": p.get("curated_on"), "base_version": p.get("base_version"),
               # WHO reviewed the phrase against its source, by role and never
               # by name (task 199; until then the file held `signed_by`). The
               # STATE travels on the row and the wording belongs to the
               # renderer. A role the engine does not know is refused at the
               # gate, so it never reads as a review.
               "signature": panel_gate.review_state(p),
               "signed_on": panel_gate.reviewed_on(p),
               "review": p.get("review"),
               "text": text, "pending": pending, "pending_why": pending_why,
               "findings": finding, "not_a_finding_why": not_why, "carrier": carrier and not confirm,
               "needs_confirmation": confirm,
               "caveat": "moderate" if (finding and cls == "Moderate") else None,
               "genotype": geno, "read": geno.get("read"),
               "read_why": geno.get("why") if geno.get("read") is False else None,
               "expect_check": _expect_check(exp, by_key) if exp else None,
               "next_step": p.get("next_step") if isinstance(p.get("next_step"), dict)
               and p["next_step"].get("kind") in BASKETS else None}
        row = panel_form.gene_row(gene, row, scan)
        row["read"] = geno.get("read")          # the position's own reading, not the gene's
        row["read_state"] = panel_form.read_state(bool(row["read"]), row.get("read_why"))
        if row["read"] is True and geno.get("depth_unverified"):
            row["read_state"] = "file_only"
            row["depth_note"] = _t("system.row.depth_unverified")
        row["presumed"] = bool(geno.get("presumed"))
        if row["presumed"]:
            row["closes_text"] = _closes_text("presumed_ref")
        row["read_why_text"] = _read_why_text(row.get("read_why"))
        rows.append(row)
    # What short reads cannot read in this system — a gene beside its
    # pseudogene, a repeat — named with the reason and a source; without a
    # source it is counted and not applied, like an exclusion (13.09.2026).
    unreadable = []
    for name, u in (spec.get("unreadable") or {}).items() if isinstance(spec.get("unreadable"), dict) else []:
        src = panel_form.one_language((u or {}).get("source")) if isinstance(u, dict) else ""
        if not src:
            refused["unreadable_without_source"] = refused.get("unreadable_without_source", 0) + 1
            continue
        unreadable.append({"gene": str(name), "reason": panel_form.one_language(u.get("reason")) or None,
                           "source": src})
    excluded, exclusions = [], spec.get("exclusions") or {}
    for gene, e in (exclusions.items() if isinstance(exclusions, dict) else []):
        src = panel_form.one_language((e or {}).get("source")) if isinstance(e, dict) else ""
        if not src:
            refused["exclusion_without_source"] = refused.get("exclusion_without_source", 0) + 1
            continue
        excluded.append({"gene": str(gene).upper(),
                         "reason": panel_form.one_language(e.get("reason")) or None,
                         "source": src, "signed_on": panel_gate.reviewed_on(e or {})})
    return {"rows": rows, "refused": refused, "excluded": excluded, "unreadable": unreadable,
            "source": sys_source or None}


# ---- the polygenic layer of a system (task 178) ------------------------------
def prs_system_map() -> Dict[str, Any]:
    """Pinned trait → system, gated against both registries.

    A trait the model registry does not pin, or a system the domain file does
    not hold, is dropped and COUNTED: a typo in either name would otherwise
    place a score on nothing, in silence — the same defect as an unmapped
    class wearing a map (`class_systems`).
    """
    try:
        book = core._read_knowledge("prs_system_map.json") or {}
        pinned = set((core._read_knowledge("prs_models.json") or {}).get("models") or {})
    except Exception:                                                # noqa: BLE001
        return {"systems": {}, "refused": 0, "updated": None}
    known = {d["key"] for d in domains()}
    out: Dict[str, Dict[str, Any]] = {}
    refused = 0
    for key, spec in (book.get("systems") or {}).items():
        traits = [str(x) for x in (spec or {}).get("traits") or []] if isinstance(spec, dict) else []
        if key not in known:
            refused += len(traits) or 1
            continue
        good = [x for x in traits if x in pinned]
        refused += len(traits) - len(good)
        out[str(key)] = {"traits": good,
                         "why_empty": panel_form.one_language(spec.get("why_empty")) or None}
    meta = book.get("_meta") or {}
    return {"systems": out, "refused": refused, "updated": meta.get("updated")}


def _prs_findings_safe() -> Dict[str, Any]:
    from .genomics import prs_findings
    try:
        return prs_findings() or {}
    except Exception as exc:                                         # noqa: BLE001
        return {"available": False, "status": type(exc).__name__}


def _polygenic_block(key: str, findings: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """The common variation of a system, AS SCORES — brief §5.0, rule 4.

    The rows are `prs_findings` filtered through the map: the percentile, the
    evidence tier and the trust flag are that layer's, not recomputed here. A
    reliable score at or above the 80th percentile is named in `high` and
    becomes one question; an unreliable one keeps its note and raises none.
    Nothing in this block reaches the verdict or the 0–100 score: a percentile
    inside a reference panel is neither a finding about a gene nor a
    measurement the next blood draw could refute.
    """
    spec = prs_system_map()["systems"].get(key) or {}
    traits = spec.get("traits") or []
    if not traits:
        return {"status": "no_map", "rows": [], "high": [], "mapped": 0, "scored": 0,
                "unscored": [], "why": spec.get("why_empty") or _t("system.polygenic.no_map")}
    if findings is None:
        findings = _prs_findings_safe()
    if not findings.get("available"):
        return {"status": "no_scores", "rows": [], "high": [], "mapped": len(traits),
                "scored": 0, "unscored": list(traits),
                "reason": findings.get("status") or "not_computed",
                "why": _t("system.polygenic.no_scores")}
    models = (core._read_knowledge("prs_models.json") or {}).get("models") or {}
    by_term: Dict[str, Dict[str, Any]] = {}
    for cat in findings.get("categories") or []:
        for t_ in (cat or {}).get("traits") or []:
            term = str((t_ or {}).get("term") or t_.get("trait") or "").strip().lower()
            if term:
                by_term[term] = t_
    rows: List[Dict[str, Any]] = []
    high: List[str] = []
    for name in traits:
        t_ = by_term.get(name.lower())
        if not t_:
            continue
        m = models.get(name) or {}
        p = t_.get("percentile")
        p = (int(p) if float(p).is_integer() else round(float(p), 1)) \
            if isinstance(p, (int, float)) else None
        row = {"trait": name,
               "label": t_.get("label") or panel_form.one_language(m.get("label")) or name,
               "pgs_id": t_.get("pgs_id") or m.get("pgs_id"), "percentile": p,
               "evidence": t_.get("evidence"), "evidence_label": t_.get("evidence_label"),
               "reliable": bool(t_.get("reliable"))}
        for k in ("validity_note", "integrity_note", "weight_mass_note", "evidence_note",
                  "model_changed_from"):
            if t_.get(k):
                row[k] = t_[k]
        rows.append(row)
        if row["reliable"] and p is not None and p >= POLYGENIC_HIGH_PERCENTILE:
            high.append(name)
    rows.sort(key=lambda r: -(r["percentile"] if r["percentile"] is not None else -1))
    scored = {r["trait"] for r in rows}
    return {"status": "ok", "rows": rows, "high": high, "mapped": len(traits),
            "scored": len(rows), "unscored": [x for x in traits if x not in scored],
            "caveat": _t("system.polygenic.caveat")}


# ---- the layers -------------------------------------------------------------
def _radar_domain(key: str) -> Optional[Dict[str, Any]]:
    from .lifestyle import health_radar
    for d in (health_radar().get("domains") or []):
        if d.get("key") == key:
            return d
    return None


def _labs_layer(dom: Dict[str, Any], rd: Optional[Dict[str, Any]],
                by_key: Dict[str, Any]) -> Dict[str, Any]:
    if rd is None:
        return {"status": "absent", "source": dom["source"]}
    stale = [{"key": k, "name": by_key[k].get("name"), "date": by_key[k].get("date")}
             for k in dom["markers"] if k in by_key
             and by_key[k].get("date") and not _recent(by_key[k].get("date"), STALE_MONTHS)]
    return {"status": "nodata" if rd.get("score") is None else "ok",
            "source": dom["source"], "score": rd.get("score"), "level": rd.get("status"),
            "ok": rd.get("ok"), "abnormal": rd.get("abnormal") or [],
            "measured": rd.get("measured"), "total": rd.get("total"),
            "missing": rd.get("missing") or [],
            # The keys stay for the joins; the names are what a reader sees.
            # Layer 7 already printed names for the same gap while this layer
            # printed `cholesterol_total` — one card, two spellings of one fact.
            "missing_names": [_marker_name(k) for k in (rd.get("missing") or [])],
            "stale": stale, "panel": panel_labs.panel_view(dom, by_key),
            "panel_term": rd.get("panel")}


def _dynamics_layer(rd: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if rd is None:
        return {"status": "absent"}
    if rd.get("prev_score") is None:
        return {"status": "no_previous", "compared": rd.get("compared") or 0}
    return {"status": "ok", "prev_score": rd.get("prev_score"),
            "compared_score": rd.get("compared_score"), "delta": rd.get("delta"),
            "prev_date": rd.get("prev_date"), "compared": rd.get("compared"),
            "moved": rd.get("moved") or []}


def _medications_layer(key: str) -> Dict[str, Any]:
    """Layer 4: the current prescriptions whose class acts on this system.

    Only CURRENT ones — the same rule the interaction check uses — and the
    ones the map does not place are listed as unmapped rather than left out: a
    prescription silently absent from every system's card would read as one
    that acts on nothing.
    """
    rows, unmapped, unclassified = [], [], []
    for p in prescriptions():
        if key in p["systems"]:
            rows.append({**{k: p[k] for k in ("name", "dose", "status", "classes")},
                         "via": sorted(c for c, keys in p["via"].items() if key in keys),
                         "map_status": "mapped"})
        elif p["map_status"] == "no_map":
            unmapped.append({"name": p["name"], "classes": p["classes"], "map_status": "no_map"})
        elif p["map_status"] == "no_class":
            unclassified.append({"name": p["name"], "map_status": "no_class"})
    cmap = class_systems()
    why = None
    if not rows:
        why = "no_current_prescriptions" if not core.active_medications() else "none_acts_here"
    return {"status": "ok" if rows else "empty", "rows": rows, "unmapped": unmapped,
            "unclassified": unclassified, "empty_why": why,
            "empty_reason": _t("system.why." + why) if why else None,
            "map": {"classes_mapped": len(cmap["classes"]), "refused": cmap["refused"],
                    "updated": cmap["updated"]}}


def _target_spec(tg: Dict[str, Any]) -> str:
    lo, hi, one = tg.get("low"), tg.get("high"), tg.get("value")
    f = lambda x: f"{float(x):g}"          # noqa: E731 — one formatter, four branches
    if lo is not None and hi is not None:
        return _t("target.spec_range", low=f(lo), high=f(hi))
    if hi is not None:
        return _t("target.spec_max", high=f(hi))
    if lo is not None:
        return _t("target.spec_min", low=f(lo))
    return _t("target.spec_value", value=f(one)) if one is not None else ""


def _target_layer(dom: Dict[str, Any], by_key: Dict[str, Any]) -> Dict[str, Any]:
    """Layer 5: the clinician's targets on this system's markers (task 170).

    Read through the same two functions the labs report uses, so the side a
    value stands on is decided once. `in_corridor` travels beside
    `outside_target` because the question this layer exists to ask is the
    conjunction: normal by the laboratory, not where the treatment is aiming.
    """
    from .targets import outside_target, target_view
    targets = core.clinician_targets_by_marker()
    rows = []
    for k in dom["markers"]:
        tg = targets.get(k)
        if not tg:
            continue
        m = by_key.get(k)
        value = m.get("value") if m else None
        rows.append({"marker": k, "name": (m or {}).get("name") or _marker_name(k),
                     **target_view(tg, value), "spec": _target_spec(tg),
                     "current": ({"value": value, "unit": m.get("unit"), "date": m.get("date"),
                                  "flag": m.get("flag"), "ref_low": m.get("ref_low"),
                                  "ref_high": m.get("ref_high")} if m else None),
                     "outside_target": outside_target(tg, value) if m else None,
                     "in_corridor": (m.get("flag") == "ok") if m else None})
    why = None if rows else ("no_lab_half" if dom["source"] != "labs" else "no_target_set")
    return {"status": "ok" if rows else "empty", "rows": rows, "empty_why": why,
            "empty_reason": _t("system.why." + why) if why else None,
            "to_discuss": [r["marker"] for r in rows if r["outside_target"] and r["in_corridor"]]}


def _rule_markers(rule: Dict[str, Any]) -> set:
    """Every marker key a test rule touches — in its condition or in `covers`."""
    out = set(str(x) for x in (rule.get("covers") or []))

    def walk(cond):
        if isinstance(cond, dict):
            if cond.get("marker"):
                out.add(str(cond["marker"]))
            for v in cond.values():
                walk(v)
        elif isinstance(cond, list):
            for v in cond:
                walk(v)
    walk(rule.get("when"))
    return out


def _tests_layer(markers: List[str]) -> Dict[str, Any]:
    """Layer 6: the rules that fired and touch a marker of THIS system.

    The list is owned by `suggest_tests` — the same rows the route prints —
    and only filtered here; a copy with its own rules would drift.
    """
    from .labs import suggest_tests
    rules = {r.get("id"): r for r in (core.test_rules().get("rules") or [])}
    rows = []
    for item in (suggest_tests().get("suggestions") or []):
        hit = sorted(_rule_markers(rules.get(item.get("id")) or {}) & set(markers))
        if hit:
            rows.append({**item, "markers_hit": hit})
    return {"status": "ok", "rows": rows,
            "empty_why": None if rows else "no_rule_fired"}


def _link_text(link, links) -> Optional[str]:
    """The name of the chain link in the reader's language — the file carries
    both, because a link is a heading a person reads, not a code."""
    if not link or not isinstance(links, dict):
        return None
    return panel_form.one_language((links.get(link) or {})) or None


def _route(block, names) -> Optional[Dict[str, Any]]:
    """How the same position reads on the three routes protein can arrive by.

    A drip removes the gut and the first pass through the liver; free amino
    acids remove the digestion of protein and the peptide path and put
    everything through one transporter. So the same genotype is not equally
    important on all three, and the row says which — with the basis it rests
    on, because most of these are mechanism rather than a measured comparison.
    """
    if not isinstance(block, dict):
        return None
    out = []
    for name in ("food", "oral_free", "iv"):
        state = block.get(name)
        out.append({"route": name,
                    "route_text": panel_form.one_language((names or {}).get(name) or {}) or name,
                    "state": state, "state_text": _t("system.panel.route." + str(state))})
    return {"routes": out, "basis": block.get("basis"), "source": block.get("source")}


def _under_load(block, names) -> Optional[Dict[str, Any]]:
    """A position a fasting corridor cannot answer for: the load that shows it.

    The whole product reads a person at rest (task 200). Where a source says the
    state is only visible under a load, the position says which load and what it
    would reveal — and never that the load should be done.
    """
    if not isinstance(block, dict):
        return None
    test = block.get("test")
    return {"test": test,
            "test_text": panel_form.one_language((names or {}).get(test) or {}) or test,
            "what_it_reveals": panel_form.one_language(block.get("what_it_reveals")) or None}


def _position_state(r: Dict[str, Any]) -> Dict[str, Any]:
    """One panel position as a state, kept in EVERY register. The patient's
    density withholds the rows where nothing was found, and the page then
    showed two rows of a seven-position panel with no word about the other
    five — as if they had not been checked (owner, 14.09.2026)."""
    ec = r.get("expect_check") if isinstance(r.get("expect_check"), dict) else None
    return {"gene": r.get("gene"), "rsid": r.get("rsid"), "kind": r.get("kind"),
            "state": r.get("state"), "read": r.get("read"), "read_why": r.get("read_why"),
            "read_why_text": r.get("read_why_text"), "text": r.get("text"),
            "level": r.get("level"), "level_short": r.get("level_short"), "ladder": r.get("ladder"),
            "link": r.get("link"), "link_text": r.get("link_text"), "under_load": r.get("under_load"),
            "read_state": r.get("read_state"), "presumed": r.get("presumed"),
            "closes_text": r.get("closes_text"), "depth_note": r.get("depth_note"),
            "local_note": r.get("local_note"), "group": r.get("group"),
            "route": r.get("route"),
            "not_a_finding_why": r.get("not_a_finding_why"), "needs_confirmation": r.get("needs_confirmation"),
            "genotype": r.get("genotype"), "unit": "position",
            "expect": {k: ec.get(k) for k in ("marker", "name", "direction", "gap", "position")} if ec else None}


def _genetics_layer(dom: Dict[str, Any], by_key: Dict[str, Any]) -> Dict[str, Any]:
    """Layer 3: the base composition and the curated positions, merged and gated."""
    key = dom["key"]
    if not dom["genetic_half"]:
        scan = {"status": "no_genetic_half", "reason": "no_genetic_half"}
        v = panel_form.verdict([], scan)
        return {"status": "no_genetic_half", "rows": [], "scan": scan,
                "polygenic": {"status": "no_genetic_half", "rows": [], "high": [],
                              "mapped": 0, "scored": 0, "unscored": []},
                "verdict": v, "verdict_line": panel_form.verdict_line(v)}
    base = _base_rows(key)
    # Beside the list, never merged with it: the rows below are genes and
    # positions; this block is scores, and the two print under separate heads.
    poly = _polygenic_block(key)
    cur_spec = (_curated().get("systems") or {}).get(key)
    cur_spec = cur_spec if isinstance(cur_spec, dict) else None
    excluded_genes: set = set()
    composed = base["status"] == "composed" or bool(cur_spec and cur_spec.get("positions"))
    if not composed:
        why = panel_form.one_language(((_terms().get("systems") or {}).get(key) or {}).get("why_empty")) \
            or panel_form.one_language((_curated().get("_meta") or {}).get("why_empty"))
        scan = {"status": "no_panel", "reason": "no_panel"}
        v = panel_form.verdict([], scan)
        return {"status": "not_composed", "why_empty": why, "rows": [], "scan": scan,
                "base": {k: base[k] for k in ("source", "version", "downloaded", "filter_version")},
                "curated": {"status": "empty",
                            "why_empty": panel_form.one_language((_curated().get("_meta") or {}).get("why_empty"))},
                "polygenic": poly,
                "verdict": v, "verdict_line": panel_form.verdict_line(v)}
    genes = [r["gene"] for r in base["rows"]]
    genes += [str(p.get("gene") or "").upper() for p in ((cur_spec or {}).get("positions") or [])
              if isinstance(p, dict)]
    scan = panel_form.scan_for(genes)
    clinvar = _clinvar_by_gene(scan)
    cur = _curated_rows(key, cur_spec or {}, dom["markers"], scan, by_key) \
        if cur_spec else {"rows": [], "refused": {}, "excluded": [], "unreadable": [], "source": None}
    excluded_genes = {e["gene"] for e in cur["excluded"]}
    rows = [_finish_base_row(r, scan, clinvar) for r in base["rows"]
            if r["gene"] not in excluded_genes]
    # A gene short reads cannot read is never «read» and never «clear»: the
    # method, not the person, is what the answer is about (owner, 13.09.2026).
    unreadable_genes = {u["gene"].upper() for u in cur["unreadable"]}
    for r in rows:
        if r["gene"] in unreadable_genes and r.get("read") is not False or (
                r["gene"] in unreadable_genes and r.get("read_why") != "separate_method"):
            r["read"], r["read_why"] = False, "separate_method"
            r["read_state"] = "unread"
            r["read_why_text"] = _read_why_text("separate_method")
            r.pop("file_says", None); r.pop("file_says_text", None)
            r["findings"], r["carrier"] = 0, False
    classes = (cur_spec or {}).get("carrier_classes")
    if isinstance(classes, dict):
        for r in rows:
            panel_form.carrier_class(r, classes, core.profile_sex(), clinvar.get("by_gene", {}).get(r["gene"]) or [])
    rows += cur["rows"]
    # The panel first — the positions a clinician acts on — and the base list
    # after it; within each, by gene.
    rows.sort(key=lambda r: (r["unit"] != "position", r["gene"], r.get("rsid") or ""))
    v = panel_form.verdict(rows, scan)
    _attach_local_notes(rows)
    groups = _groups(key, (_curated().get("systems") or {}).get(key) or {}, rows)
    return {"status": "composed", "rows": rows, "scan": scan,
            "groups": [g for g in groups if not g.get("refused")],
            "groups_refused": {g["key"]: g["refused"] for g in groups if g.get("refused")},
            "positions": [_position_state(r) for r in rows if r["unit"] == "position"],
            "base": {**{k: base[k] for k in ("status", "source", "version", "downloaded",
                                               "filter_version")},
                     "genes": base.get("genes", 0), "source_text": base.get("source_text")},
            "curated": {"status": "ok" if cur["rows"] else "empty", "source": cur["source"],
                        "positions": len(cur["rows"]),
                        "why_empty": None if cur["rows"]
                        else panel_form.one_language((_curated().get("_meta") or {}).get("why_empty"))},
            "excluded": cur["excluded"],
            "unreadable": cur["unreadable"],
            "refused": {"total": sum(cur["refused"].values()), "by_reason": cur["refused"]},
            "read_count": sum(1 for r in rows if r.get("read") is True),
            "unread_count": sum(1 for r in rows if r.get("read") is False),
            "finding_count": sum(int(r.get("findings") or 0) for r in rows),
            "carrier_count": sum(1 for r in rows if r.get("carrier")),
            "pending_count": sum(1 for r in rows if r.get("pending")),
            "read_genes": sum(1 for r in rows if r.get("unit") != "position" and r.get("read") is True),
            "depthless_genes": sum(1 for r in rows if r.get("unit") != "position" and r.get("read_state") == "file_only"),
            "read_positions": sum(1 for r in rows if r.get("unit") == "position" and r.get("read") is True),
            "signature_open_count": sum(1 for r in rows if r.get("signature") == "open"),
            "level_counts": _level_counts(rows),
            "signature_author_count": sum(1 for r in rows if r.get("signature") == "author"),
            "signature_author_date": max([str(r.get("signed_on")) for r in rows
                                          if r.get("signature") == "author" and r.get("signed_on")],
                                         default=None),
            "withheld_by_classification": sum((r.get("clinvar") or {}).get("withheld", 0)
                                              for r in rows if r["unit"] == "gene")
            + sum(1 for r in rows if r.get("not_a_finding_why") == "classification"),
            "clinvar": {"status": clinvar.get("status"), "reason": clinvar.get("reason")},
            "polygenic": poly,
            "verdict": v, "verdict_line": panel_form.verdict_line(v)}


def _read_why_text(code) -> Optional[str]:
    """The reason a gene or a position was not read, as a sentence in the
    reader's language — the code (`clinvar_not_run`) printed as such on every
    row and every basket line until 13.09.2026."""
    if not code:
        return None
    text = _t("system.read_why." + str(code))
    return str(code) if text.startswith("⟦") else text


def _closes_text(code) -> Optional[str]:
    """What closes a reason, when a step is known for it."""
    if not code:
        return None
    text = _t("system.closes." + str(code))
    return None if text.startswith("⟦") else text


def _genome_reason_text(reason) -> str:
    """The genome frame's refusal in the reader's language, not its code:
    `no_file` printed as such after the dash until 13.09.2026."""
    key = "genome.refused_head." + str(reason)
    text = _t(key)
    return str(reason) if text.startswith("⟦") else text.rstrip(".")


def _marker_name(key: str) -> str:
    """A marker's display name from the dictionary, in the reader's language —
    the marker was never measured, so there is no row of the person's to ask."""
    from ..i18n import lang as _lang
    known = (core.lab_markers().get("markers") or {})
    return core.marker_display(known.get(key) or {}, _lang() or "en", key) or key


def _questions(gen: Dict[str, Any], labs: Dict[str, Any], tests: Dict[str, Any],
               by_key: Dict[str, Any], target: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Layer 7: what to discuss with a clinician, each with the origin it came from.

    Printed as questions — no imperative, no conclusion. The engine originates
    a question only from a gap it can count, from an author's declared
    expectation with the person's numbers under it, or from a figure the
    clinician set that the person's value stands outside of.
    """
    rows: List[Dict[str, Any]] = []
    for tr in (target or {}).get("rows") or []:
        # Asked only where the corridor is silent: a value the laboratory has
        # already flagged stands in layer 1, and two lines about one number
        # would be noise rather than a second question.
        if tr.get("outside_target") and tr.get("in_corridor"):
            cur = tr.get("current") or {}
            rows.append({"origin": "target", "marker": tr["marker"],
                         "text": _t("system.q.target", marker=tr.get("name") or tr["marker"],
                                    value=cur.get("value"), unit=cur.get("unit") or "",
                                    date=cur.get("date") or "—",
                                    low=cur.get("ref_low") if cur.get("ref_low") is not None else "—",
                                    high=cur.get("ref_high") if cur.get("ref_high") is not None else "—",
                                    side=_t("target.side_above" if tr.get("side") == "above"
                                            else "target.side_below"),
                                    spec=tr.get("spec") or "", set_by=tr.get("set_by") or "",
                                    set_on=tr.get("set_on") or ""),
                         "data": tr})
    # Positions whose author expects a direction on a marker nobody has taken,
    # gathered BY MARKER. One question per position repeated the same «take LDL»
    # five times on the lipid card of a profile with no labs (13.09.2026); the
    # clinician needs one question naming the positions that wait on it.
    waiting: Dict[str, List[str]] = {}
    for r in gen.get("rows") or []:
        g, rs = r.get("gene"), r.get("rsid")
        ec = r.get("expect_check")
        if ec and ec.get("gap"):
            waiting.setdefault(ec["marker"], []).append(f"{g} {rs}")
        elif ec and str(r.get("state")) not in ("het", "hom", "hemi"):
            # «The author expects LDL higher WITH THIS GENOTYPE» was asked of a
            # position read as ABSENT — a question about a genotype the person
            # does not carry. On the owner's lipid card four of the five
            # questions were of that kind, and they buried the fifth, which was
            # the one he carries (13.09.2026). An expectation is a claim about
            # the named allele; without it there is nothing to agree or disagree
            # with, and the row already prints that the allele was not found.
            pass
        elif ec and r.get("read") is not True:
            # «The author expects LDL to be higher WITH THIS GENOTYPE» was
            # printed for a position nobody had read: on the demo profile, whose
            # genome is not readable at all, five such questions stood on the
            # lipid card (13.09.2026). The expectation is about a genotype, and
            # there is no genotype until the position is read — the position is
            # already named in the genome basket as unread, which is the true
            # next step, so nothing is lost by not asking.
            pass
        elif ec:
            rows.append({"origin": "expect", "gene": g, "rsid": rs, "marker": ec["marker"],
                         "text": _t("system.q.expect", gene=g, rsid=rs,
                                    marker=ec.get("name") or ec["marker"],
                                    direction=_t("system.direction." + str(ec.get("direction"))),
                                    value=ec.get("value"), unit=ec.get("unit") or "",
                                    date=str(ec.get("date") or "—")[:10],
                                    position=_t("system.position." + ec["position"]),
                                    corridor=_corridor(ec.get("ref_low"), ec.get("ref_high")),
                                    from_value=ec.get("from_value") if ec.get("from_value") is not None else "—",
                                    to_value=ec.get("value")),
                         "data": ec})
        if r.get("pending") and r.get("pending_why") == "risk_allele":
            rows.append({"origin": "risk_allele", "gene": g, "rsid": rs,
                         "text": _t("system.q.risk_allele", gene=g, rsid=rs), "data": None})
        elif r.get("pending") and r.get("unit") == "position":
            st = (r.get("genotype") or {}).get("state")
            rows.append({"origin": "pending", "gene": g, "rsid": rs,
                         "text": _t("system.q.pending", gene=g, rsid=rs,
                                    state=_t("system.state." + str(st))), "data": None})
        if r.get("carrier"):
            moi = r.get("moi") or ", ".join(r.get("moi_codes") or []) or "AR"
            rows.append({"origin": "moi", "gene": g, "rsid": rs,
                         "text": _t("system.q.moi", gene=g, rsid=rs or "—", moi=moi),
                         "data": None})
    poly = gen.get("polygenic") or {}
    if poly.get("status") == "ok":
        # One question per reliable score at or above the line, and a question
        # only: whether a screening follows from a percentile is a clinical
        # decision, and the two caveats travel inside the sentence.
        for r in poly.get("rows") or []:
            if r.get("trait") in (poly.get("high") or []):
                rows.append({"origin": "polygenic", "trait": r["trait"], "pgs_id": r.get("pgs_id"),
                             "text": _t("system.q.polygenic", label=r.get("label"),
                                        percentile=r.get("percentile"),
                                        pgs_id=r.get("pgs_id") or "—"),
                             "data": r})
    fired = set()
    for t_ in tests.get("rows") or []:
        fired |= set(t_.get("markers_hit") or [])
    gap = [k for k in (labs.get("missing") or []) if k not in fired]
    if gap:
        names = ", ".join(_marker_name(k) for k in gap)
        text = _t("system.q.gap", markers=names)
        held = {k: waiting.pop(k) for k in gap if k in waiting}
        if held:
            text += _t("system.gap_waiting", waiting="; ".join(
                f"{_marker_name(k)} — {', '.join(v)}" for k, v in held.items()))
        rows.append({"origin": "gap", "markers": gap, "text": text,
                     "data": {"missing": gap, "waiting": held}})
    # An expectation on a marker that is missing yet not in the plain gap (a
    # rule already asks for it, or it is outside the panel's missing list):
    # still one question per marker, never one per position.
    for k, positions in waiting.items():
        rows.append({"origin": "expect_gap", "marker": k, "positions": positions,
                     "text": _t("system.q.expect_gap", marker=_marker_name(k),
                                positions=", ".join(positions)),
                     "data": {"marker": k, "positions": positions}})
    empty_why = None
    if not rows:
        empty_why = {"no_genetic_half": "no_genetic_half",
                     "not_composed": "no_genetic_panel"}.get(gen.get("status"), "nothing_open")
    return {"status": "ok", "rows": rows, "empty_why": empty_why}


def _full_genome(gen: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """What a full genome would close for THIS system, when the input is not one.

    The primary user has a whole genome; a person with an array, an exome, a
    panel or no file at all is owed the same sentence in the other direction —
    which genes of this list would be read, and which scores computed. Said
    from `genome.available()` and nothing else: the kind of the input is
    measured there once, and a second detector here would drift from it.
    """
    from .. import genome
    from .genomics import NARROW_FOR_SCORES, NARROW_INPUTS
    try:
        st = genome.available() or {}
    except Exception:                                                # noqa: BLE001
        st = {}
    profile = st.get("input_profile")
    if not st.get("ready"):
        kind = "none"
    elif profile in ("array", "exome"):
        kind = profile
    elif profile in (NARROW_INPUTS | NARROW_FOR_SCORES):
        kind = "narrow"
    else:
        return None
    genes = sorted({r["gene"] for r in gen.get("rows") or [] if r.get("read") is not True})
    poly = gen.get("polygenic") or {}
    scores = int(poly.get("mapped") or 0) if poly.get("status") == "no_scores" else 0
    if not genes and not scores:
        return None
    parts = []
    if genes:
        parts.append(_t("system.next.full_genome_genes", genes=_plural(len(genes), "count.genes")))
    if scores:
        parts.append(_t("system.next.full_genome_scores", n=scores))
    return {"input": kind, "profile": profile, "genes": len(genes), "scores": scores,
            "text": _t("system.next.full_genome",
                       input=_t("system.input." + kind, profile=profile or "—"),
                       what="; ".join(parts))}


def _next(dom: Dict[str, Any], gen: Dict[str, Any], labs: Dict[str, Any],
          tests: Dict[str, Any], questions: Dict[str, Any]) -> Dict[str, Any]:
    """The three baskets, and none of them is ever silently empty (brief §6.5)."""
    lab: List[Dict[str, Any]] = [{"origin": "rule", **t_} for t_ in tests.get("rows") or []]
    for s in labs.get("stale") or []:
        lab.append({"origin": "stale", "marker": s["key"],
                    "text": _t("system.next.stale", marker=s.get("name") or s["key"],
                               date=s.get("date"), months=STALE_MONTHS)})
    for r in gen.get("rows") or []:
        ns = r.get("next_step")
        if ns and ns.get("kind") == "lab":
            lab.append({"origin": "author", "gene": r["gene"], "rsid": r.get("rsid"),
                        "text": panel_form.one_language(ns.get("text")), "source": ns.get("source")})
    lab_why = None
    if not lab:
        if dom["source"] != "labs":
            lab_why = "no_lab_half"
        elif labs.get("missing"):
            # The never-taken markers are not in this basket on purpose: no rule
            # fired for them, and whether to take them is a clinical decision,
            # so they stand among the questions. Saying «all measured» here
            # would be false over a panel a quarter of which was ever drawn.
            lab_why = "gaps_are_questions"
        else:
            lab_why = "all_measured_no_rule"

    genome: List[Dict[str, Any]] = []
    scan = gen.get("scan") or {}
    genome_why = None
    if gen.get("status") != "composed":
        genome_why = "no_genetic_half" if gen.get("status") == "no_genetic_half" else "no_genetic_panel"
    elif scan.get("status") != "ok":
        genome_why = "scan_not_run"
    else:
        groups: Dict[str, List[str]] = {}
        for r in gen.get("rows") or []:
            if r.get("read") is False:
                if r.get("unit") == "position":
                    genome.append({"origin": "unread", "gene": r["gene"], "rsid": r.get("rsid"),
                                   "why": r.get("read_why"),
                                   "text": _t("system.next.unread", gene=r["gene"],
                                              rsid=r.get("rsid"),
                                              why=_read_why_text(r.get("read_why")) or "—")})
                else:
                    groups.setdefault(str(r.get("read_why") or "unknown"), []).append(r["gene"])
        # One line per REASON with the genes behind it, and the step that
        # closes it — 218 lines of «not read (clinvar_not_run)» for the
        # kidneys said nothing a reader could act on.
        for code, genes in groups.items():
            shown = ", ".join(genes[:12]) + (" …" if len(genes) > 12 else "")
            genome.append({"origin": "unread_group", "why": code, "genes": genes, "n": len(genes),
                           "closes": _closes_text(code),
                           "text": _t("system.next.unread_group",
                                      genes=_plural(len(genes), "count.genes"),
                                      why=_read_why_text(code) or code, names=shown)})
            cov = r.get("coverage") or {}
            if cov.get("state") == "low" and r.get("unit") == "gene":
                genome.append({"origin": "coverage", "gene": r["gene"],
                               "text": _t("system.next.coverage", gene=r["gene"],
                                          pct=cov.get("pct_20x"))})
            ns = r.get("next_step")
            if ns and ns.get("kind") == "genome":
                genome.append({"origin": "author", "gene": r["gene"], "rsid": r.get("rsid"),
                               "text": panel_form.one_language(ns.get("text")),
                               "source": ns.get("source")})
        if not genome:
            genome_why = "all_read"

    ask = list(questions.get("rows") or [])
    for r in gen.get("rows") or []:
        ns = r.get("next_step")
        if ns and ns.get("kind") == "ask":
            ask.append({"origin": "author", "gene": r["gene"], "rsid": r.get("rsid"),
                        "text": panel_form.one_language(ns.get("text")), "source": ns.get("source")})
    return {"lab": {"rows": lab, "empty_why": lab_why,
                    "empty_reason": _t("system.why." + lab_why) if lab_why else None},
            "genome": {"rows": genome, "empty_why": genome_why,
                       "empty_reason": (_t("system.why." + genome_why)
                                        + (" — " + _genome_reason_text(scan.get("genome_reason"))
                                           if genome_why == "scan_not_run"
                                           and scan.get("genome_reason") else ""))
                       if genome_why else None,
                       "full_genome": (_full_genome(gen)
                                       if gen.get("status") != "no_genetic_half" else None)},
            "ask": {"rows": ask, "empty_why": None if ask else questions.get("empty_why"),
                    "empty_reason": _t("system.why." + str(questions.get("empty_why")))
                    if not ask and questions.get("empty_why") else None}}


# ---- registers --------------------------------------------------------------
_PATIENT_ROW = ("unit", "origin", "gene", "rsid", "mode", "moi", "classification", "state", "kind",
                "text", "pending", "pending_why", "findings", "not_a_finding_why",
                "needs_confirmation", "level", "level_short", "ladder", "carrier", "caveat", "read", "read_state", "presumed", "closes_text", "depth_note", "read_why", "read_why_text", "expect_check", "local_note", "group",
                "link", "link_text", "route", "under_load", "file_says", "file_says_text",
                "signature", "signed_on")
#: A score in the patient's register: the trait, where it sits, whether it can
#: be trusted. The model id, the evidence tier and the notes are the
#: clinician's density.
_PATIENT_POLY_ROW = ("trait", "label", "percentile", "reliable")


def _project(gen: Dict[str, Any], register: str) -> Dict[str, Any]:
    """Two densities of the same facts. The verdict was computed before this
    runs and is copied, not recomputed: it cannot differ between registers."""
    if register == "clinician":
        return gen
    out = dict(gen)
    # The patient's rows: what was found, carriership, what waits for a
    # phrase — and an authored position with its sentence, whatever the kind
    # of link says about it: the sentence was written to be read.
    out["rows"] = [{k: r.get(k) for k in _PATIENT_ROW if k in r}
                   for r in gen.get("rows") or []
                   if r.get("findings") or r.get("carrier") or r.get("pending")
                   or r.get("needs_confirmation")
                   or (r.get("unit") == "position" and r.get("text")
                       and r.get("not_a_finding_why") == "kind")]
    out["rows_withheld_as_detail"] = len(gen.get("rows") or []) - len(out["rows"])
    if isinstance(gen.get("refused"), dict):
        out["refused"] = {"total": gen["refused"].get("total", 0)}
    if isinstance(gen.get("polygenic"), dict):
        out["polygenic"] = {**gen["polygenic"],
                            "rows": [{k: r.get(k) for k in _PATIENT_POLY_ROW}
                                     for r in gen["polygenic"].get("rows") or []]}
    return out


# ---- the API ----------------------------------------------------------------
@core.in_reading
def systems() -> Dict[str, Any]:
    """The systems: key, label in both languages, source, whether a laboratory
    half and a genetic half exist, and where the genetic list comes from.

    A reader who does not know which systems have an answer at all cannot tell
    a system with no list from a system where somebody looked and found nothing.
    """
    base = (_base().get("systems") or {})
    cur = (_curated().get("systems") or {})
    from .labs import analyze_labs
    from .lifestyle import health_radar
    radar = {d.get("key"): d for d in (health_radar().get("domains") or [])}
    by_key = {m["key"]: m for m in (analyze_labs().get("markers") or [])}
    findings: Optional[Dict[str, Any]] = None
    rows = []
    for d in domains():
        rd = radar.get(d["key"]) or {}
        b = base.get(d["key"]) if isinstance(base.get(d["key"]), dict) else None
        c = cur.get(d["key"]) if isinstance(cur.get(d["key"]), dict) else None
        if not d["genetic_half"]:
            gstat = "no_genetic_half"
        elif (b and b.get("genes")) or (c and c.get("positions")):
            gstat = "composed"
        else:
            gstat = "not_composed"
        # The second ring. Two numbers and never a share of the score: how
        # much of the genetic half was read is a fact about the file, the
        # score a fact about the last draw, and one figure made of both could
        # not be refuted by any measurement (brief §4.2).
        read = unread = 0
        scan = None
        if gstat == "composed":
            g = _genetics_layer(d, by_key)
            read, unread = g.get("read_count", 0), g.get("unread_count", 0)
            scan = (g.get("scan") or {}).get("status")
        # The scores, counted and never folded into either ring: mapped by the
        # file, scored on this profile, above the line. Read once per listing.
        poly = {"status": "no_genetic_half", "mapped": 0, "scored": 0, "high": 0}
        if d["genetic_half"]:
            if findings is None:
                findings = _prs_findings_safe()
            pb = _polygenic_block(d["key"], findings)
            poly = {"status": pb["status"], "mapped": pb["mapped"], "scored": pb["scored"],
                    "high": len(pb["high"])}
        rows.append({"key": d["key"], "label": _t("radar.domain." + d["key"]),
                     "labels": _labels(d["key"]), "source": d["source"],
                     "lab_half": d["source"] == "labs", "genetic_half": d["genetic_half"],
                     "markers": d["markers"],
                     "labs": {"measured": rd.get("measured"), "total": rd.get("total"),
                              "score": rd.get("score"), "status": rd.get("status")},
                     "genetics": {"status": gstat,
                                  "base_genes": len((b or {}).get("genes") or {}),
                                  "curated_positions": len((c or {}).get("positions") or []),
                                  "base_version": (_base().get("_meta") or {}).get("export_last_modified")
                                  if b else None,
                                  "read_count": read, "unread_count": unread,
                                  "depthless_genes": g.get("depthless_genes", 0),
                                  "scan": scan, "polygenic": poly}})
    return {"status": "ok", "systems": rows, "count": len(rows), "on_demand": on_demand_panels(),
            "why_empty": panel_form.one_language((_curated().get("_meta") or {}).get("why_empty")),
            # The joins the other faces read from here rather than recomputing:
            # a prescription's systems, a gene's systems, a class's systems.
            "prescriptions": prescriptions(),
            "genes_index": genes_index(),
            "class_systems": class_systems()["classes"],
            "disclaimer": DISCLAIMER()}


@core.in_reading
def system(key: str, register: str = "patient") -> Dict[str, Any]:
    """One system whole: the seven layers, the verdict, the three baskets."""
    dom = _domain(key)
    if dom is None:
        spec = (_on_demand().get("panels") or {}).get((key or "").strip().lower())
        if isinstance(spec, dict) and register in REGISTERS:
            return _on_demand_card((key or "").strip().lower(), spec, register)
        return {"status": "unknown_system", "key": key,
                "systems": [d["key"] for d in domains()],
                "on_demand": [p["key"] for p in on_demand_panels()]}
    if register not in REGISTERS:
        # Refused, not defaulted: a plausible register served where a refusal
        # was owed would hand a clinician the patient's density under the
        # clinician's name (found 12.09.2026 through the HTTP and tool doors,
        # where argparse's `choices` does not stand).
        return {"status": "unknown_register", "key": dom["key"], "register": register,
                "registers": list(REGISTERS)}
    from .labs import analyze_labs
    by_key = {m["key"]: m for m in (analyze_labs().get("markers") or [])}
    rd = _radar_domain(dom["key"])
    labs = _labs_layer(dom, rd, by_key)
    gen = _genetics_layer(dom, by_key)
    target = _target_layer(dom, by_key)
    tests = _tests_layer(dom["markers"])
    questions = _questions(gen, labs, tests, by_key, target)
    nxt = _next(dom, gen, labs, tests, questions)
    # Task 200: what the genotype says about the ROUTE of a correction somebody
    # has already decided on. It reads the layers above it and decides nothing
    # about whether to correct — see `engine/routes.py` for the gate.
    from . import routes as _routes
    off = any((by_key.get(k) or {}).get("abnormal")
              for k in list(dom["markers"]) + list(dom.get("panel_markers") or []))
    correction = _routes.correction_routes_for(dom["key"], by_key, gen.get("rows") or [], off)
    return {"status": "ok", "key": dom["key"], "label": _t("radar.domain." + dom["key"]),
            "labels": _labels(dom["key"]), "register": register,
            "source": dom["source"], "genetic_half": dom["genetic_half"],
            "markers": dom["markers"],
            "labs": labs, "dynamics": _dynamics_layer(rd),
            "genetics": _project(gen, register),
            "medications": _medications_layer(dom["key"]),
            "target": target,
            "tests": tests, "questions": questions,
            "correction_routes": correction,
            "verdict": gen["verdict"], "verdict_line": gen["verdict_line"],
            "unread_line": panel_form.unread_line(gen["verdict"]),
            "unread": panel_form.unread_block(gen["verdict"]),
            "next": nxt, "disclaimer": DISCLAIMER()}


def composition(key: str) -> Dict[str, Any]:
    """The genes of one system's genetic half WITHOUT reading the genome — the
    base composition minus the clinician's signed exclusions, plus the genes her
    positions name. The prescription entry reaches a drug's genes through this
    (class → system → composition), so it is the same list the card prints.
    """
    dom = _domain(key)
    if dom is None or not dom["genetic_half"]:
        return {"key": key, "status": "no_genetic_half" if dom else "unknown_system", "genes": []}
    base = _base_rows(key)
    spec = (_curated().get("systems") or {}).get(key)
    spec = spec if isinstance(spec, dict) else {}
    excluded = {str(g).upper() for g, e in (spec.get("exclusions") or {}).items()
                if isinstance(e, dict) and panel_form.one_language(e.get("source"))}
    rows = [{"gene": r["gene"], "origin": "base", "source": r["source"], "mode": "monogenic"}
            for r in base["rows"] if r["gene"] not in excluded]
    seen = {r["gene"] for r in rows}
    sys_source = panel_form.one_language(spec.get("source"))
    for p in spec.get("positions") or []:
        g = str((p or {}).get("gene") or "").upper() if isinstance(p, dict) else ""
        src = panel_form.one_language(p.get("source")) or sys_source if g else ""
        if g and src and g not in seen and p.get("mode") in MODES:
            seen.add(g)
            rows.append({"gene": g, "origin": "curated", "source": src, "mode": p["mode"]})
    return {"key": key, "status": "composed" if rows else "not_composed", "genes": rows,
            "excluded": sorted(excluded), "base_version": base.get("version")}


def genes_index() -> Dict[str, List[str]]:
    """gene → the systems it is named in, from the base and the curated file —
    computed from the same files, never kept as a second source."""
    out: Dict[str, set] = {}
    for key, spec in (_base().get("systems") or {}).items():
        for g in ((spec or {}).get("genes") or {}):
            out.setdefault(str(g).upper(), set()).add(key)
    for key, spec in (_curated().get("systems") or {}).items():
        for p in ((spec or {}).get("positions") or []):
            if isinstance(p, dict) and p.get("gene"):
                out.setdefault(str(p["gene"]).upper(), set()).add(key)
    return {g: sorted(s) for g, s in sorted(out.items())}
