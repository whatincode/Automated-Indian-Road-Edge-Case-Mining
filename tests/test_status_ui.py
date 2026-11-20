"""
Tests for status.json reporting and the UI helper functions.
    python -m tests.test_status_ui
"""
import shutil
import subprocess
import tempfile
from pathlib import Path

from common.errors import PipelineError
from common.status import read_status, stage_status


def test_status_done_and_failed():
    tmp = Path(tempfile.mkdtemp())
    try:
        job = tmp / "j"
        assert read_status(job)["state"] == "idle"          # nothing yet: never raises
        with stage_status(job, "demo") as progress:
            assert read_status(job)["state"] == "running"
            progress(50, 100)
            progress(100, 100)
        s = read_status(job)
        assert s["state"] == "done" and s["percent"] == 100 and s["stage"] == "demo"
        try:
            with stage_status(job, "bad"):
                raise PipelineError("something readable went wrong")
        except PipelineError:
            pass
        s = read_status(job)
        assert s["state"] == "failed" and "readable" in s["message"]
        assert "FAILED" in (job / "logs" / "pipeline.log").read_text()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_stages_and_ui_helpers():
    try:
        import cv2  # noqa: F401
    except ImportError:
        print("  (skipped: opencv missing)")
        return
    if not shutil.which("ffmpeg"):
        print("  (skipped: ffmpeg missing)")
        return
    from modules.video_processing import frame_delay, frame_extraction, video_export
    from modules.video_processing import ui_helpers as ui
    tmp = Path(tempfile.mkdtemp())
    try:
        video = tmp / "clip.mp4"
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                        "testsrc=size=320x180:rate=30:duration=3", "-f", "lavfi", "-i",
                        "sine=frequency=440:duration=3", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                        "-c:a", "aac", str(video)], check=True)
        root, job = tmp / "jobs", tmp / "jobs" / "t"

        frame_extraction.run_extraction(video, "t", root)
        assert read_status(job)["stage"] == "extract" and read_status(job)["state"] == "done"

        lim = ui.get_option_limits("t", root)
        assert lim["total_frames"] == 90 and lim["max_frame"] == 89 and lim["min_delay_ms"] == 33.3

        thumbs = ui.get_thumbnails("t", every_n=10, width=80, root=root)
        assert [t["frame"] for t in thumbs] == list(range(0, 90, 10))
        assert all(Path(t["path"]).exists() for t in thumbs)
        assert len(ui.get_thumbnails("t", max_thumbs=20, root=root)) <= 20      # automatic spacing
        assert Path(ui.get_frame_path("t", 50, root)).name == "frame_00050.png"

        p = ui.preview_hold("t", 50, 500, root)
        assert p["extra_frames"] == 15 and p["new_total_frames"] == 105 and p["new_duration_s"] == 3.5
        for bad in ((90, 500), (-1, 500), (5, 0), (5, 999999)):
            try:
                ui.preview_hold("t", *bad, root=root)
            except PipelineError:
                continue
            raise AssertionError(f"should be rejected: {bad}")

        # the preview must agree with what really happens
        res = frame_delay.run("t", None, {"holds": [{"frame": 50, "delay_ms": 500}]}, root=root)
        assert res["frames"] == p["new_total_frames"] and read_status(job)["stage"] == "delay"
        out = video_export.run("t", None, {"quality": "preview"}, root=root)
        assert out["status"] == "ok" and read_status(job)["stage"] == "export"
        assert read_status(job)["state"] == "done" and read_status(job)["percent"] == 100

        # thumbnails still show the pre-delay frames after the delay stage exists
        assert len(ui.get_thumbnails("t", every_n=10, width=80, root=root)) == 9

        # a failing stage is reported as failed
        try:
            frame_delay.run("t", None, {"holds": [{"frame": 999, "delay_ms": 500}]}, root=root)
        except PipelineError:
            pass
        assert read_status(job)["state"] == "failed" and "999" in read_status(job)["message"]
        print("  stages + ui helpers OK")
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
