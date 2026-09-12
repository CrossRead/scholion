"""Genome-derived findings: lookups, ClinVar, ACMG, APOE, PRS, longevity, lipids.

Every answer distinguishes a genuine read from an assumed reference: a value is
inseparable from its evidential status, and a variant the VCF never covered is
reported as not-read, not as absent.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from .. import core
from ..i18n import lang as _lang, t as _t
from ._helpers import DISCLAIMER


def genome_lookup(rsid: Optional[str] = None, gene: Optional[str] = None) -> Dict[str, Any]:
    """Lookup of any locus in the personal full VCF (through the coordinate reference)."""
    from .. import genome
    r = genome.lookup(rsid=rsid, gene=gene)
    # Asked about a gene, answer with the frame as well as the loci: the
    # catalogue is one shelf of four, and «not in the coordinate reference» was
    # being read as a statement about the genome.
    # The gene this locus belongs to is known from the answer itself, so a single
    # position can carry the same qualification a gene query gets from its frame.
    if r.get("gene"):
        try:
            r["coverage"] = gene_coverage(r["gene"])
        except Exception as exc:                                     # noqa: BLE001
            # Silence here read as «coverage is fine»: the line is printed only
            # when the state is worth saying, so a state that never arrived
            # looked like the quiet one. The failure travels as its own state.
            r["coverage"] = {"gene": r["gene"], "measured": False,
                             "state": "unavailable", "reason": type(exc).__name__}
    # What this build has to SAY about the locus, as opposed to what it read
    # there. A genotype with nothing beside it is the shape that invites an
    # assistant to supply the meaning out of its own general knowledge, which is
    # how a reader came to be told about a locus this build does not interpret.
    if r.get("rsid"):
        r["basis"] = locus_basis(r["rsid"])
    for _item in (r.get("loci") or []):
        if isinstance(_item, dict) and _item.get("rsid"):
            _item["basis"] = locus_basis(_item["rsid"])
    if gene and not rsid:
        try:
            r["layers"] = gene_layers(gene)
        except Exception as exc:                                     # noqa: BLE001
            # A frame that failed to build and vanished is a frame the reader
            # believes was never needed. Same rule as everywhere else here: the
            # failure is named, not swallowed.
            r["layers"] = {"gene": (gene or "").upper(), "status": "unavailable",
                           "reason": type(exc).__name__}
    r["disclaimer"] = DISCLAIMER()
    return r


# ── a gene, asked of every layer that holds anything about one ───────────────
#
# The product keeps what it knows about a gene on several shelves, and each is
# keyed differently: the curated catalogue by rsID, the ClinVar scan by
# coordinate, the ACMG secondary-findings list by gene symbol. Nothing joined
# them, so «what does this build hold about ABCB4» had no answer — and the one
# path a person naturally takes, `genome --gene`, reads the catalogue alone and
# reports «not in the coordinate reference», which sounds like a statement about
# the genome and is a statement about one shelf.
#
# A clinician asked exactly that, about the bile-acid transporters, and was told
# there was nothing to say «even in general terms from your genome». There may
# well have been: the ClinVar table on that machine held 386 findings, and ABCB4
# and ABCB11 carry real pathogenic variants. Nobody looked, because nothing
# could.

def _chrom_key(c) -> str:
    """`chr7`, `7`, `Chr7` → `7`. The scan table and the gene cache do not agree
    on the spelling, and a join that fails on a prefix returns «nothing found»,
    which is the worst of the possible wrong answers."""
    s = str(c or "").strip().lower()
    return s[3:] if s.startswith("chr") else s


def clinvar_for_gene(gene: str, limit: int = 2000) -> Dict[str, Any]:
    """ClinVar findings that fall inside a gene, matched by COORDINATE.

    The scan table carries no gene column — the symbol is lost at the step that
    writes it — so the join goes the other way: resolve the gene to a region and
    ask which findings sit in it. That needs no re-scan of the genome, and it
    fails honestly: a gene whose coordinates nothing can supply is reported as
    unresolved, with what would resolve it, rather than as a gene with no
    findings.
    """
    from .. import genes
    out: Dict[str, Any] = {"gene": (gene or "").upper(), "hits": [], "disclaimer": DISCLAIMER()}
    rec = genes.resolve(gene) if gene else None
    if not rec or rec.get("chrom") is None:
        out["status"] = "gene_unresolved"
        out["fix"] = _t("clinvar.gene_unresolved", gene=out["gene"])
        return out
    out["status"] = "ok"
    out["region"] = {"chrom": rec.get("chrom"), "start": rec.get("start"),
                     "end": rec.get("end"), "assembly": rec.get("assembly")}
    out["resolved_by"] = rec.get("resolved_by") or rec.get("source")
    all_hits = clinvar_findings(limit=limit)
    out["scanned"] = all_hits.get("count")
    # A gene filter over a TRUNCATED read returns «no findings in this gene» when
    # the finding may simply be past the cut. That is the false negative this
    # whole layer exists to refuse, and it would be silent. Say it instead.
    got = len(all_hits.get("hits") or [])
    if all_hits.get("count") is not None and got < all_hits["count"]:
        out["truncated"] = {"read": got, "of": all_hits["count"]}
    if all_hits.get("status") and all_hits["status"] != "ok":
        out["status"] = all_hits["status"]
        # The scan's own sentence about why it has nothing. `clinvar_hits`
        # puts it under `message`, the narrow-input refusals under `reason`
        # or `note`; reading only the last two lost the commonest one — «the
        # scan has not been run» — and the renderer, finding no note, fell
        # back to a phrase about a broken index.
        out["scan_note"] = (all_hits.get("message") or all_hits.get("reason")
                            or all_hits.get("note"))
        return out
    ck, lo, hi = _chrom_key(rec.get("chrom")), rec.get("start"), rec.get("end")
    for h in all_hits.get("hits") or []:
        try:
            pos = int(h.get("pos"))
        except (TypeError, ValueError):
            continue
        if _chrom_key(h.get("chrom")) == ck and lo is not None and lo <= pos <= hi:
            out["hits"].append({**h, "gene": out["gene"]})
    out["count"] = len(out["hits"])
    return out


def gene_layers(gene: str) -> Dict[str, Any]:
    """Which shelves hold anything about this gene, and what each of them says.

    Printed BEFORE the findings, for the same reason the genome frame is: a
    reader who is not told which questions were asked cannot tell an answer from
    a silence. Every layer reports one of three things — what it holds, that it
    holds nothing, or that it could not be asked and why.
    """
    from .. import core
    g = (gene or "").upper()
    layers: Dict[str, Any] = {"gene": g}

    # 1. the curated catalogue of loci — keyed by rsID, so «a gene» is its loci
    book = core.loci().get("loci") or {}
    rows = book.values() if isinstance(book, dict) else book
    cat = [x for x in rows if isinstance(x, dict) and (x.get("gene") or "").upper() == g]
    layers["catalogue"] = {"count": len(cat)}

    # 2. ClinVar — by coordinate
    cv = clinvar_for_gene(g)
    # `scan_note` and `truncated` travel with the layer. Without the first, a
    # scan that was never run printed as «coordinates not obtained» — blaming
    # the gene lookup for a table nobody had written. Without the second, the
    # warning that the page was cut short died here, and the frame said «0 in
    # this gene» over a finding past the cut.
    layers["clinvar"] = {"status": cv.get("status"), "count": cv.get("count"),
                         "resolved_by": cv.get("resolved_by"),
                         "region": cv.get("region"), "fix": cv.get("fix"),
                         "scan_note": cv.get("scan_note"),
                         "truncated": cv.get("truncated")}

    # 3. the ACMG secondary-findings panel — by symbol, and it says which of its
    #    genes were not read, which is a coverage statement nothing else gives
    try:
        ac = acmg_findings()
        # The 84 symbols travel inside the build, so whether a gene is in the
        # panel is answerable with no network and no annotation file. That is
        # half of what a reader wants from a gene they have just named.
        panel = {str(x).upper()
                 for x in (core._read_knowledge("acmg_sf.json").get("genes") or [])}
        in_panel = g in panel if panel else None
        hits = [h for h in (ac.get("hits") or []) if (h.get("gene") or "").upper() == g]
        unread = {str(x).upper() for x in (ac.get("unread_genes") or [])}
        layers["acmg"] = {"in_panel": in_panel, "count": len(hits),
                          "unread": (g in unread) if unread else None,
                          "status": ac.get("status")}
    except Exception as exc:                                         # noqa: BLE001
        layers["acmg"] = {"in_panel": None, "status": "unavailable",
                          "reason": type(exc).__name__}

    # 5. the curated verdict about the GENE itself — the sentence somebody
    #    wrote and verified about what does NOT follow from it.
    #
    # This shelf exists because one such sentence was found written, verified,
    # translated into both languages, listed in `LOCALIZABLE_FIELDS` and covered
    # by a test — and read by nothing. The test guarded that the field was IN THE
    # FILE, which is not the same claim as that a reader ever sees it. On the
    # screen the gene it belongs to printed two bare genotypes.
    #
    # A verdict about a gene is not a shelf note: it is the answer to the
    # question the reader asked, so it is printed before the shelves and it is
    # repeated beside the findings, where a reader who scrolled past the frame
    # still meets it.
    layers["verdict"] = gene_verdict(g)

    # 4. coverage — the one that qualifies every «nothing found» above.
    #
    # Judged against THIS FILE's own middle, never against an absolute bar.
    #
    # Measured before it was chosen. On a 30× whole genome the callable fraction
    # at 20× runs: median 79.8 %, best gene 92 %, and not one of ninety-three
    # reaching 95 %. Any clinical-looking threshold therefore fires on almost
    # every gene — which is this project's own rule about a flag that goes off on
    # everything: it is then measuring a property of the data, not of the objects.
    # Eighty per cent at 20× is the shape of a 30× depth curve, not a defect of
    # the gene.
    #
    # What does stand out stands out by DISTANCE from that middle: GLA at 8 %,
    # PMS2 at 42 %, and both for reasons that are real — X-linked, and pseudogene
    # homology. So the ruler is the file's own median, and it travels with the
    # sequencing depth: the same code says something useful at 30× and at 100×.
    #
    # The number is printed whenever anything is said at all. A verdict without
    # the measurement behind it is the thing this whole layer exists to refuse.
    #
    # The first version of this line asked `core.callability()` behind a
    # `hasattr` guard. There is no such name on `core` — it lives on `limits` —
    # so the guard was false on every machine and the line said «not measured»
    # on a profile carrying ninety-three measured genes. A check that cannot
    # succeed, defaulting to a sentence that sounds cautious and is wrong.
    #
    # The table is read inside `gene_coverage`, which is where a read that
    # fails becomes its own state. Reading it here and handing over `{}` on
    # failure made an unreadable table print as «not measured» — the same
    # cautious-sounding wrong sentence, one branch over.
    layers["coverage"] = gene_coverage(g)
    return layers


#: How far below its own file's middle a gene has to sit before the answer about
#: it is qualified. Points of the callable fraction, not a clinical bar — see the
#: measurement in `gene_layers`. Twenty points puts the five genes that stand out
#: on the owner's file inside it and leaves the other eighty-eight alone.
BELOW_MEDIAN_POINTS = 20.0

#: And a floor, for the case the relative rule cannot catch: a file poorly read
#: THROUGHOUT has a low median, so every gene sits near it and nothing is ever
#: «far below». Half the gene unread is worth saying whatever the neighbours do.
POORLY_READ_BELOW = 50.0


#: The order the bases are tried in, strongest first. A verdict outranks a
#: phenotype model on purpose: MTHFR carries both, and the model is exactly what
#: the verdict exists to say must not be used for dosing.
BASIS_ORDER = ("verdict", "note", "guideline", "pair", "none")


def locus_basis(rsid: str, entry: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """What licenses saying anything at all about this locus.

    Five states, and the last of them has to be printed: a locus that carries no
    rule, no note and no verdict prints a genotype and nothing else, and a
    genotype and nothing else is read as meaning something. Which of the five a
    locus is in is decided from the files, never from the text of a note.
    """
    from .. import core
    book = core.loci().get("loci") or {}
    e = entry if entry is not None else (book.get(rsid) or {})
    gene = (e.get("gene") or "").upper()
    out: Dict[str, Any] = {"rsid": rsid, "gene": gene}

    if gene and gene_verdict(gene)["text"]:
        out["kind"] = "verdict"
        return out
    raw = e.get("note")
    if isinstance(raw, dict):                 # unresolved catalogue, both languages
        raw = raw.get("ru") or raw.get("en")
    if raw and str(raw).strip():
        out["kind"] = "note"
        return out
    kb = core.cpic_kb()
    gdef = (kb.get("genes") or {}).get(gene) or {}
    if gdef and not gdef.get("not_a_cpic_drug_pair"):
        out["kind"] = "guideline"
        return out
    pairs = core._read_knowledge("cpic_pairs.json")
    rows = pairs.get("pairs") if isinstance(pairs, dict) else pairs
    if any(isinstance(p, dict) and (p.get("gene") or "").upper() == gene
           for p in (rows or [])):
        out["kind"] = "pair"
        return out
    out["kind"] = "none"
    return out


def gene_verdict(gene: str) -> Dict[str, Any]:
    """What this project has decided to say about the gene, as opposed to a locus.

    Returns the text with the file and field it came from, so that a verdict can
    never be printed without being attributable: a sentence of this kind is a
    medical statement, and an unattributed one is indistinguishable from a guess.
    """
    from .. import core
    g = (gene or "").upper()
    gd = ((core.cpic_kb().get("genes") or {}).get(g)) or {}
    raw = gd.get("not_a_cpic_drug_pair")
    if isinstance(raw, dict):                  # unresolved catalogue, both languages
        raw = raw.get("ru") or raw.get("en")
    if not raw:
        return {"text": None}
    return {"text": str(raw), "field": "not_a_cpic_drug_pair",
            "source": "cpic_drug_gene.json"}


def gene_coverage(gene: str, rows=None) -> Dict[str, Any]:
    """How well this one gene was read — four states, and only one is silent.

    `fine` is the only state that may be left unsaid, and it means «not unusual
    for this file», never «adequate»: that judgement belongs to whoever knows
    what the question needs. The other three have to speak, and the reason is the
    same one that made a missing VCF row print as «reference»: silence is read as
    reassurance, so a silence that means «nobody measured» is a false one.
    """
    from .. import limits as _limits
    g = (gene or "").upper()
    if rows is None:
        try:
            rows = _limits.callability()
        except Exception as exc:                                     # noqa: BLE001
            # A table that exists and cannot be read is not a table nobody
            # made. `not_measured` sends the reader to run the measurement;
            # this sends them to the file.
            return {"gene": g, "measured": False, "state": "unavailable",
                    "reason": type(exc).__name__}
    out: Dict[str, Any] = {"gene": g, "measured": bool(rows)}
    if not rows:
        out["state"] = "not_measured"
        return out
    row = rows.get(g)
    if not row:
        # The table is a PANEL, not a genome: most genes are outside it, and for
        # them «this file measured coverage» is true and says nothing about this
        # gene.
        out["state"] = "gene_not_in_table"
        out["table_size"] = len(rows)
        return out
    try:
        pct = float(row.get("pct_20x"))
    except (TypeError, ValueError):
        out["state"] = "not_measured"
        return out
    vals = sorted(float(r["pct_20x"]) for r in rows.values()
                  if str(r.get("pct_20x") or "").replace(".", "", 1).isdigit())
    median = vals[len(vals) // 2] if vals else None
    out.update({"pct_20x": pct, "median_pct_20x": median,
                "mean_depth": row.get("mean_depth")})
    if pct < POORLY_READ_BELOW or (median is not None
                                   and median - pct >= BELOW_MEDIAN_POINTS):
        out["state"] = "low"
    else:
        out["state"] = "fine"
    return out


def genome_status() -> Dict[str, Any]:
    from .. import genome
    return genome.available()


#: Inputs from which ClinVar, the ACMG secondary-findings list and polygenic
#: scores may not be answered. Named by the MEASURED class (task 87), not by the
#: file's extension or the vendor's label.
NARROW_INPUTS = frozenset({
    "array",                     # a consumer chip, whatever it arrived in
    "genotype_table",            # a table of chosen positions — a chip by another name
    "panel",                     # a genotyping panel distributed as a VCF
    "sparse",                    # a low-pass screen
    "imputed_panel",             # mostly inferred, not observed
    "partial_callset_indels",    # half a call set
    "partial_callset_snvs",      # the other half
    "unmeasured",                # breadth not established — see the docstring
})

#: An exome is NOT in the set above, and that is the whole of a change made after
#: an outside reviewer ran the package over three clinical files. An exome landed
#: in `sparse` — its gene-poor windows are empty by construction — and `sparse`
#: closed ClinVar and the ACMG list. So on the one input where a screen for known
#: pathogenic variants is most obviously worth running, the screen never ran, and
#: the output said «input too narrow» about a file covering twenty thousand genes.
#:
#: Polygenic scores are a different question and stay shut. A score's weights and
#: its reference distribution are built on genome-wide data; run over the coding
#: two per cent, the sum is not a low percentile, it is a number with no
#: distribution behind it.
NARROW_FOR_SCORES = frozenset({"exome"})


def _array_only_input(also_narrow: frozenset = frozenset()) -> Optional[Dict[str, Any]]:
    """A refusal when the input is a genotyping array, for the three paths that
    must not run on one.

    ClinVar screening, ACMG secondary findings and polygenic scores are closed on
    an array not because the code cannot execute them but because the RESULT
    would not mean what it says. A chip's positive predictive value for rare
    pathogenic variants is 4.2 % for BRCA1/2 (Weedon, BMJ 2021 — 889 positives,
    37 confirmed) and 40 % of variants sent for confirmation from raw consumer
    data were false (Moscarello 2019). And a chip carries no depth, so «nothing
    found» in a gene says only that its handful of probes were negative.

    These three stay shut until the frequency floor (task 2) and the input
    quality label (task 8) exist. Until then the honest behaviour is to refuse
    with the reason — never to answer with a value that reads like a finding.
    The locus catalogue is a different matter and stays open: it is made of
    common pharmacogenetic and trait variants, which is the register where a chip
    works as designed.

    Task 99. The gate used to key on the CARRIER — `input_class == "array"` — and
    a chip does not stop being a chip by arriving as a VCF. Measured on the
    reference corpus: a genotyping panel distributed as a VCF holds 553 197
    variants and a genotype table 48 838 chosen positions, and both of them
    answered «your VCF has not been annotated yet — run the preparation», which
    is an INVITATION to do the exact thing this gate exists to prevent. Task 87
    measured the breadth of every input and nothing read the measurement; now
    this does.

    `unmeasured` is on the closed side deliberately. The two errors here are not
    symmetric: refusing a genome whose windows could not be probed costs one
    command and a sentence, while opening a screen that was never measured costs
    a finding a person may act on. Where the evidence is missing, the answer is
    the refusal — the same rule as everywhere else in this codebase.
    """
    from .. import genome
    st = genome.available()
    if not st.get("ready"):
        # No input at all is a different sentence, and the callers already have
        # it: «this has not been annotated yet». Closing here would tell a person
        # with no genome that their genome is too narrow.
        return None
    profile = st.get("input_profile")
    if profile not in (NARROW_INPUTS | also_narrow):
        return None
    if profile == "array":
        arr = st.get("array") or {}
        return {"status": "input_is_an_array", "available": False,
                "input_profile": profile, "vendor": arr.get("vendor"),
                "message": _t("array.path_closed"),
                "open_instead": _t("array.open_instead")}
    measured = st.get("callset") or st.get("tabular") or {}
    return {"status": "input_too_narrow", "available": False,
            "input_profile": profile,
            "measured": {k: measured.get(k) for k in
                         ("observed_per_mb", "variants", "rows", "imputed_share")
                         if measured.get(k) is not None},
            "message": _t("narrow.path_closed_" + profile,
                          per_mb=measured.get("observed_per_mb") or 0,
                          rows=measured.get("rows") or 0,
                          share=int(round((measured.get("imputed_share") or 0) * 100))),
            "open_instead": _t("array.open_instead")}


def _input_boundary() -> Optional[Dict[str, Any]]:
    """What this input leaves unanswered while the path is OPEN.

    A refusal names its own boundary; an answer used to name none, and the two
    together taught the reader that an answer means «everything was looked at».
    On an exome it does not: the coding part was looked at, and a reader who is
    not told that will read a silence about an intron as an absence.
    """
    from .. import genome
    st = genome.available()
    if st.get("input_profile") != "exome":
        return None
    cs = st.get("callset") or {}
    return {"input_profile": "exome",
            "coding_per_mb": cs.get("coding_per_mb"),
            "note": _t("narrow.exome_boundary")}


def clinvar_findings(limit: int = 200) -> Dict[str, Any]:
    """The patient's clinically significant findings (ClinVar × the personal VCF)."""
    closed = _array_only_input()
    if closed:
        return closed
    from .. import genome
    r = genome.clinvar_hits(limit=limit)
    r["disclaimer"] = DISCLAIMER()
    bound = _input_boundary()
    if bound:
        r["input_boundary"] = bound
    r["penetrance"] = _penetrance_block()
    # Whether an indel in this list could have been matched at all. Attached
    # always, because it qualifies the SILENCE as much as the hits: without
    # left-alignment a pathogenic indel spelled differently from ClinVar's copy
    # simply does not appear, and nothing on screen distinguishes that from a
    # genome that does not carry one.
    norm = genome.clinvar_normalisation()
    r["normalisation"] = norm
    if not norm.get("left_aligned"):
        r["indel_caveat"] = _t("genome.indels_not_left_aligned")
    return r


