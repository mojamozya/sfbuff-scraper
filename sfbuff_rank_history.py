#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import bs4
import html
import json
import requests
import sys
import urllib.parse
from typing import List, Optional, Tuple
from datetime import datetime


# ----------------------------------------------------------------------
def build_url(player_or_url: str,
              character_id: Optional[int] = None,
              date_from: Optional[str] = None,
              date_to: Optional[str] = None) -> str:
    """プレイヤーIDから検索条件付きURLを生成（既にURLならそのまま返す）。"""
    if player_or_url.startswith("http"):
        return player_or_url

    qs = {}
    if character_id is not None:
        qs["home_character_id"] = str(character_id)
    if date_from:
        qs["played_from"] = date_from
    if date_to:
        qs["played_to"] = date_to
    query = urllib.parse.urlencode(qs, safe="~")
    return f"https://www.sfbuff.site/fighters/{player_or_url}/ranked_history" + ("?" + query if query else "")


# ----------------------------------------------------------------------
def scrape_rank_history(url: str, tz: str = "Asia/Tokyo") -> List[dict]:
    """SFBuffのRanked Historyグラフから（試合x, レートy）を抽出して返す。"""
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    sess = requests.Session()
    sess.headers.update(headers)

    # ① タイムゾーンCookieを先に設定
    sess.cookies.set("timezone", tz)

    # ② 本ページを取得
    html_text = sess.get(url, timeout=20).text

    # Chart.jsのdivを探す
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


# ========================= 解析/描画ユーティリティ =========================

def _parse_dt(val) -> datetime:
    """x が ISO文字列 / エポック（μs/ms/秒）のどれでも解釈（必要時に使用）。"""
    # 数値
    if isinstance(val, (int, float)):
        ts = float(val)
        if ts >= 1e15:      # microseconds
            ts /= 1_000_000.0
        elif ts >= 1e12:    # milliseconds
            ts /= 1_000.0
        # else: seconds
        return datetime.fromtimestamp(ts)
    # 文字列
    if isinstance(val, str):
        s = val.strip()
        if s.isdigit():
            ts = float(s)
            if ts >= 1e15:
                ts /= 1_000_000.0
            elif ts >= 1e12:
                ts /= 1_000.0
            return datetime.fromtimestamp(ts)
        try:
            return datetime.fromisoformat(s.replace("Z", "+00:00"))
        except Exception:
            pass
        try:
            return datetime.strptime(s[:10], "%Y-%m-%d")
        except Exception:
            pass
    raise ValueError(f"日時の解釈に失敗しました: {val!r}")


def moving_average(series: List[float], n: int) -> List[Optional[float]]:
    """直近 n 試合の単純移動平均（不足部は None）。"""
    if n <= 0:
        raise ValueError("移動平均の窓幅 n は 1 以上で指定してください。")
    ma: List[Optional[float]] = [None] * len(series)
    if not series:
        return ma
    csum = [0.0]
    for v in series:
        csum.append(csum[-1] + float(v))
    for i in range(n - 1, len(series)):
        s = csum[i + 1] - csum[i + 1 - n]
        ma[i] = s / n
    return ma


def exponential_moving_average(series: List[float], n: int) -> List[Optional[float]]:
    """EMA(n)（見やすさ重視で全点に値を出す）。"""
    if n <= 0:
        raise ValueError("EMA の窓幅 n は 1 以上で指定してください。")
    if not series:
        return []
    alpha = 2.0 / (n + 1.0)
    ema: List[Optional[float]] = [None] * len(series)
    s0 = sum(series[:n]) / n if len(series) >= n else float(series[0])
    ema[0] = s0
    for i in range(1, len(series)):
        prev = ema[i - 1] if ema[i - 1] is not None else s0
        ema[i] = (series[i] - prev) * alpha + prev
    return ema


def split_seasons_by_jump(ys: List[float], threshold: float) -> List[Tuple[int, int]]:
    """
    前試合との差が threshold 以上（絶対値）なら、そこでシーズン切替とみなす。
    返り値: [(start_idx, end_idx_excl), ...] 例: [(0, 120), (120, 245), ...]
    """
    if not ys:
        return []
    spans: List[Tuple[int, int]] = []
    start = 0
    for i in range(1, len(ys)):
        if abs(ys[i] - ys[i - 1]) >= threshold:
            if i - start > 0:
                spans.append((start, i))  # [start, i)
            start = i
    spans.append((start, len(ys)))
    return spans


# ----------------------------------------------------------------------
def _auto_label_every(n_matches: int) -> int:
    """（フォールバック用）試合数から日付ラベル間隔を決める。"""
    if n_matches <= 400:
        return 100
    if n_matches <= 1000:
        return 200
    if n_matches <= 2000:
        return 400
    return 800


