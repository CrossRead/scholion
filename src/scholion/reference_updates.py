"""Reviewed reference refreshes on the existing sources door.

Only public reference identifiers leave the machine. Downloads are staged;
acceptance replaces one self-contained knowledge snapshot atomically. A source
comparison never pretends to be a new review of a primary scientific claim.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
import json
import os
from pathlib import Path
import re
import threading
from typing import Callable
from urllib.parse import parse_qs, urlencode, urlsplit
import uuid

from . import core, net, variant_annotations as variant_data

SOURCE_ID = "gene_variant_knowledge"
_FIELDS = ("accession", "id", "gene_names", "protein_name", "organism_id", "reviewed", "cc_function",
           "cc_disease", "cc_pathway", "cc_tissue_specificity", "cc_subcellular_location",
           "ft_variant", "ft_mutagen", "sequence_version", "version", "date_modified",
           "date_sequence_modified", "xref_hgnc", "xref_geneid")
_ACTIVE: dict[str, threading.Thread] = {}
_ACTIVE_LOCK = threading.RLock()
_SCHEDULER_STOP = threading.Event()
_SCHEDULER_STARTED = False


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _root() -> Path:
    return core.knowledge_dir_local().resolve() / ".reference-updates"


def _read(name: str) -> dict:
    path = _root() / name
    if not path.exists():
        return {}
    try:
        result = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RuntimeError("Reference update state is unreadable; existing data was preserved") from exc
    if not isinstance(result, dict):
        raise RuntimeError("Invalid reference update state; existing data was preserved")
    return result


def _write(name: str, value: dict) -> None:
    core.write_json(_root() / name, value, indent=0)


def _file_digest(path: Path) -> str:
    import hashlib
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def _job() -> dict:
    job = _read("job.json")
    if job.get("status") == "review_ready":
        metadata = variant_data.catalogue_metadata()
        if metadata.get("accepted_preview") == job.get("token"):
            job = {**job, "status": "accepted", "accepted_on": metadata.get("accepted_on")}
    if job.get("status") == "running":
        from .recompute import _alive
        with _ACTIVE_LOCK:
            current = str(_root()) in _ACTIVE
        if (job.get("pid") == os.getpid() and not current) or not _alive(job.get("pid")):
            job = {**job, "status": "interrupted"}
    return job


def status() -> dict:
    """Read-only. Neither a card nor a status request starts an update."""
    config = {"enabled": False, "interval_months": 3, **_read("schedule.json")}
    metadata = variant_data.catalogue_metadata()
    history = []
    for path in sorted((_root() / "history").glob("*.json"), key=lambda row: row.stat().st_mtime_ns, reverse=True):
        previous = core.knowledge_metadata(path)
        history.append({"token": path.stem, "source_release": previous.get("release"),
                        "source_compared_on": previous.get("updated"),
                        "scope": "snapshot_archived_before_replacement"})
    return {"source": SOURCE_ID, "job": _job(), "schedule": config, "history": history,
            "source_release": metadata.get("release"),
            "source_compared_on": metadata.get("updated"),
            "primary_reviews_automatically_renewed": False,
            "network_on_view": False, "runs_while_application_open": True}


def configure(enabled: bool, interval_months: int = 3) -> dict:
    if (not isinstance(enabled, bool) or type(interval_months) is not int
            or not 1 <= interval_months <= 12):
        raise ValueError("An enabled flag and an interval of 1 to 12 calendar months are required")
    with core.profile_write_lock():
        _write("schedule.json", {"enabled": enabled, "interval_months": int(interval_months),
                                 "configured_on": _now()})
    return status()


def _token(value: str) -> str:
    if not re.fullmatch(r"[a-f0-9]{32}", str(value)):
        raise ValueError("Invalid reference preview identifier")
    return value


def _claim() -> dict:
    with core.profile_write_lock():
        if _job().get("status") == "running":
            raise RuntimeError("A reference check is already running")
        if _job().get("status") == "review_ready":
            raise RuntimeError("Accept or discard the existing reference preview before starting another")
        job = {"source": SOURCE_ID, "token": uuid.uuid4().hex, "status": "running",
               "pid": os.getpid(), "started_on": _now(), "stage": "download",
               "pages": 0, "entries": 0, "cancel_requested": False}
        with _ACTIVE_LOCK:
            _ACTIVE[str(_root())] = threading.current_thread()
        _write("job.json", job)
        return job


class _Cancelled(RuntimeError):
    pass


def _progress(token: str, **values) -> None:
    with core.profile_write_lock():
        job = _read("job.json")
        if job.get("token") != token:
            raise RuntimeError("The reference job changed")
        if job.get("cancel_requested"):
            raise _Cancelled()
        _write("job.json", {**job, **values})


def cancel(discard: bool = False) -> dict:
    with core.profile_write_lock():
        job = _job()
        if job.get("status") == "running":
            _write("job.json", {**job, "cancel_requested": True})
            return {"ok": True, "status": "cancellation_requested"}
        if discard and job.get("status") == "review_ready":
            _write("job.json", {**job, "status": "discarded", "finished_on": _now()})
            return {"ok": True, "status": "discarded"}
    return {"ok": False, "status": "not_running"}


def _next_url(headers: dict) -> str | None:
    match = re.search(r'<([^>]+)>;\s*rel="?next"?', headers.get("link", ""))
    if not match:
        return None
    url = match.group(1)
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.netloc != "rest.uniprot.org" or parsed.path != "/uniprotkb/search":
        raise ValueError("The source supplied an unexpected pagination address")
    return url


def _download(base: dict, token: str, fetch: Callable) -> tuple[dict, dict]:
    query = {"query": "reviewed:true AND organism_id:9606", "format": "json",
             "fields": ",".join(_FIELDS), "size": 500}
    url: str | None = "https://rest.uniprot.org/uniprotkb/search?" + urlencode(query)
    target = set(base.get("genes") or {})
    if not target:
        raise ValueError("The retained gene catalogue is missing")
    proteins, records, seen_entries, seen_records = {}, [], set(), set()
    release, expected, entries, pages = None, None, 0, 0
    seen_urls = set()
    checked = date.today().isoformat()
    while url:
        if pages >= 100 or url in seen_urls:
            raise ValueError("The bounded source download did not finish")
        seen_urls.add(url)
        _progress(token, stage="download", pages=pages, entries=entries)
        response = fetch(url)
        if not isinstance(response, dict) or not isinstance(response.get("data"), dict):
            raise RuntimeError("UniProt was not reached or did not return a complete versioned response")
        headers = {str(key).lower(): value for key, value in (response.get("headers") or {}).items()}
        current_release = headers.get("x-uniprot-release")
        if not current_release or (release and release != current_release):
            raise ValueError("The source release is missing or changed during download")
        release = current_release
        if expected is None:
            expected = int(headers.get("x-total-results") or 0)
        page = response["data"].get("results")
        if not isinstance(page, list):
            raise ValueError("The source response has no result records")
        for entry in page:
            accession = entry.get("primaryAccession")
            if not accession or accession in seen_entries:
                raise ValueError("Duplicate or missing protein identity in the source pages")
            seen_entries.add(accession)
            entries += 1
            ids = sorted({row["id"] for row in entry.get("uniProtKBCrossReferences") or []
                          if row.get("database") == "HGNC" and row.get("id")})
            if not target.intersection(ids):
                continue
            proteins[accession] = variant_data.uniprot_context(entry, release, checked)
            for feature in entry.get("features") or []:
                record = variant_data.uniprot_record(entry, feature, release, checked, target)
                if record:
                    if record["id"] in seen_records:
                        raise ValueError("Duplicate source feature identity")
                    seen_records.add(record["id"])
                    records.append(record)
        pages += 1
        url = _next_url(headers)
    if not expected or entries != expected:
        raise ValueError("The source download is incomplete")
    retained_entries = ((base.get("_meta") or {}).get("source_comparison") or {}).get("entries") or (base.get("_meta") or {}).get("source_entry_count")
    if retained_entries and entries < int(retained_entries) * 0.9:
        raise ValueError("The reviewed human source population unexpectedly shrank; no snapshot was accepted")
    if base.get("records") and not any(row["type"] == "Natural variant" for row in records):
        raise ValueError("The response does not cover natural variants; FUNCTION-only is not a variant refresh")
    old_release = str((base.get("_meta") or {}).get("release") or "")
    if old_release and str(release) < old_release:
        raise ValueError("The downloaded source release is older than the retained release")
    return {"proteins": proteins, "records": records}, {"release": release,
            "entries": entries, "pages": pages, "compared_on": checked,
            "fields": list(_FIELDS), "scope": ["gene_function", "gene_disease_context", "pathway",
                                               "tissue_specificity", "subcellular_location", "natural_variant", "mutagenesis"]}


def _compare(base: dict, downloaded: dict) -> tuple[list[dict], set[str], set[str]]:
    old = {row["id"]: row for row in variant_data.records(base)}
    new = {row["id"]: row for row in downloaded["records"]}
    changes: list[dict] = []
    affected_rsids: set[str] = set()
    affected_pmids: set[str] = set()
    for identifier in sorted(set(old) | set(new)):
        before, after = old.get(identifier), new.get(identifier)
        if before and after and before["source_digest"] == after["source_digest"]:
            continue
        kind = "added" if before is None else "removed" if after is None else "changed"
        changes.append({"id": identifier, "kind": kind, "before": before, "after": after})
        for row in (before, after):
            if row:
                affected_rsids.update(row.get("rsids") or [])
                affected_pmids.update(row.get("pmids") or [])
    for accession in sorted(set(base.get("proteins") or {}) | set(downloaded["proteins"])):
        protein = downloaded["proteins"].get(accession) or {}
        previous = (base.get("proteins") or {}).get(accession) or {}
        if (previous.get("functions") or protein.get("functions")) and previous.get("functions") != protein.get("functions"):
            changes.append({"id": accession, "kind": "gene_function_changed" if "functions" in previous else "gene_function_available",
                            "before": previous.get("functions"), "after": protein.get("functions"),
                            "gene_ids": protein.get("gene_ids")})
        if previous.get("contexts") != protein.get("contexts") and (previous.get("contexts") or protein.get("contexts")):
            changes.append({"id": accession, "kind": "gene_context_changed",
                            "before": previous.get("contexts"), "after": protein.get("contexts"),
                            "gene_ids": protein.get("gene_ids") or previous.get("gene_ids")})
    return changes, affected_rsids, affected_pmids


def _run(job: dict, fetch: Callable) -> dict:
    token = job["token"]
    try:
        path = core.knowledge_path(variant_data.ANNOTATIONS)
        base_hash = _file_digest(path)
        base = variant_data.catalogue()
        downloaded, metadata = _download(base, token, fetch)
        _progress(token, stage="compare", entries=metadata["entries"], pages=metadata["pages"])
        changes, affected_rsids, affected_pmids = _compare(base, downloaded)
        checked_sources = None
        if (base.get("_meta") or {}).get("check_linked_sources"):
            from . import reference_checks
            checked_sources = reference_checks.refresh(base, progress=lambda **values:
                _progress(token, stage="linked_sources", **values))
            changes.extend({"id": event["key"], "kind": event["kind"],
                            "before": event.get("before"), "after": event.get("after"),
                            "provider": event["provider"]} for event in checked_sources["events"])
        provider_pending = set((checked_sources or {}).get("models_requiring_review") or [])
        models = []
        pending_models = []
        for model in base.get("models") or []:
            source_pmids = {str(source.get("pmid")) for source in model.get("sources") or []
                            if isinstance(source, dict) and source.get("pmid")}
            affected = bool(model["model_id"] in provider_pending
                            or affected_rsids.intersection(model.get("variant_ids") or [])
                            or affected_pmids.intersection(source_pmids))
            review = ({"review_required": True,
                       "review_reason": "source_record_changed" if model["model_id"] in provider_pending else "supporting_source_changed",
                       "interpretation_blocked": model["model_id"] in provider_pending} if affected else {})
            if model.get("review_reason") == "source_missing":
                review["review_reason"] = "source_missing"
            models.append({**model, **review})
            if affected:
                pending_models.append(model["model_id"])
        contexts = [{**row, **({"review_required": True} if (
            affected_rsids.intersection([row.get("variant_identifier")])
            or set(row.get("model_ids") or []).intersection(pending_models)
            or row.get("context_id") in pending_models) else {})}
                    for row in base.get("supported_contexts") or []]
        meta = {**(base.get("_meta") or {}), "updated": metadata["compared_on"],
                "has_interpretation_blocks": any(row.get("interpretation_blocked") for row in models),
                "release": metadata["release"], "source_comparison": metadata,
                "imported": {"source": SOURCE_ID, "fetched": metadata["compared_on"],
                             "scope": metadata["scope"]},
                "primary_studies_independently_reviewed": False,
                "record_count": len(downloaded["records"])}
        candidate = {**base, "_meta": meta, "proteins": downloaded["proteins"],
                     "record_fields": list(variant_data.RECORD_FIELDS),
                     "records": [[row.get(key) for key in variant_data.RECORD_FIELDS]
                                 for row in downloaded["records"]],
                     "models": models, "supported_contexts": contexts}
        if checked_sources is not None:
            candidate["source_checks"] = checked_sources["records"]
            candidate["_meta"]["linked_source_check"] = {
                "attempted_on": metadata["compared_on"],
                "requests_completed": checked_sources["requests_completed"],
                "failures": checked_sources["failures"],
                "primary_semantic_review_renewed": False}
            from . import sources
            def cpic_fetch(url):
                _progress(token, stage="linked_sources", provider="CPIC guidance")
                parsed = urlsplit(url)
                parameters = parse_qs(parsed.query)
                gene = (parameters.get("genesymbol") or [""])[0].removeprefix("eq.")
                kind = parsed.path.rsplit("/", 1)[-1]
                if gene and kind in ("allele", "diplotype"):
                    cached = checked_sources["records"].get("cpic:" + gene + ":" + kind) or {}
                    if cached.get("status") == "unavailable":
                        raise RuntimeError("The required CPIC table was unavailable")
                    if cached.get("status") == "current" and isinstance(cached.get("data"), dict):
                        return [{"genesymbol": gene, **row} for row in cached["data"].values()]
                value = net.get_json(url)
                if value is None:
                    raise RuntimeError("The CPIC reference could not be read")
                return value
            try:
                prepared = sources._prepare_cpic(cpic_fetch)
                base_hashes = {name: _file_digest(core.knowledge_path(name))
                               for name in ("cpic_drug_gene.json", "cpic_pairs.json")}
                candidate["cpic_overlay"] = {**prepared, "base_hashes": base_hashes,
                                             "compared_on": metadata["compared_on"]}
                candidate["_meta"]["has_cpic_overlay"] = True
                changes.extend({"id": "CPIC:" + str(change.get("gene")), "kind": "cpic_guidance_changed",
                                "before": change.get("was"), "after": change.get("now"),
                                "field": change.get("field")} for change in prepared["changes"])
            except _Cancelled:
                raise
            except Exception as exc:
                checked_sources["failures"].append({"provider": "CPIC guidance", "reason": net.reference_error(exc)})
                overlay = candidate.get("cpic_overlay") or {}
                if any(_file_digest(core.knowledge_path(name)) != expected
                       for name, expected in (overlay.get("base_hashes") or {}).items()):
                    candidate.pop("cpic_overlay", None)
                    candidate["_meta"]["has_cpic_overlay"] = False
        candidate["_meta"].pop("accepted_preview", None)
        candidate["_meta"].pop("accepted_on", None)
        _progress(token, stage="stage")
        _write("pending-" + token + ".json", candidate)
        diff = {"token": token, "base_sha256": base_hash, "metadata": metadata,
                "changes": changes, "models_requiring_review": pending_models,
                "source_check_failures": (checked_sources or {}).get("failures") or [],
                "primary_reviews_renewed": False}
        _write("diff-" + token + ".json", diff)
        _progress(token, status="review_ready", stage="review", change_count=len(changes),
                  models_requiring_review=len(pending_models), finished_on=_now())
        return {"source": SOURCE_ID, "token": token, "status": "review_ready",
                "checked": len(downloaded["records"]), "changes": changes[:20],
                "change_count": len(changes), "models_requiring_review": pending_models,
                "accepted": False, "source_release": metadata["release"]}
    except _Cancelled:
        with core.profile_write_lock():
            _write("job.json", {**_read("job.json"), "status": "cancelled", "finished_on": _now()})
        return {"source": SOURCE_ID, "status": "cancelled", "accepted": False}
    except Exception as exc:
        try:
            with core.profile_write_lock():
                _write("job.json", {**_read("job.json"), "status": "failed", "finished_on": _now(),
                                     "error": net.reference_error(exc)})
        except Exception:
            pass  # quiet: a switched container must not receive the old job's write.
        raise
    finally:
        with _ACTIVE_LOCK:
            _ACTIVE.pop(str(_root()), None)


def preview(fetch: Callable | None = None) -> dict:
    return _run(_claim(), fetch or net.get_json_response)


def start(fetch: Callable | None = None) -> dict:
    from . import container
    context, job = container.capture(), _claim()
    def worker():
        with container.pinned(context):
            try:
                _run(job, fetch or net.get_json_response)
            except Exception:
                pass  # quiet: the job records the error; no reference bytes were replaced.
    thread = threading.Thread(target=worker, daemon=True)
    with _ACTIVE_LOCK:
        _ACTIVE[str(_root())] = thread
    thread.start()
    return {"source": SOURCE_ID, "status": "running", "token": job["token"]}


def diff(token: str, offset: int = 0, limit: int = 20) -> dict:
    value = _read("diff-" + _token(token) + ".json")
    if not value or value.get("token") != token:
        raise ValueError("This reference preview does not exist in the active container")
    offset, limit = max(0, int(offset)), max(1, min(100, int(limit)))
    changes = value.get("changes") or []
    return {**value, "changes": changes[offset:offset + limit], "total": len(changes),
            "offset": offset, "next_offset": offset + limit if offset + limit < len(changes) else None}


def accept(token: str) -> dict:
    token = _token(token)
    with core.profile_write_lock():
        job = _job()
        if job.get("status") != "review_ready" or job.get("token") != token or job.get("cancel_requested"):
            raise ValueError("This source preview is not ready for acceptance")
        details = _read("diff-" + token + ".json")
        current = core.knowledge_path(variant_data.ANNOTATIONS)
        if _file_digest(current) != details.get("base_sha256"):
            raise RuntimeError("Reference knowledge changed after the preview; prepare a new comparison")
        candidate = _read("pending-" + token + ".json")
        if not candidate.get("_meta") or not candidate.get("genes"):
            raise ValueError("The staged reference snapshot is incomplete")
        if candidate.get("_meta", {}).get("has_cpic_overlay"):
            for name, expected in (candidate.get("cpic_overlay", {}).get("base_hashes") or {}).items():
                if _file_digest(core.knowledge_path(name)) != expected:
                    raise RuntimeError("CPIC knowledge changed after the preview; prepare a new comparison")
        candidate["_meta"]["accepted_preview"] = token
        candidate["_meta"]["accepted_on"] = _now()
        _write("history/" + token + ".json", variant_data.catalogue())
        core.write_knowledge_local(variant_data.ANNOTATIONS, candidate)
        _write("job.json", {**job, "status": "accepted", "accepted_on": _now(),
                             "previous_snapshot": token})
    return {"source": SOURCE_ID, "token": token, "status": "accepted", "accepted": True,
            "change_count": details.get("changes") and len(details["changes"]) or 0,
            "models_requiring_review": details.get("models_requiring_review") or []}


def check_due(today: date | None = None, *, background: bool = False) -> dict:
    from calendar import monthrange
    today = today or date.today()
    config = {"enabled": False, "interval_months": 3, **_read("schedule.json")}
    if not config["enabled"]:
        return {"source": SOURCE_ID, "status": "disabled"}
    if _job().get("status") in ("running", "review_ready"):
        return {"source": SOURCE_ID, "status": "pending"}
    job = _job()
    if job.get("status") in ("failed", "cancelled", "interrupted"):
        try:
            attempted = datetime.fromisoformat(job.get("started_on", "")).date()
            if (today - attempted).days < 1:
                return {"source": SOURCE_ID, "status": "retry_later", "last_attempt": attempted.isoformat()}
        except (TypeError, ValueError):
            pass
    stamp = (variant_data.catalogue_metadata()).get("updated")
    try:
        checked = date.fromisoformat(str(stamp or ""))
        months = checked.year * 12 + checked.month - 1 + int(config["interval_months"])
        year, month = divmod(months, 12)
        due = date(year, month + 1, min(checked.day, monthrange(year, month + 1)[1]))
        if checked <= today <= due:
            return {"source": SOURCE_ID, "status": "current", "next_due_after": due.isoformat()}
    except (ValueError, TypeError):
        pass
    return start() if background else preview()


def start_scheduler() -> None:
    """Check only explicit per-container opt-ins while the local app is running."""
    global _SCHEDULER_STARTED
    from . import container
    with _ACTIVE_LOCK:
        if _SCHEDULER_STARTED:
            return
        _SCHEDULER_STARTED = True
    def worker():
        while not _SCHEDULER_STOP.wait(60):
            try:
                with container.pinned():
                    check_due(background=True)
            except Exception:
                pass  # quiet: a failed check retains its state and the old knowledge.
    _SCHEDULER_STOP.clear()
    threading.Thread(target=worker, daemon=True).start()
