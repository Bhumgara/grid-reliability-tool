INSERT INTO neso_generation_mix (
    interval_start_utc,
    interval_end_utc,
    biomass_pct,
    coal_pct,
    imports_pct,
    gas_pct,
    nuclear_pct,
    other_pct,
    hydro_pct,
    solar_pct,
    wind_pct,
    source
)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)

ON CONFLICT (interval_start_utc)
DO UPDATE SET
    interval_end_utc = excluded.interval_end_utc,
    biomass_pct = excluded.biomass_pct,
    coal_pct = excluded.coal_pct,
    imports_pct = excluded.imports_pct,
    gas_pct = excluded.gas_pct,
    nuclear_pct = excluded.nuclear_pct,
    other_pct = excluded.other_pct,
    hydro_pct = excluded.hydro_pct,
    solar_pct = excluded.solar_pct,
    wind_pct = excluded.wind_pct,
    source = excluded.source;