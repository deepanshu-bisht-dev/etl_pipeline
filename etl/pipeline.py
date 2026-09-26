"""
Pipeline orchestrator.

run_pipeline() executes every configured source through
extract -> transform -> validate -> load, timing each stage and writing
the results to the control database so the dashboard can show exactly
what happened, source by source, stage by stage.
"""
import time
import threading

import config
import database
from etl.extract import extract
from etl.transform import transform
from etl.validate import validate
from etl.load import load

_run_lock = threading.Lock()
_is_running = False


def is_running():
    return _is_running


def _stage_timer():
    start = time.perf_counter()
    return lambda: int((time.perf_counter() - start) * 1000)


def run_pipeline(trigger="manual"):
    """Run the full pipeline once, synchronously. Returns the run summary dict."""
    global _is_running

    if not _run_lock.acquire(blocking=False):
        return {"skipped": True, "reason": "a pipeline run is already in progress"}

    _is_running = True
    run_id = database.start_run(trigger=trigger)
    overall_timer = _stage_timer()
    database.log(run_id, "info", f"Pipeline run #{run_id} started ({trigger})")

    total_extracted = 0
    total_loaded = 0
    total_rejected = 0
    failed = False
    error_message = None

    try:
        warehouse = database.get_warehouse_conn()

        # customers and products are loaded first so transactions can be
        # validated against known customer ids (a simple referential check)
        known_customer_ids = None
        ordered_sources = sorted(
            config.SOURCES, key=lambda s: 0 if s["name"] != "transactions" else 1
        )

        for source in ordered_sources:
            name = source["name"]
            try:
                # --- extract ---
                t = _stage_timer()
                df = extract(source)
                rows_in = len(df)
                total_extracted += rows_in
                database.record_stage(run_id, name, "extract", "ok",
                                       rows_in=rows_in, rows_out=rows_in,
                                       duration_ms=t(), detail=f"read {rows_in} row(s) from {source['file'].split('/')[-1]}")
                database.log(run_id, "info", f"[{name}] extracted {rows_in} row(s)")

                # --- transform ---
                t = _stage_timer()
                clean_df, notes = transform(name, df)
                database.record_stage(run_id, name, "transform", "ok",
                                       rows_in=rows_in, rows_out=len(clean_df),
                                       duration_ms=t(), detail="; ".join(notes) if notes else "no changes needed")
                for n in notes:
                    database.log(run_id, "info", f"[{name}] {n}")

                # --- validate ---
                t = _stage_timer()
                context = {"known_customer_ids": known_customer_ids} if name == "transactions" else {}
                valid_df, rejected_df = validate(name, clean_df, context=context)
                n_rejected = len(rejected_df)
                total_rejected += n_rejected
                status = "ok" if n_rejected == 0 else "warning"
                reasons = (
                    rejected_df["_rejection_reason"].value_counts().to_dict()
                    if n_rejected and "_rejection_reason" in rejected_df.columns
                    else {}
                )
                detail = ", ".join(f"{v}x {k}" for k, v in reasons.items()) or "all rows valid"
                database.record_stage(run_id, name, "validate", status,
                                       rows_in=len(clean_df), rows_out=len(valid_df),
                                       duration_ms=t(), detail=detail)
                level = "warn" if n_rejected else "success"
                database.log(run_id, level, f"[{name}] validation: {len(valid_df)} passed, {n_rejected} rejected ({detail})")

                if name == "customers":
                    known_customer_ids = set(valid_df["customer_id"].tolist())

                # --- load ---
                t = _stage_timer()
                n_loaded, n_rej_written = load(warehouse, source["table"], valid_df, rejected_df)
                total_loaded += n_loaded
                database.record_stage(run_id, name, "load", "ok",
                                       rows_in=len(valid_df), rows_out=n_loaded,
                                       duration_ms=t(), detail=f"wrote {n_loaded} row(s) to {source['table']}")
                database.log(run_id, "success", f"[{name}] loaded {n_loaded} row(s) into {source['table']}")

            except Exception as exc:  # noqa: BLE001 - surface any source failure in the log
                database.record_stage(run_id, name, "error", "error", duration_ms=0, detail=str(exc))
                database.log(run_id, "error", f"[{name}] failed: {exc}")
                failed = True
                error_message = str(exc)

        warehouse.close()

    except Exception as exc:  # noqa: BLE001 - pipeline-level failure
        failed = True
        error_message = str(exc)
        database.log(run_id, "error", f"Pipeline failed: {exc}")

    duration_ms = overall_timer()
    status = "failed" if failed else "success"
    database.finish_run(
        run_id, status,
        rows_extracted=total_extracted, rows_loaded=total_loaded,
        rows_rejected=total_rejected, duration_ms=duration_ms, error=error_message,
    )
    database.log(
        run_id,
        "error" if failed else "success",
        f"Pipeline run #{run_id} finished: {status} in {duration_ms} ms "
        f"({total_loaded} loaded, {total_rejected} rejected)",
    )

    _is_running = False
    _run_lock.release()

    return database.get_run(run_id)


def run_pipeline_async(trigger="manual"):
    """Fire off a run on a background thread so the HTTP request returns immediately."""
    if _is_running:
        return {"skipped": True, "reason": "a pipeline run is already in progress"}
    thread = threading.Thread(target=run_pipeline, kwargs={"trigger": trigger}, daemon=True)
    thread.start()
    return {"started": True}
