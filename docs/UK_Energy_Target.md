# Target name:
De-rated Margin (DRM)

## Description:
**De-rated margin** is the amount of spare electricity generation capacity expected to remain above demand after adjusting generators for how reliably that capacity is expected to be available.

**De-rated** means the generator’s maximum or nameplate capacity is discounted to reflect real-world availability rather than assuming it can always produce at 100% of its rated output.

**Margin** means the difference between expected available generation capacity and expected electricity demand.

## Source:
Elexon Insights Solution (BMRS), using data supplied by NESO

> BMRS - Balancing Mechanism Reporting Service
>
> NESO - National Energy System Operator

### Why this source?
Elexon Insights as the API source for De-Rated Margin because it publishes NESO-derived DRM data in the short-horizon, settlement-period format needed for the model, whereas NESO’s own public margin datasets are aimed more at operational planning over longer horizons.

## API endpoint/dataset:
GET /forecast/system/loss-of-load
Dataset: LOLPDRM

## Target field:
deratedMargin

## Unit:
MW

## Forecast horizon:
24 hours ahead

## What timestamp represents:
startTime = the start of the half-hour settlement period
whose margin is being predicted.

Forecast origin = 24 hours before startTime.

## When the target value becomes knowable:
Use the 1-hour-ahead DRM value (forecastHorizon = 1)
as the historical target/label.

That value is published approximately one hour before
the relevant settlement period, so it is NOT available
at the model's 24-hour forecast origin.

## Why it represents margin tightness:
DRM represents forecast excess supply after adjusting
for the expected availability of generators.

Higher DRM = more spare capacity.
Lower DRM = tighter system conditions.