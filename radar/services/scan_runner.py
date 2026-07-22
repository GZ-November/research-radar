"""Background scan execution and the ScanRun status state machine.

States: ``running`` -> ``completed`` | ``failed`` | ``cancelled`` | ``interrupted``
with a cooperative detour ``running`` -> ``cancel_requested`` -> ``cancelled``.

The runner pre-creates the ScanRun row so the UI can poll progress from the
first second, executes ``WeeklyRadarService.run_auto`` on a daemon thread with
its own session, and guarantees the row always reaches a terminal state.
"""

import threading
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from radar.db import SessionLocal, session_scope
from radar.models import ScanRun
from radar.services.weekly_radar_service import WeeklyRadarService


ACTIVE_STATUSES = frozenset({"running", "cancel_requested"})
TERMINAL_STATUSES = frozenset({"completed", "failed", "cancelled", "interrupted"})
DEFAULT_STALE_MINUTES = 30


class ScanAlreadyRunningError(RuntimeError):
    """Raised when a case already has an active scan."""


# In-process guard complementing the DB-level active-scan check. The dict only
# tracks scans owned by live worker threads in this process; recovery uses it
# to avoid interrupting scans that are genuinely alive.
_lock = threading.Lock()
_active_by_case: dict[str, str] = {}  # case_id -> scan_id
_threads: dict[str, threading.Thread] = {}


def start(
    case_id: str,
    *,
    max_results: int = 32,
    analysis_limit: int = 3,
    session_factory: sessionmaker[Session] = SessionLocal,
    service_factory: Callable[[sessionmaker[Session]], Any] = WeeklyRadarService,
) -> str:
    """Pre-create a running ScanRun and execute it on a background thread.

    Raises ScanAlreadyRunningError when the case already has an active scan,
    either owned by this process or recorded in the database.
    """

    with _lock:
        if case_id in _active_by_case:
            raise ScanAlreadyRunningError(
                f"case already has a running scan: {case_id}"
            )
        with session_scope(session_factory) as session:
            active = session.scalar(
                select(ScanRun.id).where(
                    ScanRun.case_id == case_id,
                    ScanRun.status.in_(sorted(ACTIVE_STATUSES)),
                )
            )
            if active is not None:
                raise ScanAlreadyRunningError(
                    f"case already has an active scan in the database: {case_id}"
                )
            scan = ScanRun(
                id=str(uuid4()),
                case_id=case_id,
                mode="auto_public_paper_radar",
                status="running",
                started_at=datetime.now(timezone.utc),
                query_json={
                    "max_results": max_results,
                    "analysis_limit": analysis_limit,
                },
                stats_json={
                    "progress": {"value": 0.0, "message": "扫描已排队，正在启动…"}
                },
            )
            session.add(scan)
            session.flush()
            scan_id = scan.id
        _active_by_case[case_id] = scan_id

    thread = threading.Thread(
        target=_run_worker,
        args=(
            case_id,
            scan_id,
            max_results,
            analysis_limit,
            session_factory,
            service_factory,
        ),
        name=f"scan-runner-{scan_id[:8]}",
        daemon=True,
    )
    with _lock:
        _threads[scan_id] = thread
    thread.start()
    return scan_id


def request_cancel(
    scan_id: str, *, session_factory: sessionmaker[Session] = SessionLocal
) -> bool:
    """Flag an active scan for cooperative cancellation; return False if done."""

    with session_scope(session_factory) as session:
        scan = session.get(ScanRun, scan_id)
        if scan is None:
            raise LookupError(f"scan not found: {scan_id}")
        if scan.status not in ACTIVE_STATUSES:
            return False
        scan.status = "cancel_requested"
        scan.stats_json = {**(scan.stats_json or {}), "cancel_requested": True}
    return True


def get_active_scan(
    case_id: str, *, session_factory: sessionmaker[Session] = SessionLocal
) -> ScanRun | None:
    """Return the case's active ScanRun (detached), or None."""

    with session_scope(session_factory) as session:
        scan = session.scalar(
            select(ScanRun)
            .where(
                ScanRun.case_id == case_id,
                ScanRun.status.in_(sorted(ACTIVE_STATUSES)),
            )
            .order_by(ScanRun.created_at.desc())
        )
        if scan is not None:
            session.expunge(scan)
        return scan


