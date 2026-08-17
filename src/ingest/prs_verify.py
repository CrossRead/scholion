#!/usr/bin/env python3
"""Independent recomputation of polygenic scores — a control over an outside calculation.

Why: the percentiles are computed by the external package just-prs, and its output holds
impossible values — a match_rate above 1, that is "more variants matched than the model has".
This happens through double counting: the same position is present in the target VCF
twice (normalisation of multi-allelic sites through `bcftools norm -m -both` splits
them across rows), and a naive counter credits it with both variants.

This script computes on its own, using the standard library, with explicit deduplication
and explicit parsing of the effect allele, and prints ITS OWN numbers next to the foreign
ones. It fixes nothing — it makes the discrepancy visible.

IMPORTANT about "does not carry the effect allele". The target VCF was called without -v,
so at reference-homozygous sites ALT equals ".", and the model's effect allele is
physically absent from the row. That is NOT a miss: the dose is zero and the position
counts as covered. The first version of the script treated such sites as mismatches and
halved the coverage — if you see an implausibly low rate, check this first.

    python3 src/ingest/prs_verify.py --list                 # what is in the model cache
    python3 src/ingest/prs_verify.py PGS002406 PGS001773    # recompute specific ones
    python3 src/ingest/prs_verify.py --flagged              # all with match_rate > 1

Cache of the harmonised PGS Catalog models: ~/Library/Caches/just-prs/scores/*_hmPOS_GRCh38.txt.gz
(it is filled by the first run of `python3 -m scholion.prs report`). The script works
ONLY where this cache exists — that is, on the owner's machine.
"""
import argparse
import gzip
import time
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CACHE = Path(os.environ.get("SCHOLION_PRS_CACHE", "~/Library/Caches/just-prs/scores")).expanduser()
RESULTS = ROOT / "profile" / "prs_results.json"
COMPLEMENT = {"A": "T", "T": "A", "G": "C", "C": "G"}


def _open(p):
    return gzip.open(p, "rt", errors="replace") if str(p).endswith(".gz") else open(p, encoding="utf-8")


def load_target(vcf: Path):
    """Target genotypes: {(chrom,pos): [ (ref,[alts],[idx]), ... ]} — ALL rows of the position.

    This used to pick a single row by the rule "an SNP outranks an indel". That is wrong:
    which row is needed depends on WHICH variant the model is looking for, and at load
    time that is unknown. A contested coordinate can hold an SNP-level row and an indel
    row; if the model describes a deletion, the answer lies in the second one, and a blind
    choice yields a silently wrong dose. The choice was moved into dosage(), where the
    model's alleles are known.
    """
    geno, dup = {}, 0
    lines_at = {}
    with _open(vcf) as fh:
        for line in fh:
            if line[0] == "#":
                continue
            f = line.rstrip("\n").split("\t")
            if len(f) < 10:
                continue
            chrom = f[0][3:] if f[0].startswith("chr") else f[0]
            key = (chrom, f[1])
            lines_at[key] = lines_at.get(key, 0) + 1
            gt = f[9].split(":")[0].replace("|", "/")
            idx = [int(x) for x in gt.split("/") if x.isdigit()]
            rec = (f[3], [a for a in f[4].split(",")], idx)
            if key in geno:
                dup += 1
                geno[key].append(rec)
            else:
                geno[key] = [rec]
    return geno, dup, {k: v for k, v in lines_at.items() if v > 1}


def _legacy_one_row(recs):
    """The former rule "keep the SNP-level row" — kept only to measure its cost."""
    def rank(r):
        ref, alts, idx = r
        snp = len(ref) == 1 and all(len(a) == 1 or a in (".", "<*>") for a in alts)
        return (snp, any(i > 0 for i in idx))
    return [max(recs, key=rank)] if recs else recs


