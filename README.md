# hekouwang-channel-analyst-skill · 渠道数据分析师

> 会勇禾口王的AI笔记 · `@huiyonghkw`
> 把社媒账号的公开后台数据，做成一份能看、能交付、能指导动作的复盘报告。

一个 [Claude Agent Skill](https://docs.claude.com/en/docs/claude-code/skills)：
**每日取数 → 分析 → 生成 V2 米白「渠道数据复盘报告」HTML → 给分优先级的数据建议**。
v1 覆盖小红书；结构按多渠道/多账号预留。

## 能做什么

- **取数**：用 [OpenCLI](https://github.com/jackwener/opencli) 复用 Chrome 登录态，拉小红书创作者后台的粉丝 / 转化漏斗 / 逐篇数据 / 每日明细，追加进 CSV 时间序列。
- **分析**：算固定指标体系——涨粉漏斗（观看→主页→涨粉）、出池诊断、笔记红黑榜、趋势、**涨粉目标测算**（到 N 粉还需多少出池笔记 + 转化率杠杆）、指标基准对照、逐篇判决。
- **报告**：输出自托管单文件 HTML（V2 米白），ECharts 漏斗 / 仪表盘 / 趋势 / 条形图，可截图 / 转 PDF / 转长图交付。
- **建议**：规则引擎给分优先级动作（P0 出池 / P1 转化 / P2 主页 / 底线 合规）+ 本周行动清单。

## 合规底线（写进 skill）

不刷量、不互关刷粉、不承诺涨粉数字；数据只来自账号自己的公开创作者后台。

## 三步流水线

```bash
# 前置：opencli + Chrome 登录态 + 扩展已连（opencli doctor 看 [OK] Extension）
python3 scripts/pull.py        --data-dir <数据目录>   # ① 取数 → CSV
python3 scripts/analyze.py     --data-dir <数据目录>   # ② 分析 → report_data.json
python3 scripts/build_report.py --data-dir <数据目录>  # ③ 报告 → 渠道数据复盘报告.html
```

数据默认写到当前工作目录下的 `渠道数据分析师/`（可用 `--data-dir` 改；多账号给各自目录）。
每日自动取数用 macOS launchd 定时跑 `pull.py`（配方见 `references/01-取数.md`）。

## 结构

```
SKILL.md              # 触发词 + 方法论 + 合规底线 + 路由
references/
  01-取数.md          # opencli 命令 / CSV schema / launchd 自动化 / 加渠道·加账号
  02-分析框架.md      # 指标定义 / 阈值 / 诊断与建议规则（可调参）
  03-报告设计.md      # 报告 HTML 规范 / ECharts 防踩坑 / 自用版 vs 客户版
  04-服务化.md        # 付费服务化：套餐 / 定价参考 / 获客 / 交付
scripts/              # pull.py / analyze.py / build_report.py
assets/echarts.min.js # 报告图表库（Apache-2.0，内联进报告，单文件离线可截图）
```

## 安装

放进 Claude 的 skills 目录即可被自动发现：

```bash
git clone https://github.com/huiyonghkw/hekouwang-channel-analyst-skill.git \
  ~/.claude/skills/hekouwang-channel-analyst-skill
```

报告字体默认引用 `hekouwang-content-factory` 内置的 Anthropic 字体；没有时用 `build_report.py --font-dir` 指定，或换系统字体。

## 第三方

- [Apache ECharts](https://echarts.apache.org/)（`assets/echarts.min.js`）— Apache License 2.0。

---

—— 会勇禾口王的AI笔记 · `@huiyonghkw`
不聊 AI 会不会取代你，只聊先用 AI 的人怎么取代你。
