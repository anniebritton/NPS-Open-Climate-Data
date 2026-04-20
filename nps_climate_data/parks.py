"""
Registry of the 63 designated US National Parks.

Each entry is (unit_name, state_code, slug). `unit_name` matches PAD-US
`Unit_Nm`. Parks with disjoint geometries (multipart units) are split
downstream via `split_multipart_features` so each polygon gets its own
time series while still being grouped under the parent park.
"""

from __future__ import annotations

NATIONAL_PARKS: list[tuple[str, str, str]] = [
    ("Acadia National Park", "ME", "acadia"),
    ("National Park of American Samoa", "AS", "american-samoa"),
    ("Arches National Park", "UT", "arches"),
    ("Badlands National Park", "SD", "badlands"),
    ("Big Bend National Park", "TX", "big-bend"),
    ("Biscayne National Park", "FL", "biscayne"),
    ("Black Canyon of the Gunnison National Park", "CO", "black-canyon-of-the-gunnison"),
    ("Bryce Canyon National Park", "UT", "bryce-canyon"),
    ("Canyonlands National Park", "UT", "canyonlands"),
    ("Capitol Reef National Park", "UT", "capitol-reef"),
    ("Carlsbad Caverns National Park", "NM", "carlsbad-caverns"),
    ("Channel Islands National Park", "CA", "channel-islands"),
    ("Congaree National Park", "SC", "congaree"),
    ("Crater Lake National Park", "OR", "crater-lake"),
    ("Cuyahoga Valley National Park", "OH", "cuyahoga-valley"),
    ("Death Valley National Park", "CA,NV", "death-valley"),
    ("Denali National Park", "AK", "denali"),
    ("Dry Tortugas National Park", "FL", "dry-tortugas"),
    ("Everglades National Park", "FL", "everglades"),
    ("Gates of the Arctic National Park", "AK", "gates-of-the-arctic"),
    ("Gateway Arch National Park", "MO", "gateway-arch"),
    ("Glacier National Park", "MT", "glacier"),
    ("Glacier Bay National Park", "AK", "glacier-bay"),
    ("Grand Canyon National Park", "AZ", "grand-canyon"),
    ("Grand Teton National Park", "WY", "grand-teton"),
    ("Great Basin National Park", "NV", "great-basin"),
    ("Great Sand Dunes National Park", "CO", "great-sand-dunes"),
    ("Great Smoky Mountains National Park", "TN,NC", "great-smoky-mountains"),
    ("Guadalupe Mountains National Park", "TX", "guadalupe-mountains"),
    ("Haleakala National Park", "HI", "haleakala"),
    ("Hawaii Volcanoes National Park", "HI", "hawaii-volcanoes"),
    ("Hot Springs National Park", "AR", "hot-springs"),
    ("Indiana Dunes National Park", "IN", "indiana-dunes"),
    ("Isle Royale National Park", "MI", "isle-royale"),
    ("Joshua Tree National Park", "CA", "joshua-tree"),
    ("Katmai National Park", "AK", "katmai"),
    ("Kenai Fjords National Park", "AK", "kenai-fjords"),
    ("Kings Canyon National Park", "CA", "kings-canyon"),
    ("Kobuk Valley National Park", "AK", "kobuk-valley"),
    ("Lake Clark National Park", "AK", "lake-clark"),
    ("Lassen Volcanic National Park", "CA", "lassen-volcanic"),
    ("Mammoth Cave National Park", "KY", "mammoth-cave"),
    ("Mesa Verde National Park", "CO", "mesa-verde"),
    ("Mount Rainier National Park", "WA", "mount-rainier"),
    ("New River Gorge National Park", "WV", "new-river-gorge"),
    ("North Cascades National Park", "WA", "north-cascades"),
    ("Olympic National Park", "WA", "olympic"),
    ("Petrified Forest National Park", "AZ", "petrified-forest"),
    ("Pinnacles National Park", "CA", "pinnacles"),
    ("Redwood National Park", "CA", "redwood"),
    ("Rocky Mountain National Park", "CO", "rocky-mountain"),
    ("Saguaro National Park", "AZ", "saguaro"),
    ("Sequoia National Park", "CA", "sequoia"),
    ("Shenandoah National Park", "VA", "shenandoah"),
    ("Theodore Roosevelt National Park", "ND", "theodore-roosevelt"),
    ("Virgin Islands National Park", "VI", "virgin-islands"),
    ("Voyageurs National Park", "MN", "voyageurs"),
    ("White Sands National Park", "NM", "white-sands"),
    ("Wind Cave National Park", "SD", "wind-cave"),
    ("Wrangell-St. Elias National Park", "AK", "wrangell-st-elias"),
    ("Yellowstone National Park", "WY,MT,ID", "yellowstone"),
    ("Yosemite National Park", "CA", "yosemite"),
    ("Zion National Park", "UT", "zion"),
]

# Parks that are known to have geographically disjoint units in PAD-US and
# should be split rather than unioned. Values are human-readable sub-unit
# labels keyed by a stable slug suffix; actual geometry splitting happens
# via connected-component analysis in `split_multipart_features`.
MULTIPART_PARKS: dict[str, list[str]] = {
    "saguaro": ["Rincon Mountain District", "Tucson Mountain District"],
    "channel-islands": [
        "Santa Cruz Island",
        "Santa Rosa Island",
        "San Miguel Island",
        "Anacapa Island",
        "Santa Barbara Island",
    ],
    "kings-canyon": ["Main Unit", "Grant Grove"],
    "redwood": ["Main Unit"],
    "american-samoa": ["Tutuila Unit", "Taʻū Unit", "Ofu Unit"],
    "virgin-islands": ["Main Unit"],
    "dry-tortugas": ["Main Unit"],
    "congaree": ["Main Unit"],
    "gulf-islands": ["Florida District", "Mississippi District"],
}


def get_parks() -> list[dict]:
    """Return all 63 national parks as a list of dicts."""
    return [
        {"unit_name": n, "state": s, "slug": slug, "multipart": slug in MULTIPART_PARKS}
        for n, s, slug in NATIONAL_PARKS
    ]


def get_park(slug: str) -> dict | None:
    for p in get_parks():
        if p["slug"] == slug:
            return p
    return None
