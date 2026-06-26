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


def jload(out):
    import json
    try:
        return json.loads(out) if out else None
    except ValueError:
        return None


def jnum(s):
    m = re.search(r"-?\d+\.?\d*", str(s).replace(",", ""))
    return m.group() if m else ""


def norm_date(s):
    """'2026年06月25日 22:03' → '2026-06-25 22:03'（对齐发布时间去重键）。"""
    m = re.search(r"(\d{4})\D+(\d{1,2})\D+(\d{1,2})\D*(?:(\d{1,2}):(\d{2}))?", str(s))
    if not m:
        return str(s)
    y, mo, d = m.group(1), m.group(2).zfill(2), m.group(3).zfill(2)
    hm = f" {m.group(4).zfill(2)}:{m.group(5)}" if m.group(4) else ""
    return f"{y}-{mo}-{d}{hm}"


# 单篇详情：观看来源 + 受众画像（creator-note-detail，本地创作者后台，无需主站登录）
DETAIL_SRC = ["视频推荐", "首页推荐", "关注页面", "搜索", "个人主页", "其他来源"]
DETAIL_COLS = (["拉取日期", "note_id", "标题", "曝光", "观看", "封面点击率", "平均观看时长", "涨粉"]
               + DETAIL_SRC + ["推荐占比", "男", "女", "主年龄", "主年龄占比", "top城市", "top兴趣"])


def note_detail_cells(nid, log):
    """拉单篇详情 → 对齐 DETAIL_COLS[3:] 的单元格列表；拉不到/无数据返回 None。"""
    rows = jload(run(["opencli", "xiaohongshu", "creator-note-detail", nid, "-f", "json"], log))
    if not rows:
        return None
    base, src, gender, age, city, interest = {}, {}, {}, {}, {}, {}
    for r in rows:
        sec, m, v = r.get("section"), r.get("metric"), r.get("value")
        if sec == "基础数据":
            base[m] = jnum(v)
        elif sec == "观看来源":
            src[m] = jnum(v)
        elif sec == "观众画像" and "/" in str(m):
            grp, key = m.split("/", 1)
            {"性别": gender, "年龄": age, "城市": city, "兴趣": interest}.get(grp, {})[key] = jnum(v)

    def fv(x):
        return float(x) if x not in ("", None) else 0.0
    rec = round(fv(src.get("视频推荐")) + fv(src.get("首页推荐")), 1) if src else ""
    top_age = max(age, key=lambda k: fv(age[k])) if age else ""
    top_city = max(city, key=lambda k: fv(city[k])) if city else ""
    top_int = max(interest, key=lambda k: fv(interest[k])) if interest else ""
    return ([base.get("曝光数", ""), base.get("观看数", ""), base.get("封面点击率", ""),
             base.get("平均观看时长", ""), base.get("涨粉数", "")]
            + [src.get(k, "") for k in DETAIL_SRC]
            + [rec, gender.get("男性", ""), gender.get("女性", ""),
               top_age, age.get(top_age, "") if top_age else "", top_city, top_int])


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

    # 3) 逐篇数据（全部已发布笔记）→ 数据日志 + 单篇详情(限流/来源/画像/CTR)
    notes = jload(run(["opencli", "xiaohongshu", "creator-notes", "-f", "json"], log))
    notes = notes if isinstance(notes, list) else (notes or {}).get("data") or (notes or {}).get("notes") or []
    if notes:
        log_rows, detail_rows = [], []
        for n in notes:
            nid = n.get("id") or n.get("note_id")
            title = n.get("title", "")
            pub = norm_date(n.get("date", ""))
            cells = note_detail_cells(nid, log) if nid else None
            avg_time = cells[3] if cells else ""   # 平均观看时长 作完播代理
            log_rows.append([TODAY, title, pub, n.get("views", ""), n.get("likes", ""),
                             n.get("collects", ""), n.get("comments", ""), avg_time])
            if cells:
                detail_rows.append([TODAY, nid, title] + cells)
        append_csv(os.path.join(D, "小红书数据日志.csv"),
                   ["拉取日期", "标题", "发布时间", "观看", "赞", "藏", "评", "完播"], log_rows)
        if detail_rows:
            append_csv(os.path.join(D, "小红书单篇详情.csv"), DETAIL_COLS, detail_rows)
        log(f"notes ok {len(log_rows)} 篇 | 详情 {len(detail_rows)} 篇")
    else:
        ok = False; log("notes 失败")

    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
