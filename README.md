# Dashcam Video Editing & Scene Modification

**Car-to-Auto-Rickshaw Cockpit Replacement | Frame Delay | Pedestrian Insertion**

A video-editing application for forward-facing dashcam videos. A user chooses a video and edits it in three ways, then previews and downloads the result:

| Feature | What it does |
|---|---|
| **Vehicle replacement** | Removes the car's own cockpit (dashboard, bonnet, steering wheel, mirrors) and replaces it with an auto-rickshaw cockpit. The road, buildings, vehicles and people stay as they were. |
| **Frame delay** | Freezes a chosen frame for a chosen time (for example, hold frame 50 for 500 ms). Audio is rebuilt so sound and picture stay in sync. |
| **Pedestrian insertion** | Adds one or more walking people at a chosen time and position (left, centre, right) with believable size, movement and shadows. |

The final application is a web-style interface built with **Streamlit**.

## Project status

| Part | Owner | Status |
|---|---|---|
| Video preprocessing, frame extraction, frame delay, video export | Member 1 | Done, with tests and a test report |
| Vehicle replacement (SAM 2, ProPainter, Blender) | Member 2 | In progress |
| Pedestrian insertion, Streamlit app, pipeline controller | Member 3 | In progress |

> Update this table as each part is merged.

## Team

| Member | Name | Responsibility |
|---|---|---|
| Member 1 | _add name_ | Video pipeline: preprocessing, frame extraction, frame delay, final export |
| Member 2 | _add name_ | Cockpit masks, background filling, auto-rickshaw cockpit render and compositing |
| Member 3 | _add name_ | Pedestrian assets, placement and animation, Streamlit app and pipeline controller |

## How the system works

The system has three layers: the **interface** (Streamlit), a **pipeline controller** that runs the stages in order, and **three processing modules** that read and write files in a shared job folder.

```
Upload video
   |
   v
[M1] Validate, read properties, extract frames + metadata + audio    -> 01_frames/
   |
   v
[M2] Mask the car cockpit (SAM 2)                                    -> 02_masks/
[M2] Remove cockpit, fill the road (ProPainter)                      -> 03_background/
   |
   v
[M3] Insert pedestrians on the clean background                      -> 05_pedestrians/
   |
   v
[M2] Lay the rickshaw cockpit on top (hides pedestrians correctly)   -> 06_composited/
   |
   v
[M1] Frame delay (always last, so timestamps stay correct)           -> 07_delayed/
   |
   v
[M1] Encode H.264 MP4 and attach fixed audio                         -> output/final.mp4
```

If a feature is switched off, its stage is skipped and the next stage reads the latest finished folder. The pipeline controller (`pipeline.py`) tracks which folder is the latest.

Two rules explain the stage order:

- **Pedestrians go behind the cockpit.** The cockpit is composited after the pedestrians, so a pedestrian near the bottom of the frame is partly hidden by the handlebar and panel, like in real life.
- **Frame delay is always last.** Pedestrian and cockpit work use the original frame numbers and timestamps. Delaying first would shift every timestamp after the hold.

## Folder structure

```
project/
|-- app.py                       Streamlit interface                      [M3]
|-- pipeline.py                  runs stages in order, handles errors     [M3]
|-- config.py                    paths, executables, default settings     [shared]
|-- requirements.txt
|-- README.md
|
|-- common/                      shared helpers: paths, errors, status/progress
|
|-- modules/
|   |-- video_processing/        frame extraction, frame delay, export    [M1]
|   |-- vehicle_replacement/     segmentation, inpainting, cockpit render [M2]
|   `-- pedestrian_insertion/    assets, animation, compositing           [M3]
|
|-- assets/
|   |-- auto_rickshaw/           Blender file, textures, camera.json, licences
|   `-- pedestrians/             PNG sprites, assets.json, LICENSES.csv
|
|-- third_party/                 cloned repos, not edited: sam2/, ProPainter/, Depth-Anything-V2/
|
|-- data/
|   |-- input/                   small sample test videos
|   `-- jobs/<job_id>/           generated output (not stored in Git)
|
|-- tests/                       test scripts and checklists
|-- tools/                       helper scripts (scan videos, batch process, test reports)
`-- documentation/               data contract, test reports, user guide
```