def _site_alleles(rec):
    """The site's and the call's alleles, brought to UPPER case.

    This is not cosmetic: mpileup inherits the case of the reference, and in soft-masked
    (repeat) regions the indel rows arrive in lower case —
    REF=taaaaaaaaaaaaa ALT=tAaaaaaaaaaaaaa. The PGS Catalog models are always in upper
    case, and without normalisation such rows would silently never match.
    And the contested positions are precisely the ones sitting in repeats.
    """
    ref, alts, idx = rec
    site = [ref.upper()] + [a.upper() for a in alts if a not in (".", "<*>", "")]
    calls = [site[i] for i in idx if i < len(site)]
    return site, calls


def dosage(effect: str, other: str, recs):
    """Dose of the effect allele, with the right row chosen by the model's alleles.

    Returns (dose, status): 'carried' — the allele is present in the call; 'zero' — the
    site is covered, the allele is not carried; 'flip' — matched on the opposite strand;
    None — no row of the position describes the model's variant.

    Row priority: both of the model's alleles in the site (rank 2, answered at once) →
    the effect allele present (rank 2, keep looking for better) → only the other one (rank 1).
    Ranks are compared EXPLICITLY, not by "whichever came first": a row holding only the
    other allele must not overwrite a later row that holds the effect allele.
    """
    if not recs:
        return None, None
    effect = effect.upper()
    other = (other or "").upper()
    best, best_rank = None, 0
    for rec in recs:
        site, calls = _site_alleles(rec)
        if not calls:
            continue
        has_e, has_o = effect in site, bool(other) and other in site
        if has_e and has_o:                       # unambiguous correspondence
            return sum(1 for c in calls if c == effect), "carried" if effect in calls else "zero"
        if has_e and best_rank < 2:
            best, best_rank = (sum(1 for c in calls if c == effect),
                               "carried" if effect in calls else "zero"), 2
        elif has_o and best_rank < 1:
            best, best_rank = (0, "zero"), 1
    if best:
        return best
    eff_c = "".join(COMPLEMENT.get(b, "?") for b in reversed(effect))
    oth_c = "".join(COMPLEMENT.get(b, "?") for b in reversed(other))
    for rec in recs:
        site, calls = _site_alleles(rec)
        if not calls:
            continue
        if eff_c in site:
            return sum(1 for c in calls if c == eff_c), "flip"
        if oth_c and oth_c in site:
            return 0, "flip"
    return None, None


def score_model(path: Path, geno, dup_pos=None, legacy_pick=False):
    n = matched = carried = zero = flips = 0
    total = 0.0
    unmatched_alleles = missing_pos = 0
    dup_pos = dup_pos or {}
    hits_dup = 0                 # model variants landing on a duplicated target position
    seen_model = {}              # duplicates inside the model itself
    model_indels = 0             # model variants that are not SNPs themselves
    indels_on_dup = 0            # ...and sit on a contested position — deduplication breaks them
    with _open(path) as fh:
        header = None
        for line in fh:
            if line.startswith("#"):
                continue
            f = line.rstrip("\n").split("\t")
            if header is None:
                header = {c: i for i, c in enumerate(f)}
                continue
            n += 1
            ci = header.get("hm_chr", header.get("chr_name"))
            pi = header.get("hm_pos", header.get("chr_position"))
            ei = header.get("effect_allele")
            oi = header.get("other_allele", header.get("hm_inferOtherAllele"))
            wi = header.get("effect_weight")
            if None in (ci, pi, ei, wi):
                continue
            try:
                chrom = f[ci][3:] if f[ci].startswith("chr") else f[ci]
                rec = geno.get((chrom, f[pi]))
            except IndexError:
                continue
            key = (chrom, f[pi])
            seen_model[key] = seen_model.get(key, 0) + 1
            oth_raw = f[oi] if oi is not None and oi < len(f) else ""
            is_indel = len(f[ei]) > 1 or len(oth_raw) > 1   # an indel, however it is written
            if is_indel:
                model_indels += 1
            if key in dup_pos:
                hits_dup += dup_pos[key] - 1
                if is_indel:
                    indels_on_dup += 1
            if not rec:
                missing_pos += 1
                continue
            oth = f[oi] if oi is not None and oi < len(f) else ""
            use = _legacy_one_row(rec) if legacy_pick else rec
            d, status = dosage(f[ei], oth, use)
            if d is None:
                unmatched_alleles += 1
                continue
            try:
                total += d * float(f[wi])
            except ValueError:
                continue
            matched += 1
            if status == "flip":
                flips += 1
            if d:
                carried += 1
            else:
                zero += 1
    model_dups = sum(v - 1 for v in seen_model.values() if v > 1)
    return {"variants": n, "matched": matched, "score": total,
            "match_rate": (matched / n) if n else 0.0,
            "carried": carried, "zero": zero, "flips": flips,
            "missing_pos": missing_pos, "allele_mismatch": unmatched_alleles,
            "hits_dup_target": hits_dup, "model_dups": model_dups,
            "model_indels": model_indels, "indels_on_dup": indels_on_dup,
            # what would come out if every target row were counted separately
            "naive_rate": ((matched + hits_dup) / n) if n else 0.0}


