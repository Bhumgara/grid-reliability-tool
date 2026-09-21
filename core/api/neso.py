from pathlib import Path
import json
import requests


BASE_URL = "https://api.carbonintensity.org.uk"


def fetch_generation_mix(from_dt: str, to_dt: str) -> dict:
    url = f"{BASE_URL}/generation/{from_dt}/{to_dt}"

    response = requests.get(
        url,
        timeout=(5, 30),
    )

    response.raise_for_status()
    return response.json()

def save_raw_neso(data: dict, filename: str) -> None:
    path = Path("data/raw/neso")
    path.mkdir(parents=True, exist_ok=True)

    filename = filename if filename.endswith(".json") else f"{filename}.json"
    filename = filename.replace(":", "-")

    with open(path / filename, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=2)



if __name__ == "__main__":
    data = fetch_generation_mix(
        "2026-09-01T00:00Z",
        "2026-09-02T00:00Z",
    )

    print(f"Rows returned: {len(data.get('data', []))}")

    if data.get("data"):
        print(data["data"][0])

    save_raw_neso(data, "neso_test.json")

    