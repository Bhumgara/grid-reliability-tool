INSERT INTO elexon_demand (
    event_time_utc,
    published_at_utc,
    settlement_date,
    settlement_period,
    demand_mw,
    source
)
VALUES (?, ?, ?, ?, ?, ?)

ON CONFLICT (
    event_time_utc,
    published_at_utc
)
DO UPDATE SET
    settlement_date = excluded.settlement_date,
    settlement_period = excluded.settlement_period,
    demand_mw = excluded.demand_mw,
    source = excluded.source;