def _model_alleles(path: Path, keys=None):
    """{(chrom,pos): {(effect,other), ...}} from the model's harmonised file."""
    want = {}
    with _open(path) as fh:
        header = None
        for line in fh:
            if line.startswith("#"):
                continue
            f = line.rstrip("\n").split("\t")
            if header is None:
                header = {c: i for i, c in enumerate(f)}
                continue
            ci = header.get("hm_chr", header.get("chr_name"))
            pi = header.get("hm_pos", header.get("chr_position"))
            ei = header.get("effect_allele")
            oi = header.get("other_allele", header.get("hm_inferOtherAllele"))
            if None in (ci, pi, ei):
                continue
            try:
                chrom = f[ci][3:] if f[ci].startswith("chr") else f[ci]
                eff = f[ei].upper()
                oth = (f[oi] if oi is not None and oi < len(f) else "").upper()
            except IndexError:
                continue
            key = (chrom, f[pi])
            if keys is not None and key not in keys:
                continue
            want.setdefault(key, set()).add((eff, oth))
    return want


def _is_snp_pair(eff, oth):
    return len(eff) == 1 and (not oth or len(oth) == 1)


def _row_is_snp(f):
    alts = [x for x in f[4].split(",") if x not in (".", "<*>", "")]
    return len(f[3]) == 1 and all(len(x) == 1 for x in alts)


def _row_rank_for(want_pairs, f):
    """Rank of how well a VCF row matches the model's variants at this position (0..4).

    The key part is a match of TYPE. The string "A" in the indel record REF=ATT ALT=A
    is a deletion allele, not a single-nucleotide A: identical letters mean different
    things depending on the row's REF. A match of type (SNP↔SNP, indel↔indel) therefore
    gives +2, and an SNP model will always prefer an SNP row (rank ≥3) over an indel one,
    even if the indel's anchor letter happens to match textually (rank ≤2).
    """
    site = [f[3].upper()] + [a.upper() for a in f[4].split(",") if a not in (".", "<*>", "")]
    row_snp = _row_is_snp(f)
    best = 0
    for eff, oth in want_pairs:
        have = (1 if eff in site else 0) + (1 if oth and oth in site else 0)
        if have:
            best = max(best, (2 if _is_snp_pair(eff, oth) == row_snp else 0) + have)
    return best


def _dup_positions(vcf: Path):
    """Positions represented in the target VCF by more than one row."""
    seen, dups = set(), set()
    with _open(vcf) as fh:
        for line in fh:
            if line[0] == "#":
                continue
            f = line.split("\t", 2)
            chrom = f[0][3:] if f[0].startswith("chr") else f[0]
            key = (chrom, f[1])
            (dups if key in seen else seen).add(key)
    return dups


