"""Shared gene-reference topics within the existing body systems.

Membership is navigation, never permission to interpret an unclassified variant.
Personal topics join existing indexed VCF intervals without BAM depth scans or
protein prediction. The separate gene lookup can measure additional detail.
"""
from __future__ import annotations

from typing import Any

from .. import core
from ..i18n import t
from ..panel_reference import genome_context


def thematic_catalogue() -> dict[str, Any]:
    return core._read_knowledge("thematic_gene_panels.json")


def thematic_summaries(system: str | None = None) -> list[dict[str, Any]]:
    """Reference counts: genes are not counted as read positions."""
    return [{"key": key, "label": spec["label"], "genes": len(spec["genes"]),
             "positions": None, "regions": len(spec.get("regions") or []),
             "systems": spec.get("systems") or [],
             "kind": spec["kind"], "thematic": True, "unreadable": 0}
            for key, spec in (thematic_catalogue().get("panels") or {}).items()
            if system is None or system in (spec.get("systems") or [])]


@core.in_reading
def thematic_reference(key: str) -> dict[str, Any]:
    """The same reference cards for web, CLI, MCP and printed reports."""
    book = thematic_catalogue()
    spec = book["panels"][key]
    loci = core.loci().get("loci") or {}
    identities=core._read_knowledge('variant_reference_identity.json').get('variants') or {}
    genes = []
    regions = []
    for gene in spec["genes"] + (spec.get("regions") or []):
        row = genome_context(gene)
        row["positions"] = [genome_context(gene, rsid) for rsid, loc in {**identities,**loci}.items()
                            if loc.get("gene") == gene]
        # A reference card describes a gene. E belongs to the uncurated variant
        # interpretation, not to how confidently we know the gene's function.
        row["level"] = row["reference_context"]["level"] = None
        row["position_status"] = "catalogue_positions" if row["positions"] else "no_catalogue_positions"
        if gene in (spec.get("regions") or []):
            row["unit"] = "gene_region"
            regions.append(row)
        else:
            row["unit"] = "gene"
            row["reading_request"] = {
                "command": "genome",
                "tool": "sch_genome_lookup",
                "gene": row["reference_context"].get("canonical_symbol") or gene,
                "scope": "gene_region_on_request",
            }
            genes.append(row)
    positions = [p for gene in genes + regions for p in gene["positions"]]
    return {"status": "ok", "key": key, "label": spec["label"], "thematic": True,
            "reference_only": True, "kind": spec["kind"], "systems": spec.get("systems") or [],
            "catalogue_updated": book.get("_meta", {}).get("updated"),
            "source_tier": book.get("_meta", {}).get("source_tier"),
            "genes": genes, "regions": regions, "positions": positions,
            "counts": {"genes": len(genes), "regions": len(regions), "positions": len(positions)},
            "reading_note": t("thematic.reference_note"), "unreadable": [],
            "disclaimer": t("reference.notice")}


@core.in_reading
def thematic_readings(key: str, register: str) -> dict[str, Any]:
    """Positive catalogue readings only; a missing VCF row is not a negative."""
    from .. import genome
    from .panel_intake import _intake_reading

    book = thematic_reference(key)
    state = genome.available()
    recorded = core.profile_genotypes()
    for position in book["positions"]:
        special=(position['reference_context'].get('reference_identity') or {}).get('personal_call_supported') is False
        position["reading"] = _intake_reading(position["rsid"], state, 'indel_unsupported' if special else None,
                                              recorded=recorded.get(position["rsid"]))
    from .labs import analyze_labs
    measured={m['key']:m for m in analyze_labs()['markers']}
    for gene in book['genes']+book['regions']:
        if gene.get('reading_request'):
            if state.get('ready'):
                from .. import gene_region
                region = gene_region.preview(gene['reading_request']['gene'])
            else:
                region = {'status': 'no_genome', 'gene': gene['gene'],
                          'message': t('genome.refused.' + (state.get('reason') or 'no_file'))}
            # An actual regional result travels through CLI, web and agent tools.
            # A gene has no single genotype; retain each position and its quality.
            gene['region_reading'] = region
        contexts=[gene['reference_context']]+[p['reference_context'] for p in gene['positions']]
        patterns={p['association_id']:p for c in contexts for p in c.get('mechanistic_hypotheses') or []}
        wanted={m for p in patterns.values() for m in p.get('markers') or []}
        observations=[{k:measured[m].get(k) for k in ('key','name','value','unit','date','source','source_label','censored','date_source')}
                      for m in sorted(wanted&measured.keys()) if measured[m].get('display_recency') is True]
        gene['personal_comparison']={'scope':'mechanism_reference_with_observations','personal_variant_effect_established':False,
            'status':'observed' if observations else 'no_current_supported_match',
            'observations':observations,'patterns':list(patterns.values()),'note':t('thematic.comparison_note')}
    book.update(reference_only=False, patient_readings=True, register=register,
                genome_status=state, reading_note=t("thematic.reading_note"))
    book["counts"]["read"] = sum(p["reading"]["read"] for p in book["positions"])
    return book
