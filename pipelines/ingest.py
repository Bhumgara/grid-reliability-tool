from core.api.elexon import fetch_drm, save_raw
from core.normalise import normalise_elexon_drm


def ingest_drm():
    raw = fetch_drm(
        "2026-09-15T00:00Z",
        "2026-09-16T00:00Z",
    )

    save_raw(raw, "drm_test.json")

    rows = normalise_elexon_drm(raw["data"])

    print(f"Normalised rows: {len(rows)}")


if __name__ == "__main__":
    ingest_drm()