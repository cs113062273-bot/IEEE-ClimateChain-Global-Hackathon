# Claude refinement handoff

請接手 ExtremeProof 做下一輪產品 refine。使用者要爭取 IEEE ClimateChain 第一名，
也要求批評和修改都與競賽價值有關。不要再次自行換題，不要只做審查報告。
先讀適用 AGENTS.md、git status、現有未提交變更；保留別人的工作與 git index。

本輪 Codex 已經實作「熱浪救助協議的簽署前決策比較」。請先實際操作，
再選少數最有價值的改進直接完成。這不是要求維護 Codex 的設計；你可以反駁或改善，
但要用實際操作、具體使用者決策或實驗結果支持，不以新增功能數或測試數為目標。

## 先讀、先驗證

- `extremeproof/README.md`
- `extremeproof/docs/DECISION_REVIEW.md`：使用者、比較方式、結果及限制。
- `extremeproof/web/components/DecisionReview.tsx`、`Designer.tsx`、`Agreement.tsx`、`App.tsx`
- `extremeproof/web/lib/comparison.ts`、`rule.ts`
- `extremeproof/scripts/compare_relief.py` 及 `experiments/decision_comparison.json`
- 原有 climate engine、獨立 verifier 和 ML 報告，僅在理解目前功能所需範圍閱讀。

重新讀官方，而非推測評審偏好：
- https://ieee-climatechain-hack.devpost.com/
- https://ieee-climatechain-hack.devpost.com/rules
- https://ieee-climatechain-hack.devpost.com/project-gallery

外部比較至少包括 Etherisc、Arbol、RainGuard，與同場公開作品 PLUME、CanopyProof；
連結和查核範圍見 DECISION_REVIEW.md。不要照單全收競品宣傳，也不要假設自己獨有某功能。

## 已整合的流程

主要使用者：地方熱浪救助基金的協議設計者，和社群代表、查核者共同決定付款規則。
這是季後結算，不是災前預警，不是已驗證的保險或真實救助服務。

首頁先比較相同五個夏季、門檻、補值規則、資料限制、每季 50,000 DEMO 和 fallback：
單氣象站、單 ERA5、實際雙來源協議。單來源是反事實比較，並沒有新增可部署的合約模式。
點年份看付款與等待後果，再點 review，進入同一套規則的三方簽署、回放、結算、下載查驗。
提案後的摘要從協議文字讀取；修改設計區不會改寫已提案的協議。

比較 JSON 可以下載，包含輸入表 SHA-256、規則、逐年結果及時間假設。
它是未簽署的設計報告；真正的執行證據仍用原有 verification bundle。
61 年歷史和其他補值方式仍在折疊區，沒有刪除。

## 不得把負面結果藏掉

- Antalya 預設在 2021–2025 與單來源相同，雙來源沒有展示額外付款利益。
- Muğla 預設多一場爭議；refund fallback 讓社群少收到一筆款，且多等約 30 天。
- Antalya 限制最多補 60 天時，有三個夏季缺資料；fallback 決定最後拿不拿得到款，
  模型中每次約等 44 天。
- 來源分歧不是損失真值。更多付款、更少付款、更多爭議，都不能自行稱為成效。
- 時間是「及時回報、沒有一致協商、及時執行 fallback」模型，排除資料公布延遲；
  不是實測或保證時限。實際需要有人送交易。
- 2021–2025 已多次檢視；這是新增的探索性設計比較，不是獨立驗證。
- A 用 ERA5 補值，B 也是 ERA5，不能稱為兩個完全獨立觀測。
- AI 未被採用有既有實驗支持；不要為了標籤硬加一個較差模型。

## 請優先 refine 的問題

1. **五分鐘內是否能做出決定？** 新使用者能否說出目前哪個情境有風險、付款會怎樣、
   fallback 怎麼影響社群、接下來該做什麼？請改善真正阻礙理解的互動與文案。
   若用情境測試或訪談，要區分模擬檢查與真人回饋，不能編造訪談。
2. **具體資助用途是否足夠清楚？** 確認季後付款對應哪種合理的救助支出與採用流程。
   可查成熟方案／公開實務作參照；沒有合作就不能暗示已有基金或社群採用。
3. **是否真的比簡單方案多一個有用決策？** 可以改進比較呈現或加入小而有用的分析，
   但不要把「雙來源」自動當成優點，不要以缺漏資料換出漂亮結果。

User override (2026-10-21): no further mobile-specific implementation or phone testing. The official rules do not require mobile support. Prioritise the desktop competition flow; comparison, export, signed terms and execution must remain consistent.
這輪不處理影片、投影片、正式提交、帳號、公開部署；不需要擴建保險平台或新增災種。
不改 root README 的既有提交時機安排。不清理或重新 staged 先前的 runtime 檔案。

## 本機指令

```powershell
# repo root
extremeproof\.venv\Scripts\python -m extremeproof.scripts.compare_relief
extremeproof\.venv\Scripts\python -m extremeproof.scripts.stack
# extremeproof/web
npm.cmd run typecheck
npm.cmd run build
npx.cmd playwright test
```

compare_relief 不需要服務或帳號；會執行與 UI 相同的 TS 模組，並用 Python engine
重算原始資料，查 200 筆來源／策略結果。它不是 200 個獨立樣本或成效測試。
瀏覽器測試會 reset 本機 demo chain，不要指向任何公開鏈。

最後交付：實際完成的修改、為何有用、相較目前版本的可觀察差異、跑過的檢查，
以及最可能讓作品輸掉的剩餘問題。不要只給建議，不要宣稱可以保證名次。
