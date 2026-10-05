# Notes on the Carbon Intensity API

Checked against the live API on 5 October 2026.

- Docs: https://carbon-intensity.github.io/api-definitions/
- Base URL: `https://api.carbonintensity.org.uk`
- No API key or sign-up needed. Responses are JSON.
- Covers Great Britain only (no Northern Ireland).

## Endpoints I'm using

| Endpoint | What it returns | History starts |
| --- | --- | --- |
| `/intensity/date/{YYYY-MM-DD}` | National intensity for one UK day, forecast and actual | 12 Sep 2017 |
| `/generation/{from}/{to}` | National fuel mix as percentages per half hour | May 2018 |
| `/regional/intensity/{from}/{to}` | Forecast intensity and fuel mix for each region | May 2018 |

Each half hour of national intensity looks like this:

```json
{"from": "2026-10-01T11:00Z", "to": "2026-10-01T11:30Z",
 "intensity": {"forecast": 117, "actual": 116, "index": "moderate"}}
```

Intensity is in grams of CO₂ per kWh. `index` is a band: `very low`, `low`, `moderate`, `high`
or `very high`.

Regional responses have 18 entries per half hour: the 14 distribution network regions, then
England, Scotland, Wales and GB. Regional intensity is forecast only, with no `actual`.

## Things to watch out for

**Dates are UK days, times are UTC.** `/intensity/date/2026-10-01` starts at
`2026-09-30T23:00Z`, because 1 October begins at 23:00 UTC during British Summer Time. So most
days have 48 half hours, but the day the clocks go forward has 46 and the day they go back has 50
(checked on 29 Mar 2026 and 26 Oct 2025).

**Range queries include one extra half hour at the start.** Asking `/intensity/{from}/{to}` for
`2026-10-01T00:00Z` to `2026-10-02T00:00Z` returns 49 periods. The first one is
23:30–00:00 on 30 September, because it *ends* at the `from` time. Starting one minute later
(`T00:01Z`) returns exactly 48. Loading back-to-back ranges without removing duplicates would
double count those boundary periods. The generation and regional endpoints behave the same way.

**Actuals arrive late.** For today, and for any half hour that hasn't finished yet, `actual` is
`null` and only `forecast` is filled in. A day fetched before it's over needs fetching again
later.

**An empty day is still a 200.** Dates before September 2017 return HTTP 200 with
`{"data": []}` rather than an error.

**Range limit.** The docs say a range query can cover at most 14 days. A 15 day request still
worked when I tried it, but I'll stick to 14 day chunks for backfills in case that's enforced
later.

**Formatting differs between endpoints.** The date endpoint returns indented JSON with Windows
line endings and the range endpoints return compact JSON. It doesn't matter once parsed, but it's
why the raw files are compared by content and not assumed to look a certain way.