Each upload gets its own job folder, `data/jobs/<job_id>/`, with numbered stage folders (`01_frames` to `07_delayed`, `output`, `logs`) and a `status.json` for the progress bar.

## Installation

### 1. Python environment

Python 3.10 or newer is needed (SAM 2 requires it).

```
conda create -n dashcam python=3.10 -y
conda activate dashcam
pip install -r requirements.txt
```

Install **PyTorch** with the command generated at https://pytorch.org for your operating system and CUDA/CPU. Streamlit and the other packages used by the app are installed with the requirements file once Member 3 adds them.

### 2. FFmpeg

FFmpeg and ffprobe are programs, not pip packages.

- Windows: download a build from ffmpeg.org (or use `winget`) and add its `bin` folder to `PATH`
- Ubuntu/Debian: `sudo apt install ffmpeg`
- macOS: `brew install ffmpeg`

Check with `ffmpeg -version` and `ffprobe -version`.

### 3. Model tools for vehicle replacement (Member 2)

Clone these into `third_party/` and follow their own README files for checkpoints:

```
git clone https://github.com/facebookresearch/sam2.git
git clone https://github.com/sczhou/ProPainter.git
```

- **SAM 2** needs Python 3.10+ and a recent PyTorch. On Windows its README recommends WSL.
- **ProPainter** may need its own environment; call it with `subprocess` if packages conflict.
- **Blender** (free LTS version from blender.org) renders the cockpit. Check with `blender --version`.

A GPU (NVIDIA) is recommended. Without one, use short, low-resolution clips, or run the SAM 2 and ProPainter steps on a cloud notebook and bring the results back.

## Running

**Streamlit app (once `app.py` is merged)**

```
streamlit run app.py
```

**Video pipeline from the command line (Member 1 part, available now)**

Run from the project root:

```
python -m modules.video_processing.frame_extraction --video data/input/test_10s.mp4 --job demo --width 1280
python -m modules.video_processing.frame_delay --job demo --frame 50 --delay-ms 500
python -m modules.video_processing.video_export --job demo
```

The result is `data/jobs/demo/output/final.mp4`. See [`modules/video_processing/README.md`](modules/video_processing/README.md) for all options and tools.

## Rules for the team

- Follow [`documentation/data_contract.md`](documentation/data_contract.md): frame names (`frame_00000.png`), job folders, `DONE` markers, the `metadata.json` format and the `run(job_id, input_dir, options, progress)` function shape. Change it only by team vote.
- Never rename frames. Frame numbering starts at 0, and every stage keeps the same names as its input.
- Write only inside your own numbered job folder. Read the video facts (fps, size, total frames, audio) from `01_frames/metadata.json`.
- Report progress with `common/status.py` so the app can show a progress bar.
- Work on your own branch (for example `member1-video-processing`) and open a pull request into `main`.
- Do not commit videos, GPS logs, frames or `data/jobs/`. The `.gitignore` already excludes them. Share large files through a shared drive.
- Check the licence of every asset (pedestrian images, rickshaw model, textures) and record it in `LICENSES.csv` or `LICENSES.md`.

## Testing

Each feature has a checklist in the project document (vehicle replacement, frame delay, pedestrian insertion, end-to-end). Record every test with the date, the video used, pass/fail and notes.

- Frame delay: [`documentation/test_report_frame_delay.md`](documentation/test_report_frame_delay.md) (84 checks passed, 0 failed, on three test clips)
- Run the unit tests with `python -m pytest tests`

## Notes

- A 4K PNG frame is about 10-15 MB, so one 60 s 4K clip can need 20 GB or more. Use a working width of 1280 px while developing.
- Frame delay is a **frame hold** (the picture freezes), not slow motion.
- Exports are H.264 MP4 (`yuv420p`) so they play in browsers and in Streamlit.

## References

- GenVideo: One-shot Target-image and Shape Aware Video Editing using T2I Diffusion Models (CVPR Workshops 2024, arXiv:2404.12541)
- [SAM 2](https://github.com/facebookresearch/sam2), [ProPainter](https://github.com/sczhou/ProPainter), [Depth Anything V2](https://github.com/DepthAnything/Depth-Anything-V2), [Streamlit](https://docs.streamlit.io), [FFmpeg](https://ffmpeg.org), [Blender](https://www.blender.org)
