"""Bridge to just-prs-mcp (polygenic risks, PGS Catalog) — WITHOUT dependencies.

Privacy architecture: the heavy PRS computation is done by a separate process
`uvx just-prs-mcp stdio` (Python 3.13, its own isolated env). Our module is only
a thin MCP client over stdio built on the standard library, and runs under the
application's Python 3.11. The genome does NOT leave the machine: only the local
path to the VCF is passed to just-prs; only public PGS Catalog scoring files go out.

Required on the machine: `uv`/`uvx` (https://docs.astral.sh/uv). The package is
installed and cached automatically on the first call.

CLI:
    python3 -m scholion.prs selftest              # transport check (offline)
    python3 -m scholion.prs report --vcf VCF.gz   # PRS over the trait catalogue
"""
from __future__ import annotations
import json
import os
import subprocess
from pathlib import Path

from .i18n import t as _t

PKG = os.environ.get("PRS_MCP_PKG", "just-prs-mcp@0.1.3")
_TRAITS = Path(__file__).resolve().parent / "knowledge" / "prs_traits.json"


class PrsUnavailable(RuntimeError):
    """uvx/the server is unavailable — we show a tidy placeholder in the UI."""


class _MCP:
    """A minimal synchronous MCP client over stdio (line-delimited JSON-RPC)."""

    def __init__(self, mode: str = "essentials", timeout: float = 600.0):
        self.timeout = timeout
        env = dict(os.environ)
        env.setdefault("PRS_MCP_MODE", mode)
        try:
            # stderr is inherited → the server's logs/progress are visible live (it does not «hang silently»)
            self.p = subprocess.Popen(
                ["uvx", PKG, "stdio"],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=None,
                env=env, text=True, bufsize=1,
            )
        except FileNotFoundError as e:
            raise PrsUnavailable(_t("prs.no_uvx")) from e
        self._id = 0
        self._init()

    def _send(self, obj):
        self.p.stdin.write(json.dumps(obj) + "\n")
        self.p.stdin.flush()

    def _read_id(self, want):
        for _ in range(10000):
            line = self.p.stdout.readline()
            if not line:
                raise PrsUnavailable(_t("prs.server_silent"))
            try:
                msg = json.loads(line)
            except ValueError:
                continue
            if msg.get("id") == want:
                if "error" in msg:
                    raise RuntimeError(msg["error"].get("message", "MCP error"))
                return msg.get("result", {})

    def _init(self):
        self._id += 1
        self._send({"jsonrpc": "2.0", "id": self._id, "method": "initialize",
                    "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                               "clientInfo": {"name": "scholion", "version": "1"}}})
        self._read_id(self._id)
        self._send({"jsonrpc": "2.0", "method": "notifications/initialized"})

    def call(self, name, args):
        self._id += 1
        self._send({"jsonrpc": "2.0", "id": self._id, "method": "tools/call",
                    "params": {"name": name, "arguments": args}})
        res = self._read_id(self._id)
        # FastMCP marks a tool error with isError=true (argument validation, an
        # unknown tool and so on) — we raise it as an exception, not an «empty» reply.
        if isinstance(res, dict) and res.get("isError"):
            txt = ""
            for item in (res.get("content") or []):
                if item.get("type") == "text":
                    txt += item.get("text", "")
            raise RuntimeError(txt or "tool error")
        # either a structured result or textual JSON in content[]
        if isinstance(res, dict) and res.get("structuredContent") is not None:
            sc = res["structuredContent"]
            return sc.get("result", sc) if isinstance(sc, dict) else sc
        for item in (res.get("content") or []):
            if item.get("type") == "text":
                try:
                    return json.loads(item["text"])
                except ValueError:
                    return item["text"]
        return res

    def close(self):
        try:
            self.p.terminate()
        except Exception:
            pass


def selftest() -> dict:
    """Transport check without the network: assess_quality is pure logic."""
    m = _MCP()
    try:
        return {"ok": True, "assess": m.call("assess_quality",
                {"match_rate": 0.98, "auroc": 0.65, "percentile": 88})}
    finally:
        m.close()


def _load_traits():
    """The curated panel, with the printed fields already in the current language.

    Through `core`, and not by reading the file, because `label` and `category` are
    per-language maps: read raw, a map would travel into prs_results.json and print
    there as `{'en': …}`.
    """
    if _TRAITS.exists():
        from .core import _read_knowledge
        return _read_knowledge("prs_traits.json").get("traits", [])
    return []


def _extract_path(res):
    """Pull the path to the normalised Parquet out of the normalize_vcf reply."""
    if isinstance(res, str):
        return res if res.endswith(".parquet") else None
    if isinstance(res, dict):
        for k in ("genotypes_path", "output_path", "parquet_path", "normalized_path", "path"):
            v = res.get(k)
            if isinstance(v, str) and v.endswith(".parquet"):
                return v
        for k in ("genotypes_path", "output_path", "parquet_path", "normalized_path", "path"):
            v = res.get(k)
            if isinstance(v, str) and v:
                return v
    return None


def _num(x, default=0.0):
    return x if isinstance(x, (int, float)) else default


def _rows_of(rep):
    if isinstance(rep, dict):
        return rep.get("rows") or []
    return []


_QRANK = {"High": 3, "Moderate": 2, "Low": 1, "Very Low": 0}


def _pick_covered(rows):
    """Choose from the computed models the best COVERED and HIGH-QUALITY one (rather than
    the server's top, which ranks a «reliable percentile» above coverage and sometimes
    returns a genome-wide model with ~20% coverage; and not the «most covered» one
    blindly — among equally covered ones there can be an outlier model with percentile
    0/100). Priority: match_rate≥0.9 → reliable percentile → quality (High>…>Very Low) →
    higher weight_mass_coverage → higher match_rate."""
    if not rows:
        return None
    good = [r for r in rows if _num(r.get("match_rate")) >= 0.9]
    pool = good or rows
    return max(pool, key=lambda r: (
        r.get("percentile_reliable") is True,
        _QRANK.get(r.get("quality_label"), -1),
        _num(r.get("weight_mass_coverage")),
        _num(r.get("match_rate")),
    ))


def _search_scores_fallback(m, term, geno, vcf_path, max_variants=50000, log=lambda s: None):
    """A fallback path for traits where the trait did not resolve or all models are
    genome-wide: we search for models by text, take the best COVERABLE one (≤max_variants)
    and compute it directly via compute_prs."""
    try:
        sc = m.call("search_scores", {"query": term, "limit": 25})
    except Exception as e:  # noqa
        return None, f"search_scores: {e}"
    items = sc.get("scores") if isinstance(sc, dict) else sc
    if not isinstance(items, list):
        return None, _t("prs.search_empty")
    cand = []
    for s in items:
        if not isinstance(s, dict):
            continue
        vn = s.get("variants_number")
        pid = s.get("pgs_id") or s.get("id")
        if pid and isinstance(vn, (int, float)) and 10 <= vn <= max_variants:
            cand.append((vn, pid, s))
    if not cand:
        return None, _t("prs.no_coverable_models")
    # the largest model under the threshold = usually the most elaborated and still coverable
    cand.sort(reverse=True)
    vn, pid, meta = cand[0]
    args = {"pgs_id": pid, "vcf_path": vcf_path, "attach_performance": True}
    if geno:
        args["genotypes_path"] = geno
    try:
        pr = m.call("compute_prs", args)
    except Exception as e:  # noqa
        return None, f"compute_prs({pid}): {e}"
    log(_t("prs.fallback_chosen", pgs_id=pid, variants=int(vn),
           rate=f"{_num(pr.get('match_rate') if isinstance(pr, dict) else None):.2f}"))
    return {"via": "search_scores", "pgs_id": pid, "variants_number": vn,
            "score_meta": meta, "result": pr}, None


def report(vcf_path: str, traits=None, superpopulation: str = "EUR",
           only=None, normalize: bool = True, models_per_trait: int = 3,
           profile: str = "curated", include_children: bool = False,
           pick: str = "server", min_match_rate=None, fallback: bool = False) -> dict:
    """Normalise the VCF once → compute_prs_by_trait(interpret) for each trait.

    only — a list of substrings to filter traits (a quick test on a single one).
    models_per_trait — how many PGS models to compute per trait (limit).
    profile — 'curated' (default) or 'all' (more candidate models).
    include_children — include models of child traits (a wider pool).
    pick — 'server' (top by the server's ranking) or 'covered' (the best covered here).
    min_match_rate — filter models by coverage on the server side.
    fallback — when a model is missing or poorly covered, look for one via search_scores.
    """
    traits = traits or _load_traits()
    if only:
        only = [o.lower() for o in only]
        traits = [t for t in traits
                  if any(o in (str(t.get("label", "")) + str(t.get("term", ""))).lower() for o in only)]
    if not traits:
        return {"ok": False, "error": _t("prs.no_traits")}
    if not Path(vcf_path).exists():
        return {"ok": False, "error": _t("prs.vcf_not_found", path=vcf_path)}
    def _log(msg):
        import sys as _s
        print(msg, file=_s.stderr, flush=True)

    m = _MCP()
    out = []
    geno = None
    try:
        # normalise the VCF ONCE and reuse it for all traits
        if normalize:
            _log(_t("prs.normalising"))
            try:
                nz = m.call("normalize_vcf", {"vcf_path": vcf_path})
                geno = _extract_path(nz)
                _log(_t("prs.normalised", path=geno))
            except Exception as e:  # noqa
                geno = None
                _log(_t("prs.normalise_failed", error=e))
        for i, t in enumerate(traits, 1):
            _log(f"→ [{i}/{len(traits)}] PGS: {t.get('label')}…")
            row = {"label": t.get("label"), "category": t.get("category"), "term": t.get("term")}
            try:
                efo = t.get("efo_id")
                if not efo:
                    found = m.call("search_traits", {"term": t["term"], "limit": 1, "include_pgs_ids": False})
                    hits = found.get("traits") if isinstance(found, dict) else found
                    if hits:
                        efo = (hits[0].get("trait_id") or hits[0].get("efo_id")
                               or hits[0].get("id"))
                if efo:
                    # base parameters — guaranteed to be supported by 0.1.3
                    base = {"trait_id": efo, "vcf_path": vcf_path, "interpret": True,
                            "superpopulation": superpopulation,
                            "limit": models_per_trait,
                            "top_n": (50 if pick == "covered" else 1)}
                    if geno:
                        base["genotypes_path"] = geno
                    # optional ones — only if set (present in newer server versions)
                    extra = {}
                    if profile and profile != "curated":
                        extra["profile"] = profile
                    if include_children:
                        extra["include_children"] = True
                    if min_match_rate is not None:
                        extra["min_match_rate"] = min_match_rate
                    try:
                        rep = m.call("compute_prs_by_trait", {**base, **extra})
                    except RuntimeError as e:
                        if extra and "keyword" in str(e).lower():
                            _log(_t("prs.args_rejected", args=list(extra)))
                            rep = m.call("compute_prs_by_trait", base)
                        else:
                            raise
                    rows = _rows_of(rep)
                    chosen = _pick_covered(rows) if pick == "covered" else (rows[0] if rows else None)
                    row["efo_id"] = efo
                    row["result"] = rep
                    row["chosen"] = chosen
                    row["status"] = "ok"
                else:
                    row["status"] = "trait_not_found"
                # the fallback path: no trait, or the chosen model is poorly covered
                need_fb = fallback and (not efo or _num((row.get("chosen") or {}).get("match_rate")) < 0.9)
                if need_fb:
                    fb, err = _search_scores_fallback(m, t["term"], geno, vcf_path, log=_log)
                    if fb:
                        prev = _num((row.get("chosen") or {}).get("match_rate"))
                        new = _num((fb.get("result") or {}).get("match_rate"))
                        # take the fallback only if it is better covered
                        if new > prev:
                            row["fallback"] = fb
                            row["status"] = "ok_fallback"
                    else:
                        row.setdefault("fallback_error", err)
            except Exception as e:  # noqa
                row["status"] = "error"; row["error"] = str(e)
            out.append(row)
        return {"ok": True, "vcf": vcf_path, "genotypes_path": geno,
                "superpopulation": superpopulation, "pick": pick,
                "profile": profile, "traits": out}
    finally:
        m.close()


def _main(argv=None):
    import argparse, sys
    ap = argparse.ArgumentParser(prog="scholion.prs")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("selftest")
    r = sub.add_parser("report")
    r.add_argument("--vcf", required=True)
    r.add_argument("--pop", default="EUR")
    r.add_argument("--only", nargs="*", default=None,
                   help="substrings to filter the traits by (a quick test, e.g. --only diabetes)")
    r.add_argument("--models", type=int, default=3,
                   help="how many PGS models per trait (3 by default; more = slower)")
    r.add_argument("--profile", default="curated", choices=["curated", "all"],
                   help="'all' — a wider pool of candidate models (for fixing disputed traits)")
    r.add_argument("--children", action="store_true",
                   help="include the models of child traits (a wider candidate pool)")
    r.add_argument("--pick", default="server", choices=["server", "covered"],
                   help="'covered' — pick the best-covered model instead of the server's top one")
    r.add_argument("--min-match-rate", type=float, default=None, dest="min_match_rate",
                   help="filter models by coverage on the server side (e.g. 0.9)")
    r.add_argument("--fallback", action="store_true",
                   help="on poor coverage or a missing model, search through search_scores")
    a = ap.parse_args(argv)
    try:
        res = (selftest() if a.cmd == "selftest"
               else report(a.vcf, superpopulation=a.pop, only=a.only, models_per_trait=a.models,
                           profile=a.profile, include_children=a.children, pick=a.pick,
                           min_match_rate=a.min_match_rate, fallback=a.fallback))
    except PrsUnavailable as e:
        res = {"ok": False, "unavailable": True, "error": str(e)}
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0 if res.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(_main())
