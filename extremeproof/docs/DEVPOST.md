# ExtremeProof

**Track: Climate Data & Environmental Monitoring**

ExtremeProof makes the climate data behind heat-relief payments transparent and independently verifiable.

## Inspiration

Heatwaves threaten farmers' crops and incomes. But deciding when relief should be paid introduces another problem: different weather records can give different answers.

In Muğla, Türkiye, the weather station recorded a four-day hot spell in summer 2021, while ERA5 recorded ten days under the selected rule. With a six-day payment threshold, one record supports a payment and the other does not.

Which record should decide? How should missing readings be filled? Which years should define “normal”?

ExtremeProof makes these choices visible before anyone signs or deposits money.

## What it does

A relief fund, farmers' cooperative and independent checker agree on a heat-relief rule before summer.

The application guides them through six steps:

1. **Compare the climate data.** Explore temperatures, missing readings and historical heatwaves at 14 stations across four countries.
2. **Choose a rule.** Compare payment frequency, payment amounts and disagreements between data sources. Decide in advance what happens if a dispute remains unresolved.
3. **Sign and fund the agreement.** Review the rule and daily temperature thresholds. Three parties sign the same fingerprint, and the fund deposits DEMO money into escrow before the season starts.
4. **Follow the summer.** Two providers submit daily readings. The contract counts qualifying hot days and releases the amount both records support. After the season, the amount neither supports returns to the fund. Only the difference enters dispute.
5. **Try to tamper with it.** Change a threshold, edit a temperature, alter a result or remove evidence. The contract or independent verifier detects the change.
6. **Verify it yourself.** Download the evidence bundle and run a standalone Python verifier, including an optional check against the local chain.

For Muğla 2021, the graded rule returns 15,000 DEMO and holds 35,000 in dispute, instead of holding the entire 50,000.

## Why use a blockchain?

The calculation can be checked without a blockchain. The chain adds a shared record of the rule agreed before summer, signatures from all three parties and funds already held in escrow.

The contract computes heatwave lengths from submitted daily readings and moves money according to the signed terms. Neither side can simply rewrite the agreement after seeing the season's outcome.

## How it was built

- **Climate data:** NOAA GHCN-Daily station records and ERA5 reanalysis through Open-Meteo. Downloaded files retain their source URLs, retrieval times and SHA-256 hashes.
- **Climate calculations:** A Python engine computes daily heat thresholds, fills gaps and counts hot spells. Its calculations were cross-checked against xclim.
- **Smart contracts:** Solidity contracts manage signatures, escrow, daily readings, payments and dispute handling on a local EVM chain, using Hardhat.
- **Services and interface:** FastAPI provider services, web3.py, and a Next.js interface with TypeScript, React and viem.
- **Independent verification:** A separate implementation recomputes the climate calculations and settlement. The downloadable verifier needs only Python's standard library.

## Challenges and lessons learned

Missing data must not silently become “no heatwave.” The application distinguishes insufficient evidence from a valid result that does not qualify for payment.

Another challenge was keeping the signed rule, browser calculations, contract execution and downloadable evidence consistent. The verifier independently checks those connections rather than trusting the interface.

The gap-filling experiment also changed a design decision. In a small evaluation using three complete summers, LightGBM achieved lower average temperature error but missed three of nine heatwaves. Quantile mapping detected all nine, so it became the default. Better average prediction accuracy did not mean better payment decisions.

## Results

In the Antalya 2024 replay, the contract releases 35,000 DEMO on June 15 and another 15,000 on June 22, while summer is still underway.

Across historical replays of 2021–2025 at ten Turkish stations, 96% of the money supported by both records would have been released before the season ended. This result assumes a five-day publication delay and weekly checks. It is a retrospective simulation, not evidence of payments to real farmers.

## Who could use it, and how could it scale?

Potential users include relief funds, farmers' cooperatives and independent organisations checking heat-index payments.

The public browser edition requires no installation. Users can compare rules, inspect recorded agreements and download verification bundles. The full local edition runs the signing and payment workflow.

The same code already supports ten stations in Türkiye and four in Greece, Romania and Bulgaria. Adding locations would require checking data coverage and agreeing on suitable local rules. Member summaries are available in English and Turkish.

## Current limits and next steps

This is a working prototype using real weather data and contracts executed on a local EVM chain. Participants, provider operators, DEMO funds and the chain clock are simulated. There are no real customers yet, and the project has not been deployed to a public network.

The two data sources are not fully independent because ERA5 also fills gaps in station records. Publisher revisions are not modelled, and the example payment ladder is not calibrated to crop losses.

Next steps include adding a third independent source, testing deployment on a public testnet and evaluating the workflow with a relief organisation or cooperative.

## Project links

- Browser demo: https://cs113062273-bot.github.io/IEEE-ClimateChain-Global-Hackathon/
- Source: https://github.com/cs113062273-bot/IEEE-ClimateChain-Global-Hackathon
- Video: https://youtu.be/VtFjr0pjLpM
