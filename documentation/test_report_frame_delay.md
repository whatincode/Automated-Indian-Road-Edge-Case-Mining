# Frame delay test report (checklist 12.2)

- Date: 2026-11-20 20:08
- Videos: test_10s.mp4, test_24fps_1080p.mp4, test_25fps.mp4
- Each video cut to the first 6 s
- Working width: 1280; export quality: final
- Machine: Windows 11, Python 3.14.6, OpenCV 5.1.0

**Result: 84 checks passed, 0 failed.**

| Video | FPS | Frames | Scenarios | Checks passed | Checks failed |
|---|---|---|---|---|---|
| test_10s.mp4 | 30.0 | 180 | 4 | 28 | 0 |
| test_24fps_1080p.mp4 | 24.0 | 144 | 4 | 28 | 0 |
| test_25fps.mp4 | 25.0 | 150 | 4 | 28 | 0 |

## test_10s.mp4

original size: 1280x720; frames tested at: 1280x720; fps: 30.0; frames: 180; duration (s): 6.0; audio: yes; converted from VFR: False

### S1  500 ms on the middle frame (brief example)

Holds: frame 90 for 500 ms

| Check | Result | What was measured |
|---|---|---|
| 1. Correct selected frame | PASS | every output frame is the expected source frame |
| 2. Correct delay duration (within 1 frame = 33.3 ms) | PASS | frame 90: asked 500 ms, got 500.0 ms |
| 3. Correct number of duplicated frames | PASS | frame 90: 15 duplicates (formula: 15) |
| 4. Correct output FPS | PASS | input 30.000 FPS, final.mp4 30.000 FPS |
| 5. Correct total duration | PASS | 180 + 15 extra = 195 frames expected, final.mp4 has 195; duration 6.500 s (expected 6.500 s) |
| 6. Audio synchronisation | PASS | audio 6.500 s / video 6.500 s; frame 90: 500 ms silence inserted |
| +  Hold visible in final.mp4 | PASS | decoded 195 frames; largest mean pixel difference inside a hold = 0.07 (of 255) |

### S2  100 ms (needs rounding)

Holds: frame 45 for 100 ms

| Check | Result | What was measured |
|---|---|---|
| 1. Correct selected frame | PASS | every output frame is the expected source frame |
| 2. Correct delay duration (within 1 frame = 33.3 ms) | PASS | frame 45: asked 100 ms, got 100.0 ms |
| 3. Correct number of duplicated frames | PASS | frame 45: 3 duplicates (formula: 3) |
| 4. Correct output FPS | PASS | input 30.000 FPS, final.mp4 30.000 FPS |
| 5. Correct total duration | PASS | 180 + 3 extra = 183 frames expected, final.mp4 has 183; duration 6.100 s (expected 6.100 s) |
| 6. Audio synchronisation | PASS | audio 6.100 s / video 6.100 s; frame 45: 100 ms silence inserted |
| +  Hold visible in final.mp4 | PASS | decoded 183 frames; largest mean pixel difference inside a hold = 0.06 (of 255) |

### S3  two holds at once (300 ms + 1000 ms, given out of order)

Holds: frame 135 for 1000 ms, frame 45 for 300 ms

| Check | Result | What was measured |
|---|---|---|
| 1. Correct selected frame | PASS | every output frame is the expected source frame |
| 2. Correct delay duration (within 1 frame = 33.3 ms) | PASS | frame 45: asked 300 ms, got 300.0 ms; frame 135: asked 1000 ms, got 1000.0 ms |
| 3. Correct number of duplicated frames | PASS | frame 45: 9 duplicates (formula: 9); frame 135: 30 duplicates (formula: 30) |
| 4. Correct output FPS | PASS | input 30.000 FPS, final.mp4 30.000 FPS |
| 5. Correct total duration | PASS | 180 + 39 extra = 219 frames expected, final.mp4 has 219; duration 7.300 s (expected 7.300 s) |
| 6. Audio synchronisation | PASS | audio 7.300 s / video 7.300 s; frame 45: 300 ms silence inserted; frame 135: 1000 ms silence inserted |
| +  Hold visible in final.mp4 | PASS | decoded 219 frames; largest mean pixel difference inside a hold = 0.06 (of 255) |

### S4  first frame (200 ms) and last frame (200 ms)

Holds: frame 0 for 200 ms, frame 179 for 200 ms

| Check | Result | What was measured |
|---|---|---|
| 1. Correct selected frame | PASS | every output frame is the expected source frame |
| 2. Correct delay duration (within 1 frame = 33.3 ms) | PASS | frame 0: asked 200 ms, got 200.0 ms; frame 179: asked 200 ms, got 200.0 ms |
| 3. Correct number of duplicated frames | PASS | frame 0: 6 duplicates (formula: 6); frame 179: 6 duplicates (formula: 6) |
| 4. Correct output FPS | PASS | input 30.000 FPS, final.mp4 30.000 FPS |
| 5. Correct total duration | PASS | 180 + 12 extra = 192 frames expected, final.mp4 has 192; duration 6.400 s (expected 6.400 s) |
| 6. Audio synchronisation | PASS | audio 6.400 s / video 6.400 s; frame 0: 200 ms silence inserted; frame 179: 200 ms silence inserted |
| +  Hold visible in final.mp4 | PASS | decoded 192 frames; largest mean pixel difference inside a hold = 0.02 (of 255) |


