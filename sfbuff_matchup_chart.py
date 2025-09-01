#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SFBuff Matchup Chart/Table Scraper (table-first)

- 例URL:
  https://www.sfbuff.site/fighters/3629769034/matchup_chart?home_character_id=5&home_input_type_id=0&battle_type_id=1&played_from=2025-08-01&played_to=2025-08-25

機能:
- まずページ内の「マッチアップ表（table）」をパース
- 表が無い/読めない場合のみ、埋め込み Chart.js をフォールバックで抽出
- 出力はロング形式（1行=相手×入力タイプor統合）
- --merge-inputs で C/M を統合（Total/Wins/Losses/Draws を合算、Diff/WinRate を再計算）
- JSON は stdout、--csv でCSV保存
- --dump-html / --dump-raw-chart あり（デバッグ用）

注意:
- 表の列は「VS, Control(C/M), Total, Wins, Losses, Draws, Σ(Diff), %(WinRate), Chartへのリンク」
- “-” は欠損扱い
"""

import argparse
import bs4
import csv
import html
import json
import os
import re
import sys
import urllib.parse
from typing import Any, Dict, List, Optional, Tuple

import requests


# ---------------- URL組み立て ----------------
def build_url(player_or_url: str,
              character_id: Optional[int] = None,
              home_input_type_id: Optional[int] = None,
              battle_type_id: Optional[int] = 1,
              date_from: Optional[str] = None,
              date_to: Optional[str] = None) -> str:
    """プレイヤーIDから matchup_chart のURLを構築。既にURLならそのまま返す。"""
    if player_or_url.startswith("http"):
        return player_or_url

    qs = {}
    if character_id is not None:
        qs["home_character_id"] = str(character_id)
    if home_input_type_id is not None:
        qs["home_input_type_id"] = str(home_input_type_id)
    if battle_type_id is not None:
        qs["battle_type_id"] = str(battle_type_id)
    if date_from:
        qs["played_from"] = date_from
    if date_to:
        qs["played_to"] = date_to

    query = urllib.parse.urlencode(qs, safe="~")
    return f"https://www.sfbuff.site/fighters/{player_or_url}/matchup_chart" + ("?" + query if query else "")


# ---------------- 共通ヘルパ ----------------
def _to_int(s) -> Optional[int]:
    try:
        if s is None:
            return None
        t = str(s).strip()
        if t == "-" or t == "":
            return None
        return int(t.replace(",", ""))
    except Exception:
        return None


def _to_float(s) -> Optional[float]:
    try:
        if s is None:
            return None
        t = str(s).strip().replace("%", "")
        if t == "-" or t == "":
            return None
        return float(t)
    except Exception:
        return None


def _clean_text(el) -> str:
    if el is None:
        return ""
    txt = el.get_text(strip=True)
    # “+1”“-2” が span 内の text-danger/text-success に入っているので前後空白は削る
    return txt


# ---------------- 表パーサ ----------------
def parse_matchup_table(html_text: str) -> List[Dict[str, Any]]:
    """
    <turbo-frame id="matchups-matchup-chart"> 配下の table をパース。
    列は:
      0: VS(相手)
      1: Control (C/M)
      2: Total
      3: Wins
      4: Losses
      5: Draws
      6: Diff (±n)  ※ <span>に入る
      7: Ratio (%)  ※ <span>に入る
      8: Chartリンク（無視 or 吐きたいならURLも取れる）
    """
    soup = bs4.BeautifulSoup(html_text, "html.parser")
    frame = soup.find("turbo-frame", {"id": "matchups-matchup-chart"})
    if frame is None:
        # ページによっては直接 table があるかもしれないので全体から探す
        root = soup
    else:
        root = frame

    table = root.find("table")
    if table is None:
        return []

    rows: List[Dict[str, Any]] = []

    tbody = table.find("tbody")
    if tbody is None:
        return []

    for tr in tbody.find_all("tr"):
        tds = tr.find_all("td")
        if not tds:
            continue
        # 集計行（最下段）のパターン: 1列目 colspan=2、相手名が空 → これはスキップ
        if len(tds) >= 2 and _clean_text(tds[0]) == "" and tds[0].get("colspan") in ("2", 2):
            # ここに総合計が入っているので、必要なら拾うこともできる
            continue

        # 想定：9列（VS, C/M, Total, Wins, Losses, Draws, Diff, %, Chartリンク）
        if len(tds) < 8:
            # 欠損や変則は無視
            continue

        opponent = _clean_text(tds[0])
        control = _clean_text(tds[1])  # "C" or "M" など
        total   = _to_int(_clean_text(tds[2]))
        wins    = _to_int(_clean_text(tds[3]))
        losses  = _to_int(_clean_text(tds[4]))
        draws   = _to_int(_clean_text(tds[5]))
        diff    = _clean_text(tds[6])  # "+3" / "-2" / "-" など
        ratio   = _clean_text(tds[7])  # "60.0" / "-" など
        # chart_url = tds[8].find("a")["href"] if len(tds) >= 9 and tds[8].find("a") else None

        # Diff を数値化（先頭の + はそのまま、- は負数）
        diff_val = None
        if diff and diff != "-":
            m = re.match(r"^([+\-]?\d+)$", diff)
            if m:
                diff_val = int(m.group(1))

        win_rate = _to_float(ratio)

        rows.append({
            "opponent": opponent,
            "control": control,          # "C" / "M" / など
            "total": total,
            "wins": wins,
            "losses": losses,
            "draws": draws,
            "diff": diff_val,
            "win_rate": win_rate,        # 単位は % と想定（None の場合も）
            # "chart": chart_url,
        })

    return rows


# ---------------- Chart.js フォールバック ----------------
def _json_unescape_load(s: str) -> Any:
    try:
        return json.loads(html.unescape(s))
    except Exception:
        return None


def _assemble_chart_from_parts(el) -> Optional[Dict[str, Any]]:
    cand = el.attrs
    parts = {}
    for k, v in cand.items():
        k_lower = str(k).lower()
        if not k_lower.endswith("-value"):
            continue
        if "chart" not in k_lower:
            continue
        val = _json_unescape_load(v) if isinstance(v, str) else None
        if "datasets" in k_lower:
            parts["datasets"] = val
        elif "labels" in k_lower:
            parts["labels"] = val
        elif k_lower.endswith("data-value"):
            parts["data"] = val
        elif "options" in k_lower:
            parts["options"] = val

    if isinstance(parts.get("data"), dict):
        return {"data": parts["data"], "options": parts.get("options", {})}

    labels = parts.get("labels")
    datasets = parts.get("datasets")
    if isinstance(labels, list) and isinstance(datasets, list):
        return {
            "data": {"labels": labels, "datasets": datasets},
            "options": parts.get("options", {}),
        }
    return None


def fetch_chart_json(html_text: str) -> Optional[Dict[str, Any]]:
    soup = bs4.BeautifulSoup(html_text, "html.parser")
    candidates: List[Dict[str, Any]] = []

    for el in soup.find_all(True, attrs={"data-controller": True}):
        if "chart" not in (el.get("data-controller") or "").lower():
            continue
        raw = el.get("data-chartjs-data-value") or el.get("data-chart-data-value") or el.get("data-chart-value")
        chart = _json_unescape_load(raw) if raw else None
        if not isinstance(chart, dict):
            chart = _assemble_chart_from_parts(el)
        if isinstance(chart, dict):
            candidates.append(chart)

    return candidates[-1] if candidates else None


def normalize_chart_to_rows(chart: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Chart をロング形式へ変換（フォールバック用・簡易）。
    値は 'value' に入れる。入力タイプや勝敗の内訳はChart側にないことが多い。
    """
    rows: List[Dict[str, Any]] = []
    data = chart.get("data", {})
    labels = data.get("labels", None)
    datasets = data.get("datasets", [])
    if labels and datasets:
        for ds in datasets:
            series = ds.get("label") or "series"
            vals = ds.get("data", [])
            if len(vals) == len(labels):
                for lab, val in zip(labels, vals):
                    rows.append({
                        "opponent": str(lab),
                        "series": series,
                        "value": _to_float(val) or _to_int(val),
                    })
    return rows


