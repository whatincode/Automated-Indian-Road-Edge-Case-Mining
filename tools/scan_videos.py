"""
scan_videos.py  (Member 1 helper)

Scan a folder of dashcam videos and print a table: FPS, size, duration, audio, VFR.
Use it to choose your test clips from the ~50 videos.

    python -m tools.scan_videos --folder path/to/videos --csv scan_report.csv
"""
import argparse
import csv
from pathlib import Path

from common.errors import PipelineError
from modules.video_processing.video_preprocessing import ALLOWED_EXT, probe_video

ap = argparse.ArgumentParser()
ap.add_argument("--folder", required=True)
ap.add_argument("--csv", default="scan_report.csv")
args = ap.parse_args()

rows = []
for p in sorted(Path(args.folder).iterdir()):
    if p.suffix.lower() not in ALLOWED_EXT:
        continue
    try:
        d = probe_video(p)
        rows.append({"file": p.name, "fps": round(d["fps"], 3), "width": d["width"],
                     "height": d["height"], "duration_s": round(d["duration_s"], 1),
                     "size_mb": round(p.stat().st_size / 1048576, 1),
                     "audio": d["has_audio"], "vfr": d["is_vfr"]})
    except (PipelineError, KeyError, ValueError) as e:
        rows.append({"file": p.name, "fps": "?", "width": "?", "height": "?",
                     "duration_s": "?", "size_mb": "?", "audio": "?", "vfr": f"ERROR: {e}"})

if not rows:
    raise SystemExit("No video files found in that folder.")
print(f"{'file':32} {'fps':>7} {'resolution':>11} {'sec':>6} {'MB':>7} {'audio':>6} {'vfr':>5}")
for r in rows:
    print(f"{r['file'][:32]:32} {r['fps']:>7} {str(r['width'])+'x'+str(r['height']):>11} "
          f"{r['duration_s']:>6} {r['size_mb']:>7} {str(r['audio']):>6} {str(r['vfr']):>5}")
with open(args.csv, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)
print(f"\nSaved {len(rows)} rows to {args.csv}")
