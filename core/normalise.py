from datetime import datetime, date


def parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def normalise_elexon_drm(records):
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

def normalise_elexon_demand(records):
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