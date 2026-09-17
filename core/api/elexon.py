from pathlib import Path
import json
import requests


BASE_URL = "https://data.elexon.co.uk/bmrs/api/v1"


def fetch_drm(from_dt: str, to_dt: str) -> dict:
    url = f"{BASE_URL}/forecast/system/loss-of-load"

    params = {
        "from": from_dt,
        "to": to_dt,
        "format": "json",
    }

    response = requests.get(
        url,
        params=params,
        timeout=(5, 30),
    )

    response.raise_for_status()
    return response.json()


def save_raw(data: dict, filename: str) -> None:
    path = Path("data/raw/elexon")
    path.mkdir(parents=True, exist_ok=True)

    with open(path / filename, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=2)


if __name__ == "__main__":
    data = fetch_drm(
        "2026-09-15T00:00Z",
        "2026-09-16T00:00Z",
    )

    print(f"Rows returned: {len(data.get('data', []))}")

    if data.get("data"):
        print(data["data"][0])

    save_raw(data, "drm_test.json")