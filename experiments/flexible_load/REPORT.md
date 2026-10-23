# Stage 1: carbon value of delaying flexible batch electricity

Protocol: [protocol.json](protocol.json), written before results. Jobs: 12 per day arriving 08:00-19:30 UTC, 1-4 h, 5-20 kW, contiguous, sharing an 80 kW limit; about 373 kWh of flexible work per day. The same jobs run under every policy; reductions compare against running as soon as capacity allows with the same deadline. Decisions use only carbon observed before the job arrives and commit at arrival. Location-based average GB intensity: exposure, not causal marginal abatement.

Selection on validation (May-Jun 2025, carbon at 24 h): persistence tau 6 h, LightGBM 'small'. Independent test: 2026-01-01 to 2026-10-16 NESO actual data, downloaded after the design and never used for any choice. Exploratory test: Jul-Dec 2025, months examined in earlier work.

## Independent test, 2026: carbon exposure reduction versus immediate

| Policy | 3 h | 8 h | 24 h | 48 h |
|---|---:|---:|---:|---:|
| Fixed time-of-day rule | 5.6% [4.3, 6.7] | 9.9% [6.7, 12.7] | 12.9% [8.9, 16.2] | 13.3% [9.3, 16.9] |
| Seasonal median (7 days) | 5.9% [4.9, 6.9] | 12.0% [9.5, 14.3] | 25.9% [23.1, 28.2] | 26.4% [23.1, 29.5] |
| Persistence blend | 5.4% [4.4, 6.3] | 11.7% [9.1, 14.2] | 27.4% [24.9, 29.6] | 29.3% [26.5, 32.1] |
| Multi-horizon LightGBM | 6.0% [5.0, 7.0] | 12.2% [9.7, 14.5] | 27.3% [24.8, 29.6] | 28.2% [25.5, 30.8] |
| Perfect foresight, same rules | 7.3% [6.3, 8.2] | 16.6% [14.3, 18.9] | 34.6% [32.6, 36.5] | 41.8% [39.4, 44.0] |
| NESO published forecast (reference only) | 6.0% [5.0, 7.0] | 14.7% [12.2, 17.0] | 32.8% [30.8, 34.6] | 39.9% [37.4, 42.2] |

| At 24 h | Missed deadlines | Cost change | Worse days | Mean delay h | Mean daily peak kW (immediate 27.2) | Share of perfect foresight |
|---|---:|---:|---:|---:|---:|---:|
| Fixed time-of-day rule | 0 | -37.0% | 97/289 | 15.1 | 35.0 | 0.37 |
| Seasonal median (7 days) | 0 | -25.3% | 60/289 | 16.3 | 35.1 | 0.75 |
| Persistence blend | 0 | -24.1% | 54/289 | 15.5 | 34.6 | 0.79 |
| Multi-horizon LightGBM | 0 | -23.6% | 51/289 | 13.9 | 34.1 | 0.79 |
| Perfect foresight, same rules | 0 | -22.2% | 21/289 | 14.8 | 33.2 | 1.00 |
| NESO published forecast (reference only) | 0 | -20.9% | 32/289 | 14.7 | 32.8 | 0.95 |

Scale: 377 kWh/day of flexible work at 122 g/kWh when run immediately. The seasonal median at 24 h avoids 11.9 kg/day, 4.3 t/yr, 32 g per flexible kWh.

## Exploratory test, Jul-Dec 2025: carbon exposure reduction versus immediate

| Policy | 3 h | 8 h | 24 h | 48 h |
|---|---:|---:|---:|---:|
| Fixed time-of-day rule | 7.0% [5.9, 8.2] | 15.5% [12.7, 18.5] | 16.3% [12.9, 19.8] | 16.1% [12.1, 20.2] |
| Seasonal median (7 days) | 7.5% [6.3, 8.7] | 16.2% [13.2, 19.4] | 23.0% [18.9, 27.3] | 22.4% [17.5, 27.4] |
| Persistence blend | 7.1% [5.7, 8.6] | 15.5% [12.2, 19.0] | 23.1% [18.9, 27.5] | 25.2% [20.1, 30.7] |
| Multi-horizon LightGBM | 7.4% [6.2, 8.6] | 16.0% [13.2, 19.0] | 23.8% [19.8, 27.7] | 25.4% [20.4, 30.1] |
| Perfect foresight, same rules | 9.0% [7.6, 10.4] | 19.6% [16.6, 23.0] | 32.0% [27.7, 36.1] | 39.7% [34.5, 44.7] |
| NESO published forecast (reference only) | 7.9% [6.7, 9.1] | 18.2% [15.1, 21.7] | 30.3% [26.1, 34.4] | 38.0% [32.7, 43.1] |