def recover_interrupted_scans(
    *,
    session_factory: sessionmaker[Session] = SessionLocal,
    stale_minutes: int = DEFAULT_STALE_MINUTES,
) -> int:
    """Mark active scans without a heartbeat for ``stale_minutes`` as interrupted.

    Scans owned by live worker threads in this process are never touched.
    """

    cutoff = datetime.now(timezone.utc) - timedelta(minutes=stale_minutes)
    recovered = 0
    with session_scope(session_factory) as session:
        stale = session.scalars(
            select(ScanRun).where(
                ScanRun.status.in_(sorted(ACTIVE_STATUSES)),
                ScanRun.updated_at < cutoff,
            )
        ).all()
        for scan in stale:
            with _lock:
                if scan.id in _active_by_case.values():
                    continue
                scan.status = "interrupted"
                scan.error_message = scan.error_message or (
                    "Scan showed no progress for over "
                    f"{stale_minutes} minutes; marked interrupted."
                )
                scan.finished_at = datetime.now(timezone.utc)
                recovered += 1
    return recovered


def wait_for_scan(scan_id: str, timeout: float | None = None) -> bool:
    """Join the worker thread of a scan; return True when it has finished."""

    with _lock:
        thread = _threads.get(scan_id)
    if thread is None:
        return False
    thread.join(timeout)
    return not thread.is_alive()


def _run_worker(
    case_id: str,
    scan_id: str,
    max_results: int,
    analysis_limit: int,
    session_factory: sessionmaker[Session],
    service_factory: Callable[[sessionmaker[Session]], Any],
) -> None:
    """Thread entry point; never lets the ScanRun stay in an active state."""

    try:
        service = service_factory(session_factory)

        def progress_callback(value: float, message: str) -> None:
            _write_progress(session_factory, scan_id, value, message)

        def cancel_check() -> bool:
            return _cancel_requested(session_factory, scan_id)

        service.run_auto(
            case_id,
            max_results=max_results,
            analysis_limit=analysis_limit,
            progress_callback=progress_callback,
            scan_id=scan_id,
            cancel_check=cancel_check,
        )
        _finalize_progress(session_factory, scan_id)
    except Exception as exc:  # noqa: BLE001 - the scan row must not outlive us
        _mark_failed(session_factory, scan_id, exc)
    finally:
        with _lock:
            _active_by_case.pop(case_id, None)


def _write_progress(
    session_factory: sessionmaker[Session],
    scan_id: str,
    value: float,
    message: str,
) -> None:
    """Persist UI-polled progress into stats_json with a short-lived session."""

    with session_scope(session_factory) as session:
        scan = session.get(ScanRun, scan_id)
        if scan is None:
            return
        scan.stats_json = {
            **(scan.stats_json or {}),
            "progress": {
                "value": max(0.0, min(float(value), 1.0)),
                "message": message,
            },
        }


def _cancel_requested(
    session_factory: sessionmaker[Session], scan_id: str
) -> bool:
    """Read the cancel flag fresh from the database on every poll."""

    with session_factory() as session:
        scan = session.get(ScanRun, scan_id)
        if scan is None:
            return False
        return scan.status == "cancel_requested" or bool(
            (scan.stats_json or {}).get("cancel_requested")
        )


def _finalize_progress(
    session_factory: sessionmaker[Session], scan_id: str
) -> None:
    """Stamp a terminal progress message once run_auto returns cleanly."""

    with session_scope(session_factory) as session:
        scan = session.get(ScanRun, scan_id)
        if scan is None or scan.status in ACTIVE_STATUSES:
            return
        progress = dict((scan.stats_json or {}).get("progress") or {})
        if scan.status == "completed":
            progress.update({"value": 1.0, "message": "扫描完成。"})
        elif scan.status == "cancelled":
            progress["message"] = "扫描已取消，取消前完成的中途结果已保留。"
        else:
            return
        scan.stats_json = {**(scan.stats_json or {}), "progress": progress}


def _mark_failed(
    session_factory: sessionmaker[Session], scan_id: str, exc: Exception
) -> None:
    """Record any worker-thread exception on the ScanRun instead of dying quietly."""

    with session_scope(session_factory) as session:
        scan = session.get(ScanRun, scan_id)
        if scan is None:
            return
        if scan.status in ACTIVE_STATUSES:
            scan.status = "failed"
            scan.finished_at = datetime.now(timezone.utc)
            scan.error_message = f"{type(exc).__name__}: {exc}"
        progress = dict((scan.stats_json or {}).get("progress") or {})
        progress["message"] = f"扫描失败：{exc}"
        scan.stats_json = {**(scan.stats_json or {}), "progress": progress}
