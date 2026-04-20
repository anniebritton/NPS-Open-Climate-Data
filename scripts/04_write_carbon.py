"""Dump the carbon-footprint estimate to a JSON the site can import."""

import json
from pathlib import Path

from nps_climate_data.carbon import estimate


def main():
    b = estimate()
    out = Path("site/public/data/carbon.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(b.to_dict(), indent=2))
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
