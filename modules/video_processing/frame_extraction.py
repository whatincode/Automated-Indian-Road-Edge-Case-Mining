"""
frame_extraction.py  (Member 1)

Step B of the pipeline: video -> numbered PNG frames + metadata.json + audio.wav.

Run alone:
    python -m modules.video_processing.frame_extraction --video my_clip.mp4 --job demo
Result:
    data/jobs/demo/input/original.mp4, audio.wav
    data/jobs/demo/01_frames/frame_00000.png ... metadata.json
"""
import argparse
import shutil
from pathlib import Path

import cv2

from common.errors import PipelineError
from common.paths import DEFAULT_JOBS_ROOT, frame_name, job_dir
from common.status import combine, stage_status
from common.utils import run_cmd, write_json_atomic
from modules.video_processing.video_preprocessing import prepare_input


# ---------- helpers other members can import ----------
def frame_to_timestamp(frame_number: int, fps: float) -> float:
    """Frame 50 at 30 FPS -> 1.6667 s."""
    return frame_number / fps


def timestamp_to_frame(seconds: float, fps: float, total_frames: int) -> int:
    """1.67 s at 30 FPS -> frame 50 (rounded, then kept inside 0..total_frames-1)."""
    n = round(seconds * fps)
    return max(0, min(n, total_frames - 1))


# ---------- audio ----------
def extract_audio(video_path, out_wav) -> bool:
    """Save audio as 44.1 kHz stereo WAV (so silence insertion works later).
    Returns False if the video has no audio."""
    res = run_cmd(["ffprobe", "-v", "error", "-select_streams", "a",
                   "-show_entries", "stream=index", "-of", "csv=p=0", str(video_path)],
                  "check for an audio track")
    if not res.stdout.strip():
        return False
    run_cmd(["ffmpeg", "-y", "-i", str(video_path), "-vn", "-acodec", "pcm_s16le",
             "-ar", "44100", "-ac", "2", str(out_wav)], "extract the audio")
    return True


# ---------- frames ----------
def working_size(orig_w: int, orig_h: int, width=None) -> tuple:
    """Size the frames will be saved at. `width=None` (or a width >= the original) keeps
    the original size: frames are never enlarged. Height keeps the aspect ratio and is
    made even (H.264 / yuv420p needs even sizes)."""
    if not width or width >= orig_w:
        return orig_w, orig_h
    w = int(width) - int(width) % 2
    h = round(orig_h * w / orig_w)
    return w, max(2, h + h % 2)


def extract_frames(video_path, frames_dir, fps: float, progress=None, width=None) -> list:
    """Loop over the video and save frame_00000.png, frame_00001.png, ...
    Returns the per-frame metadata list. Writes into a temp folder first and
    renames it when finished, so no one ever sees a half-finished folder."""
    frames_dir = Path(frames_dir)
    tmp_dir = frames_dir.with_name(frames_dir.name + ".tmp")
    if tmp_dir.exists():
        shutil.rmtree(tmp_dir)
    tmp_dir.mkdir(parents=True)

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise PipelineError("OpenCV could not open the video. Try re-encoding it to H.264 MP4.")
    expected = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    target = working_size(int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                          int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)), width)

    frames, i = [], 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        name = frame_name(i)
        if (frame.shape[1], frame.shape[0]) != target:
            frame = cv2.resize(frame, target, interpolation=cv2.INTER_AREA)
        if not cv2.imwrite(str(tmp_dir / name), frame):
            raise PipelineError(f"Could not save {name}. Is the disk full?")
        h, w = frame.shape[:2]
        frames.append({"frame_number": i, "timestamp": round(frame_to_timestamp(i, fps), 4),
                       "image": name, "fps": fps, "width": w, "height": h})
        i += 1
        if progress and i % 10 == 0:
            progress(i, expected)
    cap.release()

    if i == 0:
        raise PipelineError("No frames could be read from the video.")
    if expected and i != expected:
        print(f"WARNING: header said {expected} frames, but {i} were actually read. "
              f"Using {i} (the number really read).")

    if frames_dir.exists():
        shutil.rmtree(frames_dir)
    tmp_dir.rename(frames_dir)
    if progress:
        progress(i, i)
    return frames


def run_extraction(video_path, job_id: str, root=DEFAULT_JOBS_ROOT, progress=None,
                   width=None) -> dict:
    """Whole Step A + B for one job. Returns a small result dictionary.
    Writes status.json while it works (see common/status.py).
    width: optional working width in pixels (e.g. 1280). All frames are saved at that
    size; the audio is untouched. None = keep the original size."""
    job = job_dir(job_id, root)
    with stage_status(job, "extract", "Reading the video") as track:
        progress = combine(track, progress)
        working, props = prepare_input(video_path, job)

        frames_dir = job / "01_frames"
        frames = extract_frames(working, frames_dir, props["fps"], progress, width)

        audio_path = job / "input" / "audio.wav"
        has_audio = extract_audio(working, audio_path)

        first = frames[0]
        metadata = {
            "fps": props["fps"],
            "width": first["width"],
            "height": first["height"],
            "total_frames": len(frames),
            "duration_s": round(len(frames) / props["fps"], 4),
            "has_audio": has_audio,
            "audio_file": "input/audio.wav" if has_audio else None,
            "source_file": props["source_file"],
            "converted_from_vfr": props["converted_from_vfr"],
            "original_width": props["width"],      # size of the uploaded video
            "original_height": props["height"],
            "resized": (first["width"], first["height"]) != (props["width"], props["height"]),
            "frames": frames,
        }
        write_json_atomic(frames_dir / "metadata.json", metadata)
        (frames_dir / "DONE").write_text("ok")   # resume marker used by pipeline.py
    return {"status": "ok", "output_dir": str(frames_dir), "frames": len(frames), "warnings": []}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Extract frames, metadata and audio from a video.")
    ap.add_argument("--video", required=True)
    ap.add_argument("--job", required=True, help="job id, e.g. demo")
    ap.add_argument("--root", default=str(DEFAULT_JOBS_ROOT))
    ap.add_argument("--width", type=int, default=None,
                    help="working width in pixels, e.g. 1280 (default: keep original size)")
    args = ap.parse_args()
    try:
        out = run_extraction(args.video, args.job, args.root,
                             progress=lambda d, t: print(f"  {d}/{t} frames", end="\r"),
                             width=args.width)
        print(f"\nDone: {out['frames']} frames -> {out['output_dir']}")
    except PipelineError as e:
        print(f"ERROR: {e}")
        raise SystemExit(1)
