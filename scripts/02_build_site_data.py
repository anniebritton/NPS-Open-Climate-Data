"""Aggregate raw per-park data into JSON summaries for the Astro site."""

import argparse

from nps_climate_data.summarize import build_site_data


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--root", default="data")
    args = p.parse_args()
    build_site_data(args.root)


if __name__ == "__main__":
    main()
