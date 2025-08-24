# SFBuff Ranked History Scraper
* SFBuff の **Ranked History** から、試合ごとのレートを引っこ抜いて **JSON** に出力します。
* ついでに **PNG グラフ**も作れます（移動平均・EMA対応）。

## 準備

### 1) Python を入れる

[公式ページ](https://www.python.org/downloads/)から頑張ってインストールしてください。
インストール時に **“Add python.exe to PATH”** にチェックを入れるか、あとから PATH を通しておくと幸せになれます。

### 2) 仮想環境（任意だけどオススメ）

```bash
python -m venv .venv
# mac/Linux
source .venv/bin/activate
# PowerShell
.venv\Scripts\Activate.ps1
# cmd
.venv\Scripts\activate.bat
```

### 3) 依存パッケージ

```bash
pip install --upgrade pip
pip install requests beautifulsoup4 matplotlib
```

> ※ `--plot` を使わないなら matplotlib は不要ですが、入れておくと後から楽です。
> ※ Python 3.9+ 推奨（生成日時のタイムゾーンに `zoneinfo` を使っています）。

---

## 使い方（まずは JSON だけ）

1. SFBuffでプレイヤーの **Ranked History** を開いて、必要なら `My Character / From / To` を指定
2. そのページの URL を丸ごとコピペして実行

```bash
# mac/Linux
python sfbuff_rank_history.py "https://www.sfbuff.site/fighters/XXXXXXXX/ranked_history?home_character_id=1&played_from=2025-04-01&played_to=2025-04-30" > dist/result.json

# Windows (PowerShell / cmd どちらもOK)
python sfbuff_rank_history.py "https://www.sfbuff.site/fighters/XXXXXXXX/ranked_history?home_character_id=1&played_from=2025-04-01&played_to=2025-04-30" > dist\result.json
```

> 出力は **標準出力**。`>` で好きなファイルにリダイレクトするスタイルです。

---

## 使い方（グラフを作る）

### 例：プレイヤーID指定（キャラ・期間・移動平均・出力先を指定）

```bash
# Windows 例（あなたの実コマンド参考）
python sfbuff_rank_history.py 3629769034 -c 5 --from 2025-05-18 --plot --ma 50 --out dist\rank_ma.png > dist\result.json
```

### よく使うオプション

* `--plot` … PNG グラフを保存（**これを付けるときは --ma 必須**）
* `--ma N` … 移動平均（複数可: `--ma 10 --ma 50`）
* `--ema N` … 指数移動平均（任意・複数可）
* `--from YYYY-MM-DD` / `--to YYYY-MM-DD` … 期間指定

  * `--to` 省略時は **今日** になります
  * `--from/--to` 未指定でも、**データの最初・最後の日付**を読んでスタンプに反映します
* `-c, --character` … `home_character_id`（例：`5=Manon` など）
* `--out` … 出力 PNG パス（デフォルト: `rank_history.png`）
* `--show` … 生成後にウィンドウ表示（環境によっては出ないこともあります）
* `--hide-raw` … 生の折れ線（青いガタガタ）を隠して、平均線だけ見たい時に
* `--season-threshold 40.0` … **前試合とのレート差**がこの値以上なら「シーズン切替」とみなし、線を分けます

  * `--no-season-split` で分割オフ
* `--stamp-tz Asia/Tokyo` … 生成日時スタンプのタイムゾーン

## 例コマンド集

### URLをそのまま使う派

```bash
python sfbuff_rank_history.py "https://www.sfbuff.site/fighters/123456789/ranked_history?home_character_id=5&played_from=2025-05-01&played_to=2025-05-31" --plot --ma 20 --ema 50 --out dist\may.png > dist\may.json
```

### ID指定＋Fromだけ指定（Toは自動で今日）

```bash
python sfbuff_rank_history.py 123456789 -c 5 --from 2025-06-01 --plot --ma 30 --out dist\june.png > dist\june.json
```

### EMAだけ足す

```bash
python sfbuff_rank_history.py 123456789 --from 2025-07-01 --plot --ma 50 --ema 20 --ema 100 --out dist\ema.png > dist\ema.json
```