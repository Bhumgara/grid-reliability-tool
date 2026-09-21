from datetime import datetime, date


def parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def normalise_elexon_lolpdrm(records):
    return [
        {
            "event_time_utc": parse_utc(row["startTime"]),
            "published_at_utc": parse_utc(row["publishTime"]),
            "forecast_horizon_hours": row["forecastHorizon"],
            "settlement_date": date.fromisoformat(row["settlementDate"]),
            "settlement_period": row["settlementPeriod"],
            "derated_margin_mw": row["deratedMargin"],
            "loss_of_load_probability": row["lossOfLoadProbability"],
            "source": "elexon",
        }
        for row in records
    ]


def normalise_elexon_indo(records):
    return [
        {
            "event_time_utc": parse_utc(row["startTime"]),
            "published_at_utc": parse_utc(row["publishTime"]),
            "settlement_date": date.fromisoformat(
                row["settlementDate"]
            ),
            "settlement_period": row["settlementPeriod"],
            "demand_mw": row["demand"],
            "source": "elexon",
        }
        for row in records
    ]


def normalise_elexon_fuelhh(records):
    return [
        {
            "event_time_utc": parse_utc(row["startTime"]),
            "published_at_utc": parse_utc(row["publishTime"]),
            "settlement_date": date.fromisoformat(
                row["settlementDate"]
            ),
            "settlement_period": row["settlementPeriod"],
            "fuel_type": row["fuelType"],
            "generation_mw": row["generation"],
            "source": "elexon",
        }
        for row in records
    ]


def normalise_neso_generation_mix(records):
    rows = []

    for row in records:
        total = sum(
            item["perc"]
            for item in row["generationmix"]
        )

        if not 99.0 <= total <= 101.0:
            raise ValueError(
                f"Unexpected generation mix total: {total} "
                f"for interval {row['from']} -> {row['to']}"
            )

        mix = {
            item["fuel"]: item["perc"]
            for item in row["generationmix"]
        }

        rows.append(
            {
                "interval_start_utc": parse_utc(row["from"]),
                "interval_end_utc": parse_utc(row["to"]),
                "biomass_pct": mix.get("biomass"),
                "coal_pct": mix.get("coal"),
                "imports_pct": mix.get("imports"),
                "gas_pct": mix.get("gas"),
                "nuclear_pct": mix.get("nuclear"),
                "other_pct": mix.get("other"),
                "hydro_pct": mix.get("hydro"),
                "solar_pct": mix.get("solar"),
                "wind_pct": mix.get("wind"),
                "source": "neso_carbon_intensity",
            }
        )

    return rows