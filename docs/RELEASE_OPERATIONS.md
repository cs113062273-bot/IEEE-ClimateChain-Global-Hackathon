# GridProof external release and facility-manager handoff

**Prepared locally; no public release has occurred.** A judge needs a browser, not Python, Node, a wallet or registration. The operator hosts the existing app; the standalone HTML is a clearly labeled recorded backup.

## Present blockers and minimum account actions

Anonymous checks at **2026-10-13 10:16:19 UTC** returned HTTP **404** for both [repository webpage](https://github.com/cs113062273-bot/IEEE-ClimateChain-Global-Hackathon) and [GitHub API](https://api.github.com/repos/cs113062273-bot/IEEE-ClimateChain-Global-Hackathon). No authentication headers were sent. This establishes unavailable anonymous access, not the reason for it. A public video URL and a submitted Devpost confirmation are also absent.

1. Entrant reviews eligibility and the authenticated submission fields; use [requirements audit](JUDGING_REQUIREMENTS_AUDIT.md) for the unresolved official time conflict.
2. Explicitly authorize the intended source visibility change/push and exact Render release. Review this local delivery first. No resource should be created before that authorization.
3. After authorization, publish the approved commit; open and clone it without login. Record/upload the 4:35 video, verify anonymous playback, then fill actual repository/video/demo links in Devpost. Publication does not itself submit the entry.
4. Preview and formally submit through the entrant's account before the conservatively planned **October 25, 2026, 22:00 Asia/Taipei** deadline; retain the actual confirmation. Do not infer acceptance or attachment limits from discussion questions.

## One hosting profile: Render

The root [render.yaml](../render.yaml) describes the current API Dockerfile, current Next.js Dockerfile and static recorded fallback. Its JSON syntax is valid YAML. Dynamic plans are explicitly `free`; automatic deployments and previews are disabled. Configuration preparation is not a deployed URL or a tested cloud build.

The manifest passed local JSON parsing and the [official Render JSON Schema](https://render.com/schema/render.yaml.json) validation on October 13. Captured schema SHA256: `8a3fb8da6b4f55fe686fbefa790e011d3dd7895f013f355953c572a21ab6494a`. No authenticated validation/deployment API was called; this checks schema compatibility, not account capacity or successful container execution.

Render supports Dockerfile paths/context and static publish paths in Blueprints. `sync: false` prompts for the real API origin; it does not invent a URL. See the [official Blueprint reference](https://render.com/docs/blueprint-spec). Docker environment values become build arguments; only the nonsecret `GRIDPROOF_API_URL` is needed at web build time. See [Docker documentation](https://render.com/docs/docker).

After authorization, choose either the static release alone or the dynamic release plus static backup on this same platform:

| Service | Exact settings | Judge experience |
| --- | --- | --- |
| Recorded fallback | Runtime Static; build `test -s offline/index.html`; publish `./offline`; auto deploy Off | Four recorded days and seven policies, interval replay and deliberate source-forgery checks. No new solve and no chain query. |
| API | Runtime Docker; context repo root; `Dockerfile.api`; Free; health `/api/health`; variables from `gridproof-api` in the manifest | Authentic cached sources, real portable-model inference, new MILP computations, independent evidence verification. Public chain writes denied. |
| Dashboard | Runtime Docker; context repo root; `Dockerfile.web`; Free; health `/`; `GRIDPROOF_API_URL` set to API's actual public HTTPS origin, without a trailing `/api` | Four existing pages and real solver/evidence actions, served without judge installation. |

**API first:** create the API using the manifest's fields and capture its assigned HTTPS origin. Then create the web service with that origin before its build. This avoids guessing Render subdomain names. The manifest can later manage the services with their exact names and `GRIDPROOF_API_URL` supplied. Blueprint creation prompts for this value; it cannot discover an as-yet unknown public origin. Changing the origin requires a new web build because Next rewrites are built into the release.

Use the public HTTPS API origin, not `http://api:8000` from local Compose: Render free services cannot receive private-network traffic. [Official private-network limitation](https://render.com/docs/private-network).

For the fastest reliable browser link, the static release is sufficient to explore the labeled recorded prototype while the video shows genuine solver/local-chain actions. Static sites run on Render's CDN; no app runtime is required. [Official static-site documentation](https://render.com/docs/static-sites).

Free dynamic services sleep after 15 idle minutes, may take about a minute to wake, lose mutable local files on restart, and share 750 monthly instance-hours per workspace. Two services consume the shared allowance separately. No persistent disk is configured. Review bandwidth/build usage and account spending settings; free plans do not imply unlimited usage. [Official free-service limits](https://render.com/docs/free). This is a candidate hackathon profile, not a production service commitment.

## Public configuration and release checks

- Keep `GRIDPROOF_READ_ONLY=1`, `GRIDPROOF_ALLOW_CHAIN_WRITES=0`; no Hardhat node or unlocked signer is hosted. The two-request compute limit is existing application protection, not complete rate limiting.
- The manifest selects Sepolia verification mode but includes **no RPC, deployment or public proof**. Until separately authorized real metadata exists, the UI must show unavailable/not checked. Three local evidence checks still function. Never copy example deployment metadata into a successful state.
- If Sepolia is separately approved, supply only operator-controlled HTTPS RPC and actual deployment/fixed-proof files. The hosted verifier has no private key. See [existing deployment preparation](PUBLIC_DEPLOYMENT.md).
- SQLite under `/tmp` is ephemeral. Download generated schedule/evidence immediately; fixed release evidence and source anchors ship in the image. A restarted service cannot promise recovery of dynamic evidence IDs.
- Docker/Linux/cloud execution remains unverified. Before offering a dynamic URL, build both images locally or on an authorized host; check health, all four dates, evidence success and rehashed-forgery rejection, read-only rejection, body/time limits and cold-start behavior. A failed build is a release blocker, not a reason to claim static replay performed a solve.
- Review source attribution [ATTRIBUTION.md](../ATTRIBUTION.md). Sources/model anchors identify redistribution terms and exact bytes. Campus devices, load, EV needs and tariff are hypothetical; no real household or student usage is included in the shipped fixture. Git author/account identities remain ordinary public repository metadata.
- The final current-tree scan is recorded in [secrets-scan.json](validation/championship-secrets-scan.json). A separate [reachable-history scan](validation/championship-history-secrets.json) checked 288 unique UTF-8 Git blobs with bounded common credential patterns and found no matches. These do not certify every secret format. Runtime/signing environments remain excluded. Test records include local filesystem usernames/paths and hardware details; no real household/student usage is shipped. Review the approved public contents before publication rather than copying an entire desktop folder.

## Facility-manager use and adoption boundary

For the prototype, select a recorded source day and set battery capacity, EV deadline and carbon preference in Dispatch, then run the actual optimizer. Compare equal EV/lab work across Carbon, Cost and Peak goals. Export the selected schedule as CSV for review and the full comparison/evidence as JSON for reproducibility. The exported schedule is an operational planning artifact, not a control command sent to real chargers.

The two bounded adoption improvements in this iteration are **usable CSV/JSON schedule export** and **this deployment/operator handoff**. Multi-site control, arbitrary CSV imports and automatic real-device actuation are not claimed. A campus pilot still requires local meters, tariffs/capacity agreements, validated assets and safety/control integration.

An operator can use the already verified Windows clean setup: `scripts/setup.ps1`, then `scripts/run_demo.ps1`; open `http://127.0.0.1:3000`. The prior exact clone at `a29daadc` reproduced the bundled model/sources, four dates and independent proof with pinned fresh dependencies. [Existing clean-clone record](validation/fresh-clone.json) remains evidence for that release; this iteration needs targeted regression/build checks for changed UI/bridge/config, not a claim that the old clone contains the new work.

The judge-facing shortest walkthrough is [ACCEPTANCE_60_SECONDS.md](ACCEPTANCE_60_SECONDS.md). If a live API or RPC fails, show the real unavailable state and open the static/file backup. In that backup, **Local Verification** covers its disclosed subset and **On-chain Attestation is NOT CHECKED**.