def _penetrance_block() -> Dict[str, Any]:
    """Penetrance caveats — what a list of pathogenic findings misleads without."""
    from .. import genome
    pn = genome.penetrance_notes()
    return {"one_line": pn.get("_meta", {}).get("one_line"),
            "principles": [{"title": p.get("title"), "text": p.get("text"), "source": p.get("source")}
                           for p in pn.get("principles", [])]}


def _unread_genes(genes) -> List[Dict[str, Any]]:
    """Genes among `genes` whose bases were not read deeply enough to decide.

    «No pathogenic variant found» in a gene that was never read is the same
    sentence as «no pathogenic variant found» in a gene read end to end, and a
    reader cannot tell them apart. The coverage has been computed all along —
    `limits.callability()` reads it — and the findings report never consulted it.
    Two facts held, neither compared with the other.
    """
    from .. import limits
    cov = limits.callability() or {}
    out = []
    for g in genes:
        row = cov.get(g)
        if not row:
            continue
        pct = row.get("pct_10x")
        if pct is None:
            continue
        try:
            pct = float(pct)
        except (TypeError, ValueError):
            continue
        if pct < 90.0:
            out.append({"gene": g, "pct": round(pct, 1)})
    return sorted(out, key=lambda x: x["pct"])


def acmg_findings() -> Dict[str, Any]:
    """ACMG SF secondary findings + the layer of honesty about interpretation."""
    closed = _array_only_input()
    if closed:
        return closed
    from .. import genome
    r = genome.acmg_sf_findings()
    r["disclaimer"] = DISCLAIMER()
    bound = _input_boundary()
    if bound:
        r["input_boundary"] = bound
    r["penetrance"] = _penetrance_block()
    # An empty result is a claim about the panel, so it has to carry what of the
    # panel was actually readable. Attached whether or not anything was found:
    # a gene read at 72 % qualifies a finding as much as it qualifies a silence.
    from .. import genome as _g
    genes = list((_g.acmg_catalogue().get("genes") or {})) if hasattr(_g, "acmg_catalogue") \
        else list((core._read_knowledge("acmg_sf.json").get("genes") or {}))
    r["unread_genes"] = _unread_genes(genes)
    return r


