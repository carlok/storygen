# Low-RAM Video Generation: Sequential Segment Encoding

**Date:** 2026-03-11
**Status:** Approved

## Problem

`generate.py` currently holds all N block frames in memory simultaneously while
calling `write_videofile`. At 1920×1080 each numpy frame is ~6 MB; a 10-block
video keeps ~60 MB of frame data live throughout the entire encode, plus moviepy
overhead.

## Solution: Sequential Segment Encoding

Replace the "build all, then write once" pipeline with a "write one, free, repeat"
loop, then use ffmpeg directly for the final concatenation + audio mix.

```
Old: [render_frame × N → clips[] → concatenate → write_videofile]
New: [render_frame → write temp.mp4 → del → repeat] → ffmpeg concat + audio
```

Peak RAM drops from N × ~6 MB to ~6 MB (one frame) + ffmpeg subprocess.

## New Pipeline

1. **Per block:** `render_frame` → `ImageClip` → `clip.write_videofile(tmp.mp4, audio=False)` → `del clip, frame` → `gc.collect()`
2. **Concat list:** write an ffmpeg concat list pointing to all temp segments
3. **Final assembly (ffmpeg subprocess):**
   - No music: `ffmpeg -f concat -safe 0 -i list.txt -fflags +genpts -c:v copy output.mp4`
   - With music: add `-stream_loop -1 -i music.mp3 -map 0:v -map 1:a -c:a aac -t <total_dur>`
4. **Cleanup:** `finally` block deletes all temp files

## Key Properties

- `-c:v copy` stream-copies the already-encoded H264 segments → no re-encode, no quality loss
- `-fflags +genpts` regenerates PTS to avoid discontinuity issues across segments
- `-stream_loop -1` + `-t <total_dur>` replaces moviepy's `audio_loop`
- All temp files have unique names via `tempfile.mkstemp`; cleaned up even on error
- `render_frame()` is unchanged; `build_clip()` is replaced by `build_clip_to_file()`

## Files Changed

- `src/generate.py` — rewrite `main()`, add `build_clip_to_file()`

## What Does Not Change

- `render_frame()` function
- All config fields and semantics
- Output filename logic
- Error propagation to the background worker
