"""
video_preprocessing.py  (Member 1)

Step A of the pipeline: accept the upload, check it, read its properties,
and make sure the frame rate is constant.

Run alone:
    python -m modules.video_processing.video_preprocessing --video my_clip.mp4
"""
import argparse
import json
import shutil
from pathlib import Path

from common.errors import PipelineError
from common.utils import run_cmd

ALLOWED_EXT = {".mp4", ".mov", ".avi", ".mkv", ".ts"}
MAX_SIZE_MB = 500
# Common "nominal" frame rates. Used to pick a clean constant FPS for a VFR video.
COMMON_FPS = [23.976, 24, 25, 29.97, 30, 50, 59.94, 60]


def _fraction(text: str) -> float:
    """ffprobe gives frame rates like '30000/1001'. Turn that into a float."""
    try:
        num, den = text.split("/")
        return float(num) / float(den) if float(den) != 0 else 0.0
    except (ValueError, AttributeError):
        return 0.0


def validate_video(path) -> Path:
    """Check extension and size. Returns the Path, or raises PipelineError."""
    path = Path(path)
    if not path.is_file():
        raise PipelineError(f"File not found: {path}")
    if path.suffix.lower() not in ALLOWED_EXT:
        raise PipelineError(
            f"Unsupported file type '{path.suffix}'. Please upload one of: "
            + ", ".join(sorted(ALLOWED_EXT))
        )
    size_mb = path.stat().st_size / (1024 * 1024)
    if size_mb > MAX_SIZE_MB:
        raise PipelineError(
            f"File is {size_mb:.0f} MB; the limit is {MAX_SIZE_MB} MB. Please upload a shorter clip."
        )
    return path


def probe_video(path) -> dict:
    """Read video properties with ffprobe. Returns a plain dictionary."""
    path = Path(path)
    res = run_cmd(
        ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
        "read the video information",
    )
    info = json.loads(res.stdout)
    streams = info.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    if video is None:
        raise PipelineError("This file has no video stream. Is it really a video?")

    r_fps = _fraction(video.get("r_frame_rate", "0/1"))
    avg_fps = _fraction(video.get("avg_frame_rate", "0/1"))
    # VFR check: the two rates differ noticeably (more than 1 %).
    is_vfr = bool(r_fps and avg_fps and abs(r_fps - avg_fps) / r_fps > 0.01)

    duration = float(video.get("duration") or info.get("format", {}).get("duration") or 0)
    nb = video.get("nb_frames")
    return {
        "source_file": path.name,
        "width": int(video["width"]),
        "height": int(video["height"]),
        "r_frame_rate": r_fps,
        "avg_frame_rate": avg_fps,
        "fps": avg_fps or r_fps,
        "is_vfr": is_vfr,
        "duration_s": duration,
        "total_frames_reported": int(nb) if nb and nb.isdigit() else None,
        "has_audio": audio is not None,
        "audio_codec": audio.get("codec_name") if audio else None,
        "audio_sample_rate": int(audio["sample_rate"]) if audio else None,
        "audio_channels": int(audio["channels"]) if audio else None,
    }


def nominal_fps(props: dict) -> float:
    """Pick a clean constant FPS (e.g. 30) for a variable-frame-rate video."""
    avg = props["avg_frame_rate"] or props["r_frame_rate"]
    return min(COMMON_FPS, key=lambda c: abs(c - avg))


def normalize_fps(src, dst, fps: float) -> Path:
    """Re-encode to constant frame rate (H.264, yuv420p, AAC audio if present)."""
    run_cmd(
        ["ffmpeg", "-y", "-i", str(src), "-r", str(fps),
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(dst)],
        "convert the video to a constant frame rate",
    )
    return Path(dst)


def prepare_input(video_path, job_path) -> tuple:
    """
    Copy the upload into <job>/input/, validate it, probe it, and convert to
    constant FPS if needed.
    Returns (working_video_path, props)  -- props describes the WORKING video.
    """
    src = validate_video(video_path)
    input_dir = Path(job_path) / "input"
    input_dir.mkdir(parents=True, exist_ok=True)
    original = input_dir / f"original{src.suffix.lower()}"
    shutil.copy2(src, original)

    props = probe_video(original)
    props["converted_from_vfr"] = False
    working = original
    if props["is_vfr"]:
        fps = nominal_fps(props)
        working = normalize_fps(original, input_dir / "constant.mp4", fps)
        props = probe_video(working)
        props["converted_from_vfr"] = True
        props["is_vfr"] = False  # constant now; re-probe may still show tiny differences
    props["source_file"] = original.name
    return working, props


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Validate a video and print its properties.")
    ap.add_argument("--video", required=True)
    args = ap.parse_args()
    try:
        validate_video(args.video)
        print(json.dumps(probe_video(args.video), indent=2))
    except PipelineError as e:
        print(f"ERROR: {e}")
        raise SystemExit(1)