def apoe() -> Dict[str, Any]:
    from .. import genome
    return genome.apoe_status()


# ==========================================================================
# Polygenic risks (PGS) and the longevity layer (LongevityMap)
# ==========================================================================
def _panel_facts(data: Dict[str, Any]) -> Dict[str, Any]:
    """The panel these numbers were computed against, and whether it is still the
    one that applies.

    Three separate facts that were being reported as one, wrongly. `stats` used
    to carry the stored panel beside `ancestry_stated`, and that flag asked the
    PROFILE whether a panel was known — not the file whether these percentiles
    had been computed against it. Once the panel began to be determined from the
    genome, the flag went true for everybody with a genome while the numbers went
    on being whatever the scoring run had been given, which defaulted to EUR.
    The interface then said the panel was settled and showed percentiles computed
    against another one. Nothing could tell.

    So: what the numbers used, where THAT came from, what applies now, and
    whether the two agree. `ancestry_stated` stays — the contract may not
    shrink — and now means what it says: the panel behind these numbers was
    chosen rather than fallen back on. A file written before the source was
    recorded cannot say, and «cannot say» is not «yes».
    """
    meta = data.get("_meta") or {}
    used = meta.get("superpopulation", "EUR")
    used_source = meta.get("superpopulation_source")
    applies = core.ancestry()
    return {
        "superpopulation": used,
        "superpopulation_source": used_source,
        "ancestry_stated": used_source in ("asked", "stated", "genome"),
        "ancestry_determined": applies["value"],
        "ancestry_source": applies["source"],
        # True only when there IS something to disagree with. No determination
        # is not a disagreement — it is the ordinary state before the genome has
        # been asked, and it has its own line in `limits`.
        "panel_out_of_date": bool(applies["value"]) and applies["value"] != used,
    }