## test_24fps_1080p.mp4

original size: 1920x1080; frames tested at: 1280x720; fps: 24.0; frames: 144; duration (s): 6.0; audio: yes; converted from VFR: False

### S1  500 ms on the middle frame (brief example)

Holds: frame 72 for 500 ms

| Check | Result | What was measured |
|---|---|---|
| 1. Correct selected frame | PASS | every output frame is the expected source frame |
| 2. Correct delay duration (within 1 frame = 41.7 ms) | PASS | frame 72: asked 500 ms, got 500.0 ms |
| 3. Correct number of duplicated frames | PASS | frame 72: 12 duplicates (formula: 12) |
| 4. Correct output FPS | PASS | input 24.000 FPS, final.mp4 24.000 FPS |
| 5. Correct total duration | PASS | 144 + 12 extra = 156 frames expected, final.mp4 has 156; duration 6.500 s (expected 6.500 s) |
| 6. Audio synchronisation | PASS | audio 6.500 s / video 6.500 s; frame 72: 500 ms silence inserted |
| +  Hold visible in final.mp4 | PASS | decoded 156 frames; largest mean pixel difference inside a hold = 0.05 (of 255) |

### S2  100 ms (needs rounding)

Holds: frame 36 for 100 ms

| Check | Result | What was measured |
|---|---|---|
| 1. Correct selected frame | PASS | every output frame is the expected source frame |
| 2. Correct delay duration (within 1 frame = 41.7 ms) | PASS | frame 36: asked 100 ms, got 83.3 ms |
| 3. Correct number of duplicated frames | PASS | frame 36: 2 duplicates (formula: 2) |
| 4. Correct output FPS | PASS | input 24.000 FPS, final.mp4 24.000 FPS |
| 5. Correct total duration | PASS | 144 + 2 extra = 146 frames expected, final.mp4 has 146; duration 6.083 s (expected 6.083 s) |
| 6. Audio synchronisation | PASS | audio 6.083 s / video 6.083 s; frame 36: 83 ms silence inserted |
| +  Hold visible in final.mp4 | PASS | decoded 146 frames; largest mean pixel difference inside a hold = 0.02 (of 255) |

### S3  two holds at once (300 ms + 1000 ms, given out of order)

Holds: frame 108 for 1000 ms, frame 36 for 300 ms

| Check | Result | What was measured |
|---|---|---|
| 1. Correct selected frame | PASS | every output frame is the expected source frame |
| 2. Correct delay duration (within 1 frame = 41.7 ms) | PASS | frame 36: asked 300 ms, got 291.7 ms; frame 108: asked 1000 ms, got 1000.0 ms |
| 3. Correct number of duplicated frames | PASS | frame 36: 7 duplicates (formula: 7); frame 108: 24 duplicates (formula: 24) |
| 4. Correct output FPS | PASS | input 24.000 FPS, final.mp4 24.000 FPS |
| 5. Correct total duration | PASS | 144 + 31 extra = 175 frames expected, final.mp4 has 175; duration 7.292 s (expected 7.292 s) |
| 6. Audio synchronisation | PASS | audio 7.292 s / video 7.292 s; frame 36: 292 ms silence inserted; frame 108: 1000 ms silence inserted |
| +  Hold visible in final.mp4 | PASS | decoded 175 frames; largest mean pixel difference inside a hold = 0.06 (of 255) |

### S4  first frame (200 ms) and last frame (200 ms)

Holds: frame 0 for 200 ms, frame 143 for 200 ms

| Check | Result | What was measured |
|---|---|---|
| 1. Correct selected frame | PASS | every output frame is the expected source frame |
| 2. Correct delay duration (within 1 frame = 41.7 ms) | PASS | frame 0: asked 200 ms, got 208.3 ms; frame 143: asked 200 ms, got 208.3 ms |
| 3. Correct number of duplicated frames | PASS | frame 0: 5 duplicates (formula: 5); frame 143: 5 duplicates (formula: 5) |
| 4. Correct output FPS | PASS | input 24.000 FPS, final.mp4 24.000 FPS |
| 5. Correct total duration | PASS | 144 + 10 extra = 154 frames expected, final.mp4 has 154; duration 6.417 s (expected 6.417 s) |
| 6. Audio synchronisation | PASS | audio 6.417 s / video 6.417 s; frame 0: 208 ms silence inserted; frame 143: 208 ms silence inserted |
| +  Hold visible in final.mp4 | PASS | decoded 154 frames; largest mean pixel difference inside a hold = 0.04 (of 255) |


