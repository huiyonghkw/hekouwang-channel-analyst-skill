#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
渠道数据分析师 · 取数层（v1：小红书）
跑 opencli 拉【账号总览 / 漏斗概览 / 逐篇数据】，追加进 CSV 时间序列。
依赖：opencli + Chrome 登录态 + opencli 扩展已连接（须 Chrome 开着）。
拉不到只写失败日志、不写脏数据。可被 launchd 每日调用，也可手动跑。

用法:
  python3 pull.py                      # 数据写到 ./渠道数据分析师/
  python3 pull.py --data-dir <目录>     # 自定义数据目录
环境变量 CHANNEL_ANALYST_DATA 同 --data-dir（优先级低于命令行）。
"""
import argparse, csv, os, re, subprocess, sys
from datetime import datetime, timedelta

NOW = datetime.now().strftime("%Y-%m-%d %H:%M")
TODAY = datetime.now().strftime("%Y-%m-%d")

# creator-stats 的英文标识 → CSV 列名
STAT_MAP = {
    "views": "观看", "home views": "主页访问", "likes": "赞",
    "collects": "藏", "comments": "评", "shares": "分享",
    "new followers": "涨粉",
}
STAT_COLS = ["观看", "主页访问", "赞", "藏", "评", "分享", "涨粉"]
DAILY_COLS = ["观看", "主页访问", "涨粉"]  # 有每日明细趋势、对分析最有用的几项


def resolve_data_dir(arg):
    d = arg or os.environ.get("CHANNEL_ANALYST_DATA") or os.path.join(os.getcwd(), "渠道数据分析师")
    os.makedirs(d, exist_ok=True)
    return d


def run(cmd, log):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    except Exception as e:
        log(f"命令异常 {' '.join(cmd)}: {e}")
        return None
    out = "\n".join(l for l in r.stdout.splitlines()
                    if "UNDICI" not in l and "trace-warnings" not in l)
    if r.returncode != 0 or not out.strip():
        log(f"命令失败 {' '.join(cmd)} rc={r.returncode}: {r.stderr[:200]}")
        return None
    return out


def parse_blocks(text):
    """'- key: value' + 缩进 'key: value' → dict 列表。"""
    blocks, cur = [], None
    for line in text.splitlines():
        m = re.match(r"^- (\w[\w_]*): ?(.*)$", line)
        if m:
            if cur:
                blocks.append(cur)
            cur = {m.group(1): m.group(2).strip().strip("'\"")}
        else:
            m2 = re.match(r"^\s+(\w[\w_]*): ?(.*)$", line)
            if m2 and cur is not None:
                cur[m2.group(1)] = m2.group(2).strip().strip("'\"")
    if cur:
        blocks.append(cur)
    return blocks


def append_csv(path, header, rows):
    new = not os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        if new:
            w.writerow(header)
        w.writerows(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default=None)
    args = ap.parse_args()
    D = resolve_data_dir(args.data_dir)
    LOG = os.path.join(D, "拉取日志.txt")

    def log(msg):
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(f"[{NOW}] {msg}\n")

    ok = True

    # 1) 账号总览 → 粉丝日志
    prof = run(["opencli", "xiaohongshu", "creator-profile"], log)
    if prof:
        fans = re.search(r"Followers\s*\n?\s*value:\s*(\d+)", prof)
        likes = re.search(r"Likes & Collects\s*\n?\s*value:\s*([\d,]+)", prof)
        append_csv(os.path.join(D, "小红书粉丝日志.csv"),
                   ["拉取日期", "粉丝数", "获赞藏"],
                   [[TODAY, fans.group(1) if fans else "",
                     likes.group(1).replace(",", "") if likes else ""]])
        log(f"profile ok 粉丝={fans.group(1) if fans else '?'}")
    else:
        ok = False; log("profile 失败")

    # 2) 漏斗概览（近 7 日总量 + 每日明细趋势） → 概览日志 + 每日趋势
    stats = run(["opencli", "xiaohongshu", "creator-stats"], log)
    if stats:
        vals, trends = {}, {}
        for b in parse_blocks(stats):
            m = re.search(r"\(([^)]+)\)", b.get("metric", ""))
            if not (m and m.group(1).strip() in STAT_MAP):
                continue
            col = STAT_MAP[m.group(1).strip()]
            vals[col] = b.get("total", "")
            nums = re.findall(r"-?\d+", b.get("trend", ""))
            if nums:
                trends[col] = [int(x) for x in nums]
        append_csv(os.path.join(D, "小红书概览日志.csv"),
                   ["拉取日期"] + STAT_COLS,
                   [[TODAY] + [vals.get(c, "") for c in STAT_COLS]])
        # 每日明细：creator-stats 的 trend 是近 7 天每日值（oldest→newest，末位=今天）
        if any(c in trends for c in DAILY_COLS):
            n = max((len(trends.get(c, [])) for c in DAILY_COLS), default=0)
            base = datetime.now().date()
            drows = [[(base - timedelta(days=(n - 1 - i))).strftime("%Y-%m-%d")] +
                     [(trends[c][i] if c in trends and i < len(trends[c]) else "")
                      for c in DAILY_COLS] for i in range(n)]
            append_csv(os.path.join(D, "小红书每日趋势.csv"), ["日期"] + DAILY_COLS, drows)
        log(f"stats ok 观看={vals.get('观看','?')} 涨粉={vals.get('涨粉','?')} 每日明细={len(trends)}项")
    else:
        ok = False; log("stats 失败")

    # 3) 逐篇数据 → 数据日志
    notes = run(["opencli", "xiaohongshu", "creator-notes-summary"], log)
    if notes:
        rows = [[TODAY, b.get("title", ""), b.get("published_at", ""),
                 b.get("views", ""), b.get("likes", ""),
                 b.get("collects", ""), b.get("comments", ""),
                 b.get("avg_view_time", "")]
                for b in parse_blocks(notes) if "title" in b]
        if rows:
            append_csv(os.path.join(D, "小红书数据日志.csv"),
                       ["拉取日期", "标题", "发布时间", "观看", "赞", "藏", "评", "完播"],
                       rows)
            log(f"notes ok {len(rows)} 篇")
        else:
            ok = False; log("notes 解析 0 篇")
    else:
        ok = False; log("notes 失败")

    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