| At 24 h | Missed deadlines | Cost change | Worse days | Mean delay h | Mean daily peak kW (immediate 17.6) | Share of perfect foresight |
|---|---:|---:|---:|---:|---:|---:|
| Fixed time-of-day rule | 0 | -37.5% | 49/184 | 15.1 | 22.4 | 0.51 |
| Seasonal median (7 days) | 0 | -30.6% | 31/184 | 14.2 | 22.3 | 0.72 |
| Persistence blend | 0 | -27.9% | 23/184 | 13.5 | 21.6 | 0.72 |
| Multi-horizon LightGBM | 0 | -27.9% | 19/184 | 12.7 | 21.6 | 0.74 |
| Perfect foresight, same rules | 0 | -27.1% | 7/184 | 13.9 | 21.1 | 1.00 |
| NESO published forecast (reference only) | 0 | -26.9% | 11/184 | 14.0 | 21.2 | 0.95 |

Scale: 368 kWh/day of flexible work at 130 g/kWh when run immediately. The seasonal median at 24 h avoids 11.0 kg/day, 4.0 t/yr, 30 g per flexible kWh.

## Where the value is (24 h, 2026)

| Group | Fixed rule | Seasonal median | LightGBM | Perfect foresight |
|---|---:|---:|---:|---:|
| arrives: 08-12 | -16.2% | 9.3% | 11.3% | 22.7% |
| arrives: 12-16 | 12.3% | 26.3% | 27.0% | 34.2% |
| arrives: 16-20 | 33.5% | 37.1% | 38.6% | 43.1% |
| length: 1-2 h jobs | 10.1% | 25.1% | 26.8% | 36.1% |
| length: 2.5-4 h jobs | 13.8% | 26.2% | 27.5% | 34.1% |

## Forecast error (MAE g/kWh, 2026)

| Method | 0-6 h | 6-24 h | 24-52 h |
|---|---:|---:|---:|
| Fixed time-of-day rule | 51.3 | 48.9 | 50.0 |
| Seasonal median (7 days) | 37.5 | 42.1 | 43.0 |
| Persistence blend | 18.8 | 39.7 | 42.9 |
| Multi-horizon LightGBM | 24.1 | 35.9 | 44.7 |
| NESO published forecast (reference only) | 9.4 | 10.4 | 10.1 |

The NESO published field has nearly constant ~10 g/kWh error at every lead time, consistent with a short-lead forecast whose issue time is not archived. It is not a valid decision baseline.

## Reading

- Waiting matters, and the length of the wait sets the value: about 6% at 3 h, 12% at 8 h and 26-27% at 24 h on the unseen 2026 period with simple forecasts, with no missed deadlines.
- Roughly half of the 24 h value needs live grid information: a fixed clock rule gets 12.9%; a 7-day seasonal median gets 25.9%. LightGBM and persistence add about 1.5 points beyond that; the ML model is not the source of the value.
- Beyond 24 h the forecasts stop improving (48 h is close to 24 h), although perfect foresight keeps gaining. The forecast horizon, not the flexibility, becomes the limit.
- Jobs that arrive in the evening carry most of the value; morning arrivals gain least, and a fixed clock rule makes them worse.
- Costs: the illustrative tariff falls with carbon here because night is cheap in that synthetic tariff. Typical daily peaks of the flexible load rise about 25-30% as jobs bunch into clean hours, always within the 80 kW limit. 15-20% of days are worse than running immediately.
- Limits: synthetic workload (real campus job traces not yet used), commit at arrival without re-planning, no battery or PV, national average intensity.

Wall time 67 s. Data: 31488 half-hours, 43 missing actual values interpolated for scoring only.
