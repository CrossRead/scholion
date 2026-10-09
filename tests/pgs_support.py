"""Explicit, synthetic calibrated PGS fixtures; never repairs legacy inputs."""
from statistics import NormalDist

from scholion.pgs_validation import reference_snapshot


def calibrated(row):
    out = dict(row)
    p = out.get("percentile", 50.0)
    z = NormalDist().inv_cdf(p / 100) if 0 < p < 100 else (-10.0 if p == 0 else 10.0)
    out.update(score=z, z_score=z, reference_mean=0.0, reference_std=1.0,
               percentile_method="reference_panel", reference_panel="synthetic-test-panel",
               reference_panel_ancestry="EUR", genome_build="GRCh38",
               detected_genome_build="GRCh38", model_original_build="GRCh37",
               model_harmonized_build="GRCh38", build_mismatch=False)
    out.setdefault("percentile_reliable", True)
    out.setdefault("match_rate", 1.0)
    out.setdefault("weight_mass_coverage", 1.0)
    out["reference_validation"] = {"checked": True, "quality": "passed",
                                   "source": "synthetic test reference",
                                   "snapshot_sha256": reference_snapshot(out)}
    return out
