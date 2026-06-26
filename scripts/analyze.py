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
    # 同日多次拉取 / 标题被改 → 按"发布时间"去重（笔记的稳定身份；标题可随时编辑），
    # 保留最后一次（=最新标题与数据）。发布时间缺失时回退用标题。
    def nkey(r):
        return (r.get("发布时间") or "").strip() or r.get("标题")
    cur_map = {}
    for r in notes_raw:
        if r["拉取日期"] == latest:
            cur_map[nkey(r)] = r
    cur_notes = list(cur_map.values())
    prev_map = {nkey(r): r for r in notes_raw if r["拉取日期"] == prev} if prev else {}
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
        pv = prev_map.get(nkey(r))
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
        # 标杆笔记 = 观看最高的一条（账号当前唯一的"成功正样本"）；建议围绕"复制它"展开
        winner = max(notes, key=lambda n: n["观看"])
        rest = [n for n in notes if n is not winner]
        rest_max = max((n["观看"] for n in rest), default=0)

        if avg_v < COLD:
            R["诊断"].append(
                f"还没跑通出池：{len(notes)} 篇均观看 {avg_v:.0f}，仅 {len(out_pool)} 篇破 {COLD}。")
        else:
            R["诊断"].append(
                f"已有出池正样本：均观看 {avg_v:.0f}，{len(out_pool)}/{len(notes)} 篇破 {COLD}"
                f"——问题从'出不出池'变成'能不能复制'。")

        # P0：复制标杆（唯一最高优先，实验化、挂具体数字）
        gap = f"，其余仅 {rest_max}" if rest and rest_max < winner["观看"] else ""
        rep = (f"《{winner['标题']}》{winner['观看']} 观看是你目前的正样本{gap}。"
               f"别回头返工沉掉的笔记——拆这条的选题角度 / 标题句式 / 封面形式，"
               f"下一条只复制它的封面公式，验证能否再破 {int(winner['观看'] * 0.8)} 观看。")
        if winner.get("观看环比", 0) > 0:
            rep += f"它还在涨（+{winner['观看环比']}），先置顶吃满长尾。"
        adv.append({"优先级": "P0", "环节": "复制标杆", "建议": rep})

    # P1：基于真实漏斗指出瓶颈在哪、别在哪儿白费力
    hr = R["漏斗"].get("观看转主页率")
    fr = R["漏斗"].get("主页转涨粉率")
    if hr is not None and fr is not None:
        if fr >= LOW_FOLLOW_RATE and hr < GOOD_HOME_RATE:
            R["诊断"].append(f"瓶颈在'看到→点进主页'（{hr}%），不在'点进→关注'（{fr}% 已健康）。")
            adv.append({"优先级": "P1", "环节": "把力气下对环节",
                        "建议": f"主页转化已健康（{fr}%），别在关注钩子上耗。这阶段唯一杠杆是把'观看'做大（=复制标杆），转化是粉丝过千后的事。"})
        elif fr < LOW_FOLLOW_RATE:
            R["诊断"].append(f"瓶颈在'点进主页→关注'（{fr}% 偏低），人来了没留住。")
            adv.append({"优先级": "P1", "环节": "主页留人",
                        "建议": f"主页转化仅 {fr}%。置顶标杆笔记、bio 一句话讲清'关注你能得到什么'、封面风格统一，比拉新更省力。"})

    # 数据诚实：样本薄时标注置信度
    snaps = R["数据区间"].get("总快照数", 1)
    if snaps < 3 or len(notes) < 5:
        R["诊断"].append(
            f"⚠️ 样本薄（{snaps} 个快照 / {len(notes)} 篇），以上是方向性判断，需继续攒数据验证。")

    # 底线（压成一行）
    adv.append({"优先级": "底线", "环节": "合规",
                "建议": "只优化内容本身，不买量、不互关——僵尸粉伤权重、毁私域转化。"})

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

    # ── 本周行动清单：已并入"行动建议"（避免与建议重复），不再单列 ──
    R["行动清单"] = []

    # ── 结论（判断优先：一句话状态 + 本周唯一一件事 + 止损） ──
    winner = max(notes, key=lambda n: n["观看"]) if notes else None
    concl = {}
    if not notes:
        concl = {"状态": "账号刚起步，还没有可分析的笔记。",
                 "本周一件事": "先发 1–2 条，让分析师有数据可看。", "别做": ""}
    elif avg_v < COLD:
        concl = {
            "状态": f"还卡在冷启动池：{len(notes)} 篇里只有 {len(out_pool)} 篇破 {COLD} 观看。",
            "本周一件事": f"下一条主攻封面：参考观看最高的《{winner['标题']}》（{winner['观看']}），首图改成信息流抓眼版，目标破 {COLD} 出冷启动池。",
            "别做": "别一次想优化所有指标——这阶段只有'被看见'要紧，关注钩子 / 主页装修都往后放。"}
    else:
        tgt = int(winner["观看"] * 0.8)
        别做 = ("别回头返工已经沉底的笔记，性价比最低；先把标杆复制出第二条。"
                if not (fr is not None and fr >= LOW_FOLLOW_RATE and hr is not None and hr < GOOD_HOME_RATE)
                else f"别在关注钩子 / 转化上耗——主页转化已健康（{fr}%），问题是没人看见，不是留不住。")
        concl = {
            "状态": f"已跑通出池（《{winner['标题']}》破 {winner['观看']}），阶段任务从'出不出池'变成'能不能复制'。",
            "本周一件事": f"照《{winner['标题']}》的封面 + 选题公式再做一条，目标观看破 {tgt}。",
            "别做": 别做}
    snaps = R["数据区间"].get("总快照数", 1)
    concl["信心"] = (f"样本还薄（{snaps} 快照 / {len(notes)} 篇），以上是方向性判断；连续跑几期会越来越准。"
                     if snaps < 3 or len(notes) < 5 else "")
    R["结论"] = concl

    # ── 闭环验证（与上一期对比：上次让你做什么 → 数据怎么动 → 有没有执行） ──
    hist_path = os.path.join(D, "复盘历史.json")
    history = []
    if os.path.exists(hist_path):
        try:
            history = json.load(open(hist_path, encoding="utf-8"))
        except (ValueError, OSError):
            history = []
    note_keys = sorted({(n.get("发布时间") or n.get("标题")) for n in notes})
    cur_rec = {"最新日期": latest, "生成时间": R["生成时间"],
               "粉丝": R["kpi"].get("粉丝数"), "观看": R["漏斗"].get("观看"),
               "出池数": len(out_pool), "笔记数": len(notes),
               "标杆标题": winner["标题"] if winner else None,
               "标杆观看": winner["观看"] if winner else None,
               "本周一件事": concl.get("本周一件事", ""), "笔记keys": note_keys}
    prev_rec = next((h for h in reversed(history)
                     if h.get("最新日期") and h.get("最新日期") != latest), None)
    if prev_rec:
        def dline(label, old, new):
            if old is None or new is None:
                return None
            d = new - old
            arrow = "↑" if d > 0 else ("↓" if d < 0 else "→")
            return {"指标": label, "上次": old, "现在": new,
                    "变化": f"{arrow}{'+' if d > 0 else ''}{d}", "向好": d >= 0}
        recap = {"上次日期": prev_rec.get("最新日期"),
                 "上次任务": prev_rec.get("本周一件事", ""), "指标变化": []}
        for ln in (dline("粉丝", prev_rec.get("粉丝"), cur_rec["粉丝"]),
                   dline("7日观看", prev_rec.get("观看"), cur_rec["观看"]),
                   dline("出池笔记数", prev_rec.get("出池数"), cur_rec["出池数"])):
            if ln:
                recap["指标变化"].append(ln)
        new_keys = [k for k in note_keys if k not in set(prev_rec.get("笔记keys", []))]
        if new_keys:
            newest = max((n for n in notes if (n.get("发布时间") or n.get("标题")) in new_keys),
                         key=lambda n: n["观看"], default=None)
            if newest:
                base = (prev_rec.get("标杆观看") or 0) * 0.6
                recap["执行"] = f"上次后发了新内容《{newest['标题']}》（{newest['观看']} 观看）。"
                recap["执行向好"] = newest["观看"] >= base
        else:
            recap["执行"] = "上次到现在没发新内容——'本周一件事'还没动，建议悬而未决，先把它做掉。"
            recap["执行向好"] = False
        R["上周复盘"] = recap
    else:
        R["上周复盘"] = None
    # 写回历史（同一快照日重跑则替换，保持每个快照日一条）
    if history and history[-1].get("最新日期") == latest:
        history[-1] = cur_rec
    else:
        history.append(cur_rec)
    try:
        json.dump(history, open(hist_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    except OSError:
        pass

    with open(out, "w", encoding="utf-8") as f:
        json.dump(R, f, ensure_ascii=False, indent=2)
    print("wrote", out)
    print(f"  快照 {len(dates)} 个 | 最新 {latest} | 笔记 {len(notes)} 篇 | 建议 {len(adv)} 条 | "
          f"上期对比 {'有' if R.get('上周复盘') else '无(首期)'}")


if __name__ == "__main__":
    main()