def emit_fixed(pgs_ids, files, vcf: Path, out_path: Path):
    """A copy of the target VCF in which every contested position is collapsed to ONE row.

    Why always one, and not only when the alleles agree: the match_rate of just-prs
    coincided with our "naive" per-row count — their matcher credits EVERY row of a
    position. So any contested position that a model touches is counted twice regardless
    of the alleles, and the only reliable input is one row per position. Which one to keep
    is decided by a typed rank over the models' alleles (SNP models — the SNP row, indel
    models — the indel row); if models demand different rows, the higher rank wins, and
    ties are counted and printed.

    Without a list of models, ALL models of the cache are taken: whichever model just-prs
    picks when recomputing, the input is already clean for any of them.
    """
    dups = _dup_positions(vcf)
    print(f"contested positions in the target: {len(dups)}")
    if not pgs_ids:
        pgs_ids = sorted(files)
    want = {}
    t0 = time.time()
    for i, pid in enumerate(pgs_ids, 1):
        for key, pairs in _model_alleles(files[pid], keys=dups).items():
            want.setdefault(key, set()).update(pairs)
        if i % 40 == 0:
            print(f"   … models scanned {i}/{len(pgs_ids)} ({time.time()-t0:.0f} s)", flush=True)
    print(f"models taken into account: {len(pgs_ids)}; contested positions touched by models: {len(want)}")

    resolved = dropped = conflicts = unmatched = 0
    group, gkey = [], None
    out = open(out_path, "w", encoding="utf-8")

    def flush():
        nonlocal resolved, dropped, conflicts, unmatched
        if not group:
            return
        if len(group) == 1:
            out.write("\t".join(group[0]) + "\n")
            return
        chrom = group[0][0][3:] if group[0][0].startswith("chr") else group[0][0]
        key = (chrom, group[0][1])
        pairs = want.get(key)
        if pairs:
            ranked = sorted(((_row_rank_for(pairs, f), -i, f) for i, f in enumerate(group)),
                            reverse=True)
            top = ranked[0][0]
            if top == 0:
                unmatched += 1
            elif sum(1 for r in ranked if r[0] == top) > 1:
                conflicts += 1
            keep = ranked[0][2]
        else:
            keep = group[0]        # position outside the models: also one row, the first
        out.write("\t".join(keep) + "\n")
        resolved += 1
        dropped += len(group) - 1

    with _open(vcf) as fh:
        for line in fh:
            if line[0] == "#":
                out.write(line)
                continue
            f = line.rstrip("\n").split("\t")
            k = (f[0], f[1])
            if k != gkey:
                flush()
                group, gkey = [f], k
            else:
                group.append(f)
    flush()
    out.close()
    print(f"positions collapsed: {resolved}; rows dropped: {dropped}; "
          f"rank ties: {conflicts}; no allele match: {unmatched}")
    print(f"✓ {out_path}")
    print("next: bgzip -f, tabix -p vcf, then the regular computation over that file")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("pgs", nargs="*", help="PGS identifiers")
    ap.add_argument("--list", action="store_true", help="show the contents of the model cache")
    ap.add_argument("--flagged", action="store_true", help="only traits with match_rate > 1 (the symptom is already visible)")
    ap.add_argument("--all", action="store_true",
                    help="ALL models from prs_results.json: match_rate > 1 is only the visible "
                         "part — with missing positions the overcount is masked")
    ap.add_argument("--emit-fixed", default=None, metavar="OUT.vcf",
                    help="do not compute, but write a copy of the target VCF with the contested "
                         "positions resolved for the listed models (allele-dependent)")
    ap.add_argument("--compare", action="store_true",
                    help="compute the score two ways: allele-dependent and by the former rule "
                         "«keep the SNP row» — and show the cost of the error")
    ap.add_argument("--vcf", default=None, help="target VCF (genome/scoring_sites_ext.vcf.gz by default)")
    a = ap.parse_args()

    if not CACHE.exists():
        sys.exit(f"no model cache: {CACHE}\nFill it by running: "
                 "PYTHONPATH=src python3 -m scholion.prs report --vcf genome/<...>.full.vcf.gz >/dev/null")
    files = {p.name.split("_")[0]: p for p in sorted(CACHE.glob("*.txt.gz"))}
    if a.list:
        print(f"cache: {CACHE}\nmodels: {len(files)}")
        for k, p in list(files.items())[:200]:
            print(f"   {k:12} {p.stat().st_size // 1024:>7} KB  {p.name}")
        return 0

    ids = list(a.pgs)
    stored = {}
    if RESULTS.exists():
        for t in json.loads(RESULTS.read_text(encoding="utf-8")).get("traits", []):
            if t.get("pgs_id"):
                stored[t["pgs_id"]] = t
    if a.flagged:
        ids = [pid for pid, t in stored.items()
               if isinstance(t.get("match_rate"), (int, float)) and t["match_rate"] > 1]
    if a.all:
        ids = list(stored)
    if not ids and not a.emit_fixed:
        sys.exit("give PGS identifiers, or --flagged/--all, or --list; "
                 "--emit-fixed without a list takes ALL models of the cache")

    totals = {"dup": 0, "indel_dup": 0, "masked": 0}
    vcf = Path(a.vcf) if a.vcf else (ROOT / "genome" / "scoring_sites_ext.vcf.gz")
    if not vcf.exists():
        sys.exit(f"no target VCF: {vcf}")
    if a.emit_fixed:
        missing = [pid for pid in ids if pid not in files]
        if missing:
            sys.exit(f"models missing from the cache: {missing}")
        emit_fixed(ids, files, vcf, Path(a.emit_fixed))
        return 0
    print(f"target: {vcf.name}")
    geno, dup, dup_pos = load_target(vcf)
    print(f"positions in the target: {len(geno)} (duplicate rows collapsed: {dup})\n")
    print(f"{'PGS':12} {'vars':>7} {'covered':>8} {'ours':>6} {'theirs':>6} {'naive':>8} "
          f"{'dups':>6} {'indels':>7} {'ind/dup':>8} {'miss':>7}  trait")
    ids = sorted(ids, key=lambda i: files[i].stat().st_size if i in files else 0)
    t0 = time.time()
    for k, pid in enumerate(ids, 1):
        p = files.get(pid)
        if not p:
            print(f"{pid:12} — model not in the cache", flush=True)
            continue
        mb = p.stat().st_size / 1048576
        if mb > 5:
            print(f"   … {pid} — {mb:.0f} MB, this will take a while "
                  f"({k}/{len(ids)}, {time.time()-t0:.0f} s elapsed)", flush=True)
        r = score_model(p, geno, dup_pos)
        s = stored.get(pid, {})
        if a.compare:
            totals["dup"] += r["hits_dup_target"]
            totals["indel_dup"] += r["indels_on_dup"]
            r2 = score_model(p, geno, dup_pos, legacy_pick=True)
            base = abs(r["score"]) or 1.0
            print(f"{pid:12} {r['variants']:>7} score allele-dependent {r['score']:>12.4f} | "
                  f"by the old rule {r2['score']:>12.4f} | discrepancy {100*(r2['score']-r['score'])/base:>7.2f}% | "
                  f"misses {r['allele_mismatch']} against {r2['allele_mismatch']}  {s.get('label','')}", flush=True)
            continue
        theirs = s.get("match_rate")
        mark = " ←" if r["hits_dup_target"] and not (isinstance(theirs, (int, float)) and theirs > 1) else ""
        print(f"{pid:12} {r['variants']:>7} {r['matched']:>8} {r['match_rate']:>6.3f} "
              f"{(theirs if isinstance(theirs,(int,float)) else 0):>6.3f} {r['naive_rate']:>8.3f} "
              f"{r['hits_dup_target']:>6} {r['model_indels']:>7} {r['indels_on_dup']:>8} "
              f"{r['allele_mismatch']:>7}  {s.get('label','')}{mark}", flush=True)
        totals["dup"] += r["hits_dup_target"]
        totals["indel_dup"] += r["indels_on_dup"]
        totals["masked"] += 1 if mark else 0
    print(f"\ntime: {time.time()-t0:.0f} s")
    print(f"intersections with contested positions in total: {totals['dup']}; "
          f"of them indel variants of the model: {totals['indel_dup']} "
          f"(those are exactly the ones the «keep the SNP row» deduplication breaks)")
    if totals["masked"]:
        print(f"models where the overcount exists but is NOT visible in their match_rate: {totals['masked']} "
              f"— the symptom is masked by the missing positions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
