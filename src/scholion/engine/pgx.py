"""Pharmacogenetics: phenotypes, drug-gene guidance, interactions, prescriptions.

Answers carry their basis (which star alleles were actually read) and their
limits; check_new_prescription is a second opinion, not a verdict.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from .. import core
from ..i18n import t as _t
from ._helpers import (_active_names_by_class, _basis, _basis_note,
                       _brief_num, _match_count, DISCLAIMER)
from .labs import analyze_labs


def compute_phenotype(gene: str) -> Dict[str, Any]:
    """The patient's phenotype for a gene, WITH the basis it rests on.

    Returns {phenotype, label, found, certainty, basis, basis_note}.

    `certainty` is the part that matters: `determined` when every marker of the
    model was read, `assumed` when only some were, `unknown` when none were. An
    assumed phenotype is still printed — it carries real information — but it is
    labelled as assumed and says what would make it certain. Refusing to answer
    from a partial panel and asserting a phenotype from one are both wrong; the
    honest third option is to answer and mark the answer.
    """
    kb = core.cpic_kb()
    gdef = (kb.get("genes", {}) or {}).get(gene)
    if gene in core.genome_gaps():
        basis = _basis(gene, gdef, [])
        # Which of them are unread because the file has no row there, as opposed
        # to there being no file: the two need different instructions, and the
        # gene being in the gap list does not say which case this is.
        not_called = [m["rsid"] for m in basis["missing"]
                      if (core.genotype_status(m["rsid"]) or {}).get("confidence") == "assumed_ref"]
        if not_called:
            basis["not_called"] = not_called
        return {"phenotype": "unknown", "label": _t("phenotype.not_covered"),
                "found": core.markers_for_gene(gene), "certainty": "unknown",
                "basis": basis, "basis_note": _basis_note(gene, basis)}
    if not gdef:
        markers = core.markers_for_gene(gene)
        basis = _basis(gene, None, [])
        return {"phenotype": "unknown" if not markers else "reported",
                "label": _t("phenotype.no_model"), "found": markers,
                "certainty": "unknown" if not markers else "assumed",
                "basis": basis, "basis_note": _basis_note(gene, basis)}

    func_counts: Dict[str, int] = {}
    found: List[Dict[str, Any]] = []
    unread: List[str] = []
    hap_copies: Dict[str, int] = {}       # a multi-tag haplotype counts once, see below
    for m in gdef.get("markers", []):
        st = core.genotype_status(m["rsid"])
        if not st or not st.get("genotype"):
            continue
        # `assumed_ref` is not a reading. It means the position has no row in the
        # variant VCF, which is either the reference OR no coverage there, and the
        # two are indistinguishable from the file alone. Counting it as zero
        # variant copies is what made a connected genome produce a LESS cautious
        # answer than no genome at all: the string said "CC", the phenotype came
        # out normal, and a possible carrier read it as permission.
        if st.get("confidence") == "assumed_ref":
            unread.append(m["rsid"])
            continue
        gt = st["genotype"]
        copies = gt.upper().count(m["variant_allele"].upper())
        # A haplotype defined by more than one tag is ONE allele, however many of
        # its tags were read. DPYD HapB3 is tagged by rs75017182 and rs56038477,
        # which travel together; adding both would make a single heterozygous
        # carrier count as two decreased-function alleles — an activity score of
        # 1.0 read as 0.0. Nothing in the phenotype rules says so today, which is
        # exactly why it has to be right before one does.
        #
        # Among the tags of one haplotype the LARGEST copy number wins. They
        # should agree; when they do not — imperfect linkage, a missed call, a
        # phasing artefact — the cautious reading is the one that keeps the
        # variant, not the one that drops it.
        hap = m.get("haplotype")
        if hap:
            prev = hap_copies.get(hap, 0)
            if copies > prev:
                func_counts[m["function"]] = func_counts.get(m["function"], 0) + (copies - prev)
                hap_copies[hap] = copies
        else:
            func_counts[m["function"]] = func_counts.get(m["function"], 0) + copies
        found.append({"rsid": m["rsid"], "star": m.get("star", ""), "genotype": gt,
                      "copies": copies, "function": m["function"], "haplotype": hap,
                      "confidence": st.get("confidence"), "depth": st.get("depth")})

    basis = _basis(gene, gdef, found)
    if unread:
        basis["not_called"] = unread
    note = _basis_note(gene, basis)
    if not found:
        return {"phenotype": "unknown", "label": _t("phenotype.no_markers"), "found": [],
                "certainty": "unknown", "basis": basis, "basis_note": note}

    certainty = "determined" if not basis["missing"] else "assumed"
    phen, label = "NM", _t("phenotype.normal_default")
    for rule in gdef.get("phenotype_rules", []):
        if rule.get("default") or all(_match_count(func_counts.get(fn, 0), expr)
                                      for fn, expr in rule["when"].items()):
            phen, label = rule["phenotype"], rule.get("label", "")
            break
    if certainty == "assumed":
        label = _t("phenotype.assumed", label=label)
    return {"phenotype": phen, "label": label, "found": found,
            "certainty": certainty, "basis": basis, "basis_note": note}


def check_drug_gene(drug: str) -> Dict[str, Any]:
    q = (drug or "").strip().lower()
    if not q:
        return {"status": "error", "message": _t("drug.no_name"), "disclaimer": DISCLAIMER()}

    kb = core.cpic_kb()
    match = None
    for entry in kb.get("drugs", []):
        for name in entry.get("names", []):
            if q == name or q in name or name in q:
                match = entry
                break
        if match:
            break

    if not match:
        return _check_drug_online(drug)

    gene = match["gene"]
    ph = compute_phenotype(gene)
    phenotype = ph["phenotype"]
    guidance = match.get("guidance", {})

    # A determined phenotype with no entry of its own must not be answered out of
    # `default`. Voriconazole's table has keys for UM, RM, PM and default — but
    # none for IM, NM or unknown, so a carrier of a loss-of-function allele, a
    # normal metaboliser and a person with no data at all were given the same
    # sentence: "no features have been found by the markers". The catalogue's
    # silence about a phenotype was printed as a statement about the patient.
    #
    # `default` keeps its meaning — a rule that applies whatever the phenotype —
    # but only where the phenotype was never determined. Where it WAS determined
    # and the catalogue has nothing to say, that is what the answer says, and the
    # gap is machine-readable in `guidance_gap` rather than only in the prose.
    explicit = guidance.get(phenotype)
    gap = False
    if explicit:
        flag = explicit
    elif phenotype in ("unknown", "reported") or not guidance:
        flag = guidance.get("default") or {
            "level": "unknown" if phenotype == "unknown" else "low",
            "note": _t("drug.nothing_notable")}
    else:
        gap = True
        flag = {"level": "unknown",
                "note": _t("drug.no_guidance_for_phenotype", phenotype=phenotype, gene=gene)}

    # An undetermined phenotype cannot yield a reassuring level, whatever the
    # catalogue's `default` says. Five drugs had `default.level = "low"`, so a
    # person with no genotype at all was told the drug was fine on this gene —
    # azathioprine among them.
    #
    # The text is led, not replaced. A `default` note is often good advice
    # ("assess the TPMT status before prescribing") and worth keeping — but some
    # of them are claims about the patient: voriconazole's reads "no features
    # have been found by the markers", which, said to a person whose markers were
    # never read, is the same defect one layer down. Lifting the level and
    # leaving that sentence would have been the mirror of what this change is
    # for. So the answer opens by saying the phenotype was not determined, and
    # whatever the catalogue advises follows that.
    if phenotype == "unknown":
        # "Not determined" alone is a dead end. What follows it is the basis: how
        # many markers of the model were read, which were not, and whether the
        # gap is closable from the person's own data or needs a laboratory. A
        # reader can act on that; they cannot act on the absence of a word.
        lead = _t("drug.phenotype_not_determined", gene=gene)
        parts = [lead, ph.get("basis_note") or "", flag.get("note") or ""]
        flag = {**flag,
                "level": "unknown" if flag.get("level") in ("low", None) else flag["level"],
                "note": " ".join(x for x in parts if x)}
    elif ph.get("certainty") == "assumed":
        # An assumed phenotype keeps its recommendation — the information is real
        # — and carries what would make it certain, in the same sentence.
        flag = {**flag, "note": " ".join(x for x in (flag.get("note") or "",
                                                     ph.get("basis_note") or "") if x)}
    return {
        "status": "ok",
        "drug": drug,
        "gene": gene,
        "drug_class": match.get("class", ""),
        "why": match.get("why", ""),
        "phenotype": phenotype,
        "phenotype_label": ph.get("label", ""),
        "certainty": ph.get("certainty"),
        "basis": ph.get("basis"),
        "level": flag["level"],
        "guidance_gap": gap,
        "recommendation": flag["note"],
        "markers_found": ph.get("found") or core.markers_for_gene(gene),
        "clinvar": clinvar_for_drug(drug, {"genes": [{"gene": gene}]}),
        "disclaimer": DISCLAIMER(),
    }


def _guidance_for(drug: str, gene: str) -> Dict[str, Any]:
    """The recommendation table for the PAIR (drug, gene), or nothing.

    Matching on the gene alone is what let a proton pump inhibitor be answered
    out of the clopidogrel table. There is no safe fallback here: a table for
    another drug on the same gene is not an approximation, it can be the
    opposite advice. An empty result is handled by the caller as "no specific
    recommendation", which is true.
    """
    q = (drug or "").strip().lower()
    if not q:
        return {}
    for d in core.cpic_kb().get("drugs", []):
        if d.get("gene") != gene:
            continue
        for name in d.get("names", []):
            if q == name or q in name or name in q:
                return d.get("guidance", {}) or {}
    return {}


def _check_drug_online(drug: str) -> Dict[str, Any]:
    """Fallback when the drug is not in the local base: the international RxNorm/RxClass bases are searched."""
    from .. import drugsource
    info = drugsource.resolve_drug(drug)
    if not info:
        return {"status": "not_found", "drug": drug, "disclaimer": DISCLAIMER(),
                "message": _t("drug.not_found", drug=drug)}
    cls = info.get("internal_class")
    atc_names = ", ".join(a.get("name", "") for a in info.get("atc", []) if a.get("name"))
    disp = info.get("name") or drug
    ing = info.get("ingredient")
    if ing and ing.lower() not in disp.lower():
        disp = f"{disp} ({ing})"
    gene_hint = drugsource.class_gene(cls)
    if gene_hint:
        gene, why = gene_hint
        ph = compute_phenotype(gene)
        phenotype = ph["phenotype"]
        # The recommendation table belongs to the pair (drug, gene), never to the
        # gene alone. Taking the first record with a matching gene handed a proton
        # pump inhibitor the clopidogrel table — the first CYP2C19 entry in the
        # catalogue — and that table is not merely somebody else's, it is
        # pharmacologically inverted: for a PPI a reduced CYP2C19 function means
        # MORE exposure, not an insufficient effect. The screen said "consider a
        # platelet function test" about omeprazole.
        #
        # If this drug has no table of its own, no table is used. A generic
        # gene-level caution is honest; a specific recommendation borrowed from a
        # different drug is not.
        guidance = _guidance_for(drug, gene)
        flag = guidance.get(phenotype) or {"level": "unknown" if phenotype == "unknown" else "low",
                                           "note": _t("drug.nothing_notable_ask")}
        return {"status": "ok", "drug": disp, "gene": gene,
                "drug_class": atc_names or (cls or ""), "why": why,
                "phenotype": phenotype, "phenotype_label": ph.get("label", ""),
                "level": flag["level"], "recommendation": flag["note"],
                "markers_found": ph.get("found") or core.markers_for_gene(gene),
                "resolved_by": "rxnorm", "reference": info.get("url"),
                "disclaimer": DISCLAIMER()}
    # found online, but there is no pharmacogene for the class — said honestly + the class for interactions
    return {"status": "found_online", "drug": disp,
            "drug_class": atc_names or (cls or _t("drug.class_unknown")),
            "internal_class": cls, "reference": info.get("url"), "disclaimer": DISCLAIMER(),
            "message": _t("drug.online_headline", drug=disp,
                          class_note=_t("drug.online_class_note", classes=atc_names) if atc_names else "",
                          tail=_t("drug.online_check_interactions") if cls
                               else _t("drug.online_ask_doctor"))}


def _classes_for(drug: str) -> List[str]:
    """Classes of a drug: first the local dictionary, then the international base (RxClass ATC)."""
    local = core.classify_drug(drug)
    if local:
        return local
    from .. import drugsource
    info = drugsource.resolve_drug(drug)
    cls = info.get("internal_class") if info else None
    return [cls] if cls else []


_SEV_ORDER = {"high": 0, "moderate": 1, "low": 2}


def check_interactions(drug: str) -> Dict[str, Any]:
    """Interactions of a NEW drug with the patient's current prescriptions (by class).
    The class is taken from the local dictionary, and failing that — from the international RxClass base."""
    new_classes = _classes_for(drug)
    active = core.active_med_classes()
    if not new_classes:
        # telling apart: the drug was not found at all vs found online, but its class has no interaction rules
        from .. import drugsource
        info = drugsource.resolve_drug(drug)
        if info:
            atc = ", ".join(a.get("name", "") for a in info.get("atc", []) if a.get("name"))
            return {"status": "no_rules", "drug": info.get("name", drug), "new_classes": [],
                    "interactions": [], "atc": atc,
                    "message": _t("interactions.no_rules", atc=atc or _t("common.na"))}
        return {"status": "unknown_class", "drug": drug, "new_classes": [],
                "interactions": [],
                "message": _t("interactions.unknown_drug")}
    hits = []
    names_by_class = _active_names_by_class()
    for rule in core.drug_interactions().get("interactions", []):
        a, b = rule.get("a"), rule.get("b")
        pair = None
        if a in new_classes and b in active:
            pair = b
        elif b in new_classes and a in active:
            pair = a
        if pair:
            hits.append({**rule, "with_class": pair,
                         "with_meds": names_by_class.get(pair, [])})
    hits.sort(key=lambda r: _SEV_ORDER.get(r.get("severity"), 3))
    # `baseline` says WHAT the new drug was compared against. Without it an empty
    # `interactions` list is ambiguous, and the ambiguity falls on the most common
    # state there is: a fresh install before the first `add-med`, where the answer
    # "no interactions found with your current prescriptions" was byte-identical
    # to the answer given to a person on five drugs. Nothing was checked; the
    # sentence claimed it was.
    # …and `unclassified` says what the comparison could NOT see. `empty` covers only
    # the extreme: a profile with no prescriptions at all. A list of two, one of them
    # a name the dictionary does not recognise, gave `empty: False` and the flat
    # sentence "no explicit interactions with the current prescriptions were found" —
    # a negative statement resting on half the list, with the unread half never
    # named. Naming it costs one line and turns a claim into an instruction.
    unrecognised = [m.get("name", "") for m in core.medications_json().get("medications", [])
                    if m.get("name") and not core.classify_drug(m["name"])]
    return {"status": "ok", "drug": drug, "new_classes": new_classes,
            "interactions": hits, "count": len(hits),
            "baseline": {"classes": sorted(active), "count": len(active),
                         "empty": not active, "unclassified": unrecognised}}


def _assess_gene(gene: str) -> Dict[str, Any]:
    """Assessment of a gene by the PATIENT'S DATA: a phenotype (if the gene is modelled and covered)
    or raw variants from the full genome base. Works from the full VCF, not from a fixed list."""
    from .. import genome
    kb = core.cpic_kb()
    modelled = gene in kb.get("genes", {})
    covered = gene not in core.genome_gaps()
    if modelled and covered:
        ph = compute_phenotype(gene)
        return {"gene": gene, "computable": True, "phenotype": ph["phenotype"],
                "label": ph.get("label", ""), "markers": ph.get("found", [])}
    markers = core.markers_for_gene(gene)
    ready = genome.available()["ready"]
    for rs, l in genome.loci().get("loci", {}).items():   # the gene loci are taken from the full VCF
        if l.get("gene", "").upper() == gene.upper():
            gt = core.genotype_at(rs)
            if gt and not any(m.get("rsid") == rs for m in markers):
                markers.append({"rsid": rs, "genotype": gt, "interpretation": ""})
    note = _t("gene.covered_by_vcf" if ready else "gene.vcf_pending")
    return {"gene": gene, "computable": False,
            "phenotype": "reported" if markers else "pending",
            "label": note, "markers": markers}


def _genome_for_drug(drug: str, info: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Genes important for the drug (the local base + CPIC by rxcui for ANY drug),
    assessed against the patient's genome."""
    from .. import genome, drugsource
    genes: Dict[str, Dict[str, Any]] = {}
    q = (drug or "").lower()
    for entry in core.cpic_kb().get("drugs", []):
        if any(q == n or q in n or n in q for n in entry.get("names", [])):
            # The level is a VALUE the code compares — format.py and the web page both
            # test it against this exact word to tell the project's own base from CPIC.
            genes.setdefault(entry["gene"], {"level": "куратор", "actionable": True})
    # Whether the international database was actually reached. An empty answer and
    # an unreachable source are different facts, and only the first of them
    # licenses «this drug has no meaningful pharmacogenetics» downstream.
    cpic = drugsource.cpic_lookup(info["rxcui"]) if (info and info.get("rxcui")) \
        else {"genes": [], "asked": False, "reason": "not_identified"}
    for g in cpic["genes"]:
        if g["actionable"]:          # only the clinically significant ones (CPIC A/B); level D is noise
            genes.setdefault(g["gene"], {"level": g["level"], "actionable": True})
    assessed = []
    for gene, meta in genes.items():
        a = _assess_gene(gene)
        a["cpic_level"], a["actionable"] = meta["level"], meta["actionable"]
        assessed.append(a)
    assessed.sort(key=lambda a: (not a.get("actionable"), not a.get("computable")))
    return {"genes": assessed, "genome_ready": genome.available()["ready"],
            "has_pgx": bool(assessed),
            "cpic": {"asked": cpic.get("asked", False), "reason": cpic.get("reason")}}


