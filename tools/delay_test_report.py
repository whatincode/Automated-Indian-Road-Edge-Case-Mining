"""
delay_test_report.py  (Member 1 tool)   -- task M1-T9 / checklist 12.2

Runs the frame-delay checks from the project document on real videos and writes a
Markdown test report. For every video it tries 4 scenarios (the 500 ms example from
the brief, a rounding case, two holds at once, first/last frame) and checks:

  1. Correct selected frame          the repeated frame is exactly frame N (file hash)
  2. Correct delay duration          extra frames / FPS = requested delay (within 1 frame)
  3. Correct number of duplicates    counted in the output and compared with the formula
  4. Correct output FPS              ffprobe of final.mp4 = FPS of the input video
  5. Correct total duration          original + extra frames / FPS (within 1 frame), and the
                                     frame count of final.mp4 (ffprobe -count_frames)
  6. Audio synchronisation           audio length = video length (within 1 frame), silence
                                     sits exactly at the hold, the rest of the sound is
                                     unchanged and only moved later by the hold length
  +  Hold visible in final.mp4       decoded frames of the hold are (almost) identical

From the project folder:
    python -m tools.delay_test_report --videos data/input
    python -m tools.delay_test_report --videos a.mp4 b.mp4 c.mp4 --seconds 6 --width 1280
    python -m tools.delay_test_report --videos data/input --out documentation/test_report.md

Only the first --seconds of each video are used (default 6; 0 = whole video) and only
the report is kept (frames are written to a temp folder and deleted).
"""
import argparse
import hashlib
import platform
import shutil
import sys
import tempfile
import time
import wave
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

from common.errors import PipelineError
from common.paths import job_dir
from common.utils import run_cmd
from modules.video_processing import frame_delay, frame_extraction, video_export
from modules.video_processing.video_preprocessing import ALLOWED_EXT, probe_video

SAMPLE_RATE = 44100


# ------------------------------------------------------------------ helpers
def sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def expected_extra(delay_ms: float, fps: float) -> int:
    """Written independently of frame_delay.py on purpose: round half up, at least 1."""
    return max(1, int(delay_ms * fps / 1000 + 0.5))


def trim(src: Path, dst: Path, seconds: float) -> Path:
    cmd = ["ffmpeg", "-y", "-i", str(src)]
    if seconds > 0:
        cmd += ["-t", str(seconds)]
    cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "16", "-c:a", "aac", str(dst)]
    run_cmd(cmd, f"cut a test clip from {src.name}")
    return dst


def read_wav(path) -> np.ndarray:
    with wave.open(str(path), "rb") as w:
        assert w.getsampwidth() == 2 and w.getnchannels() == 2, "expected 16-bit stereo WAV"
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).reshape(-1, 2).astype(np.int32)


def audio_diff(seg: np.ndarray, fixed: np.ndarray, start: int) -> float:
    """Smallest mean absolute difference between `seg` and `fixed` placed at `start`,
    trying shifts of up to +-64 samples."""
    best = float("inf")
    for d in range(-64, 65):
        a = start + d
        if a >= 0 and a + len(seg) <= len(fixed):
            best = min(best, float(np.abs(fixed[a:a + len(seg)] - seg).mean()))
    return best


def scenarios(total: int, fps: float) -> list:
    mid, q1, q3 = total // 2, total // 4, (3 * total) // 4
    return [
        ("S1  500 ms on the middle frame (brief example)", [{"frame": mid, "delay_ms": 500}]),
        ("S2  100 ms (needs rounding)", [{"frame": q1, "delay_ms": 100}]),
        ("S3  two holds at once (300 ms + 1000 ms, given out of order)",
         [{"frame": q3, "delay_ms": 1000}, {"frame": q1, "delay_ms": 300}]),
        ("S4  first frame (200 ms) and last frame (200 ms)",
         [{"frame": 0, "delay_ms": 200}, {"frame": total - 1, "delay_ms": 200}]),
    ]


