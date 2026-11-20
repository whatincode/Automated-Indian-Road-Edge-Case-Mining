# Dashcam Video Editing: Video Pipeline (Member 1)

Part of the **Dashcam Video Editing & Scene Modification** team project (car-to-auto-rickshaw cockpit replacement, frame delay, pedestrian insertion).

This repository branch holds **Member 1's work**: video preprocessing, frame extraction, frame delay (frame hold) and final video export. Every other module receives its frames from this pipeline and hands frames back to it, so numbering, timestamps and folder layout follow a fixed contract (see [`documentation/data_contract.md`](../../documentation/data_contract.md)).

## What it does

1. **Validate and read a video:** checks the file type, reads FPS, resolution, frame count, duration and audio with `ffprobe` and OpenCV, and converts variable-frame-rate videos to a constant frame rate.
2. **Extract frames:** saves every frame as `frame_00000.png, frame_00001.png, ...` with a `metadata.json` (fps, size, timestamps) and extracts the audio as 44.1 kHz stereo WAV. An optional resize (for example 1280 px wide) keeps 4K videos manageable.
3. **Frame delay (frame hold):** freezes a chosen frame for a chosen time in milliseconds. The number of duplicate frames is `round(delay_ms * fps / 1000)`. Several holds at once are supported, and the audio is rebuilt with silence at each hold so sound and picture stay in sync.
4. **Export:** encodes the latest frames folder to an H.264 `final.mp4` (plays in browsers) and checks it with `ffprobe`.
5. **UI helpers:** thumbnails, frame limits and a delay preview for the Streamlit app, plus a `status.json` progress file for the progress bar.

## Requirements

- Python 3.10 or newer (tested on Python 3.14, Windows 11)
- **FFmpeg and ffprobe** installed and available in `PATH` (they are programs, not pip packages). Check with `ffmpeg -version`.
- Python packages:

```
pip install -r requirements.txt
```

## Folder structure

```
common/                  shared helpers: paths, errors, status/progress, command runner
modules/video_processing/
    video_preprocessing.py   validate video, probe properties, fix variable frame rate
    frame_extraction.py      extract frames, metadata.json and audio
    frame_delay.py           frame hold and matching audio
    video_export.py          encode final.mp4 and verify it
    ui_helpers.py            thumbnails, limits and preview for the app
tools/
    scan_videos.py           scan a folder of videos and report FPS, size, duration, audio
    batch_process.py         run the whole pipeline on every video in a folder
    delay_test_report.py     run the frame-delay checks and write a test report
tests/                   unit tests
documentation/
    data_contract.md         naming, folders and function rules for the whole team
    test_report_frame_delay.md   result of the frame-delay tests
    sample_metadata.json     example metadata.json
data/input/              small test clips (the large dashcam videos are not stored in Git)
scan_report.csv          scan of the dashcam videos
```

Generated output goes to `data/jobs/<job_id>/` (frames, delayed frames, logs, final video). It is not stored in Git.

## Quick start

Run everything **from the project root** with `python -m ...`.

**1. Check a video**

```
python -m modules.video_processing.video_preprocessing --video data/input/test_10s.mp4
```

**2. Extract frames** (use `--width 1280` for large videos)

```
python -m modules.video_processing.frame_extraction --video data/input/test_10s.mp4 --job demo --width 1280
```

**3. Apply a frame hold** (hold frame 50 for 500 ms)

```
python -m modules.video_processing.frame_delay --job demo --frame 50 --delay-ms 500
```

Other ways to choose the hold:

```
python -m modules.video_processing.frame_delay --job demo --time 1.67 --delay-ms 500
python -m modules.video_processing.frame_delay --job demo --holds-json "[{\"frame\":50,\"delay_ms\":500},{\"frame\":200,\"delay_ms\":1000}]"
```

**4. Export the video**

```
python -m modules.video_processing.video_export --job demo
```

The result is `data/jobs/demo/output/final.mp4`.

## Tools

**Scan a folder of videos**

```
python -m tools.scan_videos --folder path/to/videos --csv scan_report.csv
```

**Process every video in a folder** (cut a short clip, extract, delay, export; one bad file never stops the batch, and re-running skips finished videos)

```
python -m tools.batch_process --folder path/to/videos --seconds 10 --width 1280 --frame 50 --delay-ms 500
```

**Run the frame-delay checks and write a report**

```
python -m tools.delay_test_report --videos data/input --out documentation/test_report.md
```

**Run the unit tests**

```
python -m pytest tests
```

## For Member 2 and Member 3

- Follow [`documentation/data_contract.md`](../../documentation/data_contract.md): frame names, job folders, `DONE` markers and the `run(job_id, input_dir, options, progress)` function shape.
- Read the video facts (fps, width, height, total frames, audio) from `01_frames/metadata.json`.
- **Frame delay is always applied last**, after cockpit and pedestrian stages, so frame numbers and timestamps stay on the original timeline until then.
- For the Streamlit app, `modules/video_processing/ui_helpers.py` provides:

| Function | Gives the app |
|---|---|
| `get_option_limits(job_id)` | fps, total frames, min/max frame and delay |
| `get_thumbnails(job_id)` | small preview images with frame numbers and timestamps |
| `get_frame_path(job_id, frame)` | full-size frame for a bigger preview |
| `preview_hold(job_id, frame, delay_ms)` | extra frames, applied delay and new length before running |

- Progress for the app's progress bar: `from common.status import read_status`.
- Export from the app: `video_export.run(job_id, options={"quality": "final", "mute": False})`.

## Notes

- Videos, GPS logs (`.NMEA`) and the `data/jobs/` folder are **not stored in Git** (see `.gitignore`). Only small test clips in `data/input/` are kept.
- A 4K PNG frame is about 10-15 MB, so one 60 s 4K clip can need 20 GB or more. Use `--width 1280` while developing.
- Frame delay is a **frame hold** (the picture freezes), not slow motion.
- Always play the exported H.264 `final.mp4`, not the original `.TS` files, in the browser.
