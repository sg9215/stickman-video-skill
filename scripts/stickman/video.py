"""Video encoding — streams rendered frames into ffmpeg (H.264 MP4)."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from typing import Callable, List, Optional


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def encode_frames(frame_iter, out_path: str, width: int, height: int, fps: int,
                  total_frames: Optional[int] = None,
                  crf: int = 18, preset: str = "medium",
                  audio_path: Optional[str] = None,
                  progress: Optional[Callable] = None) -> str:
    """Pipe RGB frames into ffmpeg and produce an H.264 MP4.

    ``frame_iter`` yields PIL RGB images of exactly width x height.
    """
    if not ffmpeg_available():
        raise RuntimeError("ffmpeg not found on PATH; install ffmpeg to render video")
    cmd = ["ffmpeg", "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{width}x{height}", "-r", str(fps), "-i", "-"]
    if audio_path:
        cmd += ["-i", audio_path, "-c:a", "aac", "-b:a", "192k", "-shortest"]
    cmd += ["-c:v", "libx264", "-preset", preset, "-crf", str(crf),
            "-pix_fmt", "yuv420p", "-movflags", "+faststart", out_path]
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    n = 0
    try:
        for img in frame_iter:
            if img.size != (width, height):
                img = img.resize((width, height), Image_LANCZOS)
            proc.stdin.write(img.tobytes())
            n += 1
            if progress and total_frames and n % max(1, total_frames // 20) == 0:
                progress(n, total_frames)
        proc.stdin.close()
        proc.wait()
    except BrokenPipeError:
        err = proc.stderr.read().decode(errors="replace")
        raise RuntimeError(f"ffmpeg failed: {err}")
    if proc.returncode != 0:
        err = proc.stderr.read().decode(errors="replace") if proc.stderr else ""
        raise RuntimeError(f"ffmpeg exited {proc.returncode}: {err}")
    if progress:
        progress(n, n or 1)
    return out_path


from PIL import Image as _PILImage
Image_LANCZOS = _PILImage.LANCZOS


def concat_videos(paths: List[str], out_path: str) -> str:
    """Concatenate same-codec MP4s with the concat demuxer (stream copy)."""
    if len(paths) == 1:
        shutil.copyfile(paths[0], out_path)
        return out_path
    list_file = out_path + ".concat.txt"
    with open(list_file, "w") as f:
        for p in paths:
            f.write(f"file '{os.path.abspath(p)}'\n")
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "concat",
           "-safe", "0", "-i", list_file, "-c", "copy", out_path]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    os.remove(list_file)
    return out_path


def probe_duration(path: str) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True)
    try:
        return float(out.stdout.strip())
    except ValueError:
        return 0.0
