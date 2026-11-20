"""
video_export.py  (Member 1)

Last step: frames -> H.264 MP4 (plays in browsers), attach audio, verify the result.

Run alone (from the project folder):
    python -m modules.video_processing.video_export --job demo
    python -m modules.video_processing.video_export --job demo --preset preview
    python -m modules.video_processing.video_export --job demo --mute
"""
import argparse
import json
import re
from pathlib import Path

from common.errors import PipelineError
from common.paths import DEFAULT_JOBS_ROOT, job_dir, latest_frames_dir
from common.status import combine, stage_status
from common.utils import run_cmd, write_json_atomic

# preview = small and fast for the Streamlit player; final = high quality
PRESETS = {"preview": {"crf": "28", "preset": "veryfast"},
           "final": {"crf": "18", "preset": "medium"}}


def _frame_pattern(frames_dir: Path) -> tuple:
    """Find the file pattern (e.g. frame_%05d.png) and the number of frames."""
    files = sorted(p.name for p in frames_dir.glob("*.png"))
    if not files:
        raise PipelineError(f"No PNG frames in {frames_dir}.")
    m = re.match(r"^(.*?)(\d+)\.png$", files[0])
    if not m:
        raise PipelineError(f"Unexpected frame name '{files[0]}' (expected e.g. frame_00000.png).")
    prefix, digits = m.group(1), len(m.group(2))
    if int(m.group(2)) != 0:
        raise PipelineError(f"Frames must start at 0, but the first file is '{files[0]}'.")
    return f"{prefix}%0{digits}d.png", len(files)


def encode_video(frames_dir, fps: float, out_path, quality: str = "final") -> Path:
    """Frames -> video WITHOUT audio. Always libx264 + yuv420p (browser-friendly)."""
    q = PRESETS[quality]
    frames_dir = Path(frames_dir)
    pattern, _ = _frame_pattern(frames_dir)
    run_cmd(["ffmpeg", "-y", "-framerate", str(fps), "-i", str(frames_dir / pattern),
             # yuv420p needs even width and height
             "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2",
             "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", q["crf"], "-preset", q["preset"],
             str(out_path)], "encode the frames into a video")
    return Path(out_path)


def mux_audio(video_path, audio_path, out_path, duration_s: float) -> Path:
    """Attach audio. The audio is padded/cut to the exact video length so the file
    never ends early (and the video is never cut short)."""
    run_cmd(["ffmpeg", "-y", "-i", str(video_path), "-i", str(audio_path),
             "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-af", "apad",
             "-c:a", "aac", "-t", f"{duration_s:.6f}", str(out_path)], "attach the audio")
    return Path(out_path)


def _probe(path) -> dict:
    res = run_cmd(["ffprobe", "-v", "error", "-count_frames", "-show_streams", "-show_format",
                   "-of", "json", str(path)], "check the exported video")
    info = json.loads(res.stdout)
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    a = next((s for s in info["streams"] if s["codec_type"] == "audio"), None)
    num, den = v["r_frame_rate"].split("/")
    return {"frames": int(v["nb_read_frames"]), "fps": float(num) / float(den),
            "width": int(v["width"]), "height": int(v["height"]), "pix_fmt": v["pix_fmt"],
            "codec": v["codec_name"], "duration_s": float(info["format"]["duration"]),
            "audio_duration_s": float(a["duration"]) if a and a.get("duration") else None}


def verify_output(path, expected_frames: int, fps: float, expect_audio: bool) -> dict:
    """Compare the finished file with what we expected. Returns {"ok", "problems", ...}."""
    p = _probe(path)
    problems, one_frame = [], 1.0 / fps
    if p["frames"] != expected_frames:
        problems.append(f"frame count is {p['frames']}, expected {expected_frames}")
    if abs(p["fps"] - fps) > 0.01:
        problems.append(f"FPS is {p['fps']:.3f}, expected {fps:.3f}")
    if abs(p["duration_s"] - expected_frames / fps) > one_frame:
        problems.append(f"duration is {p['duration_s']:.3f} s, expected {expected_frames / fps:.3f} s")
    if p["codec"] != "h264" or p["pix_fmt"] != "yuv420p":
        problems.append(f"not browser-friendly ({p['codec']}/{p['pix_fmt']})")
    if expect_audio:
        if p["audio_duration_s"] is None:
            problems.append("audio is missing")
        elif abs(p["audio_duration_s"] - p["duration_s"]) > one_frame:
            problems.append(f"audio length {p['audio_duration_s']:.3f} s differs from "
                            f"video length {p['duration_s']:.3f} s")
    p.update({"ok": not problems, "problems": problems})
    return p


