#!/usr/bin/env python3
import argparse, json, sys, html, urllib.parse, requests, bs4

# ----------------------------------------------------------------------
def build_url(player_or_url: str,
              character_id: int | None = None,
              date_from: str | None = None,
              date_to: str | None = None) -> str:
    """プレイヤー ID から検索条件付き URL を生成（既に URL の場合はそのまま返す）。"""
    if player_or_url.startswith("http"):
        return player_or_url

    qs = {}
    if character_id is not None:
        qs["home_character"] = str(character_id)
    if date_from:
        qs["played_from"] = date_from
    if date_to:
        qs["played_to"] = date_to
    query = urllib.parse.urlencode(qs, safe="~")
    return f"https://www.sfbuff.site/fighters/{player_or_url}/ranked" + ("?" + query if query else "")

# ----------------------------------------------------------------------
def scrape_rank_history(url: str, tz: str = "Asia/Tokyo") -> list[dict]:
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    sess    = requests.Session()
    sess.headers.update(headers)

    # ① タイムゾーン cookie を先に設定
    sess.cookies.set("timezone", tz)

    # ② 本ページを取得
    html_text = sess.get(url, timeout=20).text

    # 以下は従来どおり Chart.js の div を探す
    soup = bs4.BeautifulSoup(html_text, "html.parser")
    for div in soup.select('div[data-controller="chartjs"]'):
        raw = div.get("data-chartjs-data-value")
        if not raw:
            continue
        chart = json.loads(html.unescape(raw))
        title = chart.get("options", {}).get("plugins", {}).get("title", {}).get("text", "")
        if title.startswith("Ranked History"):
            ds = next(d for d in chart["data"]["datasets"] if d.get("yAxisID") == "mr")
            return [{"d": p["x"], "r": p["y"]} for p in ds["data"]]

    raise RuntimeError("Ranked History グラフが見つかりませんでした。")

# ----------------------------------------------------------------------
def _cli():
    p = argparse.ArgumentParser()
    p.add_argument("player_or_url", help="プレイヤー ID または SFBuff のフル URL")
    p.add_argument("-c", "--character", type=int, help="home_character の値（例: 5=Manon）")
    p.add_argument("--from", dest="date_from", help="開始日 (YYYY-MM-DD)")
    p.add_argument("--to", dest="date_to", help="終了日 (YYYY-MM-DD)")
    args = p.parse_args()

    url = build_url(args.player_or_url, args.character, args.date_from, args.date_to)
    data = scrape_rank_history(url)
    json.dump(data, sys.stdout, ensure_ascii=False)

# ----------------------------------------------------------------------
if __name__ == "__main__":
    _cli()
