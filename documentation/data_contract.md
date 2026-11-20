# Data Contract (M1-T1)

Owner: Member 1. Every member follows these rules. Change them only by team vote.

## 1. Frames
- Format: PNG (lossless), read by OpenCV as BGR. Same width and height as the original video in every stage.
- Numbering starts at **0**. File name: `frame_` + 5 digits + `.png` (frame 100 -> `frame_00100.png`).
- A module NEVER renames frames. A stage that outputs frames uses exactly the same names as its input.
  (Only the frame-delay stage, 07_delayed/, makes new sequential numbering `out_00000.png ...`.)
- Timestamp (seconds) = frame_number / fps, on the ORIGINAL timeline until the frame-delay stage.
- Frames are always constant frame rate (variable-frame-rate uploads are converted first).

## 2. Job folder: `data/jobs/<job_id>/`
| Folder | Written by | Content |
|---|---|---|
| input/ | M1 | original.<ext>, constant.mp4 (only if VFR was fixed), audio.wav (44.1 kHz stereo, only if the video has audio) |
| 01_frames/ | M1 | frame_*.png, metadata.json, DONE marker |
| 02_masks/ | M2 | cockpit masks |
| 03_background/ | M2 | cockpit removed, road filled in |
| 04_cockpit_rgba/ | M2 | transparent cockpit render |
| 05_pedestrians/ | M3 | frames with pedestrians |
| 06_composited/ | M2 | cockpit on top |
| 07_delayed/ | M1 | frames after frame hold: `out_00000.png ...` (hard links to the source frames) + delay_info.json + DONE |
| output/ | M1 | final.mp4, settings.json, audio_fixed.wav (audio rebuilt for the delayed video) |
| logs/, status.json | all | progress and errors |

A stage writes into `<folder>.tmp` and renames it when finished; a `DONE` file marks a finished folder.

## 3. metadata.json (lives in 01_frames/)
Video-level facts at the top, then one entry per frame:
```json
{
  "fps": 30.0, "width": 1920, "height": 1080,
  "total_frames": 300, "duration_s": 10.0,
  "has_audio": true, "audio_file": "input/audio.wav",
  "source_file": "original.mp4", "converted_from_vfr": false,
  "frames": [
    {"frame_number": 100, "timestamp": 3.3333, "image": "frame_00100.png",
     "fps": 30.0, "width": 1920, "height": 1080}
  ]
}
```
Read it with `json.load`. `total_frames` is the number of frames actually read, not the file header's claim.

## 4. Function shape (all stages)
```python
def run(job_id: str, input_dir: str, options: dict, progress=None) -> dict:
    """returns {"status": "ok", "output_dir": "...", "frames": 900, "warnings": []}"""
```
- Read only `input_dir` and `metadata.json`. Write only inside your own numbered folder.
- Call `progress(done, total)` regularly.
- On problems raise `PipelineError("what went wrong, how to fix it")` (see common.py).

## 5. Helpers from Member 1
`frame_to_timestamp(n, fps)`, `timestamp_to_frame(seconds, fps, total_frames)` in frame_extraction.py;
`frame_name(i)` and `PipelineError` in common.py.

## 6. Rules added while building the frame-delay and export steps
- **Working resolution:** agree once as a team (suggested for development: 1280x720, 30 FPS). Everyone starts from the same shared test clip.
- **Every frames folder must have a `DONE` file** when finished (write it LAST). `latest_frames_dir()` in `common/paths.py` only trusts folders with `DONE`, so an unfinished stage is never exported by accident.
- **Stage order for "latest frames":** 07_delayed, 06_composited, 05_pedestrians, 03_background, 01_frames.
- **Delay is always applied LAST** and reads the newest folder except 07_delayed itself. It needs `01_frames/metadata.json` (fps, total frames, audio).
- **Frame count must not change** before the delay stage: each stage's output has exactly as many frames as `total_frames` in metadata.
- **Switching the delay OFF:** the pipeline controller (pipeline.py, Member 3) must delete the old `07_delayed/` folder, otherwise the export will pick up the old delayed frames.
- **Export:** `video_export.run(job_id, options={"quality": "final"|"preview", "mute": False})` writes `output/final.mp4` (H.264, yuv420p) and checks it with ffprobe; the result dictionary has `"status"` ("ok" or "warning") and `"warnings"`.

## 6b. Working resolution (resize at extraction)
- `frame_extraction --width 1280` (or `run_extraction(..., width=1280)`) saves ALL frames at that width; the height keeps the aspect ratio and is made even. A width equal to or larger than the original is ignored (frames are never enlarged). Default: keep the original size.
- `metadata.json` `width`/`height` are the WORKING size every stage must use. `original_width`, `original_height` and `resized` record what was uploaded. The audio is never changed.
- Size warning: a 4K PNG frame is about 10-15 MB, so one 60 s 4K clip (1,800 frames) can need 20+ GB. Use `--width 1280` for development.

## 7. Progress reporting: status.json (for Member 3's progress bar)
Every stage writes `data/jobs/<job_id>/status.json` and appends to `logs/pipeline.log`:
```json
{"job_id": "demo", "stage": "extract", "state": "running", "percent": 42.0,
 "message": "extract: 126/300", "updated": "2026-11-19T12:00:00"}
```
- `state` is `idle`, `running`, `done` or `failed`. On `failed`, `message` holds a readable explanation.
- `percent` is the progress of the CURRENT stage (0-100). The overall bar across all stages is built by pipeline.py.
- Read it with `from common.status import read_status; read_status(job_path)` (never raises, returns `idle` if missing).
- Member 1's stages (`extract`, `delay`, `export`) already do this. Members 2 and 3 wrap their stage the same way:
```python
from common.status import stage_status, combine
with stage_status(job_path, "mask") as progress:
    for i in range(total):
        ...
        progress(i + 1, total)
```

## 8. Helpers for the Frame Delay panel: modules/video_processing/ui_helpers.py
| Function | Gives the app |
|---|---|
| `get_option_limits(job_id)` | fps, total frames, min/max frame, min/max/default delay in ms |
| `get_thumbnails(job_id, every_n=None, max_thumbs=40, width=160)` | list of `{"frame", "timestamp_s", "path"}` small JPEGs (cached in `<job>/thumbs/`) |
| `get_frame_path(job_id, frame)` | full-size frame for a bigger preview |
| `preview_hold(job_id, frame, delay_ms)` | extra frames, applied delay, new length BEFORE running; raises PipelineError with a readable message on bad input |
Thumbnails come from the newest stage before the delay (the delay is always applied last), so they show cockpit/pedestrian edits once those stages have run.