def _panel_caveat(data: Dict[str, Any]) -> List[Dict[str, str]]:
    """Said out loud when the panel behind the numbers is not the one that applies.

    A field nobody prints is a fact nobody meets. These percentiles carry the
    panel they were computed against into every screen; when the genome has since
    named a different one, the number is a position inside the wrong population
    and the reader is owed that sentence beside it rather than a flag in a
    structure.
    """
    facts = _panel_facts(data)
    if facts["panel_out_of_date"]:
        return [{"key": "panel_out_of_date",
                 "note": _t("prs.caveat.panel_out_of_date",
                            used=facts["superpopulation"],
                            applies=facts["ancestry_determined"])}]
    if not facts["ancestry_stated"]:
        return [{"key": "panel_defaulted",
                 "note": _t("prs.caveat.panel_defaulted", used=facts["superpopulation"])}]
    return []


def prs_method_caveats() -> List[Dict[str, str]]:
    """What the polygenic computation does NOT do, said once and carried.

    The scoring itself happens in a separate process (`just-prs-mcp`), so these
    are not defects this codebase can repair — which is exactly why they have to
    be printed rather than left implicit. A percentile that arrives without them
    reads as a measurement; with them it reads as what it is.

    Three of the four are structural to how the score is summed, and the fourth
    is about provenance:

    · STRAND-AMBIGUOUS VARIANTS. A locus whose alleles are their own complement
      (A/T, C/G) matches whichever strand it is reported on, so a strand flip is
      indistinguishable from a correct call. This build identifies those loci on
      the array path (`array_genome.strand_ambiguous_loci`, computed from the
      catalogue) and cannot do so inside a score it does not sum.
    · MISSING VARIANTS. A variant absent from the file is simply not added,
      which is arithmetically the same as imputing a zero dose and biases the sum
      downward. This one IS measured here — `weight_mass_coverage` says how much
      of the model's weight was actually present, and the percentile is withdrawn
      from trust below the threshold rather than printed with a footnote.
    · HARD GENOTYPES ONLY. No dosage; an uncertain call counts as a certain one.
    · THE REFERENCE PANEL. The percentile is a position within a reference
      sample. The scoring package is pinned by version, not by hash, and the
      1000 Genomes cache it downloads on first use is not pinned at all — so two
      machines can, in principle, produce percentiles from different reference
      data for the same genome.
    """
    return [{"key": k, "note": _t(f"prs.caveat.{k}")}
            for k in ("strand_ambiguous", "missing_as_zero", "hard_genotypes",
                      "reference_panel")]


