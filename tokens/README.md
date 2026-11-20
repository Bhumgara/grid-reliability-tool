# Design tokens

`tokens.json` holds the app's colours so the Streamlit dashboard and the
Flutter app can share them.

- `palette`: named colours as `#RRGGBB` hex (light mode).
- `palette_dark`: the same names with dark-mode values.
- `fuel_colours`, `model_colours`, `demand_profile_colours`: map a fuel type,
  model or demand profile to a **palette name** (not a hex value). Resolve the
  name through `palette` or `palette_dark` to get the colour, so the mappings
  work in both modes.

Several palette names share a hex value on purpose (for example
`historical_iqr` and `grid_border`). They describe different roles, so keep
them separate even when the colour matches.

`dashboard/styles.py` loads this file, so editing a colour here changes the
Streamlit dashboard too. The dashboard uses the light palette only.

## Dark palette

The dark background and text are derived from the light `text_primary`
blue, so both modes share a hue.

- **Marks** (lines, bars, points, doughnut slices, arrows) are lightened and
  must reach at least 3:1 contrast against both `background` and
  `card_surface` (WCAG non-text contrast).
- **Text** (`text_primary`, `text_secondary`, and `delayed_text` on
  `delayed_background`) must reach at least 4.5:1 (WCAG AA).
- **Fills** (risk tints, uncertainty and IQR bands, surfaces, borders) are
  darkened so they sit behind the data rather than glow.

`tests/test_tokens.py` checks these thresholds, so a colour change that
breaks them fails the tests.

## Colour choices

Demand profiles (typical-day chart):

- **Current profile** uses `demand_observed` (purple), the same "today's
  demand" colour as the recent history chart.
- **Latest full profile** uses `generation_wind` (teal), tying it to wind as
  the dominant generator.
- **Historical median** uses `reference` (neutral grey-blue), so it reads as
  the baseline rather than a third competing series.
