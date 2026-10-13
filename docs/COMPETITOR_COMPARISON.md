# GridProof 競品與產品呈現對照

查核日期：2026-10-13。結論是：**能源排程、約束檢查與可獨立重算的證據串成一條操作流程，是 GridProof 最適合展示的差異。Hash、Dashboard 或鏈上錨定本身並不獨有。** 本輪沒有執行競品程式、交易、提交、登入或付費操作；不把作者敘述當成獨立實測。

## 歷屆與名次

搜尋同名 IEEE ClimateChain 2025、2024、歷屆 winners，並查核現行官方活動頁，**沒有找到可信的同名歷屆得獎名單**。這不證明以前從未舉辦；目前不能稱任何作品為「去年冠軍」。[ClimateChain 官方頁](https://ieee-climatechain-hack.devpost.com/)。

CarbonShield、AION V3 的 Devpost 頁皆列 Submitted to IEEE ClimateChain；屬本屆公開作品，並非已知得獎者。官方 Project gallery 仍顯示尚未公布，兩個作品不代表完整競品集合。[CarbonShield](https://devpost.com/software/carbonshield)、[AION V3](https://devpost.com/software/aion-v3-sovereign-value-os)、[官方作品集](https://ieee-climatechain-hack.devpost.com/project-gallery)。

OneAquaHealth 為不同的 IEEE 環境類競賽。主辦最新公告寫仍在評選、預計 October 25 於 IEEE iGET 公布得獎者；因此以下參考投稿不能稱為冠軍。[主辦公告，Winner Announcement 段](https://oneaquahealth-ieee-hackathon.devpost.com/updates/46903-thank-you-for-your-oneaquahealth-submission-join-us-at-ieee-iget-2026)。

## 功能、技術與證據

「已讀程式」表示確認實作存在；「作者報告」表示未獨立重跑；「已讀公開頁」與「已看截圖」不等於完成端到端測試。

| 對照 | 真正核對到的功能與證據 | AI / Blockchain | Demo、UI 成熟度 | 限制 |
|---|---|---|---|---|
| CarbonShield | 匿名 Repo 可讀；已讀模型、AuditorPage、合約、驗證器及已提交結果。44 個專案、43 個可用標籤是其結果檔內容，未重跑 | `make_model()` 實作 ElasticNet／淺層 GradientBoosting；六類假設壓力分析。合約 `anchorAudit()`、驗證器重算 SHA256／讀 anchor，部署檔寫 `local-dev` | 程式確有專案選擇、敏感度卡、來源／supported 狀態、Hash／鏈狀態；Devpost 有影片嵌入。未取得可操作公開網站，未觀看完整影片，不能判定實際延遲或視覺優於 GridProof | 碳信用稽核而非能源調度；存在提交的報告不代表結論獨立驗證；不推論所有來源轉換或部署安全性已通過 |
| AION V3 | 已讀作者的機會→決策→執行→證據敘述；明確區分 Expected / Verified Value，尚未執行時 Verified Value 可為 €0 | 作者稱使用 AI 機會／風險評估，Built With 含 OpenAI、Ethereum、Hyperledger；沒有據此確認具體模型、合約或公鏈交易 | 有影片嵌入；檢視頁未見公開 Repo／可操作 Demo 的 Try it out 連結，未能獨立檢視完整畫面。「企業級 UX」目前屬作者定位 | 作者將經濟＋環境驗證列為後續工作；不能把預期金額或環境效益當成已量測結果 |
| Second Look（OneAquaHealth 參考投稿） | 公開首頁及 `/judges` 可匿名讀取；已看提交的 landing、judges、verify 手機截圖；Repo 有結果／來源與截圖路徑 | 作者使用視覺模型通過特徵測試後才可追問；Hash-chain audit + OpenTimestamps，audit log 與 blockchain 明確區分 | 一個問題開始、單一主要按鈕；評審頁列各步時間及預期結果。截圖是作者提交的歷史畫面，未操作填答或提交觀察 | Repo 明確說未取得可用的完成者資料，尚未證實人類受益；live creek checker 當時關閉，Judge demo 不即時呼叫模型。測試數不代表實際採用 |
| GridProof（本地基準） | 本地實测 122 天；可執行排程、來源重建、物理驗證、重新 Hash 偽造拒絕、錄製結果離線展示；詳細紀錄見連結 | 真正使用原訓練 LightGBM 樹；MILP 處理 EV／電池／批次；本機 EVM scope／revision／revocation，公鏈尚未部署 | 四頁及既有 Browser E2E 可重現。此表不宣稱外部評審或非工程使用者已完成可用性測試 | 一個宣告的校園模板、模擬需求／電池／PV／費率；有真實來源但不是實際場域減碳；匿名 Repo／正式影片／公開服務待交付 |

CarbonShield 的讀碼快照固定於 commit `1a1471a1859027bc8c61546f554226944289b550`：[模型實作](https://github.com/saideeksha19/carbonshield/blob/1a1471a1859027bc8c61546f554226944289b550/src/carbonshield/ml/models.py)、[驗證器](https://github.com/saideeksha19/carbonshield/blob/1a1471a1859027bc8c61546f554226944289b550/src/carbonshield/blockchain/verifier.py)、[合約](https://github.com/saideeksha19/carbonshield/blob/1a1471a1859027bc8c61546f554226944289b550/artifacts/CarbonShieldAnchor.sol)、[UI 原始碼](https://github.com/saideeksha19/carbonshield/blob/1a1471a1859027bc8c61546f554226944289b550/frontend/src/pages/AuditorPage.tsx)、[模型結果摘要](https://github.com/saideeksha19/carbonshield/blob/1a1471a1859027bc8c61546f554226944289b550/outputs/phase2/validation_summary.json)、[本地部署紀錄](https://github.com/saideeksha19/carbonshield/blob/1a1471a1859027bc8c61546f554226944289b550/outputs/blockchain/deployment.json)。

AION 的技術／效益均為 [作者頁 What it does、How we built it、What's next 段](https://devpost.com/software/aion-v3-sovereign-value-os) 的可核對敘述，並非本輪 runtime 檢驗。

Second Look：[投稿頁](https://devpost.com/software/buzzbee)、[匿名評審入口](https://second-look-79t.pages.dev/judges)、[Repo 的 live checker／研究限制說明](https://github.com/alejandro-publius/second-look)、[截圖及 mock 標示](https://github.com/alejandro-publius/second-look/blob/main/docs/screens/README.md)。本輪視覺檢查的是該頁列出的 `landing.webp`、`judges.webp`、`verify.webp`；沒有安裝或呼叫模型。

GridProof 本地根據：[升級報告](UPGRADE_REPORT.md)、[122 天結果](COMPETITION_EVALUATION.md)、[驗證紀錄](VALIDATION.md)、[來源血緣](LINEAGE_VERIFICATION.md)、`frontend/components/judge-panels.tsx` 的 PolicyMatrix／TradeoffPlot／VerificationLayers，以及 `dashboard.tsx` 的實際 API 動作。

## 相對強弱與值得採用的呈現

| 參考 | GridProof 相對優勢（限已知功能） | GridProof 相對弱點 | 這輪值得學習 | 不值得現在模仿 |
|---|---|---|---|---|
| CarbonShield | 前瞻調度的碳／成本／尖峰決策與 deadline／SoC 約束，加上獨立來源映射；不是只評估歷史碳信用假設 | 對方已公開 Repo；我們的能源證據鏈若藏在 JSON，評審不會理解差異。沒有證據可稱我們的稽核方法全面領先 | 把資料→決策→拒絕攻擊做成明確步驟；來源不足顯示不支持，來源和限制就在結果旁 | 複製 REDD+ 六壓力維度、重新收集森林資料或增加更多 ML，與能源使用者的決策不相干 |
| AION | 有實際可重跑的能源情境、排程與固定全期間結果；能展示變更目標後的可計算取捨 | 首頁仍可能先像工程監控台，未立即說明設施管理人員下一步；AION 的敘事直接連到管理者價值，但其實作成熟度未證實 | 讓「模擬決策結果」與「已驗證報告」分開顯示；一眼看出誰採用、要做哪個決策 | 橫跨採購／庫存／物流的 Value OS、Points 或泛企業 ROI 儀表，會稀釋校園微電網問題 |
| Second Look | 能真正求解有約束的可執行能源計畫，輸出可驗證；技術領域不同，不做減碳或 AI 效能高低比較 | 對方已有匿名可讀的 judge start；GridProof 仍缺授權後的外部可操作入口和真人 60 秒理解證據 | 單一問題開場；60 秒：選目標→比較結果→看排程→驗證／拒絕；步驟旁有預期畫面與耗時；Mock／Replay 明示 | 為了追上測試數而增加測試；照搬照片測驗、FHIR、研究招募或水域社群，均非目前能源使用需求 |

## 下一個可交付產品差異

第一個畫面應回答「設施管理人員要在明早前充完 EV，又不能把尖峰推高；哪個計畫更合適？」然後讓使用者切換 Carbon／Cost／Peak／Balanced，看同樣需求下三項數值和負載曲線如何改變。這是產品建議，不是新 benchmark 成果。

第二個記憶點是**改寫碳強度並重新 Hash，Integrity 仍成立，但 Source Lineage 拒絕**。將原始值、偽造值、拒絕理由放在四層狀態旁，超過整頁 Hash／receipt JSON 的溝通價值。第三個是離線可看同一案例，明確標為 Recorded Replay／Local Verification，而非假稱已連公鏈。

公開服務可讓評審自行驗證，但要經使用者授權；本輪不以新增公鏈名詞、競品未知實作或不同領域的百分比來推定得獎優勢。這份比較也不提供名次預測。