# ---------------- C/M 統合（合算） ----------------
def merge_inputs(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    control 列（C/M）を統合。
    合算の上で WinRate と Diff を再計算。
    """
    buckets: Dict[str, Dict[str, Optional[float]]] = {}  # opponent -> aggregated stats

    for r in rows:
        opp = r.get("opponent") or ""
        b = buckets.setdefault(opp, {
            "opponent": opp,
            "total": 0,
            "wins": 0,
            "losses": 0,
            "draws": 0,
        })
        # 合算（None は無視）
        for k in ("total", "wins", "losses", "draws"):
            v = r.get(k)
            if isinstance(v, int):
                b[k] = (b[k] or 0) + v

    out: List[Dict[str, Any]] = []
    for opp, b in buckets.items():
        total = int(b.get("total") or 0)
        wins = int(b.get("wins") or 0)
        losses = int(b.get("losses") or 0)
        draws = int(b.get("draws") or 0)
        diff = wins - losses
        win_rate = (wins / total * 100.0) if total > 0 else None

        out.append({
            "opponent": opp,
            "total": total,
            "wins": wins,
            "losses": losses,
            "draws": draws,
            "diff": diff,
            "win_rate": round(win_rate, 2) if win_rate is not None else None,
        })
    # 相手名でソートしておくと使いやすい
    out.sort(key=lambda x: x["opponent"])
    return out


# ---------------- CSV 出力 ----------------
def save_csv(rows: List[Dict[str, Any]], path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    if not rows:
        with open(path, "w", newline="", encoding="utf-8") as f:
            f.write("")
        return

    fieldnames: List[str] = []
    for r in rows:
        for k in r.keys():
            if k not in fieldnames:
                fieldnames.append(k)

    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


# ---------------- メインフロー ----------------
def _cli():
    ap = argparse.ArgumentParser(description="SFBuff Matchup Scraper (table-first)")
    ap.add_argument("player_or_url", help="プレイヤーID または matchup_chart のフルURL")
    ap.add_argument("-c", "--character", type=int, help="home_character_id の値")
    ap.add_argument("--home-input", type=int, dest="home_input_type_id",
                    help="home_input_type_id (0=Classic, 1=Modern 等、サイト表記に準拠)")
    ap.add_argument("--battle-type", type=int, dest="battle_type_id", default=1,
                    help="battle_type_id (例: 1=Ranked) デフォルト:1")
    ap.add_argument("--from", dest="date_from", help="開始日 YYYY-MM-DD")
    ap.add_argument("--to", dest="date_to", help="終了日 YYYY-MM-DD")
    ap.add_argument("--merge-inputs", action="store_true",
                    help="C/M を統合（合算してDiff/WinRateを再計算）")
    ap.add_argument("--csv", dest="csv_path", help="CSVの保存先パス（指定時のみ書き出し）")
    ap.add_argument("--dump-raw-chart", dest="dump_raw", help="見つかったChart JSONを保存（フォールバック用）")
    ap.add_argument("--dump-html", dest="dump_html", help="取得HTMLを保存（デバッグ用）")

    args = ap.parse_args()

    url = build_url(
        args.player_or_url,
        character_id=args.character,
        home_input_type_id=args.home_input_type_id,
        battle_type_id=args.battle_type_id,
        date_from=args.date_from,
        date_to=args.date_to,
    )

    # 取得
    sess = requests.Session()
    sess.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    sess.cookies.set("timezone", "Asia/Tokyo")
    resp = sess.get(url, timeout=20)
    resp.raise_for_status()
    html_text = resp.text

    # 要求があればHTMLダンプ
    if args.dump_html:
        os.makedirs(os.path.dirname(args.dump_html) or ".", exist_ok=True)
        with open(args.dump_html, "w", encoding="utf-8") as f:
            f.write(html_text)

    # 1) 表を優先してパース
    rows = parse_matchup_table(html_text)

    # 2) 表が見つからない／空なら、Chart をフォールバックで試す
    if not rows:
        chart = fetch_chart_json(html_text)
        if args.dump_raw and chart:
            os.makedirs(os.path.dirname(args.dump_raw) or ".", exist_ok=True)
            with open(args.dump_raw, "w", encoding="utf-8") as f:
                json.dump(chart, f, ensure_ascii=False, indent=2)
        rows = normalize_chart_to_rows(chart) if chart else []

    # 3) 統合オプション
    if args.merge_inputs:
        # 表パース結果には control 列(C/M)があるので合算集計
        rows = merge_inputs(rows)
    else:
        # 非統合の場合は “control” が無い行（フォールバック由来）もありうる
        # 使いやすさのためソート
        rows.sort(key=lambda r: (r.get("opponent") or "", r.get("control") or ""))

    # diff（勝ち-負け）が小さい順（負けが多い相手ほど上に）
    rows.sort(key=lambda r: (r.get("diff") if r.get("diff") is not None else 0))
    
    # 4) JSON を標準出力へ
    json.dump(rows, sys.stdout, ensure_ascii=False)

    # 5) CSV 保存
    if args.csv_path:
        save_csv(rows, args.csv_path)


if __name__ == "__main__":
    _cli()