## test_25fps.mp4

original size: 1280x720; frames tested at: 1280x720; fps: 25.0; frames: 150; duration (s): 6.0; audio: yes; converted from VFR: False

### S1  500 ms on the middle frame (brief example)

Holds: frame 75 for 500 ms

| Check | Result | What was measured |
|---|---|---|
| 1. Correct selected frame | PASS | every output frame is the expected source frame |
| 2. Correct delay duration (within 1 frame = 40.0 ms) | PASS | frame 75: asked 500 ms, got 520.0 ms |
| 3. Correct number of duplicated frames | PASS | frame 75: 13 duplicates (formula: 13) |
| 4. Correct output FPS | PASS | input 25.000 FPS, final.mp4 25.000 FPS |
| 5. Correct total duration | PASS | 150 + 13 extra = 163 frames expected, final.mp4 has 163; duration 6.520 s (expected 6.520 s) |
| 6. Audio synchronisation | PASS | audio 6.520 s / video 6.520 s; frame 75: 520 ms silence inserted |
| +  Hold visible in final.mp4 | PASS | decoded 163 frames; largest mean pixel difference inside a hold = 0.07 (of 255) |

### S2  100 ms (needs rounding)

Holds: frame 37 for 100 ms

| Check | Result | What was measured |
|---|---|---|
| 1. Correct selected frame | PASS | every output frame is the expected source frame |
| 2. Correct delay duration (within 1 frame = 40.0 ms) | PASS | frame 37: asked 100 ms, got 120.0 ms |
| 3. Correct number of duplicated frames | PASS | frame 37: 3 duplicates (formula: 3) |
| 4. Correct output FPS | PASS | input 25.000 FPS, final.mp4 25.000 FPS |
| 5. Correct total duration | PASS | 150 + 3 extra = 153 frames expected, final.mp4 has 153; duration 6.120 s (expected 6.120 s) |
| 6. Audio synchronisation | PASS | audio 6.120 s / video 6.120 s; frame 37: 120 ms silence inserted |
| +  Hold visible in final.mp4 | PASS | decoded 153 frames; largest mean pixel difference inside a hold = 0.04 (of 255) |

### S3  two holds at once (300 ms + 1000 ms, given out of order)

Holds: frame 112 for 1000 ms, frame 37 for 300 ms

| Check | Result | What was measured |
|---|---|---|
| 1. Correct selected frame | PASS | every output frame is the expected source frame |
| 2. Correct delay duration (within 1 frame = 40.0 ms) | PASS | frame 37: asked 300 ms, got 320.0 ms; frame 112: asked 1000 ms, got 1000.0 ms |
| 3. Correct number of duplicated frames | PASS | frame 37: 8 duplicates (formula: 8); frame 112: 25 duplicates (formula: 25) |
| 4. Correct output FPS | PASS | input 25.000 FPS, final.mp4 25.000 FPS |
| 5. Correct total duration | PASS | 150 + 33 extra = 183 frames expected, final.mp4 has 183; duration 7.320 s (expected 7.320 s) |
| 6. Audio synchronisation | PASS | audio 7.320 s / video 7.320 s; frame 37: 320 ms silence inserted; frame 112: 1000 ms silence inserted |
| +  Hold visible in final.mp4 | PASS | decoded 183 frames; largest mean pixel difference inside a hold = 0.06 (of 255) |

### S4  first frame (200 ms) and last frame (200 ms)

Holds: frame 0 for 200 ms, frame 149 for 200 ms

| Check | Result | What was measured |
|---|---|---|
| 1. Correct selected frame | PASS | every output frame is the expected source frame |
| 2. Correct delay duration (within 1 frame = 40.0 ms) | PASS | frame 0: asked 200 ms, got 200.0 ms; frame 149: asked 200 ms, got 200.0 ms |
| 3. Correct number of duplicated frames | PASS | frame 0: 5 duplicates (formula: 5); frame 149: 5 duplicates (formula: 5) |
| 4. Correct output FPS | PASS | input 25.000 FPS, final.mp4 25.000 FPS |
| 5. Correct total duration | PASS | 150 + 10 extra = 160 frames expected, final.mp4 has 160; duration 6.400 s (expected 6.400 s) |
| 6. Audio synchronisation | PASS | audio 6.400 s / video 6.400 s; frame 0: 200 ms silence inserted; frame 149: 200 ms silence inserted |
| +  Hold visible in final.mp4 | PASS | decoded 160 frames; largest mean pixel difference inside a hold = 0.02 (of 255) |


## How the checks work

- Frames are compared by SHA-256 of the PNG files, against an expected sequence that this script builds on its own (not by calling the code under test).
- Video length, FPS and frame count come from ffprobe on the exported `final.mp4`.
- Audio is compared sample by sample: silence exactly during each hold, unchanged before it, and the original sound moved later by the hold length after it.