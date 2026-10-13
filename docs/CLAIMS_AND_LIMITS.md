# Claims and limits

The supported impact claim is **estimated location-based grid emissions exposure for a simulated London campus under the selected GB carbon-intensity series**. Compute it as `sum(grid_import_kwh * intensity_gco2_per_kwh) / 1000`. A baseline-to-plan difference is a modeled counterfactual under the same jobs, constraints and terminal battery energy.

| Evidence in this prototype | What it supports | What it does not support |
|---|---|---|
| Downloaded NESO snapshot with SHA256, attribution and timestamps | Reproducible use of this version of public GB grid data. | Individual campus meter truth, NESO endorsement, or marginal/causal avoided emissions. |
| Simulated fixed load, EV/lab jobs, PV and battery | A physically constrained hypothetical operating schedule with explicit assumptions. | A live meter connection, observed site PV generation, completed real EV charging, or a field trial. |
| Illustrative tariff and optimized expense | Comparison under the disclosed tariff. | Actual utility billing, paid energy trades, or a licensed market price feed. |
| Past-only forecast / held-out replay | Performance for the specified chronological evaluation windows and permitted inputs. | Guaranteed future performance. Historical forecast columns whose issuance time is unknown remain labeled as such. Historical reanalysis is not decision-time weather foresight. |
| SHA256 evidence commitment and successful registry event | This actor committed these report bytes on this chain; the current exact scope has one active registration. | Correctness of source measurements, ownership of the site, scientific verification, additionality, permanence, certified offsets, RECs or credits. |
| Local Hardhat receipt verified against the running node | A real zero-cost transaction in the operator's development chain with checkable contract state/event. | Public explorer visibility, independent consensus, permanent public-chain publication or public-testnet deployment. |
| Revocation and linked replacement | An explicit auditable lifecycle without discarding the original digest. | The original report never existed; the current report is automatically truthful. |

Exports receive no negative-emissions credit by default. PV lowers imports through energy balance; it is not counted a second time as an offset. Initial and terminal battery state must match to prevent claiming savings from depleted stored energy.

The uniqueness policy covers **exact** `(site_hash,from_utc,to_utc,category)` values; model version and scenario ID cannot bypass it. It is not a global carbon double-counting standard. Overlapping intervals and alternative identifiers need a future identity and allocation protocol.

Verification statuses are explicit: `VERIFIED`, `HASH_MISMATCH`, `REVOKED`, `NOT_REGISTERED`, and `UNVERIFIABLE`. `VERIFIED` means integrity and registry status passed the implemented checks against the configured local RPC. It is never an environmental certification badge.

No ERC20 asset, tradable environmental certificate, paid transaction, mainnet deployment, public posting or competition submission is performed by the prototype. A later public deployment or submission needs the user's explicit instruction.
