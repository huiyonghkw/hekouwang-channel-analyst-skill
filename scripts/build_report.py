#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
渠道数据分析师 · 报告生成器 v2（ECharts 版）
读 report_data.json → 输出 V2 米白「渠道数据复盘报告」HTML：
ECharts 漏斗/仪表盘/趋势/条形图 + 目标测算 + 基准对照 + 逐篇判决 + 行动清单。
ECharts 内联（单文件、离线可截图）。

用法:
  python3 build_report.py [--data-dir <目录>] [--in <json>] [--out <html>] [--font-dir <字体>]
"""
import argparse, html, json, os

SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEF_FONT = os.path.expanduser("~/.claude/skills/hekouwang-content-factory/assets/fonts")
ECHARTS = os.path.join(SKILL, "assets", "echarts.min.js")
PRI_COLOR = {"P0": "#c0392b", "P1": "#c15f3c", "P2": "#5c6b7a", "底线": "#8a877e"}
GRADE_CLS = {"健康": "ok", "好": "ok", "及格": "warn", "偏低": "bad", "—": ""}
VERDICT_CLS = {"good": "ok", "warn": "warn", "bad": "bad"}


def esc(s):
    return html.escape(str(s if s is not None else ""))


def kpi_card(label, value, sub=None, color="var(--accent)"):
    sub_h = f'<div class="kpi-sub">{esc(sub)}</div>' if sub else ""
    return (f'<div class="kpi"><div class="kpi-lb">{esc(label)}</div>'
            f'<div class="kpi-num" style="color:{color}">{esc(value)}</div>{sub_h}</div>')


def build(R, font_dir):
    k = R.get("kpi", {})
    fn = R.get("漏斗", {})
    netfans = k.get("粉丝净增")
    net_s = (f"环比 {'+' if netfans >= 0 else ''}{netfans}" if netfans is not None else "首次快照")

    kpis = "".join([
        kpi_card("粉丝数", k.get("粉丝数", "—"), net_s),
        kpi_card("近7日观看", fn.get("观看") or "—", "全部笔记累计", "var(--accent3)"),
        kpi_card("近7日涨粉", fn.get("涨粉") or "—", f"每千观看 {R.get('每千观看涨粉','—')} 粉", "var(--accent2)"),
        kpi_card("获赞与收藏", k.get("获赞藏", "—"),
                 (f"距 500 等级差 {k['距500等级']}" if k.get("距500等级") else None)),
    ])

    # 目标测算卡
    tgt_cards = ""
    for t in R.get("目标测算", []):
        tgt_cards += (
            f'<div class="goal"><div class="goal-h">到 {t["目标"]} 粉</div>'
            f'<div class="goal-row"><span>还差</span><b>{t["还差粉"]} 粉</b></div>'
            f'<div class="goal-row"><span>需累计观看</span><b>{t["需观看"]:,}</b></div>'
            f'<div class="goal-big">{t["需出池笔记"]}<span> 篇出池笔记</span></div></div>')
    lever = R.get("杠杆测算")
    lever_h = ""
    if lever:
        lever_h = (
            f'<div class="lever"><div class="lever-i">⚡</div><div>'
            f'<b>{esc(lever["假设"])}</b>，到 500 粉所需出池笔记从 '
            f'<s>{lever["对比当前"]} 篇</s> 降到 <em>{lever["到500需出池笔记"]} 篇</em>'
            f'——转化率是比"多发"更省力的杠杆。</div></div>')
    goal_sec = (f'<div class="card"><div class="sec-h">涨粉目标测算</div>'
                f'<div class="goals">{tgt_cards}</div>{lever_h}'
                f'<div class="note">{esc(R.get("目标测算",[{}])[0].get("说明","")) if R.get("目标测算") else ""}</div></div>'
                ) if R.get("目标测算") else ""

    # 基准对照
    base_rows = ""
    for name, b in R.get("基准", {}).items():
        v = b.get("值")
        vs = f'{v}%' if isinstance(v, (int, float)) and "率" in name else (f'{v}%' if (name == "出池笔记占比" and v is not None) else (v if v is not None else "—"))
        cls = GRADE_CLS.get(b.get("评级"), "")
        base_rows += (f'<tr><td>{esc(name)}</td><td class="t-num">{esc(vs)}</td>'
                      f'<td class="t-num" style="color:var(--text3)">{esc(b.get("健康线"))}</td>'
                      f'<td><span class="badge {cls}">{esc(b.get("评级"))}</span></td></tr>')
    base_sec = (f'<div class="card"><div class="sec-h">指标基准对照</div>'
                f'<table class="tbl"><thead><tr><th>指标</th><th>你的值</th><th>健康线</th><th>评级</th></tr></thead>'
                f'<tbody>{base_rows}</tbody></table></div>') if base_rows else ""

    # 笔记红黑榜（表 + 判决）
    rows = ""
    for n in R.get("笔记", []):
        badge = ('<span class="badge ok">已出池</span>' if n["出池"]
                 else '<span class="badge bad">卡冷启动</span>')
        delta = n.get("观看环比")
        d_h = (f'<span class="delta up">+{delta}</span>' if delta and delta > 0
               else (f'<span class="delta">{delta}</span>' if delta else ""))
        vcls = VERDICT_CLS.get(n.get("判决色"), "")
        rows += (
            f'<tr><td class="t-title">{esc(n["标题"])}<div class="t-time">{esc(n["发布时间"])}</div></td>'
            f'<td class="t-num">{n["观看"]} {d_h}</td><td class="t-num">{n["赞"]}</td>'
            f'<td class="t-num">{n["藏"]}</td><td class="t-num">{n["评"]}</td>'
            f'<td>{badge}</td><td><span class="verdict {vcls}">{esc(n.get("判决",""))}</span></td></tr>')
    notes_sec = (
        '<div class="card"><div class="sec-h">笔记红黑榜 · 逐篇判决</div>'
        '<div id="c_notes" class="echart" style="height:240px"></div>'
        '<table class="tbl" style="margin-top:18px"><thead><tr><th>笔记</th><th>观看</th><th>赞</th>'
        '<th>藏</th><th>评</th><th>状态</th><th>建议动作</th></tr></thead>'
        f'<tbody>{rows}</tbody></table></div>') if R.get("笔记") else ""

    # 诊断
    diag = "".join(f'<li>{esc(d)}</li>' for d in R.get("诊断", []))
    diag_sec = (f'<div class="card"><div class="sec-h">诊断</div><ul class="diag">{diag}</ul></div>'
                if diag else "")

    # 行动清单
    todos = "".join(f'<li><span class="chk"></span>{esc(t)}</li>' for t in R.get("行动清单", []))
    todo_sec = (f'<div class="card todo"><div class="sec-h">本周行动清单</div>'
                f'<ul class="todolist">{todos}</ul></div>') if todos else ""

    # 建议
    adv = ""
    for a in R.get("建议", []):
        pri = a.get("优先级", "")
        adv += (f'<div class="adv"><div class="adv-tag" style="background:{PRI_COLOR.get(pri,"#8a877e")}">{esc(pri)}</div>'
                f'<div><div class="adv-h">{esc(a.get("环节",""))}</div>'
                f'<div class="adv-t">{esc(a.get("建议",""))}</div></div></div>')
    adv_sec = f'<div class="card"><div class="sec-h">本周怎么做（按优先级 · 每条挂着你的数据）</div>{adv}</div>' if adv else ""

    # 图表数据
    chart_data = {
        "funnel": [{"name": s, "value": fn.get(s) or 0} for s in ("观看", "主页访问", "涨粉")],
        "g_home": fn.get("观看转主页率"), "g_follow": fn.get("主页转涨粉率"),
        "trend_fans": R.get("趋势", {}).get("粉丝", []),
        "trend_views": R.get("趋势", {}).get("观看", []),
        "trend_newfans": R.get("趋势", {}).get("涨粉", []),
        "notes": [{"name": n["标题"], "value": n["观看"], "out": n["出池"]}
                  for n in R.get("笔记", [])][::-1],
    }

    with open(ECHARTS, encoding="utf-8") as f:
        echarts_js = f.read()
    di = R.get("数据区间", {})
    return TEMPLATE.format(
        font_dir=font_dir, echarts=echarts_js, data=json.dumps(chart_data, ensure_ascii=False),
        account=esc(R.get("账号", "")), platform=esc(R.get("平台", "")), gen=esc(R.get("生成时间", "")),
        period=esc(f'最新 {di.get("最新","—")} · 共 {di.get("总快照数",0)} 个数据快照'),
        kpis=kpis, goal=goal_sec, base=base_sec, notes=notes_sec,
        diag=diag_sec, todo=todo_sec, adv=adv_sec)


TEMPLATE = """<!DOCTYPE html><html lang="zh-CN" class="light"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>渠道数据复盘报告</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@400;500;700;800;900&display=swap" rel="stylesheet">
<style>
@font-face{{font-family:'Anthropic Sans';src:url('{font_dir}/anthropicSans.woff2') format('woff2');font-weight:300 800;font-display:swap}}
@font-face{{font-family:'Anthropic Mono';src:url('{font_dir}/anthropicMono.woff2') format('woff2');font-weight:300 800;font-display:swap}}
:root{{--bg:#faf9f5;--surface:#fff;--surface2:#f4f2eb;--border:rgba(20,20,19,.10);
--text:#1a1a18;--text2:#56544e;--text3:#8a877e;--accent:#c15f3c;--accent2:#5c6b7a;--accent3:#a07a3c;--danger:#c0392b;--good:#137333;
--font:'Anthropic Sans','Noto Sans SC','PingFang SC',system-ui,sans-serif;
--mono:'Anthropic Mono','PingFang SC',ui-monospace,monospace;
--shadow:0 1px 2px rgba(20,20,19,.04),0 8px 24px rgba(20,20,19,.06)}}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:var(--bg);color:var(--text);font-family:var(--font);-webkit-font-smoothing:antialiased;line-height:1.7;padding:56px 24px 80px}}
.wrap{{max-width:1080px;margin:0 auto}}
.sysbar{{display:flex;justify-content:space-between;font-family:var(--mono);font-size:15px;letter-spacing:.16em;text-transform:uppercase;color:var(--text3);border-bottom:1px solid var(--border);padding-bottom:18px}}
.sys-l{{display:flex;align-items:center;gap:10px;color:var(--text2)}}
.live{{width:10px;height:10px;border-radius:50%;background:var(--accent)}}
.sys-r{{color:var(--accent)}}
h1{{font-size:60px;font-weight:900;letter-spacing:-.01em;margin-top:34px;line-height:1.1}}
.subline{{font-size:21px;color:var(--text2);margin-top:14px}}
.period{{font-family:var(--mono);font-size:15px;color:var(--text3);margin-top:8px;letter-spacing:.04em}}
.kpis{{display:grid;grid-template-columns:repeat(4,1fr);gap:18px;margin-top:38px}}
.kpi{{background:var(--surface);border:1px solid var(--border);border-radius:16px;padding:26px 24px;box-shadow:var(--shadow)}}
.kpi-lb{{font-size:16px;color:var(--text2)}}
.kpi-num{{font-family:var(--mono);font-size:46px;font-weight:700;margin-top:6px;line-height:1}}
.kpi-sub{{font-size:13px;color:var(--text3);margin-top:8px;font-family:var(--mono)}}
.card{{background:var(--surface);border:1px solid var(--border);border-radius:18px;padding:34px 36px;box-shadow:var(--shadow);margin-top:26px}}
.sec-h{{font-size:26px;font-weight:800;margin-bottom:22px}}
.grid2{{display:grid;grid-template-columns:1.3fr 1fr;gap:22px}}
.echart{{width:100%}}
.goals{{display:grid;grid-template-columns:1fr 1fr;gap:18px}}
.goal{{background:var(--surface2);border:1px solid var(--border);border-radius:14px;padding:24px 26px}}
.goal-h{{font-size:22px;font-weight:800;color:var(--accent)}}
.goal-row{{display:flex;justify-content:space-between;font-size:16px;color:var(--text2);margin-top:12px}}
.goal-row b{{font-family:var(--mono);color:var(--text);font-size:18px}}
.goal-big{{font-family:var(--mono);font-size:52px;font-weight:800;margin-top:14px;color:var(--text);line-height:1}}
.goal-big span{{font-family:var(--font);font-size:17px;font-weight:600;color:var(--text2)}}
.lever{{display:flex;gap:16px;align-items:flex-start;background:rgba(193,95,60,.06);border:1px solid rgba(193,95,60,.2);border-radius:14px;padding:22px 26px;margin-top:20px;font-size:18px;color:var(--text2)}}
.lever-i{{font-size:26px}}.lever b{{color:var(--text)}}.lever s{{color:var(--text3)}}.lever em{{color:var(--accent);font-style:normal;font-weight:800;font-size:20px}}
.note{{font-size:14px;color:var(--text3);margin-top:16px;font-family:var(--mono)}}
.tbl{{width:100%;border-collapse:collapse}}
.tbl th{{text-align:left;font-family:var(--mono);font-size:13px;color:var(--text3);text-transform:uppercase;letter-spacing:.06em;padding:10px 10px;border-bottom:2px solid var(--border)}}
.tbl td{{padding:14px 10px;border-bottom:1px solid var(--border);font-size:17px;vertical-align:top}}
.t-title{{font-weight:600;max-width:300px}}.t-time{{font-family:var(--mono);font-size:12px;color:var(--text3);margin-top:4px;font-weight:400}}
.t-num{{font-family:var(--mono);font-size:18px;white-space:nowrap}}
.delta{{font-size:13px;color:var(--text3)}}.delta.up{{color:var(--good)}}
.badge{{font-family:var(--mono);font-size:12px;padding:4px 11px;border-radius:999px;white-space:nowrap;background:var(--surface2);color:var(--text2)}}
.badge.ok{{background:rgba(19,115,51,.1);color:var(--good)}}
.badge.warn{{background:rgba(160,122,60,.13);color:var(--accent3)}}
.badge.bad{{background:rgba(192,57,43,.1);color:var(--danger)}}
.verdict{{font-size:14px;font-weight:600;white-space:nowrap}}
.verdict.ok{{color:var(--good)}}.verdict.warn{{color:var(--accent3)}}.verdict.bad{{color:var(--danger)}}
.diag{{list-style:none}}.diag li{{font-size:18px;padding:13px 0 13px 28px;position:relative;border-bottom:1px solid var(--border)}}
.diag li:before{{content:'';position:absolute;left:4px;top:22px;width:9px;height:9px;border-radius:50%;background:var(--accent)}}
.diag li:last-child{{border-bottom:none}}
.todo .todolist{{list-style:none}}
.todolist li{{display:flex;align-items:flex-start;gap:14px;font-size:18px;padding:14px 0;border-bottom:1px dashed var(--border)}}
.todolist li:last-child{{border-bottom:none}}
.chk{{width:22px;height:22px;border:2px solid var(--accent);border-radius:6px;flex-shrink:0;margin-top:2px}}
.adv{{display:flex;gap:18px;align-items:flex-start;padding:18px 0;border-bottom:1px solid var(--border)}}
.adv:last-child{{border-bottom:none}}
.adv-tag{{font-family:var(--mono);font-size:14px;font-weight:700;color:#fff;padding:6px 14px;border-radius:8px;flex-shrink:0;min-width:54px;text-align:center}}
.adv-h{{font-size:20px;font-weight:800}}.adv-t{{font-size:17px;color:var(--text2);margin-top:6px}}
.foot{{margin-top:48px;padding-top:26px;border-top:1px solid var(--border);display:flex;justify-content:space-between;align-items:flex-end;flex-wrap:wrap;gap:16px}}
.foot-brand{{font-size:26px;font-weight:800}}.foot-brand span{{color:var(--accent)}}
.foot-note{{font-family:var(--mono);font-size:13px;color:var(--text3);max-width:560px;text-align:right;line-height:1.6}}
@media(max-width:760px){{.kpis,.goals{{grid-template-columns:repeat(2,1fr)}}.grid2{{grid-template-columns:1fr}}h1{{font-size:40px}}}}
</style></head><body><div class="wrap">
<div class="sysbar"><div class="sys-l"><span class="live"></span>{account}</div><div class="sys-r">渠道数据分析 · {platform}</div></div>
<h1>渠道数据<br>复盘报告</h1>
<div class="subline">基于公开创作者后台数据的中立复盘 · 不承诺涨粉数字 · 不刷量</div>
<div class="period">{period} · 生成于 {gen}</div>
<div class="kpis">{kpis}</div>
<div class="card"><div class="sec-h">转化漏斗 · 近 7 日</div>
<div class="grid2"><div id="c_funnel" class="echart" style="height:320px"></div>
<div><div id="c_g1" class="echart" style="height:172px"></div><div id="c_g2" class="echart" style="height:172px"></div></div></div></div>
{goal}{base}
<div class="card"><div class="sec-h">近 7 日每日趋势（观看 / 涨粉）</div>
<div id="c_trend" class="echart" style="height:300px"></div></div>
{notes}{diag}{todo}{adv}
<div class="foot"><div class="foot-brand">会勇禾口王 · <span>数据复盘</span></div>
<div class="foot-note">数据来源：小红书创作者中心公开后台 · 本报告为运营复盘工具，结论基于历史数据，不构成对未来表现的承诺。</div></div>
</div>
<script>{echarts}</script>
<script>
var D={data};
var C={{clay:'#c15f3c',slate:'#5c6b7a',ochre:'#a07a3c',text:'#1a1a18',t2:'#56544e',t3:'#8a877e',danger:'#c0392b',good:'#137333',line:'rgba(20,20,19,.10)'}};
var FONT="'Noto Sans SC','PingFang SC',sans-serif";
function I(id,opt){{var el=document.getElementById(id);if(!el)return;var ch=echarts.init(el,null,{{renderer:'canvas'}});opt.animation=false;opt.textStyle={{fontFamily:FONT,color:C.t2}};ch.setOption(opt);window.addEventListener('resize',function(){{ch.resize();}});}}
// 漏斗
I('c_funnel',{{tooltip:{{trigger:'item',formatter:'{{b}}: {{c}}'}},color:[C.clay,C.ochre,C.slate],
series:[{{type:'funnel',sort:'descending',gap:6,minSize:'26%',left:'4%',right:'4%',top:6,bottom:6,
label:{{show:true,position:'inside',color:'#fff',fontSize:16,fontWeight:700,formatter:'{{b}}\\n{{c}}'}},
data:D.funnel}}]}});
// 仪表盘
function gauge(id,title,val,max,low,good){{
 I(id,{{series:[{{type:'gauge',min:0,max:max,radius:'78%',center:['50%','52%'],startAngle:210,endAngle:-30,
 axisLine:{{lineStyle:{{width:13,color:[[low/max,C.danger],[good/max,C.ochre],[1,C.good]]}}}},
 pointer:{{width:5,length:'46%',itemStyle:{{color:C.text}}}},
 anchor:{{show:true,size:12,itemStyle:{{color:C.text}}}},axisTick:{{show:false}},splitLine:{{show:false}},
 axisLabel:{{show:false}},title:{{offsetCenter:[0,'92%'],fontSize:14,color:C.t2}},
 detail:{{valueAnimation:false,offsetCenter:[0,'62%'],fontSize:28,fontWeight:800,color:C.text,formatter:(val==null?'—':'{{value}}%')}},
 data:[{{value:(val==null?0:val),name:title}}]}}]}});
}}
gauge('c_g1','观看→主页',D.g_home,10,3,5);
gauge('c_g2','主页→涨粉',D.g_follow,20,8,10);
// 趋势（双线）
(function(){{
 var dates={{}};D.trend_views.forEach(function(p){{dates[p['日期']]=1;}});D.trend_newfans.forEach(function(p){{dates[p['日期']]=1;}});
 var cats=Object.keys(dates).sort();
 function ser(arr){{var m={{}};arr.forEach(function(p){{m[p['日期']]=p['值'];}});return cats.map(function(d){{return m[d]!=null?m[d]:null;}});}}
 var single=cats.length<2;
 I('c_trend',{{tooltip:{{trigger:'axis'}},legend:{{data:['每日观看','每日涨粉'],top:0,textStyle:{{color:C.t2}}}},
 grid:{{left:55,right:55,top:40,bottom:30}},
 xAxis:{{type:'category',boundaryGap:false,data:cats.map(function(d){{return d.slice(5);}}),axisLine:{{lineStyle:{{color:C.line}}}},axisLabel:{{color:C.t3}}}},
 yAxis:[{{type:'value',name:'观看',axisLabel:{{color:C.t3}},splitLine:{{lineStyle:{{color:C.line}}}}}},
        {{type:'value',name:'涨粉',minInterval:1,axisLabel:{{color:C.t3}},splitLine:{{show:false}}}}],
 series:[{{name:'每日观看',type:'line',smooth:true,symbolSize:8,data:ser(D.trend_views),itemStyle:{{color:C.clay}},lineStyle:{{width:3,color:C.clay}},areaStyle:{{color:'rgba(193,95,60,.08)'}}}},
         {{name:'每日涨粉',type:'line',yAxisIndex:1,smooth:true,symbolSize:8,data:ser(D.trend_newfans),itemStyle:{{color:C.slate}},lineStyle:{{width:3,color:C.slate}}}}],
 graphic:single?[{{type:'text',left:'center',top:'middle',style:{{text:'数据积累中：每天自动拉一次，\\n≥2 天后这里出现完整趋势线',fill:C.t3,fontSize:15,fontFamily:FONT,textAlign:'center'}}}}]:[]}});
}})();
// 笔记观看条形（按出池着色）
I('c_notes',{{tooltip:{{trigger:'axis',axisPointer:{{type:'shadow'}}}},grid:{{left:170,right:64,top:38,bottom:26}},
xAxis:{{type:'value',axisLabel:{{color:C.t3}},splitLine:{{lineStyle:{{color:C.line}}}}}},
yAxis:{{type:'category',data:D.notes.map(function(n){{return n.name;}}),axisLine:{{lineStyle:{{color:C.line}}}},
axisLabel:{{color:C.t2,fontSize:13,width:152,overflow:'truncate',align:'right'}}}},
series:[{{type:'bar',barWidth:'52%',data:D.notes.map(function(n){{return {{value:n.value,itemStyle:{{color:n.out?C.good:C.danger,borderRadius:[0,6,6,0]}}}};}}),
label:{{show:true,position:'right',color:C.t2,fontFamily:'monospace'}},
markLine:{{symbol:'none',data:[{{xAxis:300,label:{{formatter:'出池线 300',position:'end',color:C.t3}},lineStyle:{{color:C.t3,type:'dashed'}}}}]}}}}]}});
</script>
</body></html>"""


def main():
    ap = argparse.ArgumentParser()
    dd = os.environ.get("CHANNEL_ANALYST_DATA") or os.path.join(os.getcwd(), "渠道数据分析师")
    ap.add_argument("--data-dir", default=dd)
    ap.add_argument("--in", dest="inp", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--font-dir", default=DEF_FONT)
    args = ap.parse_args()
    inp = args.inp or os.path.join(args.data_dir, "report_data.json")
    out = args.out or os.path.join(args.data_dir, "渠道数据复盘报告.html")
    with open(inp, encoding="utf-8") as f:
        R = json.load(f)
    open(out, "w", encoding="utf-8").write(build(R, args.font_dir))
    print("wrote", out, f"({os.path.getsize(out)//1024} KB)")


if __name__ == "__main__":
    main()
