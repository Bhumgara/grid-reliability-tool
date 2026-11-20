# Design tokens

`tokens.json` holds the app's colours so the Streamlit dashboard and the
Flutter app can share them.

- `palette`: named colours as `#RRGGBB` hex.
- `fuel_colours`, `model_colours`, `demand_profile_colours`: map a fuel type,
  model or demand profile to a **palette name** (not a hex value). Resolve the
  name through `palette` to get the colour.

Several palette names share a hex value on purpose (for example
`historical_iqr` and `grid_border`). They describe different roles, so keep
them separate even when the colour matches.

`dashboard/styles.py` loads this file, so editing a colour here changes the
Streamlit dashboard too.

## Colour choices

Demand profiles (typical-day chart):

- **Current profile** uses `demand_observed` (purple), the same "today's
  demand" colour as the recent history chart.
- **Latest full profile** uses `generation_wind` (teal), tying it to wind as
  the dominant generator.
- **Historical median** uses `reference` (neutral grey-blue), so it reads as
  the baseline rather than a third competing series.