# ----------------------------------------------------------------------
def _infer_tick_step(ax, n_matches: int) -> int:
    """
    x軸の実際の目盛り間隔を推定して整数ステップで返す。
    例: 目盛りが [0, 250, 500, ...] → 250 を返す。
    """
    # いったん描画して tick を確定
    try:
        ax.figure.canvas.draw()  # Agg等でもOK
    except Exception:
        pass

    ticks = [t for t in ax.get_xticks() if 1 <= t <= n_matches]
    if len(ticks) >= 2:
        diffs = []
        for a, b in zip(ticks, ticks[1:]):
            d = int(round(b - a))
            if d > 0:
                diffs.append(d)
        if diffs:
            return max(1, min(diffs))
    # うまく取れない場合はフォールバック
    return _auto_label_every(n_matches)


# ----------------------------------------------------------------------
def plot_rank_history(
    data: List[dict],
    ma_windows: List[int],
    out_path: str,
    show: bool = False,
    hide_raw: bool = False,
    title: Optional[str] = None,
    ema_windows: Optional[List[int]] = None,
    season_threshold: Optional[float] = 40.0,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    generated_at_str: Optional[str] = None,
) -> None:
    """
    横軸=試合番号で、生データ＋SMA(必須)＋EMA(任意)を描画。
    シーズン切替（大ジャンプ）は自動検出し、各シーズン内で独立に平滑化。
    """
    import matplotlib.pyplot as plt

    if not data:
        raise ValueError("描画するデータが空です。")

    xs_all = list(range(1, len(data) + 1))
    ys_all = [float(item["r"]) for item in data]

    # 期間表示用
    try:
        first_dt = _parse_dt(data[0]["d"])
        last_dt = _parse_dt(data[-1]["d"])
    except Exception:
        first_dt = last_dt = None
    disp_from = date_from or (first_dt.strftime("%Y-%m-%d") if first_dt else "—")
    disp_to = date_to or (last_dt.strftime("%Y-%m-%d") if last_dt else "—")

    # シーズン分割
    spans = split_seasons_by_jump(ys_all, season_threshold) if season_threshold else [(0, len(ys_all))]

    fig, ax = plt.subplots(figsize=(11, 5), dpi=120)

    # x軸の試合番号目盛をグレーに
    ax.tick_params(axis="x", colors="#666666")

    # 生データ
    if not hide_raw:
        first_label_done = False
        for (a, b) in spans:
            if b - a <= 0:
                continue
            ax.plot(xs_all[a:b], ys_all[a:b],
                    linewidth=1.0, alpha=0.75,
                    label=("Rating (raw)" if not first_label_done else None))
            first_label_done = True

    # SMA
    uniq_ma = sorted(set(int(n) for n in (ma_windows or []) if int(n) > 0))
    for n in uniq_ma:
        first_leg = True
        for (a, b) in spans:
            seg = ys_all[a:b]
            if not seg:
                continue
            ma = moving_average(seg, n)
            xs = [xs_all[a + i] for i, v in enumerate(ma) if v is not None]
            ys = [v for v in ma if v is not None]
            if xs:
                ax.plot(xs, ys, linewidth=2.0, label=f"MA({n})" if first_leg else None)
                first_leg = False

    # EMA
    if ema_windows:
        for n in sorted(set(int(w) for w in ema_windows if int(w) > 0)):
            first_leg = True
            for (a, b) in spans:
                seg = ys_all[a:b]
                if not seg:
                    continue
                ema = exponential_moving_average(seg, n)
                xs = [xs_all[a + i] for i in range(len(ema))]
                ax.plot(xs, ema, linewidth=2.0, linestyle="--",
                        label=f"EMA({n})" if first_leg else None)
                first_leg = False

    # シーズン境界
    if len(spans) > 1:
        for i in range(1, len(spans)):
            boundary_index = spans[i][0]
            if 1 <= boundary_index <= len(xs_all):
                ax.axvline(x=xs_all[boundary_index - 1],
                           linestyle=":", linewidth=1.0, alpha=0.4)

    # x範囲を 1..N に固定して余白を消す（ズレ防止）
    ax.set_xlim(1, len(xs_all))
    ax.margins(x=0)

    # 一度レイアウトを確定させる
    fig.tight_layout()

    # ====== 日付ラベル（x軸の目盛間隔に自動追従。先頭末尾も表示） ======
    step = _infer_tick_step(ax, len(xs_all))

    # 目盛位置を取得（1..Nの範囲）
    tick_positions = [int(round(t)) for t in ax.get_xticks() if 1 <= t <= len(xs_all)]
    if not tick_positions:
        tick_positions = list(range(step, len(xs_all) + 1, step))
    positions = sorted(set([1, len(xs_all)] + tick_positions))

    # ラベルは「x=データ座標、y=軸座標」で描く（水平ズレしない）
    xtrans = ax.get_xaxis_transform()

    # 下余白を少し広げ、日付は x 軸のすぐ下（軸座標で 0 より少し下）
    fig.subplots_adjust(bottom=0.30)
    ax.tick_params(axis="x", pad=6)  # x目盛と日付の間の隙間

    # 薄い補助線
    for pos in positions:
        ax.axvline(x=pos, linestyle=":", linewidth=0.5, alpha=0.25, zorder=0)

    # 日付ラベル（青・45度）。y は軸座標で -0.12 くらい（必要なら微調整）
    for pos in positions:
        try:
            dt = _parse_dt(data[pos - 1]["d"])
            label = dt.strftime("%Y-%m-%d")
        except Exception:
            label = ""
        if not label:
            continue
        ax.text(
            pos, -0.12, label,
            transform=xtrans,
            rotation=45, ha="right", va="top",
            fontsize=9, alpha=0.9, color="#1f77b4",
            clip_on=False,
        )

    # ====== 右下スタンプ（最下段。被り回避のため y を低めに） ======
    stamp = f"Generated: {generated_at_str or ''}  |  Range: {disp_from} — {disp_to}"
    fig.text(0.995, 0.02, stamp, ha="right", va="bottom", fontsize=9, alpha=0.75)


    fig.savefig(out_path, bbox_inches="tight")
    if show:
        plt.show()
    plt.close(fig)