# ------------------------------------------------------------------ the checks
def check_scenario(job: Path, meta: dict, src_hashes: list, holds: list, orig: dict,
                   quality: str, jobs_root: Path, job_id: str) -> list:
    """Returns rows: (check name, 'PASS'|'FAIL'|'n/a', detail)."""
    fps, total = meta["fps"], meta["total_frames"]
    one_frame_ms = 1000 / fps
    rows = []

    res = frame_delay.run(job_id, None, {"holds": holds}, root=jobs_root)
    exp = video_export.run(job_id, None, {"quality": quality}, root=jobs_root)
    out_dir = job / "07_delayed"
    out_hashes = [sha(p) for p in sorted(out_dir.glob("out_*.png"))]

    # My own, independent expectation of what the output must look like
    extra = {}
    for h in holds:
        extra[h["frame"]] = extra.get(h["frame"], 0) + expected_extra(h["delay_ms"], fps)
    expected_seq = []
    for i in range(total):
        expected_seq += [src_hashes[i]] * (1 + extra.get(i, 0))

    # 1. correct selected frame (whole sequence must match, so this also proves that
    #    nothing else moved or was lost)
    ok1 = out_hashes == expected_seq
    first_bad = next((k for k, (a, b) in enumerate(zip(out_hashes, expected_seq)) if a != b), None)
    rows.append(("1. Correct selected frame", "PASS" if ok1 else "FAIL",
                 "every output frame is the expected source frame" if ok1 else
                 f"output has {len(out_hashes)} frames, expected {len(expected_seq)}; "
                 f"first difference at output frame {first_bad}"))

    # 2 + 3. duplicates counted in the OUTPUT
    pos, bad2, bad3, d2, d3 = 0, [], [], [], []
    for i in range(total):
        if i in extra:
            run = 1
            while pos + run < len(out_hashes) and out_hashes[pos + run] == out_hashes[pos] \
                    and run < 1 + extra[i]:
                run += 1
            seen = run - 1
            req = sum(h["delay_ms"] for h in holds if h["frame"] == i)
            applied = seen * 1000 / fps
            d3.append(f"frame {i}: {seen} duplicates (formula: {extra[i]})")
            d2.append(f"frame {i}: asked {req:g} ms, got {applied:.1f} ms")
            if seen != extra[i]:
                bad3.append(i)
            if abs(applied - req) > one_frame_ms + 1e-6:
                bad2.append(i)
            pos += 1 + extra[i]
        else:
            pos += 1
    rows.append(("2. Correct delay duration (within 1 frame = "
                 f"{one_frame_ms:.1f} ms)", "FAIL" if bad2 else "PASS", "; ".join(d2)))
    rows.append(("3. Correct number of duplicated frames", "FAIL" if bad3 else "PASS", "; ".join(d3)))

    # 4. FPS
    v = exp["verification"]
    ok4 = abs(v["fps"] - orig["fps"]) < 0.01
    rows.append(("4. Correct output FPS", "PASS" if ok4 else "FAIL",
                 f"input {orig['fps']:.3f} FPS, final.mp4 {v['fps']:.3f} FPS"))

    # 5. duration + frame count
    n_extra = len(expected_seq) - total
    want_s = (total + n_extra) / fps
    ok5 = (v["frames"] == total + n_extra) and abs(v["duration_s"] - want_s) <= 1 / fps + 1e-6
    rows.append(("5. Correct total duration", "PASS" if ok5 else "FAIL",
                 f"{total} + {n_extra} extra = {total + n_extra} frames expected, final.mp4 has "
                 f"{v['frames']}; duration {v['duration_s']:.3f} s (expected {want_s:.3f} s)"))

    # 6. audio
    if not meta.get("has_audio"):
        rows.append(("6. Audio synchronisation", "n/a", "this video has no audio track"))
    else:
        problems = []
        a_len, v_len = v["audio_duration_s"], v["duration_s"]
        if a_len is None:
            problems.append("final.mp4 has no audio")
        elif abs(a_len - v_len) > 1 / fps + 1e-6:
            problems.append(f"audio {a_len:.3f} s vs video {v_len:.3f} s")
        notes = [f"audio {a_len:.3f} s / video {v_len:.3f} s" if a_len else "no audio"]

        orig_a = read_wav(job / meta["audio_file"])
        fixed = read_wav(job / "output" / "audio_fixed.wav")
        shift = 0                                        # samples inserted so far
        prev_end = 0                                     # original sample where the last hold ended
        for h in res["holds"]:
            hold_start = int(round((h["frame"] + 1) / fps * SAMPLE_RATE))     # in the original
            sil_len = int(round(h["extra_frames"] / fps * SAMPLE_RATE))
            shift += sil_len                                 # silence inserted up to and including this hold
            s0 = hold_start + shift - sil_len
            region = fixed[s0 + 200: s0 + sil_len - 200] if sil_len > 400 else fixed[s0:s0 + sil_len]
            if len(region) and np.abs(region).max() != 0:
                problems.append(f"hold at frame {h['frame']}: audio is not silent during the hold")
            # sound just before the hold must be untouched, and the sound right after the hold
            # must be the original sound moved later by the silence. Hold lengths are rarely a
            # whole number of audio samples (e.g. 5 frames at 24 FPS = 9187.5 samples), so a
            # shift of up to 64 samples (1.5 ms) is accepted.
            lo = max(prev_end, hold_start - 4410)
            before = orig_a[lo: hold_start - 100]
            if len(before) and np.abs(before).max() > 0 and \
                    audio_diff(before, fixed, lo + shift - sil_len) > 0.5:
                problems.append(f"hold at frame {h['frame']}: sound before the hold changed")
            seg = orig_a[hold_start + 100: hold_start + 4410]
            if len(seg) and np.abs(seg).max() > 0 and \
                    audio_diff(seg, fixed, hold_start + 100 + shift) > 0.5:
                problems.append(f"hold at frame {h['frame']}: sound after the hold is not in sync")
            prev_end = hold_start
            notes.append(f"frame {h['frame']}: {h['extra_frames'] / fps * 1000:.0f} ms silence inserted")
        rows.append(("6. Audio synchronisation", "FAIL" if problems else "PASS",
                     "; ".join(problems) if problems else "; ".join(notes)))

    # + hold visible in the decoded video
    cap = cv2.VideoCapture(exp["output_file"])
    decoded, ok = [], True
    while ok:
        ok, fr = cap.read()
        if ok:
            decoded.append(fr)
    cap.release()
    worst, pos = 0.0, 0
    for i in range(total):
        if i in extra:
            for k in range(1, extra[i] + 1):
                if pos + k < len(decoded):
                    worst = max(worst, float(cv2.absdiff(decoded[pos], decoded[pos + k]).mean()))
            pos += 1 + extra[i]
        else:
            pos += 1
    rows.append(("+  Hold visible in final.mp4", "PASS" if worst < 2.0 and len(decoded) == len(expected_seq) else "FAIL",
                 f"decoded {len(decoded)} frames; largest mean pixel difference inside a hold = {worst:.2f} (of 255)"))
    return rows


