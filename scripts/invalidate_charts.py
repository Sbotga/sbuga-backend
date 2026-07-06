"""Invalidate chart views so the server re-renders and re-uploads them.

Deletes the rendered chart files (svg/png/webp) from the score bundle dirs,
leaving the `.txt` scores. On the next asset cycle the server's chart backfill
(`ensure_charts`) notices they're missing, re-renders them, and re-uploads each
song to R2. Nothing is generated here.

    python -m scripts.invalidate_charts            # all regions
    python -m scripts.invalidate_charts en jp      # specific regions
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

DEFAULT_REGIONS = ["en", "jp"]


def main(regions: list[str]) -> None:
    for region in regions:
        score_root = (
            Path("pjsk_api") / "data" / region / "assets" / "music" / "music_score"
        )
        if not score_root.exists():
            print(f"[{region}] no scores, skipping")
            continue
        deleted = 0
        for ext in ("png", "webp", "svg"):
            for f in score_root.glob(f"*/*.{ext}"):
                f.unlink()
                deleted += 1
        print(f"[{region}] deleted {deleted} chart files")
    print("done. restart sbuga-backend to re-render and re-upload charts.")


if __name__ == "__main__":
    args = sys.argv[1:]
    main(args or DEFAULT_REGIONS)
