from pathlib import Path

DEFAULT_JOBS_ROOT = Path("data/jobs")
FRAME_DIGITS = 5          # frame_00000.png  (see documentation/data_contract.md)
FRAME_EXT = ".png"


def frame_name(i: int) -> str:
    """Frame 100 -> 'frame_00100.png'. Frames are numbered from 0."""
    return f"frame_{i:0{FRAME_DIGITS}d}{FRAME_EXT}"


def job_dir(job_id: str, root=DEFAULT_JOBS_ROOT) -> Path:
    return Path(root) / job_id


# Stage folders from newest to oldest. "Latest frames" = first one that is finished.
STAGE_FOLDERS = ["07_delayed", "06_composited", "05_pedestrians", "03_background", "01_frames"]


def latest_frames_dir(job, exclude=()) -> Path:
    """Newest finished frames folder of a job (a folder is finished when it has a DONE file)."""
    from common.errors import PipelineError
    for name in STAGE_FOLDERS:
        if name in exclude:
            continue
        d = Path(job) / name
        if (d / "DONE").exists():
            return d
    raise PipelineError(
        f"No finished frames folder found in {job}. Run frame extraction first "
        f"(python -m modules.video_processing.frame_extraction --video ... --job ...)."
    )
