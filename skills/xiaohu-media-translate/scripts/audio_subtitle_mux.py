#!/usr/bin/env python3
"""Create a subtitle-burned MP4 from an audio file plus SRT/ASS subtitles."""

import argparse
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path


SUBTITLE_EXTS = {".ass", ".srt", ".vtt"}


def run(cmd):
    return subprocess.run(cmd, check=True)


HOMEBREW_FFMPEG_FULL = Path("/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg")


def has_ffmpeg_filter(ffmpeg_bin, name):
    result = subprocess.run(
        [ffmpeg_bin, "-hide_banner", "-filters"],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return any(line.split()[1:2] == [name] for line in result.stdout.splitlines())


def pick_ffmpeg(explicit=None):
    candidates = []
    if explicit:
        candidates.append(explicit)
    if os.environ.get("FFMPEG_BIN"):
        candidates.append(os.environ["FFMPEG_BIN"])
    if HOMEBREW_FFMPEG_FULL.exists():
        candidates.append(str(HOMEBREW_FFMPEG_FULL))
    if shutil.which("ffmpeg"):
        candidates.append(shutil.which("ffmpeg"))

    seen = set()
    for candidate in candidates:
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        if shutil.which(candidate) or Path(candidate).exists():
            return candidate
    raise SystemExit("ffmpeg not found. Install ffmpeg or set FFMPEG_BIN=/path/to/ffmpeg")


def require_ffmpeg_filter(ffmpeg_bin, name, message):
    if not has_ffmpeg_filter(ffmpeg_bin, name):
        raise SystemExit(f"ffmpeg filter not found: {name}. {message}")


def ffmpeg_escape_filter_path(path):
    value = str(Path(path).expanduser().resolve())
    return value.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")


def ffmpeg_escape_text(text):
    return text.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")


def subtitle_filter(subtitle_path, ffmpeg_bin):
    path = Path(subtitle_path)
    escaped = ffmpeg_escape_filter_path(path)
    if path.suffix.lower() == ".ass":
        require_ffmpeg_filter(ffmpeg_bin, "ass", "ASS subtitle burn-in requires ffmpeg with libass, e.g. brew install ffmpeg-full and use --ffmpeg /opt/homebrew/opt/ffmpeg-full/bin/ffmpeg")
        return f"ass=filename='{escaped}'"
    require_ffmpeg_filter(ffmpeg_bin, "subtitles", "SRT/VTT subtitle burn-in requires ffmpeg with libass, e.g. brew install ffmpeg-full and use --ffmpeg /opt/homebrew/opt/ffmpeg-full/bin/ffmpeg")
    return (
        f"subtitles=filename='{escaped}':force_style="
        "'FontName=PingFang SC,Bold=1,FontSize=28,"
        "PrimaryColour=&H00FFFFFF,OutlineColour=&H64000000,"
        "Outline=1.2,Shadow=0,MarginV=56'"
    )


def build_background_args(args):
    size = args.size
    fps = str(args.fps)
    if args.cover:
        cover = Path(args.cover).expanduser()
        if not cover.exists():
            raise SystemExit(f"cover not found: {cover}")
        return [
            "-loop",
            "1",
            "-framerate",
            fps,
            "-i",
            str(cover),
        ], f"scale={size}:force_original_aspect_ratio=decrease,pad={size}:(ow-iw)/2:(oh-ih)/2:color={args.background}"

    return [
        "-f",
        "lavfi",
        "-i",
        f"color=c={args.background}:s={size}:r={fps}",
    ], None


def main():
    parser = argparse.ArgumentParser(
        description="Merge audio and SRT/ASS subtitles into a shareable MP4 with burned subtitles."
    )
    parser.add_argument("audio", help="Input audio path, e.g. mp3/m4a/wav/flac")
    parser.add_argument("subtitle", help="Input subtitle path, preferably bilingual ASS")
    parser.add_argument("--output", "-o", required=True, help="Output MP4 path")
    parser.add_argument("--title", default=None, help="Optional title drawn near the top")
    parser.add_argument("--cover", help="Optional still image used as the background")
    parser.add_argument("--size", default="1920x1080", help="Video size, default 1920x1080")
    parser.add_argument("--fps", type=int, default=30, help="Video frame rate, default 30")
    parser.add_argument("--background", default="black", help="Background color when no cover is supplied")
    parser.add_argument("--crf", type=int, default=23, help="libx264 CRF, default 23")
    parser.add_argument("--preset", default="veryfast", help="libx264 preset, default veryfast")
    parser.add_argument("--ffmpeg", help="ffmpeg binary path; also supports FFMPEG_BIN env var")
    args = parser.parse_args()

    ffmpeg_bin = pick_ffmpeg(args.ffmpeg)

    audio = Path(args.audio).expanduser()
    subtitle = Path(args.subtitle).expanduser()
    output = Path(args.output).expanduser()

    if not audio.exists():
        raise SystemExit(f"audio not found: {audio}")
    if not subtitle.exists():
        raise SystemExit(f"subtitle not found: {subtitle}")
    if subtitle.suffix.lower() not in SUBTITLE_EXTS:
        raise SystemExit(f"unsupported subtitle type: {subtitle.suffix}")

    output.parent.mkdir(parents=True, exist_ok=True)
    bg_args, bg_filter = build_background_args(args)
    filters = []
    if bg_filter:
        filters.append(bg_filter)
    if args.title and has_ffmpeg_filter(ffmpeg_bin, "drawtext"):
        title = ffmpeg_escape_text(args.title)
        filters.append(
            "drawtext="
            f"text='{title}':fontcolor=white@0.86:fontsize=44:"
            "x=(w-text_w)/2:y=72:box=1:boxcolor=black@0.35:boxborderw=18"
        )
    elif args.title:
        print("warning: ffmpeg drawtext filter is unavailable; skipping title overlay", file=sys.stderr)
    filters.append(subtitle_filter(subtitle, ffmpeg_bin))

    cmd = [
        ffmpeg_bin,
        "-y",
        *bg_args,
        "-i",
        str(audio),
        "-vf",
        ",".join(filters),
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-preset",
        args.preset,
        "-crf",
        str(args.crf),
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-shortest",
        "-movflags",
        "+faststart",
        str(output),
    ]
    print("Running:", " ".join(shlex.quote(x) for x in cmd), file=sys.stderr)
    run(cmd)


if __name__ == "__main__":
    main()
