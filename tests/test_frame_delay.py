"""
Tests for Member 1's modules.  Run from the project folder:
    python -m tests.test_frame_delay          (plain Python)
    python -m pytest tests                    (if pytest is installed)
The end-to-end test needs ffmpeg + opencv and makes its own small test video.
"""
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from common.errors import PipelineError
from modules.video_processing import frame_delay as fd


# ---------------- unit tests (no video needed) ----------------
def test_formula_from_brief():
    assert fd.delay_to_frames(500, 30) == 15          # the worked example in the document
    assert fd.delay_to_frames(100, 24) == 2           # 2.4 rounds to 2
    assert fd.delay_to_frames(100, 25) == 3           # 2.5 rounds UP to 3
    assert fd.delay_to_frames(1, 30) == 1             # never less than one frame
    assert abs(fd.applied_delay_ms(15, 30) - 500) < 1e-9


def test_plan_single_hold():
    plan = fd.build_frame_plan(100, [{"frame": 50, "delay_ms": 500}], 30)
    assert len(plan) == 115                            # 100 + 15
    assert plan.count(50) == 16                        # 1 original + 15 duplicates
    assert plan[:51] == list(range(51))                # before the hold: untouched
    assert plan[51:66] == [50] * 15                    # duplicates directly after frame 50
    assert plan[66] == 51                              # then the video continues


def test_plan_several_holds_do_not_disturb_each_other():
    holds = [{"frame": 80, "delay_ms": 1000}, {"frame": 10, "delay_ms": 500}]   # unordered input
    plan = fd.build_frame_plan(100, holds, 30)
    assert len(plan) == 100 + 30 + 15
    assert plan.count(10) == 16 and plan.count(80) == 31
    assert [x for i, x in enumerate(plan) if i == 0 or plan[i - 1] != x] == list(range(100))


def test_same_frame_twice_is_added():
    plan = fd.build_frame_plan(10, [{"frame": 3, "delay_ms": 100}, {"frame": 3, "delay_ms": 100}], 30)
    assert plan.count(3) == 1 + 3 + 3


def test_validation_messages():
    for bad in ([], [{"frame": 500, "delay_ms": 500}], [{"frame": -1, "delay_ms": 500}],
                [{"frame": 5, "delay_ms": 0}], [{"frame": 5, "delay_ms": 99999}], [{"frame": "x"}]):
        try:
            fd.validate_holds(bad, 100)
        except PipelineError:
            continue
        raise AssertionError(f"should have been rejected: {bad}")


def test_timestamp_conversion():
    from modules.video_processing.frame_extraction import frame_to_timestamp, timestamp_to_frame
    assert abs(frame_to_timestamp(50, 30) - 1.6667) < 1e-3
    assert timestamp_to_frame(1.67, 30, 100) == 50
    assert timestamp_to_frame(999, 30, 100) == 99      # clamped
    assert timestamp_to_frame(-5, 30, 100) == 0


# ---------------- end-to-end test ----------------
def _ff(*args):
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", *args], check=True)


def _probe(path, entries):
    out = subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
                          "-show_entries", entries, "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True, check=True)
    return out.stdout.strip()


def test_end_to_end():
    try:
        import cv2  # noqa: F401
    except ImportError:
        print("  (skipped end-to-end: opencv missing)")
        return
    if not shutil.which("ffmpeg"):
        print("  (skipped end-to-end: ffmpeg missing)")
        return
    from modules.video_processing import frame_extraction, video_export
    tmp = Path(tempfile.mkdtemp())
    try:
        video = tmp / "clip.mp4"      # 3 s, 30 FPS, constant 440 Hz tone (so silence = our insertion)
        _ff("-f", "lavfi", "-i", "testsrc=size=320x180:rate=30:duration=3",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=3",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(video))
        root = tmp / "jobs"
        r = frame_extraction.run_extraction(video, "t", root)
        assert r["frames"] == 90

        res = fd.run("t", None, {"holds": [{"frame": 50, "delay_ms": 500},
                                           {"frame": 10, "delay_ms": 1000}]}, root=root)
        assert res["frames"] == 90 + 15 + 30 and res["extra_frames"] == 45
        d = root / "t" / "07_delayed"
        # the repeated frame is exactly the chosen source frame (hash compare)
        h = lambda p: hashlib.md5(Path(p).read_bytes()).hexdigest()
        src50 = h(root / "t" / "01_frames" / "frame_00050.png")
        plan = fd.build_frame_plan(90, [{"frame": 50, "delay_ms": 500}, {"frame": 10, "delay_ms": 1000}], 30)
        positions = [k for k, f in enumerate(plan) if f == 50]
        assert len(positions) == 16 and all(h(d / f"out_{k:05d}.png") == src50 for k in positions)

        out = video_export.run("t", None, {"quality": "preview"}, root=root)
        v = out["verification"]
        assert out["status"] == "ok", out["warnings"]
        assert v["frames"] == 135 and abs(v["duration_s"] - 4.5) < 1 / 30
        assert abs(v["audio_duration_s"] - v["duration_s"]) < 1 / 30
        assert v["codec"] == "h264" and v["pix_fmt"] == "yuv420p"

        # silence must sit exactly where the holds are (frame 10 -> 0.3667 s, 1.0 s long)
        sd = subprocess.run(["ffmpeg", "-i", str(root / "t" / "output" / "final.mp4"), "-af",
                             "silencedetect=noise=-50dB:d=0.3", "-f", "null", "-"],
                            capture_output=True, text=True).stderr
        starts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", sd)]
        assert len(starts) == 2, sd
        assert abs(starts[0] - 11 / 30) < 0.06                      # hold at frame 10
        assert abs(starts[1] - (51 / 30 + 1.0)) < 0.06             # hold at frame 50, after +1.0 s
        print("  end-to-end OK: 135 frames, 4.5 s, audio in sync")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"PASS  {name}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"FAIL  {name}: {type(e).__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} tests passed")
    raise SystemExit(1 if failed else 0)
