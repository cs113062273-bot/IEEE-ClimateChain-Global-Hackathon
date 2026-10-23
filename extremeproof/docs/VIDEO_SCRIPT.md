# Demo video script (target 4:20, hard limit 5:00)

Follows the three things the official Presentation criterion asks for: the
climate problem, how the solution works, and the potential real-world impact.

Record the live edition at 1440×900, zoom 100 %, light theme, with a fresh
stack (`python -m extremeproof.scripts.stack`) so the chain clock reads
1 May 2021. Every number spoken appears on screen at that moment; do not round,
add or recall numbers. Never call it insurance; say "pre-arranged relief".
Do not claim real users, avoided losses or emissions reductions.

| Time | Screen | Voice-over |
|---|---|---|
| 0:00–0:25 | Hero. Hold on the Muğla 2021 card: the two bars and the 6-day marker. | "Summer 2021 in Muğla, Türkiye. Forest fires burned across Muğla and Antalya in heat above 40 degrees. Suppose a relief fund had promised a farmers' cooperative a heat payment for a run of 6 unusually hot days. The Muğla weather station counted 4. The ERA5 reanalysis counted 10." |
| 0:25–0:45 | Card text: "Station only would refund; ERA5 only would pay." | "Same summer, same rule, two honest records. A station-only rule would refund; an ERA5-only rule would pay. 50,000 depends on which record someone picked, and when they picked it. That is the climate-data problem in track 4: the data is fragmented and hard to verify, and money moves on it." |
| 0:45–1:20 | Click "Decide this case". The decision brief: 4 summers settle themselves; 2021 records disagree; "Not a one-off: … 8 … 1 of the 60 summers". | "ExtremeProof moves that choice to before summer. The brief sorts the last five summers: four settle themselves because the records agree. One does not. And it is not a one-off: under this rule the two records disagreed in 8 of 60 summers since 1966." |
| 1:20–1:45 | In the brief, toggle "return to the fund" → "go to the cooperative"; the line changes 0 → 50,000 DEMO, about 30 days. | "So the fund, the cooperative and an independent checker decide now: if the records disagree and they cannot agree afterwards, where does the money go? Here, to the cooperative, about 30 days after the season. That is the cost, shown before anyone signs." |
| 1:45–2:05 | Scroll to the comparison table, then step 2 chart (Muğla 2024, station). Point at the two threshold lines. | "Each record is judged against its own place's 30-year normal, the climate statistics of that place. We tested a machine-learning model, LightGBM, to fill station gaps; it missed 3 of 9 heatwaves, so quantile mapping is the default. The AI test is shown on the page." |
| 2:05–2:40 | Hero case "Sources disagree" → step 3. Fingerprint, "your browser computed the same fingerprint". Fund proposes → "contract terms match the signed text". Three signatures; Locked; 50,000.00 DEMO held. | "Now the rule becomes one text and one fingerprint. My browser and the server compute the same one, and the contract's terms are read back against it. The fund, the cooperative and the checker each sign that fingerprint; the fund's signature deposits the money. After the third signature nobody can change the rule." |
| 2:40–3:10 | Step 4: Play summer 2021. Providers fetch the season and report: station 4 days, ERA5 10 days → Settle: dispute → "Skip 30 days → apply the signed fallback". | "The summer plays out on a simulated clock. Only now does the summer's data exist. Each provider fetches it and files one final report, fingerprinting the exact files it used: station 4 days, ERA5 10. They disagree, so nobody decides alone. With no unanimous vote, after 30 days the fallback they signed in May applies." |
| 3:10–3:40 | Step 5: the three "Try it" buttons and "Drop the evidence"; red "checks failed" chips. | "Now try to cheat. The fund re-signs the rule with another normal after the season: the contract refuses. Edit one temperature reading, flip a provider's verdict, or drop the evidence: the independent verifier fails every altered bundle." |
| 3:40–4:00 | Step 6: "Run the independent verifier" → all checks passed. Then the public page's step 6: Download bundle and verify.py; terminal `python verify.py sources-disagree.zip` → 28/28 checks passed. | "You don't have to trust us. The verifier is one standard-library Python file sharing no code with the providers. Download a bundle from the public page, run it, and it recomputes every threshold and hot spell from the raw files: 28 of 28 checks." |
| 4:00–4:20 | Hero status row (Real / Executed / AI tested / Simulated). | "What is real: the weather records, the contract, the verifier. What is simulated: the parties and the money. A blockchain doesn't make data true; it makes the rule, and what happens when sources disagree, impossible to change after the heat. Antalya hosts COP31 this November. ExtremeProof: decide the disagreement before summer, settle it by the rule, and let anyone check." |

## Shot checklist

- [ ] Fresh stack: chain clock 1 May 2021, agreement #1.
- [ ] The hero card numbers (4, 10, 6) are visible when spoken.
- [ ] The status row "Simulated" item is on screen at least once.
- [ ] Terminal shot uses the files downloaded from the public page, not the repository copy.
- [ ] No claims of real users, avoided losses or emissions reductions.
