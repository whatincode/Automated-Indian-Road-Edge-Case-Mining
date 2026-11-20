"""
status.py  (shared; written by Member 1)

Progress reporting. Every long stage writes  data/jobs/<job_id>/status.json  so the
Streamlit app can show a progress bar by simply reading that file.

status.json looks like:
    {"job_id": "demo", "stage": "extract", "state": "running",   # idle|running|done|failed
     "percent": 42.0, "message": "extract: 126/300", "updated": "2026-11-19T12:00:00"}

Readers (Member 3):   from common.status import read_status;  read_status(job_path)
Writers (every stage): with stage_status(job_path, "mystage") as progress: ... progress(done, total)
"""
import datetime
import json
import time
from contextlib import contextmanager
from pathlib import Path

IDLE = {"job_id": None, "stage": None, "state": "idle", "percent": 0, "message": "", "updated": None}


def _now() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


def set_status(job, stage: str, state: str, percent: float, message: str) -> None:
    """Write status.json. Best effort: a status problem must never crash a stage."""
    job = Path(job)
    data = {"job_id": job.name, "stage": stage, "state": state,
            "percent": round(float(percent), 1), "message": message, "updated": _now()}
    try:
        job.mkdir(parents=True, exist_ok=True)
        path, tmp = job / "status.json", job / "status.json.tmp"
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        for _ in range(5):
            try:
                tmp.replace(path)
                return
            except PermissionError:          # Windows: the app is reading the file right now
                time.sleep(0.05)
    except OSError:
        pass


def read_status(job) -> dict:
    """Current status of a job. Never raises; returns an 'idle' dictionary if there is none."""
    path = Path(job) / "status.json"
    for _ in range(3):
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            break
        except (json.JSONDecodeError, OSError):   # caught while being rewritten: try again
            time.sleep(0.05)
    return dict(IDLE, job_id=Path(job).name)


def log(job, message: str) -> None:
    """Append one line to logs/pipeline.log."""
    try:
        d = Path(job) / "logs"
        d.mkdir(parents=True, exist_ok=True)
        with open(d / "pipeline.log", "a", encoding="utf-8") as f:
            f.write(f"{_now()}  {message}\n")
    except OSError:
        pass


def combine(*callbacks):
    """One progress(done, total) function that calls every non-None callback."""
    cbs = [c for c in callbacks if c]

    def both(done, total):
        for c in cbs:
            c(done, total)
    return both


@contextmanager
def stage_status(job, stage: str, message: str = ""):
    """Wrap a stage: marks it running, then done, or failed (with the error text).
    Yields progress(done, total) which updates the percentage."""
    job = Path(job)
    state = {"pct": 0.0, "t": 0.0}
    set_status(job, stage, "running", 0, message or f"{stage} started")
    log(job, f"[{stage}] started")

    def progress(done, total):
        pct = 100.0 * done / total if total else 0.0
        now = time.time()
        if pct < 100 and now - state["t"] < 0.25:     # do not rewrite the file hundreds of times a second
            return
        state.update(pct=pct, t=now)
        set_status(job, stage, "running", pct, f"{stage}: {done}/{total}")

    try:
        yield progress
    except Exception as e:  # noqa: BLE001 (re-raised below)
        set_status(job, stage, "failed", state["pct"], str(e))
        log(job, f"[{stage}] FAILED: {e}")
        raise
    set_status(job, stage, "done", 100, f"{stage} finished")
    log(job, f"[{stage}] done")
