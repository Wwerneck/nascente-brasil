import json
from pathlib import Path


GEOJSON = Path("dashboard/assets/brazil_states.geojson")


def test_state_geojson_contains_all_federative_units() -> None:
    content = json.loads(GEOJSON.read_text(encoding="utf-8"))
    codes = {feature["properties"]["codarea"] for feature in content["features"]}
    assert content["type"] == "FeatureCollection"
    assert len(content["features"]) == 27
    assert codes == {
        "11", "12", "13", "14", "15", "16", "17", "21", "22", "23", "24", "25", "26",
        "27", "28", "29", "31", "32", "33", "35", "41", "42", "43", "50", "51", "52", "53",
    }