# ------------------------------------------------------------------ one video
def test_video(src: Path, work: Path, a) -> dict:
    result = {"file": src.name, "error": None, "info": {}, "scenarios": []}
    clip = trim(src, work / f"{src.stem}.mp4", a.seconds)
    orig = probe_video(clip)
    job_id = f"tr_{src.stem}"
    ext = frame_extraction.run_extraction(clip, job_id, work / "jobs", width=a.width)
    job = job_dir(job_id, work / "jobs")
    import json
    meta = json.loads((job / "01_frames" / "metadata.json").read_text(encoding="utf-8"))
    src_hashes = [sha(job / "01_frames" / f["image"]) for f in meta["frames"]]
    result["info"] = {"original size": f"{orig['width']}x{orig['height']}",
                      "frames tested at": f"{meta['width']}x{meta['height']}",
                      "fps": meta["fps"], "frames": meta["total_frames"],
                      "duration (s)": meta["duration_s"], "audio": "yes" if meta["has_audio"] else "no",
                      "converted from VFR": meta["converted_from_vfr"]}
    for title, holds in scenarios(meta["total_frames"], meta["fps"]):
        try:
            rows = check_scenario(job, meta, src_hashes, holds, orig, a.quality, work / "jobs", job_id)
        except PipelineError as e:
            rows = [("Run", "FAIL", f"pipeline error: {e}")]
        result["scenarios"].append({"title": title, "holds": holds, "rows": rows})
    shutil.rmtree(job, ignore_errors=True)
    return result


