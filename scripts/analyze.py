#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
渠道数据分析师 · 分析引擎（v1：小红书）
读取 CSV 时间序列 → 算【账号KPI / 漏斗 / 逐篇红黑榜 / 趋势 / 诊断 / 建议】→ report_data.json

用法:
  python3 analyze.py [--data-dir <目录>] [--out <json路径>]

诊断/建议是规则引擎，守底线：不建议刷量、不承诺涨粉数字。
"""
import argparse, csv, json, os
from collections import defaultdict
from datetime import datetime

COLD = 300            # 观看 < 此值 ≈ 卡在冷启动池，没出池
LOW_HOME_RATE = 3.0   # 观看→主页 < 3% 偏低
GOOD_HOME_RATE = 5.0  # 观看→主页 ≥ 5% 健康
LOW_FOLLOW_RATE = 8.0  # 主页→涨粉 < 8% 偏低
GOOD_FOLLOW_RATE = 10.0  # 主页→涨粉 ≥ 10% 健康
OUT_POOL_VIEWS = 3000  # 一篇"出池"笔记的参考观看量（用于目标测算）
TARGETS = [500, 1000]  # 创作者等级 / 里程碑


def num(s):
    try:
        return int(float(str(s).replace(",", "").strip()))
    except (ValueError, AttributeError):
        return None


def read_csv(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default=os.environ.get("CHANNEL_ANALYST_DATA")
                    or os.path.join(os.getcwd(), "渠道数据分析师"))
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    D = args.data_dir
    out = args.out or os.path.join(D, "report_data.json")

    fans = read_csv(os.path.join(D, "小红书粉丝日志.csv"))
    overview = read_csv(os.path.join(D, "小红书概览日志.csv"))
    notes_raw = read_csv(os.path.join(D, "小红书数据日志.csv"))

    dates = sorted({r["拉取日期"] for r in notes_raw} |
                   {r["拉取日期"] for r in fans} |
                   {r["拉取日期"] for r in overview})
    latest = dates[-1] if dates else None
    prev = dates[-2] if len(dates) >= 2 else None

    R = {
        "账号": "会勇禾口王的AI笔记 @huiyonghkw",
        "平台": "小红书",
        "生成时间": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "数据区间": {"最新": latest, "上一次": prev, "总快照数": len(dates)},
        "kpi": {}, "漏斗": {}, "笔记": [], "趋势": {},
        "基准": {}, "目标测算": [], "诊断": [], "建议": [], "行动清单": [],
    }

    # ── KPI（账号总览 + 环比） ──
    def row_of(rows, date):  # 同日多次拉取时取最后一次（最新）
        found = None
        for r in rows:
            if r["拉取日期"] == date:
                found = r
        return found
    fa, fp = row_of(fans, latest), row_of(fans, prev)
    if fa:
        cur_fans = num(fa.get("粉丝数"))
        R["kpi"]["粉丝数"] = cur_fans
        R["kpi"]["获赞藏"] = num(fa.get("获赞藏"))
        if fp and cur_fans is not None and num(fp.get("粉丝数")) is not None:
            R["kpi"]["粉丝净增"] = cur_fans - num(fp.get("粉丝数"))
        # 距下一创作者等级（500）
        if cur_fans is not None and cur_fans < 500:
            R["kpi"]["距500等级"] = 500 - cur_fans

    # ── 漏斗（近 7 日总量） ──
    ov = row_of(overview, latest)
    if ov:
        v, h, nf = num(ov.get("观看")), num(ov.get("主页访问")), num(ov.get("涨粉"))
        R["漏斗"] = {
            "观看": v, "主页访问": h, "涨粉": nf,
            "观看转主页率": round(h / v * 100, 1) if v and h is not None else None,
            "主页转涨粉率": round(nf / h * 100, 1) if h and nf is not None else None,
            "区间": "近 7 日",
        }

    # ── 逐篇红黑榜（最新快照） + 单篇环比 ──
    # 同日多次拉取 → 按标题去重，保留最后一次
    cur_map = {}
    for r in notes_raw:
        if r["拉取日期"] == latest:
            cur_map[r["标题"]] = r
    cur_notes = list(cur_map.values())
    prev_map = {r["标题"]: r for r in notes_raw if r["拉取日期"] == prev} if prev else {}
    for r in cur_notes:
        v = num(r.get("观看")) or 0
        lk, cl = num(r.get("赞")) or 0, num(r.get("藏")) or 0
        item = {
            "标题": r.get("标题"), "发布时间": r.get("发布时间"),
            "观看": v, "赞": lk, "藏": cl, "评": num(r.get("评")) or 0,
            "完播": r.get("完播", "").strip() or None,
            "出池": v >= COLD,
            "藏赞合计": lk + cl,
        }
        pv = prev_map.get(r.get("标题"))
        if pv and num(pv.get("观看")) is not None:
            item["观看环比"] = v - num(pv.get("观看"))
        R["笔记"].append(item)
    R["笔记"].sort(key=lambda x: x["观看"], reverse=True)

    # 逐篇判决（给每条笔记一个具体动作）
    for n in R["笔记"]:
        if n["出池"] and n.get("观看环比", 0) > 0:
            n["判决"], n["判决色"] = "🔝 置顶 / 追投", "good"
        elif n["出池"]:
            n["判决"], n["判决色"] = "✅ 保持", "good"
        elif n["藏赞合计"] >= 5:
            n["判决"], n["判决色"] = "♻️ 换封面返工重发", "warn"
        else:
            n["判决"], n["判决色"] = "✏️ 封面+选题重做", "bad"

    # ── 趋势（按日期去重保留最后一次） ──
    def trend_by_date(rows, col, datecol="拉取日期"):
        d = {}
        for r in rows:
            v = num(r.get(col))
            if v is not None and r.get(datecol):
                d[r.get(datecol)] = v
        return [{"日期": k, "值": d[k]} for k in sorted(d)]
    daily = read_csv(os.path.join(D, "小红书每日趋势.csv"))
    R["趋势"]["粉丝"] = trend_by_date(fans, "粉丝数")          # 快照，随天数累积
    R["趋势"]["观看"] = trend_by_date(daily, "观看", "日期")   # creator-stats 每日明细，开箱 7 点
    R["趋势"]["涨粉"] = trend_by_date(daily, "涨粉", "日期")

    # ── 诊断 + 建议（规则引擎） ──
    notes = R["笔记"]
    avg_v = sum(n["观看"] for n in notes) / len(notes) if notes else 0
    out_pool = [n for n in notes if n["出池"]]
    adv = R["建议"]

    if notes:
        if avg_v < COLD:
            R["诊断"].append(
                f"核心病灶：内容没出冷启动池。{len(notes)} 篇均观看仅 {avg_v:.0f}，"
                f"出池(≥{COLD}) 仅 {len(out_pool)} 篇。")
            adv.append({"优先级": "P0", "环节": "封面 CTR",
                        "建议": "小红书冷启动 80% 看首图。把封面从素编辑卡改成信息流抓眼版（大字+数字反差），是出池第一杠杆。"})
            adv.append({"优先级": "P0", "环节": "标题",
                        "建议": "标题埋搜索词 + 留悬念，和封面一起决定点击率。"})
        else:
            R["诊断"].append(f"内容能出池：均观看 {avg_v:.0f}，{len(out_pool)} 篇破 {COLD}。重点转向转化。")

    hr = R["漏斗"].get("观看转主页率")
    if hr is not None and hr < LOW_HOME_RATE:
        R["诊断"].append(f"观看→主页率仅 {hr}%（<{LOW_HOME_RATE}%），看的人没被引去主页。")
        adv.append({"优先级": "P1", "环节": "完播 + 关注钩子",
                    "建议": "首图制造往下滑的理由提完播；正文结尾加'系列承诺+关注追更'，把读者从单篇引到主页。"})

    fr = R["漏斗"].get("主页转涨粉率")
    if fr is not None:
        if fr < LOW_FOLLOW_RATE:
            R["诊断"].append(f"主页→涨粉率 {fr}%（偏低），主页没留住人。")
            adv.append({"优先级": "P2", "环节": "主页装修",
                        "建议": "置顶最能代表人设的笔记、bio 用一句强 slogan、保持封面风格统一，提主页转化。"})
        else:
            R["诊断"].append(f"主页→涨粉率 {fr}%（健康），点进主页的人愿意关注——放大流量即可。")

    # 爬坡笔记 → 建议放大
    climbing = sorted([n for n in notes if n.get("观看环比", 0) > 0],
                      key=lambda x: x["观看环比"], reverse=True)
    if climbing:
        top = climbing[0]
        adv.append({"优先级": "P1", "环节": "乘胜追击",
                    "建议": f"《{top['标题']}》还在爬（+{top['观看环比']} 观看），是当前最能跑的内容。考虑置顶，并照这个方向再做一条。"})
    # 高藏赞比但低观看 = 好内容没被看见
    hidden = [n for n in notes if not n["出池"] and n["藏赞合计"] >= 5]
    if hidden:
        adv.append({"优先级": "P1", "环节": "好内容返工",
                    "建议": f"《{hidden[0]['标题']}》藏赞不低但观看没起来——内容是好的，给它换个抓眼封面+标题重发，性价比最高。"})

    adv.append({"优先级": "底线", "环节": "合规",
                "建议": "只做内容/封面/标题/节奏优化，不买量、不互关刷粉。买来的是僵尸粉，伤账号权重，也毁私域转化。"})

    # ── 基准对照（你的指标 vs 健康区间） ──
    def rate_grade(v, low, good):
        if v is None:
            return "—"
        return "健康" if v >= good else ("及格" if v >= low else "偏低")
    hr = R["漏斗"].get("观看转主页率")
    fr = R["漏斗"].get("主页转涨粉率")
    R["基准"] = {
        "观看转主页率": {"值": hr, "健康线": f"≥{GOOD_HOME_RATE}%", "评级": rate_grade(hr, LOW_HOME_RATE, GOOD_HOME_RATE)},
        "主页转涨粉率": {"值": fr, "健康线": f"≥{GOOD_FOLLOW_RATE}%", "评级": rate_grade(fr, LOW_FOLLOW_RATE, GOOD_FOLLOW_RATE)},
        "出池笔记占比": {"值": (round(len(out_pool) / len(notes) * 100) if notes else None),
                    "健康线": "越高越好", "评级": ("好" if notes and len(out_pool) / len(notes) >= .5 else "偏低")},
    }

    # ── 涨粉目标测算（按当前漏斗反推所需观看 / 出池笔记数） ──
    cur_fans = R["kpi"].get("粉丝数")
    fans_per_view = None
    if R["漏斗"].get("观看") and R["漏斗"].get("涨粉") is not None and R["漏斗"]["观看"]:
        fans_per_view = R["漏斗"]["涨粉"] / R["漏斗"]["观看"]
    R["每千观看涨粉"] = round(fans_per_view * 1000, 1) if fans_per_view else None
    if cur_fans is not None and fans_per_view:
        for tgt in TARGETS:
            need_fans = tgt - cur_fans
            if need_fans <= 0:
                continue
            need_views = need_fans / fans_per_view
            R["目标测算"].append({
                "目标": tgt, "还差粉": need_fans,
                "需观看": round(need_views),
                "需出池笔记": round(need_views / OUT_POOL_VIEWS, 1),
                "说明": f"按当前漏斗({R['每千观看涨粉']}粉/千观看)估算；提高封面CTR/转化率可大幅降低所需。",
            })
        # 杠杆场景：把观看转主页率提到健康线 5%，所需出池笔记会少多少
        if hr and fr and hr < GOOD_HOME_RATE:
            new_fpv = (GOOD_HOME_RATE / 100) * (fr / 100)
            tgt = TARGETS[0]
            need_fans = tgt - cur_fans
            if need_fans > 0:
                R["杠杆测算"] = {
                    "假设": f"把观看转主页率从 {hr}% 提到 {GOOD_HOME_RATE}%",
                    "到500需出池笔记": round((need_fans / new_fpv) / OUT_POOL_VIEWS, 1),
                    "对比当前": round((need_fans / fans_per_view) / OUT_POOL_VIEWS, 1),
                }

    # ── 本周行动清单（从判决 + 建议提炼成可勾选待办） ──
    todo = []
    for n in R["笔记"]:
        if n["判决色"] == "good" and "置顶" in n["判决"]:
            todo.append(f"把《{n['标题']}》置顶（还在爬，最能跑）")
        elif n["判决"].startswith("♻️"):
            todo.append(f"给《{n['标题']}》换抓眼封面+标题重发（好内容没被看见）")
    todo.append("下一条笔记：封面用信息流抓眼版（大字+数字反差），标题埋搜索词+悬念")
    todo.append("每篇结尾加'系列承诺 + 关注追更'钩子，把读者从单篇引到主页")
    todo.append("发布后 1 小时内自己引导前几条评论，帮冲出冷启动池")
    R["行动清单"] = todo[:6]

    with open(out, "w", encoding="utf-8") as f:
        json.dump(R, f, ensure_ascii=False, indent=2)
    print("wrote", out)
    print(f"  快照 {len(dates)} 个 | 最新 {latest} | 笔记 {len(notes)} 篇 | 建议 {len(adv)} 条")


if __name__ == "__main__":
    main()