def run(job_id: str, input_dir=None, options: dict = None, progress=None,
        root=DEFAULT_JOBS_ROOT) -> dict:
    """options = {"quality": "final"|"preview", "mute": False}"""
    options = options or {}
    quality = options.get("quality", "final")
    if quality not in PRESETS:
        raise PipelineError(f"Unknown quality '{quality}'. Use one of: {', '.join(PRESETS)}.")
    job = job_dir(job_id, root)
    meta_path = job / "01_frames" / "metadata.json"
    if not meta_path.exists():
        raise PipelineError(f"{meta_path} not found. Run frame extraction first.")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    with stage_status(job, "export", "Encoding the video") as track:
        progress = combine(track, progress)
        fps = meta["fps"]

        frames_dir = Path(input_dir) if input_dir else latest_frames_dir(job)
        _, n_frames = _frame_pattern(frames_dir)
        out_dir = job / "output"
        out_dir.mkdir(parents=True, exist_ok=True)

        # which audio belongs to these frames?
        warnings, audio = [], None
        if meta.get("has_audio") and not options.get("mute"):
            if frames_dir.name == "07_delayed":
                # use exactly the audio the delay stage says it built for these frames
                info = json.loads((frames_dir / "delay_info.json").read_text(encoding="utf-8"))
                if info.get("audio_file") and Path(info["audio_file"]).exists():
                    audio = Path(info["audio_file"])
                else:
                    warnings.append("The frame delay was made without audio: exported muted.")
            else:
                audio = job / meta["audio_file"]
        elif meta.get("has_audio"):
            warnings.append("Exported without audio (mute was selected).")

        silent = out_dir / "video_noaudio.mp4"
        final = out_dir / "final.mp4"
        progress(0, 3)
        encode_video(frames_dir, fps, silent, quality)
        progress(1, 3)
        if audio:
            mux_audio(silent, audio, final, n_frames / fps)
            silent.unlink()
        else:
            silent.replace(final)
        progress(2, 3)

        report = verify_output(final, n_frames, fps, expect_audio=audio is not None)
        write_json_atomic(out_dir / "settings.json", {
            "frames_source": str(frames_dir), "quality": quality, "fps": fps, "frames": n_frames,
            "audio_used": str(audio) if audio else None, "verification": report})
        progress(3, 3)
        if not report["ok"]:
            warnings += [f"Check failed: {x}" for x in report["problems"]]
        return {"status": "ok" if report["ok"] else "warning", "output_file": str(final),
                "frames": n_frames, "duration_s": report["duration_s"], "audio": audio is not None,
                "verification": report, "warnings": warnings}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Encode the latest frames into final.mp4.")
    ap.add_argument("--job", required=True)
    ap.add_argument("--root", default=str(DEFAULT_JOBS_ROOT))
    ap.add_argument("--frames-dir", help="use this frames folder instead of the latest one")
    ap.add_argument("--preset", choices=list(PRESETS), default="final")
    ap.add_argument("--mute", action="store_true")
    a = ap.parse_args()
    try:
        out = run(a.job, a.frames_dir, {"quality": a.preset, "mute": a.mute}, root=a.root)
        print(f"{out['status'].upper()}: {out['output_file']}  ({out['frames']} frames, "
              f"{out['duration_s']:.2f} s, audio: {out['audio']})")
        for w in out["warnings"]:
            print("  WARNING:", w)
    except PipelineError as e:
        print(f"ERROR: {e}")
        raise SystemExit(1)
