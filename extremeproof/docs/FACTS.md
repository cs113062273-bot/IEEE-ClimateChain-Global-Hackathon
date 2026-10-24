# Data facts, re-checked from pinned files

Every number below is recomputed by `python -m extremeproof.scripts.reproduce_facts`
from the files pinned in `data/manifest.json` and written to `docs/facts.json`.

## Antalya station (GHCN-Daily TUM00017300)

- First daily maximum temperature (TX): **1963-01-21**; last: 2025-08-01.
- 1961–1990 base period: 7,143 of 10,957 days present (**65.2 %**); 1991–2020: 7,781 of 10,958 (71.0 %).
- Recent years are thin: days with TX per year — 2018: 113, 2019: 2, 2020: 11, 2021: 281, 2022: 258, 2023: 112, 2024: 48, 2025: 5.
- No values were removed by our quality control (GHCN quality flags, physical limits, stuck-value runs).

## Antalya station vs ERA5 (Open-Meteo, model `era5`)

- ERA5 grid point returned: 37.0 °N, 30.75 °E, 59 m (the station is at 36.899 °N, 30.800 °E, 54 m).
- 15,628 days with both values; daily Pearson r = **0.970**.
- ERA5 is warmer by **0.58 °C** on average, but by **2.28 °C in June–August**. Because each
  source is compared with its own base-period percentiles, a constant bias cancels; a
  season-dependent bias does not, which is one reason the two sources disagree in summer.

## The same heat rule gives different answers

Rule: 1 Jun–30 Sep, at least 6 consecutive days with TX above the calendar-day 90th
percentile of the base period (centred 5-day window, type-8 quantile). Missing days
break a spell; nothing is filled. Bootstrapped results apply the Zhang et al. (2005)
procedure to years inside the base period (triggered when at least half of the replicates trigger).
During development the engine's percentiles, TX90p, WSDI, spells and bootstrap matched xclim 0.58 to within 1e-9 on this station (with gaps) and ERA5.

| Source / base | Years triggered, 1966–2025 |
|---|---|
| ERA5, 1961–1990 | 1979, 1987, 1988, 1991, 1993, 1994, 1997, 1998, 2000, 2004, 2007, 2008, 2011, 2015, 2016, 2021, 2024, 2025 |
| ERA5, 1991–2020 (bootstrapped) | 1979, 1987, 1988, 1991, 1993, 1994, 1997, 1998, 2000, 2007, 2009, 2016, 2021, 2023, 2024, 2025 |
| Station, 1961–1990 | 1993, 2007, 2008, 2023 |
| Station, 1991–2020 (bootstrapped) | 2008, 2023 |

- **The base period changes the verdict.** With ERA5, 2004, 2008, 2011 and 2015 trigger only under
  1961–1990 (and 1980–1982 once bootstrapped); 2009 and 2023 trigger only under 1991–2020.
- **Older is not always lower.** ERA5's 1961–1990 thresholds are higher than 1991–2020's on several
  mid-July days (by 0.3–1.0 °C), so the 13–26 July 2023 heatwave qualifies only against the newer base.
  ERA5 before the late 1970s is constrained by far fewer observations than in the satellite era, so a
  1961–1990 reanalysis baseline carries extra uncertainty; we have not tested whether that explains the difference.
- **Missing data changes the verdict.** Summer gaps break spells at the station: in 2000, 2021 and 2024
  ERA5 records 12-, 10- and 14-day spells while the station's longest recorded spell is 4, 3 and 2 days.
- Event count: ERA5 has 23 qualifying spells in 1966–2025 against 1961–1990 and 18 against 1991–2020;
  the station has 5. Far too few to train a model to decide "disaster or not" — the AI in this project
  only estimates missing station values, and the trigger is always decided by the published rule.

## Neighbouring stations (TX days per year, 2018–2025)

| Station | Distance from Antalya | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 |
|---|---|---|---|---|---|---|---|---|---|
| Finike TU000017375 | 87 km | 45 | 3 | 41 | 291 | 355 | 298 | 243 | 360 |
| Isparta TU000017240 | 97 km | 49 | 3 | 7 | 75 | 170 | 56 | 10 | 6 |
| Muğla TUM00017292 | 219 km | 358 | 360 | 357 | 357 | 353 | 353 | 346 | 360 |
| Mersin TUM00017340 | 341 km | 29 | 10 | 37 | 356 | 353 | 353 | 297 | 360 |

Finike has 521 values removed by GHCN's own quality flags (D: duplicate, N: naught check, I: internal consistency).

## GHCN inventory, Mediterranean countries

191 stations in countries bordering the Mediterranean (GHCN FIPS codes listed in `facts.json`)
have TX inventory spanning 1961–2024. The inventory only records first and last year with any
data, so completeness has to be checked station by station.

## Licences

- **GHCN-Daily**: no explicit licence is published. The readme and the NOAA ISO metadata ask for
  citation (doi:10.7289/V5D21VHZ), state no use restrictions and say electronic downloads are free;
  NOAA/NCEI disclaim liability. Downloaded without an account.
- **Open-Meteo**: API data under CC BY 4.0; the free API is non-commercial only (<10,000 calls/day).
  Reanalysis from the Copernicus Climate Change Service (ERA5, ERA5-Land). No API key.
