"""
frame_delay.py  (Member 1)

Frame delay = FRAME HOLD: a chosen frame is shown again and again so the video
looks paused. (Not slow motion.)  Also builds the matching audio (silence is
inserted at the hold so sound and picture stay in sync).

    duplicate frames = round(delay_ms * fps / 1000)

Run alone (from the project folder):
    python -m modules.video_processing.frame_delay --job demo --frame 50 --delay-ms 500
    python -m modules.video_processing.frame_delay --job demo --time 1.67 --delay-ms 500
    python -m modules.video_processing.frame_delay --job demo --holds-json "[{\"frame\":50,\"delay_ms\":500},{\"frame\":200,\"delay_ms\":1000}]"
"""
import argparse
import json
import os
import shutil
from pathlib import Path

from common.errors import PipelineError
from common.paths import DEFAULT_JOBS_ROOT, job_dir, latest_frames_dir
from common.status import combine, stage_status
from common.utils import run_cmd, write_json_atomic
from modules.video_processing.frame_extraction import timestamp_to_frame

MAX_DELAY_MS = 10_000          # limit for one hold (demo safety)
OUT_PREFIX = "out_"            # frames after the delay stage: out_00000.png ...


# ---------------------------------------------------------------- the formula
def delay_to_frames(delay_ms: float, fps: float) -> int:
    """500 ms at 30 FPS -> 15 extra frames. Rounded; never less than 1 frame."""
    if delay_ms <= 0:
        raise PipelineError("Delay must be more than 0 ms.")
    return max(1, int(delay_ms * fps / 1000 + 0.5))      # round half up (2.5 -> 3)


def applied_delay_ms(extra_frames: int, fps: float) -> float:
    """The delay the video REALLY gets (can differ slightly from the request)."""
    return extra_frames * 1000 / fps


def validate_holds(holds: list, total_frames: int) -> list:
    """Check user input. Returns a clean list of {"frame": int, "delay_ms": float}."""
    if not holds:
        raise PipelineError("No frame hold given. Choose a frame and a delay in milliseconds.")
    clean = []
    for h in holds:
        try:
            frame, delay = int(h["frame"]), float(h["delay_ms"])
        except (KeyError, TypeError, ValueError):
            raise PipelineError('Each hold must look like {"frame": 50, "delay_ms": 500}.')
        if not 0 <= frame < total_frames:
            raise PipelineError(
                f"Frame {frame} does not exist. This video has frames 0 to {total_frames - 1}.")
        if not 0 < delay <= MAX_DELAY_MS:
            raise PipelineError(f"Delay must be between 1 and {MAX_DELAY_MS} ms (got {delay:g}).")
        clean.append({"frame": frame, "delay_ms": delay})
    return clean


def merge_holds(holds: list, fps: float) -> dict:
    """{frame: extra_frames}. Two holds on the same frame are added together."""
    extra = {}
    for h in holds:
        extra[h["frame"]] = extra.get(h["frame"], 0) + delay_to_frames(h["delay_ms"], fps)
    return extra


# ------------------------------------------------------------- the frame plan
def build_frame_plan(total_frames: int, holds: list, fps: float) -> list:
    """plan[k] = which ORIGINAL frame is shown at output position k.
    Walks the original frames once, so several holds never disturb each other."""
    extra = merge_holds(holds, fps)
    plan = []
    for i in range(total_frames):
        plan.append(i)                       # the original frame
        plan.extend([i] * extra.get(i, 0))   # its duplicates, right after it
    return plan


def hold_summary(holds: list, fps: float) -> list:
    """Readable list of what was really applied, sorted by time."""
    requested = {}
    for h in holds:
        requested[h["frame"]] = requested.get(h["frame"], 0) + h["delay_ms"]
    extra = merge_holds(holds, fps)
    return [{"frame": f, "timestamp_s": round(f / fps, 4), "requested_ms": requested[f],
             "extra_frames": extra[f], "applied_ms": round(applied_delay_ms(extra[f], fps), 2)}
            for f in sorted(extra)]


def apply_frame_plan(src_dir, dst_dir, plan: list, progress=None) -> None:
    """Create out_00000.png ... as HARD LINKS to the source frames (no extra disk space).
    If hard links are not possible (some Windows/OneDrive setups) the files are copied."""
    src_dir, dst_dir = Path(src_dir), Path(dst_dir)
    tmp = dst_dir.with_name(dst_dir.name + ".tmp")
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)

    sources = sorted(src_dir.glob("*.png"))
    if not sources:
        raise PipelineError(f"No PNG frames found in {src_dir}.")
    can_link = True
    for k, original in enumerate(plan):
        src = sources[original]            # frames are numbered 0..N-1 without gaps
        dst = tmp / f"{OUT_PREFIX}{k:05d}.png"
        linked = False
        if can_link:
            try:
                os.link(src, dst)
                linked = True
            except OSError:
                can_link = False           # fall back to copying for the rest
        if not linked:
            shutil.copy2(src, dst)
        if progress and k % 20 == 0:
            progress(k, len(plan))
    if dst_dir.exists():
        shutil.rmtree(dst_dir)
    tmp.rename(dst_dir)
    if progress:
        progress(len(plan), len(plan))