def _labs_for_drug(classes: List[str]) -> Dict[str, Any]:
    """Which of YOUR lab tests matter with this drug (by class) and their current state."""
    mon = core.drug_lab_monitoring().get("classes", {})
    by = {m["key"]: m for m in analyze_labs()["markers"]}
    rows, whys, seen = [], [], set()
    for c in classes:
        spec = mon.get(c)
        if not spec:
            continue
        if spec.get("why"):
            whys.append(spec["why"])
        for k in spec.get("labs", []):
            if k in seen:
                continue
            seen.add(k)
            m = by.get(k)
            rows.append({"key": k, "present": m is not None,
                         "name": m["name"] if m else k, "value": m["value"] if m else None,
                         "unit": m["unit"] if m else "", "flag": m["flag"] if m else "nodata",
                         "near_limit": m.get("near_limit") if m else None,
                         "decisions": m.get("decisions") if m else [],
                         "personal_move": m.get("personal_move") if m else None,
                         "ref_low": m.get("ref_low") if m else None, "ref_high": m.get("ref_high") if m else None})
    # Which of the drug's classes the monitoring catalogue actually has a rule for.
    # An empty `markers` used to print «no lab monitoring is required for this
    # class» whether the catalogue said so or simply had no entry — nine of the
    # project's 41 classes have no entry, among them SSRI/SNRI, clopidogrel and
    # amiodarone, all of which need monitoring in real life.
    return {"reason": "; ".join(dict.fromkeys(whys)), "markers": rows,
            "basis": {"classes": list(classes),
                      "with_rules": [c for c in classes if c in mon]},
            "watch": [r for r in rows if r["flag"] in ("high", "low")],
            "near": [r for r in rows if r.get("near_limit")],
            "crossed": [r for r in rows if any(d["crossed"] for d in (r.get("decisions") or []))]}


