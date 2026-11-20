"""
batch_process.py  (Member 1 tool)

Run the video pipeline (cut a short clip -> extract frames -> frame delay -> export)
on EVERY video in a folder. One bad file never stops the batch, and a report is saved.
Only the small final.mp4 of each video is kept (frame folders are deleted) unless --keep-frames.

From the project folder:
    python -m tools.batch_process --folder C:\\path\\to\\Dashcam
    python -m tools.batch_process --folder C:\\path\\to\\Dashcam --limit 5 --seconds 10 --start 10
    python -m tools.batch_process --folder C:\\path\\to\\Dashcam --frame 50 --delay-ms 500 --width 1280

Re-running skips videos that are already done (resume), so it is safe to stop and restart.
"""
import argparse
import csv
import json
import shutil
import time
from pathlib import Path

from common.errors import PipelineError
from common.paths import job_dir
from common.utils import run_cmd
from modules.video_processing import frame_delay, frame_extraction, video_export
from modules.video_processing.video_preprocessing import ALLOWED_EXT, probe_video

FIELDS = ["file", "status", "fps", "frames", "extra_frames", "duration_s", "audio",
          "seconds_taken", "note"]


def cut_clip(src: Path, dst: Path, start: float, seconds: float, width: int) -> Path:
    """Short, smaller MP4 copy of the source (original is never touched)."""
    cmd = ["ffmpeg", "-y", "-ss", str(start), "-i", str(src)]
    if seconds > 0:
        cmd += ["-t", str(seconds)]
    cmd += ["-vf", f"scale={width}:-2", "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-crf", "18", "-c:a", "aac", str(dst)]
    run_cmd(cmd, f"cut a clip from {src.name}")
    return dst


def load_previous(report: Path) -> dict:
    """Rows of the last report, so a resumed run keeps the numbers of finished videos."""
    if not report.exists():
        return {}
    with open(report, newline="", encoding="utf-8") as f:
        return {r["file"]: r for r in csv.DictReader(f)}


def process_one(src: Path, a, dirs: dict, previous: dict) -> dict:
    stem = src.stem
    row = {k: "" for k in FIELDS}
    row["file"] = src.name
    final_copy = dirs["results"] / f"{stem}_final.mp4"
    if final_copy.exists():
        old = previous.get(src.name)
        if old and old.get("status") == "ok":
            return old                       # keep the earlier numbers
        row.update(status="ok", note="already done earlier (delete its result file to redo it)")
        return row

    t0 = time.time()
    clip = cut_clip(src, dirs["clips"] / f"{stem}.mp4", a.start, a.seconds, a.width)
    ext = frame_extraction.run_extraction(clip, stem, dirs["jobs"])
    total = ext["frames"]
    hold_frame = min(a.frame, total - 1)         # clip shorter than expected? stay inside it
    dly = frame_delay.run(stem, None, {"holds": [{"frame": hold_frame, "delay_ms": a.delay_ms}]},
                          root=dirs["jobs"])
    out = video_export.run(stem, None, {"quality": a.quality}, root=dirs["jobs"])
    shutil.copy2(out["output_file"], final_copy)

    v = out["verification"]
    row.update(status=out["status"], fps=round(v["fps"], 3), frames=out["frames"],
               extra_frames=dly["extra_frames"], duration_s=round(out["duration_s"], 2),
               audio=out["audio"], seconds_taken=round(time.time() - t0, 1),
               note="; ".join(out["warnings"]))
    if not a.keep_frames:
        shutil.rmtree(job_dir(stem, dirs["jobs"]), ignore_errors=True)
    return row


def main():
    ap = argparse.ArgumentParser(description="Run the pipeline on every video in a folder.")
    ap.add_argument("--folder", required=True, help="folder with the original videos")
    ap.add_argument("--out", default="data/batch", help="where results go (default data/batch)")
    ap.add_argument("--seconds", type=float, default=10, help="clip length; 0 = whole video")
    ap.add_argument("--start", type=float, default=0, help="start second of the clip")
    ap.add_argument("--width", type=int, default=1280, help="working width (720p = 1280)")
    ap.add_argument("--frame", type=int, default=50, help="frame to freeze")
    ap.add_argument("--delay-ms", type=float, default=500, help="freeze length in ms")
    ap.add_argument("--quality", choices=list(video_export.PRESETS), default="preview")
    ap.add_argument("--limit", type=int, default=0, help="only the first N videos (0 = all)")
    ap.add_argument("--keep-frames", action="store_true", help="keep frame folders (uses lots of disk)")
    a = ap.parse_args()

    out = Path(a.out)
    dirs = {"clips": out / "clips", "jobs": out / "jobs", "results": out / "results"}
    for d in dirs.values():
        d.mkdir(parents=True, exist_ok=True)

    videos = [p for p in sorted(Path(a.folder).iterdir()) if p.suffix.lower() in ALLOWED_EXT]
    if a.limit:
        videos = videos[:a.limit]
    if not videos:
        raise SystemExit("No video files found in that folder.")
    print(f"{len(videos)} videos -> {out}  ({a.seconds:g} s clips from {a.start:g} s, "
          f"{a.width} px wide, freeze frame {a.frame} for {a.delay_ms:g} ms)\n")

    report = out / "batch_report.csv"
    previous = load_previous(report)
    rows = []
    for n, src in enumerate(videos, 1):
        print(f"[{n}/{len(videos)}] {src.name} ... ", end="", flush=True)
        try:
            row = process_one(src, a, dirs, previous)
        except PipelineError as e:
            row = {k: "" for k in FIELDS}
            row.update(file=src.name, status="FAILED", note=str(e))
        except Exception as e:  # noqa: BLE001  (never let one file stop the batch)
            row = {k: "" for k in FIELDS}
            row.update(file=src.name, status="FAILED", note=f"{type(e).__name__}: {e}")
        if len(row["note"]) > 250:
            row["note"] = "..." + row["note"][-250:]
        rows.append(row)
        print(row["status"] + (f"  ({row['note']})" if row["note"] else ""))

    with open(report, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    ok = sum(r["status"] == "ok" for r in rows)
    print(f"\nFinished: {ok}/{len(rows)} fine, {len(rows) - ok} need a look. Report: {report}")


if __name__ == "__main__":
    main()
