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
