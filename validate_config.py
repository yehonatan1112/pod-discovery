"""
Run this to check your podcasts.yaml before anything else:
    python validate_config.py
"""

import sys
import re
import yaml


YOUTUBE_PATTERNS = [
    r"youtube\.com/playlist\?list=",
    r"youtube\.com/@",
    r"youtube\.com/channel/",
    r"youtube\.com/c/",
    r"youtu\.be/",
]

VALID_FORMATS = {"audio", "video"}


def is_youtube_url(url: str) -> bool:
    return any(re.search(p, url) for p in YOUTUBE_PATTERNS)


def validate(path: str = "podcasts.yaml") -> bool:
    with open(path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    podcasts = config.get("podcasts", [])
    errors = []
    warnings = []
    slugs_seen = set()

    for i, pod in enumerate(podcasts):
        name = pod.get("name", f"[entry #{i}]")
        slug = pod.get("slug", "")
        url = pod.get("url") or ""
        fmt = pod.get("default_format", "")
        active = pod.get("active", True)

        if slug in slugs_seen:
            errors.append(f"{name}: duplicate slug '{slug}'")
        slugs_seen.add(slug)

        if not slug:
            errors.append(f"{name}: missing slug")

        if fmt not in VALID_FORMATS:
            errors.append(f"{name}: default_format must be 'audio' or 'video', got '{fmt}'")

        if active:
            if not url:
                warnings.append(f"{name}: no URL set (will be skipped during scan)")
            elif not is_youtube_url(url):
                errors.append(f"{name}: URL doesn't look like a YouTube URL → {url}")

    ok = not errors
    print(f"\n{'='*50}")
    print(f"Podcasts configured : {len(podcasts)}")
    print(f"Active with URL     : {sum(1 for p in podcasts if p.get('active') and p.get('url'))}")
    print(f"Missing URL         : {sum(1 for p in podcasts if p.get('active') and not p.get('url'))}")
    print(f"{'='*50}\n")

    if warnings:
        print("Warnings:")
        for w in warnings:
            print(f"  ⚠  {w}")
        print()

    if errors:
        print("Errors:")
        for e in errors:
            print(f"  ✗  {e}")
        print()
    else:
        print("  ✓  No errors found\n")

    return ok


if __name__ == "__main__":
    ok = validate()
    sys.exit(0 if ok else 1)
