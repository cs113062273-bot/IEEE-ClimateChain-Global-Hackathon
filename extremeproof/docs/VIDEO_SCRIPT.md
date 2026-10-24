# ExtremeProof 示範影片腳本（目標 4:52，上限 5:00）

畫面操作用中文寫，旁白（英文）照念。每段列出「畫面上必須看得到」的數字：念到那個數字時，它要出現在畫面上。以下所有點擊與數字，都是 2026-10-24 在全新啟動的本機版上實際操作過的結果。

## 錄影前準備（不計入影片）

1. 關掉所有舊的 ExtremeProof 終端機。在 repository 根目錄開一個 PowerShell，執行：
   ```powershell
   extremeproof\.venv\Scripts\python -m extremeproof.scripts.stack
   ```
   等到出現 `web    http://127.0.0.1:3000` 和 `press Ctrl+C to stop`（約 20–30 秒）。這個視窗不要關。
2. 開一個 **無痕視窗**（Edge `Ctrl+Shift+N` / Chrome `Ctrl+Shift+N`），視窗大小約 1440×900，縮放 100 %，淺色主題。無痕是必要的：一般視窗如果存有上一次的協議，畫面會出現 "Could not restore the previous agreement"。
3. 分頁 1：`http://127.0.0.1:3000`。右上角 **Demo chain clock** 必須是 `2021-05-01 … · simulated`。如果不是，先往下捲到第 3 步按 **Reset demo chain**，再回到最上面。
4. 分頁 2：`https://cs113062273-bot.github.io/IEEE-ClimateChain-Global-Hackathon/`（先載入好）。
5. 第二個 PowerShell 視窗，先 `cd $HOME\Downloads`，字體放大到約 18 pt。
6. 下載資料夾裡如果已有 `extremeproof-agreement-1.zip` 或 `extremeproof-agreement-1\`，先刪掉。
7. 要等待的地方（第 4 步第一顆按鈕約 12 秒、一鍵案例約 14 秒），剪輯時可以加速，旁白照念。

---

## 00:00–00:20　開場：問題

**畫面**：分頁 1 最上方，不捲動。滑鼠依序指向右側卡片的 **Muğla weather station 4 days**、**ERA5 reanalysis 10 days**，再指向下方黃色與灰色長條。

**必須看得到**：4 days、10 days、35,000 in dispute、15,000 back to the fund at once。

**旁白**：
> Summer 2021 in Muğla, Türkiye, a summer of forest fires. A relief fund promised a farmers' cooperative a heat payment. The weather station counted a four-day hot spell. The ERA5 reanalysis counted ten. Same summer, same rule, two honest records — and fifty thousand in relief depends on which one you pick.

## 00:20–00:38　怎麼運作與影響

**畫面**：往下捲到 **How it works**，停在四個步驟（Compare / Lock / Settle / Verify）；再往下一點，停在綠色 **Real-world impact** 方框。

**必須看得到**：四個步驟卡片；96%。

**旁白**：
> ExtremeProof fixes the climate rule before summer, lets a contract count the heat from both records, and lets anyone recheck it. Replayed over 2021 to 2025 at ten Turkish stations, 96 percent of the money both records agreed on would have been released before the season ended.

## 00:38–01:02　第 1 步：什麼算「異常炎熱」

**畫面**：點上方導覽列 **1 Climate**。
1. **Place** 點 **Antalya**，**Data** 點 **Weather station**（Summer 維持 2024）。指向圖下方灰色缺值列和右側 **91 of 122**。
2. **Place** 點回 **Muğla**，**Data** 點 **ERA5 reanalysis**。指向右側 **10 summers**。
3. 往下捲到 **Sixty summers in Muğla** 長條圖，指向說明裡的 **9 of 30** 和 **19 of 30**。

**必須看得到**：91 of 122；10 summers；9 of 30 → 19 of 30。

**旁白**：
> Unusually hot means above this place's own 90th percentile for that day, over thirty years. The Antalya station is missing 91 of 122 summer days in 2024 — someone has to fill those gaps. In Muğla, the choice of normal alone flips ten summers. And the heat is moving: six-day spells went from 9 to 19 summers in thirty.

## 01:02–02:00　第 2 步：簽約前先設計規則

**畫面**：點導覽列 **2 Rule**。

1. **1/4 Purpose**（約 5 秒）：指向已選的 **1 in 5**、**grows with the heatwave**、**returns to the fund**。
2. **2/4 Compare complete rules for Muğla**（約 15 秒）：依序指向表格這幾列：
   - **Community paid**：Your rule now **1 in 2.1**，Option A **1 in 5.0**（綠色 on target）
   - **Payments that hinge on one day**
   - **Decided by the data alone**：87% 對 92%
   - **Heat that met this definition**：**6 → 16**
3. 點 Option A 下方的 **Adopt this rule**。指向 **3/4** 的綠色標籤 **meets your purpose: pays 1 in 5.0**。
4. 點 **Adjust every setting** 展開，停 2 秒讓設定項出現（gap filling、base period、percentile、天數滑桿、payout ladder、data limits）。點一下 **For at least 8 days in a row** 的滑桿，按鍵盤 **←** 兩次，標題變回 **6 days**。再點 **Adjust every setting** 收起來。
5. **4/4 Check the consequences**：指向 **3 of 5 summers need a decision from you now** 和 2021 那一行。在 **Decide now** 點 **go to the cooperative**，指向下面那行 **the cooperative receives 105,000 DEMO: 40,000 by the end of the season, 65,000 about 30 days later**，再指向 **disagreed in 15 … of the 60 summers**。
6. 往下捲，點 **Inspect all 61 summers, the alternative gap rules and full-history counts** 展開，停在藍色方框 **Why quantile mapping is the default gap fill**。
7. 再往下，點 **The same rule at all 14 stations: where the record decides the payment** 展開，指向 **6 of 10 places**、**No station normal** 的四列（İzmir、Konya、Mersin、Adana），再捲到國外那段 **3 of 3 places**。
8. 往上捲回黃色決策框，點 **Next: review & sign this rule for 2021 →**。

**必須看得到**：1 in 2.1、1 in 5.0、6 → 16、meets your purpose、3 of 5 summers、105,000 DEMO、3 of 9 heatwaves 那段藍框、6 of 10 places、No station normal。

**旁白**：
> Before anyone signs, the parties say what the money is for: about one summer in five, more for a longer heatwave. The finder compares complete rules over thirty summers: how often they pay, how many payments hinge on one day, how much sits in dispute, and how warming shifts them. One click adopts a rule, and every setting stays editable; here I keep the six-day rule from the opening. Three of the last five summers need a decision, so the parties decide now: an unresolved dispute pays the cooperative. We tested AI for filling station gaps: LightGBM had the lowest average error but missed three of nine heatwaves, so it was not adopted. The same rule runs at fourteen stations; at four in Türkiye, the public record cannot even define a normal.

## 02:00–02:32　第 3 步：季節開始前鎖定規則

**畫面**：頁面自動捲到第 3 步。
1. 指向 **What this signed rule means**，再指向 **“Unusually hot”, day by day** 那一列（122 daily thresholds）。
2. 指向 **Fingerprint** 的長雜湊和綠色 **✓ your browser computed the same fingerprint**。
3. 點 **Download a summary for members (EN/TR)**，在瀏覽器下載提示中打開這個 HTML，停 3 秒（英文／土耳其文的一頁說明），關掉這個分頁回來。
4. 點 **Show the exact text that is signed**，停 2 秒，再點一次收起。
5. 點 **Fund proposes it on chain** → 出現 **✓ contract terms match the signed text**。
6. 右邊三張卡片依序點：**Sign fingerprint + deposit**（Relief fund）、**Sign fingerprint**（Farmers' cooperative）、**Sign fingerprint**（Independent checker）。每張都變成 **✓ signed**。
7. 指向 **Agreement #1 · Locked** 和 **Still in escrow 50,000.00 DEMO**，再指向左上 **Demo chain clock 2021-05-01 · simulated**。

**必須看得到**：122 daily thresholds、兩個綠色 ✓、三個 ✓ signed、Locked、Still in escrow 50,000.00 DEMO。

**旁白**：
> The rule, its 122 daily heat thresholds for each record, and every contract term become one text with one fingerprint. My browser recomputes it, and the contract's terms are read back against it. The cooperative gets a plain-language summary in English and Turkish. The fund proposes, then the fund, the cooperative and the independent checker each sign; the fund's signature locks fifty thousand in escrow. After the season starts, the contract refuses to lock anything.

## 02:32–03:17　第 4 步：合約自己讀熱浪

**畫面**：點導覽列 **4 Season**。
1. 點 **Play summer 2021**，圖表約 4 秒畫完。
2. 點 **1 · During the season: release as the heat builds**（約 12 秒，上方日期會一路往前跑）。完成後指向右邊 **What happened** 的 ERA5 posted 66 days 那行。
3. 點 **2 · Providers fetch the season data and report**。指向兩張提供者卡片：**contract: rule not met · 4 days**、**contract: rule met · 10 days**，以及 Fetched after the season 的雜湊。
4. 點紅色 **Attack: ERA5 provider lowers the signed hot line by 2 °C** → 指向 **rejected by the contract (NormalMismatch)**。
5. 點 **3 · Settle (anyone can)**。指向資金框：**Held in dispute 35,000.00 DEMO**、**Returned to fund 15,000.00 DEMO**，以及三方的 vote pay / vote refund 按鈕（不要點）。
6. 點 **Skip 30 days → apply the signed fallback**。資金框變成 **Paid to cooperative 35,000.00 DEMO**。
7. 在 **What happened** 裡往下捲，指向任一行的 `tx … · block … · gas · emits …`，最後指向底部 **10 transactions, 1,726,183 gas**。

**必須看得到**：4 days / 10 days、NormalMismatch、35,000 held / 15,000 returned、Paid to cooperative 35,000.00、10 transactions。

**旁白**：
> The summer plays out on a simulated clock. Each week the providers post the readings already published; the contract compares every day with the signed threshold and counts the spell itself. The station never qualifies, so nothing is released early. After the season: station four days, ERA5 ten. The ERA5 provider tries to lower the signed hot line by two degrees: rejected. Settling, the thirty percent neither record supports goes straight back to the fund; only the difference, thirty-five thousand, is disputed. Nobody votes, so after thirty days the fallback signed in May pays the cooperative. Every step is a real transaction, read from its receipt.

## 03:17–03:25　重新整理也能從鏈上恢復

**畫面**：按 **F5**。載入後點導覽列 **3 Lock**，指向提示 **Restored agreement #1 from the live chain, including its receipts and provider evidence.**

**旁白**：
> Reload the page, and the agreement is rebuilt from the chain itself, not from the browser.

## 03:25–03:43　第 5 步：試著作弊

**畫面**：點導覽列 **5 Attack**，由左到右：
1. **Change the normal after the heatwave** → **Try it**：出現 **refused · WrongStatus** 和 **✕ 11 of 47 checks failed**。
2. **Edit one temperature reading** → **Try it**：**✕ 2 of 41 checks failed**。
3. **Hide or change a provider's evidence** → **Try it**：**✕ 2 of 47 checks failed**；再點 **Drop the evidence**：**✕ 2 of 22 checks failed**。

**必須看得到**：四個紅色 ✕ 結果。

**旁白**：
> Try to cheat. Re-sign the rule with a different normal after the heatwave: the contract refuses, and the verifier flags eleven checks. Change one temperature to forty-five degrees, flip a provider's verdict, or hand over the bundle without the evidence: every altered bundle fails.

## 03:43–04:01　第 6 步：不用相信我們，自己驗

**畫面**：
1. 點導覽列 **6 Verify**，點 **Run the independent verifier** → **✓ all 47 checks passed**。
2. 點 **Download verification bundle (.zip)**。
3. 切到第二個 PowerShell（在 Downloads），依序打：
   ```powershell
   Expand-Archive extremeproof-agreement-1.zip -DestinationPath . -Force
   cd extremeproof-agreement-1
   python verify.py .
   python verify.py . --rpc http://127.0.0.1:8545
   ```
   第一個結果最後一行是 **42/42 checks passed**，第二個是 **44/44 checks passed**。

**必須看得到**：all 47 checks passed、42/42、44/44。

**旁白**：
> The verifier is one Python file, standard library only, sharing no code with the engine. It recomputes every threshold and every season day from the raw data and checks every term and payment. Offline: forty-two of forty-two. Against the live chain: forty-four of forty-four.

## 04:01–04:18　一鍵案例：季中就付款

**畫面**：切回瀏覽器，按 **Home** 回到頁首，點 **A heatwave that pays →**。頁面會自己簽約並跑完整個夏天（約 14 秒，不用點任何東西）。跑完後：
1. 指向圖上六月的綠色放款標記。
2. 在 **What happened** 指向 **2024-06-15 Released 35,000.00 DEMO** 和 **2024-06-22 Released 15,000.00 DEMO**。
3. 指向資金框 **Agreement #2 · Paid to cooperative 50,000.00 DEMO**。

**必須看得到**：35,000 於 2024-06-15、15,000 於 2024-06-22、50,000.00 paid。

**旁白**：
> One click runs a whole agreement. Antalya, summer 2024: both records show a long heatwave by mid-June, so the contract releases thirty-five thousand on the fifteenth of June and the rest a week later — during the heat, not after September.

## 04:18–04:35　評審不用安裝也能看

**畫面**：切到分頁 2（GitHub Pages）。點導覽列 **3 Lock**，點分頁按鈕 **Antalya 2023 · too little data**。往下捲到第 4 步的紀錄，指向 **NO VERDICT: more filled days than the agreed limit** 和最後 **50,000.00 DEMO paid to the cooperative (pay)**。再捲到第 6 步，指向 **Download bundle** 和 **Download verify.py**。

**必須看得到**：網址列的 github.io 網址、NO VERDICT、Download verify.py。

**旁白**：
> Judges can open the same project online without installing anything. It replays three recorded agreements, including this one: the station has too little data, so its provider abstains instead of saying no, and the signed fallback decides. Every bundle can be downloaded and verified.

## 04:35–04:52　結尾

**畫面**：在分頁 2 按 **Home** 回到頁首，停在 **Real / Executed / AI tested / Simulated** 那一列。

**必須看得到**：Simulated 那一格（Fund, cooperative, checker, DEMO money, chain clock）。

**旁白**：
> What is real: the weather records, the contract and the verifier. What is simulated: the parties and the money. A blockchain doesn't make data true. It makes the rule, and what happens when records disagree, impossible to change after the heat. ExtremeProof.

---

## 錄完檢查

- [ ] 00:00 段畫面上看得到 4 days 和 10 days。
- [ ] 第 2 步最後回到 6 天規則，再按 **Next: review & sign**（標題要寫 6+ days）。
- [ ] 第 4 步結尾是 Paid to cooperative 35,000.00 / Returned to fund 15,000.00。
- [ ] 終端機畫面出現 42/42 和 44/44。
- [ ] Simulated 那一格至少出現一次。
- [ ] 旁白沒有說 insurance、real users、減碳或避免損失。

## 出錯時

| 狀況 | 處理 |
|---|---|
| 第 3 步出現 "Could not restore the previous agreement" | 不是無痕視窗。按 **Forget saved view & start fresh**，或改用無痕視窗重來。 |
| Season to protect 的 2021 顯示 (already started) | 按 **Reset demo chain**，從 00:38 重錄。 |
| 頁面寫 "The live part needs the local chain" | 第一個 PowerShell 的 stack 沒在跑。重新執行準備第 1 點，重新整理頁面。 |
| `python` 找不到 | 改用 `..\..\Desktop\IEEE-ClimateChain-Global-Hackathon\extremeproof\.venv\Scripts\python verify.py .`（依你的 repository 位置調整）。 |
