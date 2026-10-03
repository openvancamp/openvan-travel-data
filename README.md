# OpenVan.camp travel data — daily snapshots

[![Daily snapshot](https://github.com/openvancamp/openvan-travel-data/actions/workflows/snapshot.yml/badge.svg)](https://github.com/openvancamp/openvan-travel-data/actions/workflows/snapshot.yml)
[![Data: CC BY 4.0](https://img.shields.io/badge/data-CC%20BY%204.0-467187)](https://creativecommons.org/licenses/by/4.0/)

Open CSV and JSON for road trips, updated every day by a GitHub Action from the free
[OpenVan.camp API](https://github.com/openvancamp/openvan-camp-public-api):

- **Retail fuel prices** — gasoline, diesel, LPG, CNG, E85 in 170+ countries
- **Exchange rates** — 150+ currencies per EUR
- **Food cost index** — 92 countries, world average = 100
- **Vanlife weather scores** — 160+ countries, 0–100 with sleep / drive / solar / sea sub-scores
- **Reference** — toll roads (85 countries), power plugs and voltage (229), public and school
  holidays (212), customs rules, license plates (199), passport ranking

Every day adds a row per country to `history/`, so the repository is also a time series.

## Files

| File | What | Updated |
|------|------|---------|
| [`data/fuel-prices.csv`](data/fuel-prices.csv) | country, grade, price, currency, unit | daily |
| [`data/currency-rates.csv`](data/currency-rates.csv) | currency, units per 1 EUR | daily |
| [`data/vanbasket.csv`](data/vanbasket.csv) | food cost index by country | daily |
| [`data/vansky-weather.csv`](data/vansky-weather.csv) | weather suitability scores by country | daily |
| `history/<dataset>-<year>.csv` | the same rows with a leading `date` column, one row set per day | daily |
| `data/*.json` | the raw API answers, including toll, plug, holiday, customs, plate and visa-ranking reference | daily |
| [`datapackage.json`](datapackage.json) | [Frictionless](https://frictionlessdata.io/) descriptor with field types | — |

### Read fuel prices correctly

Prices are kept **exactly as published**: local currency, local unit. Two things trip people up:

- `currency` is per **grade**, not per country — Venezuela sells diesel in USD and gasoline in VES.
- `unit` can be `gallon` (US) or `imperial_gallon`.

To compare in EUR per liter, divide by **the same day's** rate from `currency-rates`
(not today's) and by 3.78541 for US gallons or 4.54609 for imperial gallons. A currency without
a rate that day is left unconverted rather than guessed.

## Use it

```python
import pandas as pd

base = "https://raw.githubusercontent.com/openvancamp/openvan-travel-data/main"
# keep_default_na=False: otherwise pandas reads Namibia's code "NA" as a missing value
fuel = pd.read_csv(f"{base}/data/fuel-prices.csv", keep_default_na=False)
rates = pd.read_csv(f"{base}/data/currency-rates.csv", keep_default_na=False).set_index("currency")["per_eur"]
rates["EUR"] = 1.0

per_liter = {"liter": 1, "gallon": 3.78541, "imperial_gallon": 4.54609}
diesel = fuel[fuel.grade == "diesel"].copy()
diesel["eur_per_liter"] = diesel.price / diesel.currency.map(rates) / diesel.unit.map(per_liter)
print(diesel.sort_values("eur_per_liter")[["country_name", "eur_per_liter"]].head(10))
```

```bash
# Diesel price history of one country
curl -s https://raw.githubusercontent.com/openvancamp/openvan-travel-data/main/history/fuel-prices-2026.csv \
  | grep -E '^date|,DE,diesel,'
```

Need live data, a route estimate or visa rules instead of a daily file? Use the API directly —
no key: [docs](https://openvan.camp/docs?utm_source=github&utm_medium=referral&utm_campaign=travel-data),
[`pip install openvan`](https://github.com/openvancamp/openvan-camp-public-api/tree/main/python-sdk),
[`npm install @openvancamp/sdk`](https://www.npmjs.com/package/@openvancamp/sdk), or the
[MCP server](https://github.com/openvancamp/openvan-camp-public-api/tree/main/mcp-server) for AI agents.

## License and attribution

Data: [CC BY 4.0](LICENSE-DATA). Credit it as

```html
Data: <a href="https://openvan.camp/">OpenVan.camp</a> — CC BY 4.0
```

Fuel prices are aggregated from official bulletins, government price portals and station
networks; each country entry in `data/fuel-prices.json` lists its `sources`. The snapshot script
in [`scripts/`](scripts/snapshot.py) is MIT.

Spotted a wrong number? [Report it](https://github.com/openvancamp/openvan-camp-public-api/issues/new?template=wrong-data.yml).
