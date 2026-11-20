"""
ui_helpers.py  (Member 1 -> used by Member 3's Streamlit app)

Small functions that give the interface everything it needs for the Frame Delay panel,
so app.py contains no video maths:

    from modules.video_processing.ui_helpers import (
        get_option_limits, get_thumbnails, get_frame_path, preview_hold)

    lim = get_option_limits("demo")            # slider ranges: frames, delay in ms, FPS ...
    thumbs = get_thumbnails("demo")            # small pictures to choose a frame from
    info = preview_hold("demo", 50, 500)       # "what will happen" text numbers, BEFORE running
    # status of a running stage:  common.status.read_status(job_path)
Every function raises PipelineError with a readable message on bad input.
"""
import json
import math
from pathlib import Path

import cv2

from common.errors import PipelineError
from common.paths import DEFAULT_JOBS_ROOT, frame_name, job_dir, latest_frames_dir
from modules.video_processing import frame_delay as fd


def _meta(job_id: str, root) -> dict:
    path = job_dir(job_id, root) / "01_frames" / "metadata.json"
    if not path.exists():
        raise PipelineError("This video has not been prepared yet. Upload it first.")
    return json.loads(path.read_text(encoding="utf-8"))


def _source_dir(job_id: str, root) -> Path:
    """Frames the user is choosing from: the newest stage BEFORE the delay (delay is applied last)."""
    return latest_frames_dir(job_dir(job_id, root), exclude=("07_delayed",))


def get_option_limits(job_id: str, root=DEFAULT_JOBS_ROOT) -> dict:
    """Valid ranges for the Frame Delay sliders / number boxes."""
    m = _meta(job_id, root)
    fps, total = m["fps"], m["total_frames"]
    return {"fps": fps, "total_frames": total, "duration_s": round(total / fps, 3),
            "min_frame": 0, "max_frame": total - 1,
            "min_delay_ms": round(1000 / fps, 1),        # one frame
            "max_delay_ms": fd.MAX_DELAY_MS,
            "default_delay_ms": 500,
            "delay_step_ms": round(1000 / fps, 1)}


def preview_hold(job_id: str, frame: int, delay_ms: float, root=DEFAULT_JOBS_ROOT) -> dict:
    """What a hold WILL do, without running it. Raises PipelineError for invalid input."""
    m = _meta(job_id, root)
    fps, total = m["fps"], m["total_frames"]
    hold = fd.validate_holds([{"frame": frame, "delay_ms": delay_ms}], total)[0]
    extra = fd.delay_to_frames(hold["delay_ms"], fps)
    return {"frame": hold["frame"], "timestamp_s": round(hold["frame"] / fps, 3),
            "requested_ms": hold["delay_ms"], "extra_frames": extra,
            "applied_ms": round(fd.applied_delay_ms(extra, fps), 1),
            "new_total_frames": total + extra, "new_duration_s": round((total + extra) / fps, 3)}


def get_frame_path(job_id: str, frame: int, root=DEFAULT_JOBS_ROOT) -> str:
    """Full-size picture of one frame (for a bigger preview)."""
    total = _meta(job_id, root)["total_frames"]
    if not 0 <= frame < total:
        raise PipelineError(f"Frame {frame} does not exist (0 to {total - 1}).")
    return str(_source_dir(job_id, root) / frame_name(frame))


def get_thumbnails(job_id: str, every_n: int = None, max_thumbs: int = 40, width: int = 160,
                   root=DEFAULT_JOBS_ROOT) -> list:
    """Small JPEG pictures, one every `every_n` frames (chosen automatically if None so that
    there are at most `max_thumbs`). Cached in <job>/thumbs/. Returns a list of
    {"frame": int, "timestamp_s": float, "path": str}."""
    m = _meta(job_id, root)
    fps, total = m["fps"], m["total_frames"]
    if every_n is None:
        every_n = max(1, math.ceil(total / max_thumbs))
    if every_n < 1 or width < 16:
        raise PipelineError("every_n must be at least 1 and width at least 16.")
    src = _source_dir(job_id, root)
    cache = job_dir(job_id, root) / "thumbs" / f"{src.name}_n{every_n}_w{width}"

    if not (cache / "DONE").exists():
        tmp = cache.with_name(cache.name + ".tmp")
        tmp.mkdir(parents=True, exist_ok=True)
        for i in range(0, total, every_n):
            img = cv2.imread(str(src / frame_name(i)))
            if img is None:
                raise PipelineError(f"Could not read {frame_name(i)} in {src}.")
            h, w = img.shape[:2]
            small = cv2.resize(img, (width, max(1, round(h * width / w))), interpolation=cv2.INTER_AREA)
            cv2.imwrite(str(tmp / f"thumb_{i:05d}.jpg"), small, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if cache.exists():
            import shutil
            shutil.rmtree(cache)
        tmp.rename(cache)
        (cache / "DONE").write_text("ok")

    return [{"frame": i, "timestamp_s": round(i / fps, 3), "path": str(cache / f"thumb_{i:05d}.jpg")}
            for i in range(0, total, every_n)]
