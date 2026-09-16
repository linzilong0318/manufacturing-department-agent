# TDengine 查询结果 → 图表交付（matplotlib）

场景：用户要求"画个柱状图/图表/趋势图"展示产线产量、能耗等查询结果（飞书交付）。

## 环境（实测可用配置）

| 项目 | 配置 |
|---|---|
| 绘图解释器 | `/opt/data/.venv/bin/python`（uv venv 创建，已装 matplotlib 3.11 + numpy + Pillow）。execute_code 默认 python 是 Hermes venv，**无 matplotlib**，须 subprocess 调 `/opt/data/.venv/bin/python` |
| 首次安装 | `UV_CACHE_DIR=/tmp/uv-cache uv venv /opt/data/.venv` 然后 `UV_CACHE_DIR=/tmp/uv-cache uv pip install --python /opt/data/.venv/bin/python matplotlib` |
| uv 缓存坑 | HOME=/opt/data/home，uv 默认缓存 `/opt/data/home/.cache/uv` 无写权限 → 必须设 `UV_CACHE_DIR=/tmp/uv-cache`（否则报 "Permission denied ... .cache/uv"） |
| 中文字体 | 系统有 WenQuanYi Zen Hei；matplotlib 需 `plt.rcParams['font.sans-serif'] = ['WenQuanYi Zen Hei', 'DejaVu Sans']` + `axes.unicode_minus=False`，否则中文变方块。启动时遍历候选字体名确认 |
| 图片自检 | vision_analyze 工具缓存目录 `/opt/data/cache/vision` 不可写会报错 → 改用 `/opt/data/.venv/bin/python` + PIL 检查尺寸/非空，或 font_manager 查字体 |

## 流程

1. **数据先行**：按 dtx-query-cases.md 查逐日数据（含缺行补充、口径确认）。数值**零篡改**：脚本直接内嵌查询返回值，禁止手算/改写（遵循 SKILL.md 规则0）。
2. **图表规范**（面向业务用户）：
   - 柱状图：生产日蓝色 `#4C72B0`、停产日灰色 `#C8C8C8`；柱顶标注千分位数值；横轴"日期+星期"；标题含区间与数据截止说明
   - 单位标注明确：极数 vs 台数，非 1P 产品注明换算关系（如 2P：台数 = 极数 ÷ 2）
   - `figsize=(10, 5.2), dpi=150`，保存 PNG 到 `/opt/data/charts/`（目录不存在则 os.makedirs）
   - 脚本模板可直接复用：`/opt/data/charts/67线_plot.py`（本次会话产物，含字体检测+柱状图完整逻辑）
3. **交付**：回复中 `MEDIA:/绝对路径.png`（飞书内联显示）+ 图表要点解读（峰值/低谷/停产日/数据说明）。

## 权限审批坑（重要）

- execute_code/terminal 首次执行需用户侧审批；**用户在聊天里说"确认执行"不一定触达审批通道** → 工具返回 `BLOCKED: timed out without user response`
- 被 BLOCKED 后**不可重试、不可换工具绕道**（系统明令 "do NOT retry / do NOT attempt the same outcome via a different tool"）
- 正确降级路径：**write_file 交付完整可运行脚本**（write_file 通常可用，审批只拦代码执行类）+ 给出运行命令（如 `/opt/data/.venv/bin/python script.py` 或 `uv run --with matplotlib python script.py`），请用户本机执行；或等用户恢复审批后重试
- 审批放行后可能仍有环境问题（依赖缺失），此时 execute_code 可正常跑诊断脚本（检查 HOME/python/uv/可写目录），再按上表安装依赖
