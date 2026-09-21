CREATE TABLE IF NOT EXISTS elexon_margin (
    event_time_utc TEXT NOT NULL,
    published_at_utc TEXT NOT NULL,
    forecast_horizon_hours INTEGER NOT NULL,
    settlement_date TEXT NOT NULL,
    settlement_period INTEGER NOT NULL,
    derated_margin_mw REAL,
    loss_of_load_probability REAL,
    source TEXT NOT NULL,

    PRIMARY KEY (
        event_time_utc,
        forecast_horizon_hours
    )
);

CREATE TABLE IF NOT EXISTS elexon_demand (
    event_time_utc TEXT NOT NULL,
    published_at_utc TEXT NOT NULL,
    settlement_date TEXT NOT NULL,
    settlement_period INTEGER NOT NULL,
    demand_mw REAL NOT NULL,
    source TEXT NOT NULL,

    PRIMARY KEY (
        event_time_utc,
        published_at_utc
    )
);

CREATE TABLE IF NOT EXISTS neso_generation_mix (
    interval_start_utc TEXT NOT NULL,
    interval_end_utc TEXT NOT NULL,
    biomass_pct REAL,
    coal_pct REAL,
    imports_pct REAL,
    gas_pct REAL,
    nuclear_pct REAL,
    other_pct REAL,
    hydro_pct REAL,
    solar_pct REAL,
    wind_pct REAL,
    source TEXT NOT NULL,

    PRIMARY KEY (interval_start_utc)
);
