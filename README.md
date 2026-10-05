# UK grid carbon pipeline

How much CO₂ comes with a unit of electricity in Great Britain depends a lot on when you use it.
When it's windy most of the grid runs on wind and nuclear, and when it's still, gas plants fill the
gap. In January 2026 the national carbon intensity went as low as 42 g of CO₂ per kWh and as high
as 286. The longer-term picture is changing too: the January average was 279 g/kWh in 2019 and
146 g/kWh in 2026.

The National Energy System Operator (NESO) publishes these figures every half hour, nationally and
for 14 regions, through its free [Carbon Intensity API](https://carbonintensity.org.uk/). I'm
building a pipeline that collects this data every day and keeps it in a form I can query, to
answer two questions:

1. **When is electricity cleanest?** Which times of day and days of the week have the lowest
   carbon intensity, and does that change from one region to another?
2. **How quickly is the grid decarbonising?** How have carbon intensity and the fuel mix behind
   it changed since 2018, nationally and by region?

Work in progress. At the moment it downloads national carbon intensity for one day at a time and
saves the raw response locally.

## Running it

You'll need Python 3.10 or later. Set up a virtual environment and install the project:

```
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
```

On macOS or Linux, activate it with `source .venv/bin/activate` instead.

To download a day of national data:

```
carbon-ingest intensity --date 2026-10-01
```

If you leave out `--date` it fetches yesterday. The files go into
`data/raw/national_intensity/date=2026-10-01/`. `intensity.json` is the API's response, saved
exactly as it was sent, and `_manifest.json` records the URL, when it was fetched and how many
half hours had an actual reading.

You can fetch today as well, but the half hours that haven't happened yet will only have
forecasts. Running the same day again later overwrites the files with the complete version.

## Tests

Run `pytest`. The tests use real API responses saved in `tests/fixtures`, so they don't need an
internet connection.

I use [pre-commit](https://pre-commit.com/) to lint and format code with ruff before each commit.
Run `pre-commit install` once to set it up.

## About the data

My notes on the API are in [docs/sources.md](docs/sources.md). The thing that catches you out
first is that it groups data by UK day but gives every timestamp in UTC, so the days the clocks
change have 46 or 50 half hours rather than 48.