# --------------------------------------------------------------------- audio
def build_delayed_audio(audio_in, audio_out, summary: list, fps: float, sample_rate: int = 44100):
    """Strategy B: cut the audio where each hold starts, insert silence, continue.
    The silence starts when the held frame's own display time ends, i.e. at (frame+1)/fps,
    which is exactly where the duplicates start in the video."""
    fmt = f"aformat=sample_fmts=s16:sample_rates={sample_rate}:channel_layouts=stereo"
    parts, labels, prev = [], [], 0.0
    for idx, h in enumerate(summary):
        t = (h["frame"] + 1) / fps
        d = h["extra_frames"] / fps
        parts.append(f"[0:a]atrim=start={prev:.6f}:end={t:.6f},asetpts=PTS-STARTPTS,{fmt}[a{idx}]")
        parts.append(f"anullsrc=r={sample_rate}:cl=stereo,atrim=duration={d:.6f},{fmt}[s{idx}]")
        labels += [f"[a{idx}]", f"[s{idx}]"]
        prev = t
    last = len(summary)
    parts.append(f"[0:a]atrim=start={prev:.6f},asetpts=PTS-STARTPTS,{fmt}[a{last}]")
    labels.append(f"[a{last}]")
    parts.append("".join(labels) + f"concat=n={len(labels)}:v=0:a=1[out]")
    run_cmd(["ffmpeg", "-y", "-i", str(audio_in), "-filter_complex", ";".join(parts),
             "-map", "[out]", "-c:a", "pcm_s16le", "-ar", str(sample_rate), "-ac", "2",
             str(audio_out)], "insert silence into the audio at the frame hold")
    return Path(audio_out)


# ------------------------------------------------------------------ one call
def run(job_id: str, input_dir=None, options: dict = None, progress=None,
        root=DEFAULT_JOBS_ROOT) -> dict:
    """options = {"holds": [{"frame": 50, "delay_ms": 500}, ...], "skip_audio": False}
    Returns {"status","output_dir","frames","extra_frames","added_seconds","holds","audio","warnings"}"""
    options = options or {}
    job = job_dir(job_id, root)
    meta_path = job / "01_frames" / "metadata.json"
    if not meta_path.exists():
        raise PipelineError(f"{meta_path} not found. Run frame extraction first.")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    fps, total = meta["fps"], meta["total_frames"]

    with stage_status(job, "delay", "Applying the frame hold") as track:
        progress = combine(track, progress)
        src = Path(input_dir) if input_dir else latest_frames_dir(job, exclude=("07_delayed",))
        n_src = len(list(src.glob("*.png")))
        if n_src != total:
            raise PipelineError(f"{src} has {n_src} frames but metadata says {total}. "
                                f"The previous stage must keep every frame.")

        holds = validate_holds(options.get("holds"), total)
        plan = build_frame_plan(total, holds, fps)
        summary = hold_summary(holds, fps)
        out_dir = job / "07_delayed"
        apply_frame_plan(src, out_dir, plan, progress)

        extra = len(plan) - total
        (job / "output").mkdir(exist_ok=True)
        stale = job / "output" / "audio_fixed.wav"      # never reuse audio from an older run
        if stale.exists():
            stale.unlink()
        warnings, audio_file = [], None
        if meta.get("has_audio") and not options.get("skip_audio"):
            audio_file = str(build_delayed_audio(job / meta["audio_file"],
                                                 job / "output" / "audio_fixed.wav", summary, fps))
        elif meta.get("has_audio"):
            warnings.append("Audio skipped: the exported video will be muted.")

        info = {"fps": fps, "source_dir": str(src), "source_frames": total, "output_frames": len(plan),
                "extra_frames": extra, "added_seconds": round(extra / fps, 4),
                "holds": summary, "audio_file": audio_file}
        write_json_atomic(out_dir / "delay_info.json", info)
        (out_dir / "DONE").write_text("ok")
        return {"status": "ok", "output_dir": str(out_dir), "frames": len(plan), "extra_frames": extra,
                "added_seconds": info["added_seconds"], "holds": summary, "audio": audio_file,
                "warnings": warnings}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Apply a frame hold (freeze) to a job.")
    ap.add_argument("--job", required=True)
    ap.add_argument("--root", default=str(DEFAULT_JOBS_ROOT))
    ap.add_argument("--frame", type=int, help="frame number to hold")
    ap.add_argument("--time", type=float, help="OR timestamp in seconds of the frame to hold")
    ap.add_argument("--delay-ms", type=float, help="how long to hold, in milliseconds")
    ap.add_argument("--holds-json", help="several holds as JSON list")
    ap.add_argument("--no-audio", action="store_true", help="skip the audio fix (muted output)")
    a = ap.parse_args()
    try:
        if a.holds_json:
            holds = json.loads(a.holds_json)
        else:
            if a.delay_ms is None or (a.frame is None and a.time is None):
                raise PipelineError("Give --frame (or --time) together with --delay-ms.")
            if a.frame is None:
                meta = json.loads((job_dir(a.job, a.root) / "01_frames" / "metadata.json").read_text())
                a.frame = timestamp_to_frame(a.time, meta["fps"], meta["total_frames"])
            holds = [{"frame": a.frame, "delay_ms": a.delay_ms}]
        out = run(a.job, None, {"holds": holds, "skip_audio": a.no_audio}, root=a.root)
        print(f"Done: {out['frames']} frames (+{out['extra_frames']}, +{out['added_seconds']} s) "
              f"-> {out['output_dir']}")
        for h in out["holds"]:
            print(f"  frame {h['frame']} at {h['timestamp_s']} s: requested {h['requested_ms']:g} ms, "
                  f"applied {h['applied_ms']} ms ({h['extra_frames']} extra frames)")
        for w in out["warnings"]:
            print("  WARNING:", w)
    except PipelineError as e:
        print(f"ERROR: {e}")
        raise SystemExit(1)
