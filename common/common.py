"""Small shared helpers for Member 1's modules (and anyone else who wants them)."""
import json
import subprocess
from pathlib import Path

DEFAULT_JOBS_ROOT = Path("data/jobs")
FRAME_DIGITS = 5          # frame_00000.png  (see documentation/data_contract.md)
FRAME_EXT = ".png"


class PipelineError(Exception):
    """Readable error: say WHAT went wrong and HOW to fix it."""


def frame_name(i: int) -> str:
    """Frame 100 -> 'frame_00100.png'. Frames are numbered from 0."""
    return f"frame_{i:0{FRAME_DIGITS}d}{FRAME_EXT}"


def job_dir(job_id: str, root=DEFAULT_JOBS_ROOT) -> Path:
    return Path(root) / job_id


def run_cmd(cmd: list, what: str) -> subprocess.CompletedProcess:
    """Run an external tool (ffmpeg/ffprobe). Raise a readable error if it fails."""
    try:
        res = subprocess.run(cmd, capture_output=True, text=True)
    except FileNotFoundError:
        raise PipelineError(
            f"Could not find '{cmd[0]}' while trying to {what}. "
            f"Install FFmpeg and make sure 'ffmpeg -version' works in the terminal."
        )
    if res.returncode != 0:
        tail = res.stderr.strip().splitlines()[-5:]
        raise PipelineError(f"Failed to {what}. Tool said: " + " | ".join(tail))
    return res


def write_json_atomic(path: Path, data) -> None:
    """Write to a temp file first, then rename: nobody ever reads half a file."""
    path = Path(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.replace(path)