def PRS_DISCLAIMER() -> str:
    """The caveat specific to polygenic scores — see the note on DISCLAIMER()."""
    return _t("disclaimer.prs")


def _localise_from_catalogue(rows, cat_rows, key_field, fields, extra_key=None):
    """Take the named fields from the catalogue, in the reader's language.

    `prs_results.json` and `longevity_findings.json` are STORED RESULTS. A label
    inside one of them is a copy of the catalogue made on the day the file was
    written, in the language that run happened to be speaking — so a person
    reading the product in English met Russian names among the English rows.
    Neither catalogue is missing a translation: `core._read_knowledge` resolves
    both languages on read, and nobody asked it.

    The catalogue decides what a thing is CALLED; the stored file decides what
    the number is. A row the catalogue does not carry keeps every string it was
    stored with — dropping it would leave a percentile with no name, which is a
    worse answer than a name in the wrong language.
    """
    by_key = {}
    for c in cat_rows:
        k = c.get(key_field)
        if isinstance(k, str) and k:
            by_key[k.lower()] = c
        if extra_key:
            e = c.get(extra_key)
            if isinstance(e, str) and e:
                by_key.setdefault(e.lower(), c)
    for r in rows:
        src = by_key.get(str(r.get(key_field) or "").lower())
        if src is None and extra_key:
            src = by_key.get(str(r.get(extra_key) or "").lower())
        if src is None:
            continue
        for f_from, f_to in fields:
            v = src.get(f_from)
            if isinstance(v, str) and v:
                r[f_to] = v