# ========================= CLI =========================

def _cli():
    p = argparse.ArgumentParser()
    p.add_argument("player_or_url", help="プレイヤー ID または SFBuff のフル URL")
    p.add_argument("-c", "--character", type=int, help="home_character_id の値（例: 5=Manon）")
    p.add_argument("--from", dest="date_from", help="開始日 (YYYY-MM-DD)")
    p.add_argument("--to", dest="date_to", help="終了日 (YYYY-MM-DD)")
    p.add_argument("--plot", action="store_true", help="グラフを作成してファイルに保存します。")
    p.add_argument("--ma", type=int, action="append", help="移動平均の窓幅。複数指定可。--plot 時必須。")
    p.add_argument("--ema", type=int, action="append", default=[], help="EMAの窓幅。複数指定可。")
    p.add_argument("--out", default="rank_history.png", help="出力 PNG パス")
    p.add_argument("--show", action="store_true", help="保存後にウィンドウ表示")
    p.add_argument("--hide-raw", action="store_true", help="生データ線を非表示")
    p.add_argument("--title", default=None, help="グラフタイトル")
    p.add_argument("--season-threshold", type=float, default=40.0,
                   help="差がこの値以上ならシーズン切替とみなす（デフォ:40）")
    p.add_argument("--no-season-split", action="store_true", help="シーズン分割を無効化")
    p.add_argument("--stamp-tz", default="Asia/Tokyo", help="生成日時のタイムゾーン")

    args = p.parse_args()

    if args.plot and not args.ma:
        p.error("--plot 使用時は --ma を少なくとも1つ指定してください")

    for opt_name, vals in (("--ma", args.ma or []), ("--ema", args.ema or [])):
        for v in vals:
            if v is None or v <= 0:
                p.error(f"{opt_name} の値は正の整数で指定してください: {v}")

    if args.date_to is None:
        args.date_to = datetime.today().strftime("%Y-%m-%d")

    url = build_url(args.player_or_url, args.character, args.date_from, args.date_to)
    data = scrape_rank_history(url)

    try:
        from zoneinfo import ZoneInfo
        now = datetime.now(ZoneInfo(args.stamp_tz))
        generated_at_str = now.strftime("%Y-%m-%d %H:%M:%S %Z")
    except Exception:
        generated_at_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # JSONはstdoutへ
    json.dump(data, sys.stdout, ensure_ascii=False)

    if args.plot:
        title = args.title or "Ranked History with Moving Averages"
        season_thr = None if args.no_season_split else args.season_threshold
        plot_rank_history(
            data=data,
            ma_windows=args.ma,
            out_path=args.out,
            show=args.show,
            hide_raw=args.hide_raw,
            title=title,
            ema_windows=args.ema,
            season_threshold=season_thr,
            date_from=args.date_from,
            date_to=args.date_to,
            generated_at_str=generated_at_str,
        )


# ----------------------------------------------------------------------
if __name__ == "__main__":
    _cli()
