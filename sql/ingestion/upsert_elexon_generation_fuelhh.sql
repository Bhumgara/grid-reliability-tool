INSERT INTO elexon_generation_fuelhh (
    event_time_utc,
    published_at_utc,
    settlement_date,
    settlement_period,
    fuel_type,
    generation_mw,
    source
)
VALUES (?, ?, ?, ?, ?, ?, ?)

ON CONFLICT (
    event_time_utc,
    fuel_type,
    published_at_utc
)
DO UPDATE SET
    settlement_date = excluded.settlement_date,
    settlement_period = excluded.settlement_period,
    generation_mw = excluded.generation_mw,
    source = excluded.source;