def _rsids_for_genes(gene_names) -> Dict[str, str]:
    """rsID → gene for the given genes (from the CPIC model and the loci.json catalogue)."""
    from .. import genome
    want = {g.upper() for g in gene_names if g}
    out: Dict[str, str] = {}
    for gname, gdef in core.cpic_kb().get("genes", {}).items():
        if gname.upper() in want:
            for m in gdef.get("markers", []):
                if m.get("rsid"):
                    out[m["rsid"]] = gname
    for rs, l in genome.loci().get("loci", {}).items():
        if (l.get("gene", "") or "").upper() in want:
            out.setdefault(rs, l.get("gene"))
    return out


def clinvar_for_drug(drug: str, genome_sec: Dict[str, Any], info=None) -> Dict[str, Any]:
    """Find the patient's ClinVar findings that relate to the drug: by the rsIDs of the drug's genes
    (drug_response/risk/pathogenic) and by a mention of the drug name in the description of a finding.
    Refreshed by the monthly ClinVar check (update_check.sh)."""
    from .. import genome as gm
    try:
        cv = gm.clinvar_hits(limit=2000)
    except Exception:  # noqa
        return {"available": False, "hits": []}
    if cv.get("status") != "ok":
        return {"available": False, "status": cv.get("status"), "hits": []}
    gene_names = [g.get("gene") for g in (genome_sec or {}).get("genes", [])]
    rs2gene = _rsids_for_genes(gene_names)
    toks = set()
    for s in (drug or "", (info or {}).get("name") or "", (info or {}).get("ingredient") or ""):
        for t in str(s).lower().replace("/", " ").replace(",", " ").split():
            if len(t) >= 4:
                toks.add(t)
    out, seen = [], set()
    for h in cv.get("hits", []):
        rsid = h.get("rsid", "")
        clndn = (h.get("clndn", "") or "").lower()
        by_gene = rsid in rs2gene
        by_drug = any(t in clndn for t in toks)
        if not (by_gene or by_drug):
            continue
        tier = h.get("tier")
        if by_gene and not by_drug and tier not in ("drug", "risk", "pathogenic"):
            continue
        key = f"{rsid}|{h.get('pos')}"
        if key in seen:
            continue
        seen.add(key)
        out.append({"rsid": rsid, "genotype": h.get("genotype"), "clnsig": h.get("clnsig"),
                    "disease": h.get("disease"), "tier": tier,
                    "gene": rs2gene.get(rsid), "by_drug": by_drug})
    order = {"drug": 0, "pathogenic": 1, "risk": 2, "protective": 3}
    out.sort(key=lambda x: order.get(x["tier"], 5))
    return {"available": True, "count": len(out), "hits": out}


