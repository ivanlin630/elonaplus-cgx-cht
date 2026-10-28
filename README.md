# Elona+ Custom-GX 繁體中文化工具

把 [Elona+ Custom-GX](https://github.com/JianmengYu/ElonaPlusCustom-GX) 2.32.1.2 翻成繁體中文的工具與譯文表。
不含遊戲本體、Custom-GX 原始碼或任何第三方譯文，只有我們自己做的工具、名詞表與機器翻譯結果。

## 做法概要

- **譯文不寫進原始碼**。HSP 3.4 的編譯器只認 Shift-JIS，中文直接放進字串會讓編譯器切錯字元而崩潰。
  所以原始碼裡被翻譯的字串換成 `zh(編號)`，中文放在外部文字表 `data\zh_text.bin`／`.idx`，
  遊戲啟動時由 `tools/zh.hsp` 讀進來，只用位元組層級的指令取字。
- **中文用 Shift-JIS 存**。HSP 內建的 `instr`、`strrep`、`split` 和遊戲自己的換行程式都寫死照
  Shift-JIS 判斷字元邊界，Big5／GBK 的中文會被從中間切開（委託板 `{reward}` 不會被替換、對話在換行處亂碼）。
  改用 Shift-JIS 後這些處理天生正確，而且 HSP 建字型時寫死日文字集，**繁中 Windows 不用 Locale Emulator 也能正確顯示**。
  代價是日文字碼沒有的字要換替身（`tools/sjis_map.py`），例如 你→汝、吧→罷、嗎→麼、咖啡→珈琲。
- **翻譯來源**：專有名詞 4,243 條由人工翻譯（`work/glossary.tsv`）；句子用本機
  [SakuraLLM](https://huggingface.co/SakuraLLM/Sakura-14B-Qwen2.5-v1.0-GGUF) 14B 機翻，附帶名詞表；
  再用 Qwen2.5-14B-Instruct 潤稿（`tools/polish.py`）。NPC 語尾表（です、だぜ、俺…）另外人工對應（`tools/tone_map.py`），
  個別錯譯由 `tools/fixes.py` 修正。

## 需要的東西

| 項目 | 放在哪 | 來源 |
|---|---|---|
| Custom-GX 原始碼 | `src/`（= repo 的 `2.05-custom-gx/` 資料夾） | JianmengYu/ElonaPlusCustom-GX，commit `aebe0d8`（2.32.1.2） |
| HSP 3.4 SDK | `hsp34/` | <https://www.onionsoft.net/hsp/file/hsp34a.zip>（zip 內檔名是 Shift-JIS，解壓時注意） |
| Elona+ 2.32 本體＋Custom-GX 發布檔 | 任意遊戲資料夾 | 見 Custom-GX README |
| Python 3.11（64 位元） | | `pip install opencc opencc-python-reimplemented` |
| （選用）llama.cpp＋Sakura／Qwen 模型 | 例如 `F:\sakura` | 只有要重新機翻或潤稿時才需要 |

## 產生翻譯版

```bash
# 1. 抽出所有日文字串（lang() 與直接字串），中文欄先空著
python -I tools/extract.py src work
# 2. 依序填入譯文：名詞表 → 機翻 → 潤稿 → 語尾表 → 人工修正
python -I tools/apply_gloss.py
python -I tools/apply_mt.py
python -I tools/apply_polish.py      # 有 work/mt/polish.tsv 時
python -I tools/apply_tone.py
python -I tools/fixes.py
# 3. 寫回：原始碼保持 Shift-JIS，中文進文字表（預設 cp932）
python -I tools/inject.py src work/strings.tsv work/src_tbl --table work/zh_text
python -I tools/patch_src.py work/src_tbl        # HSP 3.4 相容修正（見下）
python -I tools/scene.py build work/src_tbl      # 劇情過場 scene1.hsp
python -I tools/check_structure.py src work/src_tbl   # 應為 0：改寫沒有動到參數結構
```

編譯（32 位元 PowerShell；要編哪一份由同資料夾的 `build-src.txt` 指定，一行相對路徑）：

```powershell
Set-Content build-src.txt 'work\src_tbl'
C:\Windows\SysWOW64\WindowsPowerShell\v1.0\powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\build.ps1
```

把 `work\src_tbl\elonapluscgx.exe`、`work\zh_text.bin`、`work\zh_text.idx` 複製到遊戲資料夾（後兩個放 `data\`）。

### data 資料夾的文字檔（閒聊、書、說明書…）

也是我們自己從 Custom-GX 的日文 data 機翻的（`tools/data_tr.py`）：

```bash
python -I tools/data_tr.py collect "<Custom-GX 遊戲>/data"   # 列出待譯單位 work/data_units.txt
python -I tools/mt_sakura.py --lines work/data_units.txt
python -I tools/data_tr.py build "<Custom-GX 遊戲>/data" work/data_zh
```

閒聊、提示、委託、說明書逐行翻；書的內文先把硬換行併回段落再翻、照 20 個全形字重新換行；
隨機人名的音節（name.csv）用固定音譯表；隨機稱號詞彙（ndata.csv）逐欄翻、分類欄不動。
`{だ}`、`{player}`、`<emp1>` 等標記全部原樣保留。`ndata-e.csv`、`autopick.txt` 不動。

（`tools/merge_data.py` 是舊做法：拿 2.30 簡中漢化版的譯文轉繁體。那是漢化組的作品，本 repo 不含其輸出。）

### 一次重建

```bash
bash tools/rebuild.sh "<Custom-GX 遊戲>/data"
```

依序抽取、填譯文、寫回、修補、劇情、data、結構檢查、編譯。不會自動跑機翻；報告裡有未譯句子時先跑 `tools/mt_sakura.py`。

## 更新到新版 Custom-GX

1. 換掉 `src/` 為新版原始碼。
2. `bash tools/rebuild.sh` 第一次跑：譯文是用**日文原文**對應的，沒變的句子自動沿用舊譯文（名詞表、機翻、潤稿、語尾表、人工修正都是），報告會列出新增的未譯句數。
3. `python -I tools/mt_sakura.py` 只送空的句子；劇情與 data 同樣只補新增部分。
4. 新的怪物、物品名：`python -I tools/glossary.py work/strings.tsv work/glossary.new.tsv` 找出沒有譯名的專有名詞，補進 `work/gloss/` 後 `python -I tools/gloss_fill.py`。
5. 再跑一次 `bash tools/rebuild.sh`。

`tools/patch_src.py` 的修補是找特定程式碼插入的；新版若改了那段，腳本會直接報錯停下，不會默默套錯。

## 不能翻的字串

有些日文字串是程式拿來比對的資料，翻了遊戲邏輯就會壞，`tools/extract.py` 會自動跳過：

- `==`、`!=`、`case`、`instr()` 比對用的字串。
- 性別（男性、女性、自称男性…）：存進角色資料後再拿來比對。
- 種族的身體部位表（`頭|体|背|手|…`）：`*set_figure` 每 3 個位元組切一段再跟日文比對，決定裝備欄位。

### 2.30 簡中版的舊存檔

```bash
python -I tools/convert_save.py "<遊戲>/save/sav_xxx"
```

只轉文字檔（角色名、地圖名、委託名、新聞、讀檔資訊），二進位資料不動；轉之前會先把整個存檔複製到 `sav_xxx.gbk-backup`。
備份資料夾以 `sav_` 開頭，會出現在讀檔清單裡，確認沒問題後請移到遊戲資料夾外。

## 對 Custom-GX 原始碼的修改（`tools/patch_src.py`）

- `sound.hsp` 的 `sndstop`：原本在音效設定為 2（MCI）時呼叫 `mmstop 聲道`，這要 HSP 3.5 以上；
  用 HSP 3.4 編譯時每次對話結束都會跳「HspError 16 參數數量過多」。改成在 MCI 模式下不停止聲道。
- `main.hsp`：開頭呼叫 `zh_load`，`zh.hsp` 接在程式最尾端，讓新增的變數與外部函式排在所有原有項目之後。

## 機器翻譯（選用）

```bash
python -I tools/mt_sakura.py                  # 送 strings.tsv 裡還沒譯的句子
python -I tools/mt_sakura.py --lines work/scene_lines.txt   # 劇情過場
python -I tools/polish.py                     # Qwen 潤稿（伺服器換成 Qwen 模型）
```

伺服器是 llama.cpp 的 `llama-server`，OpenAI 相容端點 `127.0.0.1:8080`。
`mt_sakura.py` 會把 `{0}` 換成 `X1` 代號（Sakura 會吃掉 `{0}`）、在 `\n` 等控制碼處切段、檢查標記數量，失敗的句子留空可重跑。

## 已知限制

- 日文字碼沒有的字以替身顯示，全部列在 `tools/sjis_map.py`。
- Custom-GX 只有英文的部分（自訂設定選單、卡牌模組等，約 1,500 條）尚未翻譯。
- 33 列機翻在變數位置上對不上原文，保留日文。

## 致謝

Elona（Noa）、Elona+（Ano）、Custom-G／Custom-GX（Ruin0x11、JianmengYu）、HSP（onion software）、SakuraLLM、Qwen、OpenCC。
本 repo 只包含翻譯工具與譯文；遊戲本體與原始碼的權利屬於各自的作者。