def _annotate_prs_evidence(traits: List[Dict[str, Any]]) -> None:
    """Set the level of evidence from knowledge/prs_traits.json.

    Without it all 74 traits look equally weighty, and that is not true: coronary
    artery disease and prostate cancer have prospective data, most of the rest have
    only a population association.
    """
    cat = core._read_knowledge("prs_traits.json")
    tiers = (cat.get("_meta") or {}).get("evidence_tiers", {})
    by_term, by_label = {}, {}
    for c in cat.get("traits", []):
        if c.get("term"):
            by_term[c["term"].lower()] = c
        if c.get("label"):
            by_label[c["label"].lower()] = c
    for t in traits:
        src = by_term.get(str(t.get("term", "")).lower()) or by_label.get(str(t.get("label", "")).lower())
        if not src:
            continue
        ev = src.get("evidence")
        if not ev:
            continue
        t["evidence"] = ev
        t["evidence_label"] = (tiers.get(ev) or {}).get("label", ev)
        if src.get("evidence_note"):
            t["evidence_note"] = src["evidence_note"]


#: The same 0.90 the variant-count gate uses, applied to the WEIGHT the model
#: actually places on what was found. Kept equal deliberately: two thresholds
#: with different numbers would be two policies, and nobody could say which one
#: a withdrawn percentile failed.
_PRS_MIN_WEIGHT_MASS = 0.90

from .prs_quality import annotate_measurement as _annotate_prs_measurement  # noqa: E402


def _withheld_by_sex(traits):
    """(kept, withheld). A trait the catalogue marks for one sex only.

    Symmetric, and it also withholds when the sex is NOT RECORDED: choosing a
    side there would be the same failure pointing the other way. The catalogue is
    the authority — a stored result carries no such mark, and matching is by the
    trait term the catalogue uses.
    """
    marked = {}
    for t in (core._read_knowledge("prs_traits.json").get("traits") or []):
        if t.get("applies_to_sex"):
            marked[(t.get("term") or "").strip().lower()] = t["applies_to_sex"]
    if not marked:
        return traits, []
    sex = core.profile_sex()
    kept, withheld = [], []
    for t in traits:
        need = marked.get((t.get("term") or t.get("trait") or "").strip().lower())
        if need and need != sex:
            withheld.append({"label": t.get("label") or t.get("term"),
                             "applies_to_sex": need,
                             "reason": "sex_not_recorded" if not sex else "other_sex",
                             "note": _t("prs.withheld_by_sex" if sex
                                        else "prs.withheld_sex_unknown", sex=need)})
            continue
        kept.append(t)
    return kept, withheld


def prs_findings() -> Dict[str, Any]:
    """Aggregated polygenic scores (profile/prs_results.json), grouped by category.

    Closed on an array input for now: a score computed from a chip needs
    imputation and an ancestry-matched reference before its percentile means
    anything, and neither the frequency floor (task 2) nor the input quality
    label (task 8) exists yet. Refusing with the reason is the only honest state
    in between.

    Returns {categories:[{category, traits:[...]}], high[], stats, disclaimer}.
    high — the reliable traits with a percentile ≥80 (what to look at when screening).
    """
    closed = _array_only_input(NARROW_FOR_SCORES)
    if closed:
        return closed
    data = core.prs_results()
    traits = data.get("traits", []) if isinstance(data, dict) else []
    if not traits:
        return {"available": False, "disclaimer": PRS_DISCLAIMER(),
                "message": _t("prs.not_computed")}
    # WHERE THESE NUMBERS CAME FROM, and when. A polygenic score is a stored
    # RESULT: it was computed once from a VCF and lives in the profile afterwards.
    # So the screen could show twelve percentiles a centimetre below a chip
    # reading «Full genome (VCF): no data», both true and reading as a
    # contradiction — a reader has no way to tell which of the two to believe.
    # The answer is neither: the file was there when this was computed and is not
    # attached now, and saying so is shorter than either half.
    _pm = core.profile_meta(data)
    _computed = _pm.get("generated") or _pm.get("updated")
    _connected = bool(genome_status().get("ready"))
    for tr in traits:                      # a guard layer: double counting of the input shows at once
        _mr = tr.get("match_rate")
        if isinstance(_mr, (int, float)) and _mr > 1.0001:
            tr["reliable"] = False
            tr["integrity_note"] = _t("prs.integrity_double")
        # A FLAT threshold on the COUNT of matched variants is weight-blind, and
        # a polygenic score is not a vote — its variants carry wildly different
        # weights. Ninety per cent of the variants can be sixty per cent of the
        # weight, and the percentile computed from what is left is a number about
        # a different model. The engine already returns `weight_mass_coverage`;
        # nothing consulted it. The gate now takes the WEAKER of the two and says
        # which one withdrew trust.
        _wm = tr.get("weight_mass_coverage")
        if isinstance(_wm, (int, float)) and _wm < _PRS_MIN_WEIGHT_MASS:
            tr["reliable"] = False
            tr["weight_mass_note"] = _t("prs.weight_mass_low",
                                        pct=round(float(_wm) * 100, 1))
    # THE SEX GUARD, applied where the report is built and not only where the
    # score is computed. `prs_results.json` is a stored result: it may have been
    # computed before the person recorded their sex, or on another machine
    # entirely, and a percentile for an organ the reader does not have would then
    # sail through as an ordinary line. Withheld traits are NAMED — a trait that
    # disappears from a panel in silence is indistinguishable from one that was
    # never in it.
    traits, withheld_by_sex = _withheld_by_sex(traits)
    # The name of a trait and the name of its category are the catalogue's, in
    # the language being read; the percentile is the file's. Joined on `term`,
    # which is the one field of a stored trait that is not in any language.
    _localise_from_catalogue(
        traits, core._read_knowledge("prs_traits.json").get("traits") or [],
        "term", (("label", "label"), ("category", "category")), extra_key="label")
    _annotate_prs_evidence(traits)
    _annotate_prs_measurement(traits)
    cats: Dict[str, List[Dict[str, Any]]] = {}
    order: List[str] = []
    for t in traits:
        c = t.get("category") or _t("prs.category_other")
        if c not in cats:
            cats[c] = []; order.append(c)
        cats[c].append(t)
    def pnum(t):
        p = t.get("percentile")
        return p if isinstance(p, (int, float)) else -1
    high = sorted([t for t in traits if t.get("reliable") and pnum(t) >= 80],
                  key=lambda t: -pnum(t))
    reliable = [t for t in traits if t.get("reliable")]
    return {
        "available": True,
        "categories": [{"category": c, "traits": cats[c]} for c in order],
        "provenance": {
            "computed": _computed, "genome_connected": _connected,
            "note": (None if _connected
                     else _t("prs.from_a_genome_not_attached", date=_computed or "—")),
        },
        "high": high,
        "withheld_by_sex": withheld_by_sex,
        # Said on every report rather than remembered by whoever reads it: the
        # sum happens in another process, and what that process does not do is
        # part of what this number means.
        "method_caveats": prs_method_caveats() + _panel_caveat(data),
        "stats": {"total": len(traits), "reliable": len(reliable),
                  "high": len(high), **_panel_facts(data),
                  "updated": (data.get("_meta") or {}).get("updated")},
        "disclaimer": PRS_DISCLAIMER(),
    }