def _dose_context(drug: str, info: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Dose and critical-claim context of a drug from knowledge/dose_evidence.json.

    The point of the layer: not "drug X worsens Y", but the dose, the effect size with a reference,
    the difference between formulations — and the comparison with the patient's CONCRETE numbers
    (labs.json and, for lifestyle metrics, wearable_trends.json). The search goes by the Russian
    spelling and by the RxNorm ingredient — otherwise two spellings of one drug find different entries.
    """
    # Lazy on purpose: lifestyle imports pgx at the top (second_opinion needs
    # check_drug_gene), so pgx reaching back for one renderer must not be a
    # top-level import -- that would close the circle.
    from .lifestyle import _brief_life
    names = {(drug or "").strip().lower()}
    if info:
        for k in ("name", "ingredient"):
            if info.get(k):
                names.add(str(info[k]).strip().lower())
    ent = (core.dose_evidence().get("entries") or {})
    hit = None
    for key, spec in ent.items():
        pats = [key] + list(spec.get("match") or [])
        if any(p and p.lower() in n for n in names for p in pats):
            hit = spec
            break
    if not hit:
        return {"matched": False}
    by = {m["key"]: m for m in analyze_labs()["markers"]}
    items = []
    for it in hit.get("critical") or []:
        pts = []
        for key in it.get("compare_marker") or []:
            m = by.get(key)
            if m:
                pts.append({"name": m["name"], "value": m["value"], "unit": m.get("unit", ""),
                            "ref_low": m.get("ref_low"), "ref_high": m.get("ref_high"),
                            "flag": m.get("flag"), "measured": True})
                continue
            lv = _brief_life(key)          # a wearable-device metric, not a lab test
            if lv.get("value") and lv.get("value") != "—":
                # the human-readable name and the units come from the public metrics reference
                meta = (core.wearable_metrics().get("metrics") or {}).get(key) or {}
                unit = meta.get("unit", "")
                if any(ch.isdigit() for ch in unit):   # "0–100" is a scale, not a unit
                    unit = ""
                pts.append({"name": meta.get("label") or key,
                            "value": _brief_num(lv.get("value")), "unit": unit,
                            "flag": None, "measured": True})
            else:
                pts.append({"name": key, "measured": False})
        items.append({**{k: it.get(k) for k in
                         ("claim", "dose_dependent", "effect_size", "low_dose_note", "source")},
                      "patient": pts})
    return {"matched": True,
            "nutritional_dose": hit.get("nutritional_dose"),
            "pharmacologic_dose": hit.get("pharmacologic_dose"),
            "items": items, "forms": hit.get("forms"),
            "verdict_rule": hit.get("verdict_rule"),
            "alternatives": hit.get("alternatives") or [],
            "note": hit.get("note")}


def _own_safety_flags(drug: str, disp: Optional[str] = None) -> List[Dict[str, Any]]:
    """Red flags recorded against THIS drug in the owner's own prescription file.

    A flag lives in `medications.json` → `medications[].safety_flags[]` and states a
    fact about this patient that makes the drug a question rather than a routine:
    a documented diagnosis, a documented event, an interaction with their own history.
    It is curated by hand — the engine never invents one — and it is deliberately
    kept OUT of the shared knowledge base, because the fact is personal.

    Why this exists at all: a flag written into the profile and rendered nowhere is
    the defect this project keeps finding in itself — honest prose beside a green
    machine-readable field. `check_new_prescription` therefore lifts `overall` to
    `high` on a `red_flag`, and the renderer prints it before anything else.
    """
    try:
        meds = (core.medications_json() or {}).get("medications") or []
    except Exception:
        return []
    q = {core._norm_drug(x) for x in (drug, disp) if x}
    qt = {t for s in q for t in s.split()}
    out = []
    for med in meds:
        flags = med.get("safety_flags") or []
        if not flags:
            continue
        nm = core._norm_drug(med.get("name", ""))
        nt = set(nm.split())
        # A match on any whole token: «атенолол» finds «Атенолол 50 мг», and a query
        # written as the brand or with the dose still lands on the same entry.
        if not (nt & qt):
            continue
        for f in flags:
            out.append(dict(f, medication=med.get("name")))
    return out


def check_new_prescription(drug: str) -> Dict[str, Any]:
    """SECOND OPINION on a prescription — PERSONAL, relative to the patient's data:
    🧬 their genome (the genes important for the drug per CPIC + their genotypes),
    🧪 their labs (which to monitor and what is already out of range),
    🔗 their current prescriptions (interactions). Works for any drug."""
    drug = (drug or "").strip()
    if not drug:
        return {"status": "error", "message": _t("drug.no_name"), "disclaimer": DISCLAIMER()}
    from .. import drugsource
    pgx = check_drug_gene(drug)
    info = drugsource.resolve_drug(drug)
    classes = _classes_for(drug)
    genome_sec = _genome_for_drug(drug, info)
    labs_sec = _labs_for_drug(classes)
    inter = check_interactions(drug)
    clinvar_sec = clinvar_for_drug(drug, genome_sec, info)

    atc = ", ".join(a.get("name", "") for a in (info.get("atc") if info else []) if a.get("name"))
    labels = core.med_classes().get("classes", {})
    class_display = (", ".join(labels.get(c, {}).get("label", c) for c in classes) if classes
                     else atc or pgx.get("drug_class") or _t("prescription.class_undefined"))
    disp = (info.get("name") if info else None) or (
        pgx.get("drug") if pgx.get("status") in ("ok", "found_online") else drug)
    ing = info.get("ingredient") if info else None
    if ing and disp and ing.lower() not in disp.lower():
        disp = f"{disp} ({ing})"

    # The verdict, and what could not be determined for it.
    #
    # This used to read `if pgx.get("level") in ("high", "moderate")`, so an
    # `unknown` pharmacogenetic status contributed nothing and the answer came
    # out green. That one condition was the common denominator of five of the six
    # clinical failures found in the audit: the strongest of them was that
    # CONNECTING A GENOME made the answer less cautious than having none, because
    # an unread position turns "no data" into a confident phenotype downstream.
    #
    # An undetermined input now lifts the verdict off `low`, and — separately —
    # it is named. Both halves matter. Escalating without naming leaves the
    # reader guessing which of several inputs is missing; naming without
    # escalating is exactly the defect this project keeps finding in itself:
    # honest prose beside a green machine-readable field.
    concerns, unresolved = [], []
    if pgx.get("status") == "ok":
        # A graded concern and an unresolved input are not alternatives. Clopidogrel
        # with no genotype at all returns `moderate` from its catalogue default —
        # a real recommendation — and the phenotype is still unknown. Treating the
        # two as one branch meant the answer raised the verdict for the right
        # reason and then said nothing about the missing genotype, which is the
        # very thing the reader could act on.
        if pgx.get("level") in ("high", "moderate"):
            concerns.append(pgx["level"])
        if (pgx.get("level") == "unknown" or pgx.get("phenotype") == "unknown"
                or pgx.get("certainty") == "assumed"):
            # The detail names what is missing and what would close it, not just
            # that something is. A verdict raised without an instruction is only
            # half an answer.
            basis = pgx.get("basis") or {}
            miss = ", ".join(f"{m['rsid']}{(' (' + m['star'] + ')') if m.get('star') else ''}"
                             for m in basis.get("missing", []))
            unresolved.append({"what": "pharmacogenetics", "gene": pgx.get("gene"),
                               "missing": [m["rsid"] for m in basis.get("missing", [])],
                               "closable": any(m.get("obtainable")
                                               for m in basis.get("missing", [])),
                               "detail": _t("unresolved.pgx", names=miss)
                                         if miss else (pgx.get("phenotype_label") or "")})
    for it in inter.get("interactions", []):
        concerns.append(it["severity"])
    if inter.get("status") in ("unknown_class", "no_rules"):
        unresolved.append({"what": "interactions", "gene": None,
                           "detail": _t("unresolved.drug_not_classified")})
    elif (inter.get("baseline") or {}).get("empty"):
        unresolved.append({"what": "interactions", "gene": None,
                           "detail": _t("unresolved.no_baseline")})
    elif (inter.get("baseline") or {}).get("unclassified"):
        unresolved.append({"what": "interactions", "gene": None,
                           "detail": _t("unresolved.baseline_partial",
                                        names=", ".join((inter["baseline"]["unclassified"])[:6]))})
    # A source that was never reached cannot license a negative statement. Both of
    # these print as absence — «no pharmacogenetics», «no monitoring required» —
    # and absence of an answer is not absence of a finding.
    cp = genome_sec.get("cpic") or {}
    if not genome_sec.get("genes") and not cp.get("asked"):
        unresolved.append({"what": "pharmacogenetics", "gene": None,
                           "detail": _t("unresolved.pgx_source",
                                        why=_t("pgx_unchecked." + (cp.get("reason")
                                                                   or "unreachable")))})
    lbasis = labs_sec.get("basis") or {}
    if not labs_sec["markers"] and lbasis.get("classes") and not lbasis.get("with_rules"):
        unresolved.append({"what": "monitoring", "gene": None,
                           "detail": _t("unresolved.labs_no_rule", classes=class_display)})
    if labs_sec["watch"]:
        concerns.append("moderate")
    if unresolved:
        concerns.append("moderate")     # not green; the reason travels in `unresolved`
    # A hand-curated red flag from the owner's own file outranks everything computed
    # here: it is a documented fact about this patient, not an inference from a rule.
    own_flags = _own_safety_flags(drug, disp)
    for f in own_flags:
        concerns.append("high" if f.get("severity") == "red_flag" else "moderate")
    overall = "high" if "high" in concerns else ("moderate" if "moderate" in concerns else "low")

    return {
        "status": "ok",
        "drug": disp or drug,
        "overall": overall,
        "safety_flags": own_flags,
        "unresolved": unresolved,
        "class_display": class_display,
        "classes": classes,
        "identified": {"name": disp, "atc": atc,
                       "rxcui": info.get("rxcui") if info else None,
                       "reference": info.get("url") if info else None,
                       "source": "rxnorm" if info else ("local" if pgx.get("status") == "ok" else "none")},
        "genome": genome_sec,
        "labs": labs_sec,
        "interactions": inter,
        "pharmacogenetics": pgx,
        "clinvar": clinvar_sec,
        "dose_context": _dose_context(drug, info),
        "disclaimer": DISCLAIMER(),
    }
