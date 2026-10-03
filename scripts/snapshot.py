"""Daily snapshot of the OpenVan.camp public API into CSV and JSON.

Writes the current state to data/ (overwritten every day) and appends the day's
rows to history/<dataset>-<year>.csv. Prices are kept in local currency with
the local unit, exactly as published; convert with the same day's
currency-rates rows, never with today's rates.
"""

from __future__ import annotations

import csv
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

API = "https://openvan.camp"
SOURCE = "github-openvan-travel-data"
ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
HISTORY = ROOT / "history"
TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")


def get(path: str) -> dict:
    sep = "&" if "?" in path else "?"
    url = f"{API}{path}{sep}source={SOURCE}"
    for attempt in range(4):
        try:
            request = Request(url, headers={"Accept": "application/json", "User-Agent": SOURCE})
            with urlopen(request, timeout=60) as response:
                return json.loads(response.read().decode())
        except Exception as error:  # noqa: BLE001 — retry any network / decode failure
            if attempt == 3:
                raise RuntimeError(f"{path}: {error}") from error
            time.sleep(10 * (attempt + 1))
    raise AssertionError("unreachable")


def write_json(name: str, payload: dict) -> None:
    payload = {k: v for k, v in payload.items() if k != "_attribution"}
    (DATA / f"{name}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1, sort_keys=True) + "\n")


def write_csv(name: str, fields: list[str], rows: list[dict]) -> None:
    rows = sorted(rows, key=lambda r: tuple(str(r.get(f, "")) for f in fields[:3]))
    with open(DATA / f"{name}.csv", "w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    history = HISTORY / f"{name}-{TODAY[:4]}.csv"
    history_fields = ["date", *fields]
    kept: list[dict] = []
    if history.exists():
        with open(history, newline="") as handle:
            kept = [r for r in csv.DictReader(handle) if r["date"] != TODAY]
    with open(history, "w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=history_fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(kept)
        writer.writerows({"date": TODAY, **r} for r in rows)


def fuel() -> int:
    res = get("/api/fuel/prices")
    write_json("fuel-prices", res)
    rows = []
    for code, country in res["data"].items():
        for grade, price in (country.get("prices") or {}).items():
            if price is None:
                continue
            rows.append(
                {
                    "country_code": code,
                    "country_name": country.get("country_name"),
                    "grade": grade,
                    "price": price,
                    "currency": (country.get("currencies") or {}).get(grade) or country.get("currency"),
                    "unit": (country.get("units") or {}).get(grade) or country.get("unit"),
                    "fetched_at": country.get("fetched_at"),
                }
            )
    write_csv("fuel-prices", ["country_code", "grade", "country_name", "price", "currency", "unit", "fetched_at"], rows)
    return len(rows)


def currency() -> int:
    res = get("/api/currency/rates")
    write_json("currency-rates", res)
    rows = [{"currency": code, "per_eur": rate} for code, rate in res["rates"].items()]
    write_csv("currency-rates", ["currency", "per_eur"], rows)
    return len(rows)


def vanbasket() -> int:
    res = get("/api/vanbasket/countries")
    write_json("vanbasket", res)
    rows = list(res["data"].values())
    write_csv(
        "vanbasket",
        ["country_code", "country_name", "region", "vanbasket_index", "pct_vs_world", "data_quality", "last_updated_at"],
        rows,
    )
    return len(rows)


def vansky() -> int:
    res = get("/api/vansky/weather")
    rows = []
    for c in res["data"]:
        weather = c.get("weather") or {}
        rows.append(
            {
                "country_code": c.get("code"),
                "region": c.get("region"),
                "van_score": c.get("van_score"),
                "score_label": c.get("score_label"),
                "week_score": c.get("week_score"),
                "sleep_score": c.get("sleep_score"),
                "drive_score": c.get("drive_score"),
                "solar_score": c.get("solar_score"),
                "sea_score": c.get("sea_score"),
                "solar_kwh": c.get("solar_kwh"),
                "temp_day": weather.get("temp_day"),
                "temp_night": weather.get("temp_night"),
                "precip_sum": weather.get("precip_sum"),
                "wind_max": weather.get("wind_max"),
                "fetched_at": c.get("fetched_at"),
            }
        )
    fields = list(rows[0].keys()) if rows else ["country_code"]
    write_csv("vansky-weather", fields, rows)
    return len(rows)


REFERENCE = {
    "electricity": "/api/electricity/countries",
    "holidays-countries": "/api/holidays/countries",
    "tolls": "/api/tolls/countries",
    "customs": "/api/customs/countries",
    "license-plates": "/api/plates",
    "visa-rank": "/api/visa/rank",
}


def main() -> int:
    DATA.mkdir(exist_ok=True)
    HISTORY.mkdir(exist_ok=True)
    failures = []
    for name, job in {"fuel": fuel, "currency": currency, "vanbasket": vanbasket, "vansky": vansky}.items():
        try:
            print(f"{name}: {job()} rows")
        except Exception as error:  # noqa: BLE001 — one broken endpoint must not lose the others
            failures.append(f"{name}: {error}")
    for name, path in REFERENCE.items():
        try:
            write_json(name, get(path))
            print(f"{name}: ok")
        except Exception as error:  # noqa: BLE001
            failures.append(f"{name}: {error}")
    (DATA / "updated.txt").write_text(TODAY + "\n")
    for failure in failures:
        print(f"::error::{failure}", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