def genome_updates() -> Dict[str, Any]:
    """Result of the last check for database updates (genome/whats_new.json).
    Shows what appeared when the genome was checked against a fresh ClinVar."""
    data = core.whats_new()
    if not data or not data.get("clinvar"):
        return {"available": False}
    cv = data.get("clinvar", {})
    return {"available": True, "last_checked": data.get("last_checked"),
            "clinvar": {"release": cv.get("release"), "new": cv.get("new", []),
                        "changed": cv.get("changed", []), "counts": cv.get("counts", {})}}


def longevity_findings() -> Dict[str, Any]:
    """Longevity layer (LongevityMap × the owner's genome, profile/longevity_findings.json).

    Returns {available, apoe, known[], significant_genes[], stats, disclaimer}.
    The key parts are the APOE ε status and the well-studied markers (FOXO3 and so on).
    """
    data = core.longevity_data()
    if not data or not data.get("known"):
        return {"available": False, "disclaimer": DISCLAIMER(),
                "message": _t("longevity.not_built")}
    known = data.get("known", []) or []
    # Same rule as the polygenic layer, and one more thing: the page was printing
    # `note`, and these rows carry none. Everything that says what a marker MEANS
    # — what the allele is, what the dose does, what it argues for — is in the
    # catalogue with both languages in it, and none of it reached the reader.
    _localise_from_catalogue(
        known, [{**v, "rsid": k} for k, v in
                (core._read_knowledge("longevity_directions.json").get("directions") or {}).items()],
        "rsid", (("label", "label"), ("action", "action"),
                 ("zygosity_note", "zygosity_note"),
                 ("population_caveat", "population_note")))
    # The verdict is a TOKEN — `plus`, `neutral`, `flag` — and the sentence for it
    # lives in the message catalogue, so it is written once and in both languages.
    # Recomputed from the catalogue where the copies are known: a stored verdict
    # was decided by whatever the catalogue said on the day of the build.
    _dirs = core._read_knowledge("longevity_directions.json").get("directions") or {}
    # The set of verdicts the CATALOGUE can produce. A stored file may carry
    # anything — the demo profile holds «🟢 favourable», a sentence somebody
    # rendered once — and composing a message key out of an unknown token is how
    # ⟦longevity.verdict.🟢 favourable⟧ reaches a reader. Known token → the
    # sentence, in both languages; unknown → whatever the file already says,
    # which is at least prose.
    _known_verdicts = {v for d in _dirs.values()
                       for v in (d.get("verdict_by_copies") or {}).values()}
    # `see_apoe` is written by our own builder for the two positions the ε-status
    # is computed FROM. They are not findings of their own — the card above is the
    # finding — but the word still has to be a sentence wherever it is printed.
    _known_verdicts.add("see_apoe")
    _known_conf = {"high", "medium", "low", "curated"}
    for k in known:
        src = _dirs.get(k.get("rsid")) or {}
        by_copies = src.get("verdict_by_copies") or {}
        c = k.get("copies_favorable")
        tok = (by_copies.get(str(c)) if c is not None else None) or k.get("verdict")
        k["verdict_token"] = tok if tok in _known_verdicts else None
        k["verdict_label"] = (_t("longevity.verdict." + tok) if tok in _known_verdicts
                              else (k.get("verdict") or None))
        conf = src.get("confidence") or k.get("confidence")
        k["confidence_label"] = (_t("web.longevity.confidence." + conf)
                                 if conf in _known_conf else None)
    sig = data.get("significant_by_gene", {}) or {}
    # the famous longevity genes come first
    famous = ["FOXO3", "APOE", "SIRT1", "SIRT3", "CETP", "IL6", "TP53", "KL", "IGF1R",
              "AKT1", "APOC3", "ADIPOQ", "ACE", "TOMM40"]
    genes = sorted(sig.keys(), key=lambda g: (famous.index(g) if g in famous else 999, g))
    sig_genes = [{"gene": g, "variants": sig[g]} for g in genes]
    meta = data.get("_meta", {})
    return {
        "available": True,
        "apoe": data.get("apoe"),
        "known": known,
        "significant_genes": sig_genes,
        "stats": {"genotyped": meta.get("genotyped"), "carriers": meta.get("carriers"),
                  "significant_carriers": meta.get("significant_carriers"),
                  "significant_genes": len(sig_genes)},
        "disclaimer": (meta.get("disclaimer") or "") + " " + DISCLAIMER(),
    }


# ==================== the genetic side of the lipid profile ==================
# Task 63. Two facts that belong beside each other and were sitting in three
# different places: whether a protective loss-of-function variant of PCSK9 is
# carried, and what Lp(a) is. Neither is a risk calculation; together they say
# how much of a lipid picture is inheritance a person cannot change and how much
# is the part that moves.
#
# The reason this is one card and not two lines on two tabs is that each is
# misread alone. A low LDL-C with a PCSK9 LOF variant behind it means something
# different from the same number reached on a statin. And Lp(a) is invisible to
# the rest of a lipid panel entirely: it is set at birth, it does not respond to
# the things LDL-C responds to, and a normal panel with a high Lp(a) is a normal
# panel that has missed the finding.
#
# Two limits are printed rather than left implicit, because both are the kind
# that turn an absence into a false reassurance:
#
#   · Lp(a) level is driven mostly by the number of KIV-2 repeats in LPA — a
#     copy-number variant. Short-read sequencing and SNP arrays see it poorly.
#     A polygenic score is a genetic ESTIMATE and cannot stand in for the
#     measurement; the catalogue's own «Moderate» quality mark on PGS002101 is
#     that limit, stated in the place a reader will not look.
#   · Not carrying C679X is close to meaningless outside populations of African
#     descent, where it is almost absent. «Not a carrier» has to say so.

