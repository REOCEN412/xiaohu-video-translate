#!/usr/bin/env python3
"""Find local audio/video files for uploaded or fuzzy media requests."""

import argparse
import json
import os
import sys
import time
from pathlib import Path


AUDIO_EXTS = {".mp3", ".m4a", ".wav", ".aac", ".flac", ".ogg", ".opus", ".wma"}
VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v", ".flv", ".wmv"}
SKIP_DIRS = {
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    "Library",
    ".cache",
    ".Trash",
}


def default_roots():
    home = Path.home()
    roots = [Path.cwd(), home / "Downloads", home / "Desktop", home / "Documents", Path("/tmp")]
    seen = set()
    out = []
    for root in roots:
        try:
            resolved = root.expanduser().resolve()
        except OSError:
            continue
        if resolved.exists() and resolved not in seen:
            seen.add(resolved)
            out.append(resolved)
    return out


def iter_files(root, exts, max_depth):
    root = Path(root).expanduser()
    if not root.exists():
        return
    base_depth = len(root.parts)
    for dirpath, dirnames, filenames in os.walk(root):
        current = Path(dirpath)
        depth = len(current.parts) - base_depth
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        if max_depth is not None and depth >= max_depth:
            dirnames[:] = []
        for name in filenames:
            path = current / name
            if path.suffix.lower() in exts:
                yield path


def score(path, query_terms, cwd):
    name = path.name.lower()
    full = str(path).lower()
    value = 0
    for term in query_terms:
        if term in name:
            value += 20
        elif term in full:
            value += 8
    try:
        if cwd in path.resolve().parents or path.resolve() == cwd:
            value += 10
    except OSError:
        pass
    try:
        age_hours = max(0, (time.time() - path.stat().st_mtime) / 3600)
        value += max(0, 12 - min(12, age_hours / 24))
        value += min(10, path.stat().st_size / (1024 * 1024 * 100))
    except OSError:
        pass
    return value


def main():
    parser = argparse.ArgumentParser(description="Search common local folders for audio/video files.")
    parser.add_argument("query", nargs="*", help="Optional filename/title keywords")
    parser.add_argument("--root", action="append", default=[], help="Additional search root; can be repeated")
    parser.add_argument("--kind", choices=["all", "audio", "video"], default="all")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--recent", type=float, help="Only include files modified within N days")
    parser.add_argument("--max-depth", type=int, default=6)
    parser.add_argument("--json", action="store_true", help="Emit JSON")
    args = parser.parse_args()

    if args.kind == "audio":
        exts = AUDIO_EXTS
    elif args.kind == "video":
        exts = VIDEO_EXTS
    else:
        exts = AUDIO_EXTS | VIDEO_EXTS

    roots = default_roots() + [Path(r).expanduser() for r in args.root]
    query_terms = [q.lower() for q in " ".join(args.query).split() if q.strip()]
    min_mtime = time.time() - args.recent * 86400 if args.recent else None
    cwd = Path.cwd().resolve()

    matches = {}
    for root in roots:
        for path in iter_files(root, exts, args.max_depth):
            try:
                stat = path.stat()
            except OSError:
                continue
            if min_mtime and stat.st_mtime < min_mtime:
                continue
            if query_terms and not all(term in str(path).lower() for term in query_terms):
                continue
            resolved = str(path.resolve())
            matches[resolved] = {
                "path": resolved,
                "name": path.name,
                "kind": "audio" if path.suffix.lower() in AUDIO_EXTS else "video",
                "size_mb": round(stat.st_size / 1024 / 1024, 2),
                "modified": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stat.st_mtime)),
                "score": score(path, query_terms, cwd),
            }

    results = sorted(matches.values(), key=lambda item: (-item["score"], item["path"]))[: args.limit]
    if args.json:
        json.dump(results, sys.stdout, ensure_ascii=False, indent=2)
        print()
        return

    if not results:
        print("No media files found.")
        return
    for idx, item in enumerate(results, 1):
        print(
            f"{idx:2d}. [{item['kind']}] {item['path']} "
            f"({item['size_mb']} MB, modified {item['modified']})"
        )


if __name__ == "__main__":
    main()