# ------------------------------------------------------------------ report
def write_report(results: list, out: Path, a) -> bool:
    all_rows = [r for res in results for s in res["scenarios"] for r in s["rows"]]
    fails = sum(1 for r in all_rows if r[1] == "FAIL")
    passes = sum(1 for r in all_rows if r[1] == "PASS")
    lines = ["# Frame delay test report (checklist 12.2)", "",
             f"- Date: {datetime.now():%Y-%m-%d %H:%M}",
             f"- Videos: {', '.join(r['file'] for r in results)}",
             f"- Each video cut to the first {a.seconds:g} s" if a.seconds else "- Whole videos used",
             f"- Working width: {a.width or 'original'}; export quality: {a.quality}",
             f"- Machine: {platform.system()} {platform.release()}, Python {platform.python_version()}, "
             f"OpenCV {cv2.__version__}", "",
             f"**Result: {passes} checks passed, {fails} failed.**", ""]
    lines += ["| Video | FPS | Frames | Scenarios | Checks passed | Checks failed |", "|---|---|---|---|---|---|"]
    for r in results:
        rows = [x for s in r["scenarios"] for x in s["rows"]]
        fps = r["info"].get("fps", "-")
        lines.append(f"| {r['file']} | {fps} | {r['info'].get('frames', '-')} | {len(r['scenarios'])} | "
                     f"{sum(x[1] == 'PASS' for x in rows)} | {sum(x[1] == 'FAIL' for x in rows)} |"
                     if not r["error"] else f"| {r['file']} | - | - | - | - | ERROR: {r['error']} |")
    for r in results:
        lines += ["", f"## {r['file']}", ""]
        if r["error"]:
            lines += [f"**ERROR:** {r['error']}"]
            continue
        lines += ["; ".join(f"{k}: {v}" for k, v in r["info"].items()), ""]
        for s in r["scenarios"]:
            lines += [f"### {s['title']}", "", "Holds: " + ", ".join(
                f"frame {h['frame']} for {h['delay_ms']:g} ms" for h in s["holds"]), "",
                "| Check | Result | What was measured |", "|---|---|---|"]
            for name, status, detail in s["rows"]:
                lines.append(f"| {name} | {status} | {detail.replace('|', '/')} |")
            lines.append("")
    lines += ["", "## How the checks work", "",
              "- Frames are compared by SHA-256 of the PNG files, against an expected sequence that this "
              "script builds on its own (not by calling the code under test).",
              "- Video length, FPS and frame count come from ffprobe on the exported `final.mp4`.",
              "- Audio is compared sample by sample: silence exactly during each hold, unchanged before it, "
              "and the original sound moved later by the hold length after it."]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    return fails == 0


def main():
    ap = argparse.ArgumentParser(description="Run the frame-delay checks (12.2) and write a report.")
    ap.add_argument("--videos", nargs="+", required=True, help="video files and/or folders")
    ap.add_argument("--seconds", type=float, default=6, help="use only the first N seconds (0 = all)")
    ap.add_argument("--width", type=int, default=1280, help="working width (0 = keep original)")
    ap.add_argument("--quality", choices=["preview", "final"], default="final")
    ap.add_argument("--out", default="documentation/test_report_frame_delay.md")
    a = ap.parse_args()
    a.width = a.width or None

    files = []
    for v in a.videos:
        p = Path(v)
        files += sorted(x for x in p.iterdir() if x.suffix.lower() in ALLOWED_EXT) if p.is_dir() else [p]
    if not files:
        print("No videos found.")
        raise SystemExit(1)

    results = []
    with tempfile.TemporaryDirectory(prefix="delay_report_") as tmp:
        for f in files:
            t0 = time.time()
            print(f"Testing {f.name} ...", flush=True)
            try:
                res = test_video(f, Path(tmp), a)
            except Exception as e:                     # one bad video never stops the others
                res = {"file": f.name, "error": str(e), "info": {}, "scenarios": []}
            bad = sum(r[1] == "FAIL" for s in res["scenarios"] for r in s["rows"])
            print(f"  {'ERROR: ' + res['error'] if res['error'] else ('all checks passed' if not bad else f'{bad} FAILED')}"
                  f"  ({time.time() - t0:.0f} s)")
            results.append(res)
    ok = write_report(results, Path(a.out), a) and not any(r["error"] for r in results)
    print(f"Report written to {a.out}")
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