_PCSK9_LOF = ["rs11591147", "rs28362286"]        # direction resolved, primary PMIDs


_PCSK9_WAITING = ["rs28362263", "rs72646508"]    # position known, direction unresolved


_LPA_PGS = "PGS002101"


def _copies_of(genotype: str, allele: str) -> Optional[int]:
    if not genotype or not allele:
        return None
    g = genotype.replace("|", "").replace("/", "").strip().upper()
    if not g or set(g) - set("ACGT"):
        return None
    return g.count(allele.upper())


def _genome_readable() -> bool:
    """Whether a genome is being read at all — asked, not assumed.

    Every card in this module has an empty state, and each of them used to be
    written as if the genome were open and this particular position had nothing
    in it. The two are different facts with different remedies: one is answered
    by sequencing, the other by naming which file in a folder is yours.
    """
    from .. import genome as _g                              # lazy: core does the same
    try:
        return _g.vcf_path() is not None
    except Exception:                                        # noqa: BLE001
        return False


def lipid_genetics() -> Dict[str, Any]:
    """PCSK9 carriage and Lp(a), in one answer, each with what it is worth.

    Every branch has to say something. A card that renders nothing when the
    genome is absent is the failure this project exists to refuse: the reader
    concludes there was nothing to find, when the truth is that nothing was
    looked at. So the empty states carry the test that would fill them —
    for Lp(a), once in a lifetime, in nmol/L, and before a therapy decision
    rather than after it.
    """
    directions = (core.longevity_directions().get("directions") or {})
    loci = (core.loci().get("loci") or {})

    pcsk9 = []
    for rsid in _PCSK9_LOF:
        d = directions.get(rsid) or {}
        st = core.genotype_status(rsid)
        gt = (st or {}).get("genotype") or ""
        copies = _copies_of(gt, d.get("favorable") or "")
        # `assumed_ref` is not «reference». It means there is no row at this
        # position: either the reference, or nothing was read there. Counting it
        # as zero copies is the exact defect the answerability layer was built
        # after, so it is reported as unread instead.
        unread = bool(st and st.get("confidence") == "assumed_ref")
        # The catalogue stores a TOKEN per copy count, and the sentence lives in
        # the message catalogue. Prose inside a knowledge file prints raw into a
        # report the moment a field name is one the resolver does not know, and
        # it is invisible to the language gate besides.
        token = None
        if copies is not None and not unread:
            token = (d.get("verdict_by_copies") or {}).get(str(min(copies, 2)))
        pcsk9.append({
            "rsid": rsid, "gene": "PCSK9",
            "label": core._localized(d.get("label") or {}, _lang()) or "",
            "genotype": None if unread else (gt or None),
            "confidence": (st or {}).get("confidence"),
            "source": (st or {}).get("source"),
            "favorable": d.get("favorable"),
            "copies": None if unread else copies,
            "carrier": None if (copies is None or unread) else copies > 0,
            "verdict_token": token,
            "verdict": (_t(f"lipidgen.copies.{min(copies, 2)}")
                        if (token and copies is not None) else None),
            "population_note": core._localized(d.get("population_caveat") or {}, _lang()) or None,
            "action": core._localized(d.get("action") or {}, _lang()) or None,
            "pmids": d.get("pmids") or [],
            "status": "unread" if unread else ("read" if copies is not None else "no_data"),
        })

    # --- Lp(a): the measurement, and separately the genetic estimate ---------
    lab = (core.labs().get("markers") or {}).get("lpa") or {}
    pts = sorted([p for p in (lab.get("series") or []) if p.get("value") is not None],
                 key=lambda p: str(p.get("date", "")))
    measured = None
    if pts:
        last = pts[-1]
        hi = lab.get("ref_high")
        measured = {"value": last["value"], "unit": lab.get("unit") or "",
                    "date": str(last.get("date", "")), "ref_high": hi,
                    "above": (hi is not None and float(last["value"]) > float(hi))}
    estimate = None
    for cat in (prs_findings().get("categories") or []):
        for tr in cat.get("traits") or []:
            if tr.get("pgs_id") == _LPA_PGS:
                estimate = {"percentile": tr.get("percentile"), "pgs_id": tr.get("pgs_id"),
                            "quality": tr.get("quality_label"), "label": tr.get("label")}
    lpa = {
        "measured": measured,
        "estimate": estimate,
        # Printed whenever an estimate is on screen without a measurement — which
        # is precisely when it is most likely to be read as one.
        "estimate_is_not_a_measurement": _t("lipidgen.lpa.estimate_limit"),
        "what_to_do": None if measured else _t("lipidgen.lpa.order_it"),
    }

    read = [x for x in pcsk9 if x["status"] == "read"]
    carriers = [x for x in read if x["carrier"]]
    return {
        "status": "ok",
        "pcsk9": pcsk9,
        "pcsk9_waiting": [{"rsid": r, "gene": "PCSK9",
                           "why": core._localized(((core.longevity_directions().get("unresolved") or {})
                                                   .get("variants") or {}).get(r, {}).get("why") or {},
                                                  _lang())}
                          for r in _PCSK9_WAITING if r in loci],
        "lpa": lpa,
        # Four facts, and until now three sentences. «The positions have not
        # been read» is a statement about two rows of a file that IS being read;
        # when no genome is being read at all, saying it sends the reader to look
        # at their genome instead of at the folder, which is where the answer is.
        "headline": (_t("lipidgen.headline.carrier") if carriers
                     else (_t("lipidgen.headline.not_carrier") if read
                           else (_t("lipidgen.headline.unread") if _genome_readable()
                                 else _t("lipidgen.headline.no_genome")))),
        "how_to_read": _t("lipidgen.how_to_read"),
        "disclaimer": DISCLAIMER(),
    }
