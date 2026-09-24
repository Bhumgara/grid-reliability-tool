INSERT INTO neso_demand_update (
    settlement_date,
    settlement_period,
    forecast_actual_indicator,
    embedded_wind_mw,
    embedded_solar_mw,
    pump_storage_pumping_mw,
    source
)
VALUES (?, ?, ?, ?, ?, ?, ?)

ON CONFLICT (
    settlement_date,
    settlement_period,
    forecast_actual_indicator
)
DO UPDATE SET
    embedded_wind_mw =
        excluded.embedded_wind_mw,
    embedded_solar_mw =
        excluded.embedded_solar_mw,
    pump_storage_pumping_mw =
        excluded.pump_storage_pumping_mw,
    source =
        excluded.source;