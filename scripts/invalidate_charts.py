"""Invalidate and regenerate all chart views.

Deletes every rendered chart under `music_score_view/` and re-renders them from
the already-extracted score files (no re-download). Run after changing the
chart renderer, or to repair missing/corrupt charts:

    python -m scripts.invalidate_charts            # all regions
    python -m scripts.invalidate_charts en jp      # specific regions
"""

import asyncio
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pjsk_api.asset_handlers.charts import generate_views

DEFAULT_REGIONS = ["en", "jp", "tw", "kr"]


async def main(regions: list[str]) -> None:
    from helpers.config_loader import get_config

    config = get_config()
    s3_base = getattr(config.s3, "base_url", None)

    for region in regions:
        data_path = Path("pjsk_api") / "data" / region
        view_path = data_path / "music_score_view"
        master_path = data_path / "master" / "musics.json"

        if not master_path.exists():
            print(f"[{region}] no masterdata, skipping")
            continue

        if view_path.exists():
            shutil.rmtree(view_path)
            print(f"[{region}] deleted music_score_view")

        musics = json.loads(master_path.read_text(encoding="utf8"))
        count = await generate_views(
            data_path, region, s3_base, musics, padded_ids=None, force=True
        )
        print(f"[{region}] regenerated {count} chart views")


if __name__ == "__main__":
    args = sys.argv[1:]
    asyncio.run(main(args or DEFAULT_REGIONS))
