from nps_climate_data.parks import get_parks, get_park, NATIONAL_PARKS


def test_all_63_parks_present():
    parks = get_parks()
    assert len(parks) == 63


def test_slugs_unique():
    slugs = [p["slug"] for p in get_parks()]
    assert len(slugs) == len(set(slugs))


def test_known_parks_lookup():
    y = get_park("yellowstone")
    assert y is not None
    assert y["unit_name"] == "Yellowstone National Park"

    assert get_park("not-a-park") is None


def test_multipart_flags_set():
    saguaro = get_park("saguaro")
    assert saguaro["multipart"] is True
    yellowstone = get_park("yellowstone")
    assert yellowstone["multipart"] is False
