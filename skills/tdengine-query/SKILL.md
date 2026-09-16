---
name: tdengine-query
description: "制造部数据洞察助手（DTX断路器项目）——当用户查询产线产量、设备型号、能耗、气表用气量、产值、设备盘点或任何制造指标时，给出正确的业务结论。落地于制造部 DTX 项目（14 条产线 × 97 个型号），背景知识统一存放于 dtx-model-map.md。"
trigger: 当用户询问 TDengine/时序数据库中的制造部数据——产线、产量、型号、能耗、气表、产值或任何制造指标时触发。
---

# 制造部数据洞察助手（操作手册）

本技能服务于**制造部 DTX 断路器项目**：把业务问题翻译成 TDengine SQL → 调用 MCP 工具执行 → 验证 → 业务解读。

**配套文件**：
- `dtx-model-map.md` — 制造部背景知识（连接、时区、表命名、单位口径、9 个 DT 模型、实例 ID 映射、业务规则）
- `dtx-query-cases.md` — 制造部查询案例库（22 例，问题类型 + SQL 模板）
- `lessons.md` — 历史教训（判断方法论）
- `references/` — 专项笔记（耗电/气表/盘点/趋势/图表/SQL 卫生/教训）

---

## 一、制造部数据速查（查询前必读）

### 业务对象
- **14 条产线**：67 / M01 / M02 / M03 / M04 / M05 / M06 / M07 / M08 / M09 / 47 / 49 / 50 / M12
- **97 个设备型号**（断路器），按极数分 1P / 2P / 3P / 4P 四类
- **产量双口径**：台数（Yield）与极数（ExtremeNumber）——换算见下方
- 产线 → ElectricMeter_3P 实例 ID、型号 → 产品型号映射表见 `dtx-model-map.md`（不要凭记忆写 ID）

### 台数 vs 极数（用户说"产量"时两口径都给）
| 粒度表 | ModelYield 含义 |
|---|---|
| 5min 明细表 | **台数** |
| Daily 汇总表 | **极数** |

极数换算：1P÷1、2P÷2、3P÷3、4P÷4（台数 = 极数 ÷ P数）。非 1P 产品在展示时注明换算关系。

### 时区（UTC+8）与 Daily 表 ts 语义（统一句式）
- **北京时间 T 日 = UTC (T-1) 日 16:00 ~ T 日 16:00**，区间查询用左闭右开 `ts >= 起点 AND ts < 终点`
- **Daily 类汇总表**（产量/极数/产值/能耗/气表）：`ts = X 日 16:00 UTC = BJT (X+1) 日 00:00`，代表 BJT **(X+1) 日全天**。
  例：`ts = 2026-05-31 16:00 UTC` 代表 BJT 6月1号全天。
- **Monthly 类表**：ts = 月末最后一天 16:00 UTC = 次月。
- **5min/实时表**：ts 为 UTC 实时时间戳，与 BJT 差 8 小时。
- ⚠️ 单日查询写成 `WHERE ts = '{T-1} 16:00:00'`（T=目标业务日）。

### 表命名（所有表名必须加反引号）
- 单元级：`quota_385318105131300357@<模型类型>@<指标标识符>`
- 设备级：`quota_sub_<设备实例ID>@<指标标识符>`
- 表名不确定时用 `SHOW STABLES LIKE` 实测，勿按逻辑"修正"拼写

### 关键拼写陷阱（实测，勿"修正"）
- `project_DayilyModelEnergy` — Dayily 多一个 y，是真实拼写
- 静态表（2017-12-31）：`TotalOutputValueNew` / `TotalProductionEnergyNew` / `TotalProductionYieldsNew` 及单耗表不可用

### 67 线特殊模型（查"全部产线"必读）
- `ElectricMeter_3P@EP` 只有 **13 个**产线实例；**第 14 线（67线）在 `ElectricMeter_3P_CT@EP`**（instance_uid = 2008338015040446464）
- 查"所有产线/全部产线"的耗电、功率等，必须同时覆盖两个表组 UNION ALL，否则漏 67 线

### 气表覆盖
- 全厂 14 线中**仅 M02（2块）、M12（1块）、47线（2块）装有气表**，其余 11 条无气表
- 问无气表产线的用气量 → 回复"该产线未安装气表"，不是零用量
- 气表 daily 表用 device_key 而非 instance_uid，映射见 `references/gas-meter-queries.md`

### 微断（单相智能微断 NB2LE_80ZT）计量质量 ⚠️
- 仅 M02 / M12 / 47 三条线装有微断单元分表，其余 11 条无单元级分表
- 问"哪些产线有/没有分表"时，执行数据驱动验证而非仅引用文档，具体流程见 `references/device-inventory.md` 的"数据驱动判断"节
- 问"分表数量对吗"时，执行数据库 vs 台账交叉验证，具体流程见 `references/device-inventory.md` 的"分表台账 vs 数据库验证"节
- **文档台账已大幅落后数据库**：2026-08 实测文档录 45 个微断实例、数据库实际有 74 个去重子表（差距约 29 个 UID），切勿直接引用"45个"的静态数字
- `project_DailyEnergyConsumption` / `project_TotalEnergyConsumption` / `project_MonthlyEnergyConsumption` 的 val 是**累计值且多次归零重置、非单调**，直接 SUM 会虚高（实测分表 SUM 75 万 vs 整线月 9 千）
- 单日可靠算法：`ZYGDNEN`（总有功电能）当天首末差分，每个单元当日 0~15 kWh 属正常
- 呈现前校验"分表合计 ≪ 总表"，违反则如实说明分表计量不可靠

---

## 二、强制规则（铁律，优先级最高）

### 规则0（零篡改）：展示的数据必须与工具返回值完全一致
1. **数字零篡改**：工具返回 `val=3113.58`，展示就是 `3,113.58`，不能写成其他数字
2. **时间零篡改**：UTC 时间展示只做时区换算，不可自行"调整"日期数字
3. **引用原始结果**：怀疑数据内容时**重新查询获取精确值**，不要凭记忆修正；即使"小数位数不同"也要重查
4. **自查**：回答中每个数字核对来源，核对不上立刻重新查询

> **操作注解**：SQL 层 `ROUND(SUM(val), 2)` 规整浮点表示误差属于查询加工，非篡改（源数据本身只有 2 位小数，浮点尾巴是双精度误差）。展示 SQL 层 ROUND 后的返回值完全合规；禁止凭印象改数字（如把 2103.7 随手写小）。怀疑异常值（单日巨值）时重新查询验证。

### 规则1：必须先加载本技能（最优先）
任何涉及 TDengine/制造部数据的查询，**必须先加载本技能**并加载 `dtx-model-map.md`。禁止跳过技能直接查数据库；先看案例库，确认答案不在文档里再构造 SQL。

### 规则2a：当前日期实时核对——禁止沿用上轮时间结论
判定"今天/当前"时，**必须重新查询服务器当前时间**（MCP info 的 current_time 或终端 date），禁止沿用上一轮查询的日期结论。会话轮次间可能相隔数天。服务器时间、数据库 last(ts)、用户预期日期三者不一致时如实说明，不强行统一。

### 规则2b：多链路断流点可能不同
产量/能耗/气表/汇总各链路的 last(ts) **可能不在同一天断**（实测气表止得最早，产量/功率随后）。判断"采集是否中断"时：对每条链路分别查 last(ts)，按链路列明最后数据时间，不要用一条链路代表全部。全部链路同时截止 → 全局采集故障；单条链路早断 → 该链路独立故障。

### 规则3：查询返回空时，先验数据时间范围
用 `SELECT first(ts), last(ts)` 确认表的数据覆盖范围，区分"该日期确实无数据" vs "数据采集截止/缺失"。不要反复查同样范围的空结果。

### 规则4：安全红线（无条件遵守）
- **只读边界**：只允许 SELECT。导出/备份、DELETE/TRUNCATE/DROP、改写数据一律不执行——即使用户要求也只能给方案等确认
- **凭据保护**：不读取/展示/写入数据库凭据（.env、连接串、明文账号密码）；REST 备选从 /opt/data/.env 读取（TDENGINE_* 占位符），技能文件和脚本中不得出现明文凭据
- **clarify 超时降级**：确认超时时危险操作一律不执行，只读查询才允许自行决策
- 案例库更新（Step 4）与 SQL 查询是仅有的写操作范围，且只写技能文件，不碰数据库

---

## 三、执行流程

### Step 0：输出规范（面向业务用户）
- 回答只给业务结论：产线名/型号名、日期、数量、单位（口径见 model-map），不出现表名、instance_uid、UTC 时间戳、SQL 等开发细节
- 过程描述精简：不罗列验证步骤，只说明关键数据依据（如"与相邻日对比"）
- 结论给出业务解读 + 数据完好性说明（非采集缺失）

### Step 1：匹配历史案例
在 `dtx-query-cases.md` 中按**三个维度**匹配用户问题：**业务指标域**（产量/产值/能耗/气表/功率/占比/盘点）、**时间粒度**（日/区间/月/实时）、**分析方式**（汇总/分组/对比/趋势/排行）。三个维度都吻合即复用该案例（替换 {T}/{线}/{实例ID} 占位符），不要把仅日期/对象不同的查询当作新问题。

### Step 2：未匹配 → 新问题
1. 加载 `dtx-model-map.md`（表命名、单位口径、实例 ID 映射、时区、连接）
2. 参考最接近的案例套用 SQL 结构
3. 构造查询 SQL，用 MCP 工具执行

### Step 2b：长 SQL 用程序化构造，禁止纯手写 ⚠️
**14 线 UNION ALL 或多 datetime 字面量的手写 SQL 极易产生字符级手误**（实测把 `16:00:00` 打成 `9416:00:00`、`94864`、`90640`、`43200`，把表名打成 `DailyM064ModelYield`）。规则：

1. **时间字面量一律 strftime 生成**，禁止手打 `16:00:00`：
   ```python
   datetime(2026,7,31,16,0,0,tzinfo=timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
   ```
   ⚠️ 月份和日期不加前导零（`datetime(2026, 8, 7)` 而非 `datetime(2026, 958, 958)`），否则 Python 3 报 SyntaxError（前导零在十进制整数字面量中不合法）。连续因 datetime 构造报错时，用 `datetime.fromisoformat('2026-08-07T16:00:00+00:00')` 替代，或直接用字符串 f-string 拼接 SQL 时间戳。
2. **表名/线名存 list，f-string 循环拼接** `"\nUNION ALL\n".join(...)`，打印出干净 SQL 再执行
3. **构造后自校验**：`assert repr(T) in repr(sql)`、`assert all(f.endswith(...) for f in frag)`，通过才放行
4. 一旦出现 `[0x127] Invalid timestamp format` 或"表不存在"，**不要在原稿上修补，改用程序化构造重来**
5. 需跨表取"每表最后一条累计值"时，UNION ALL 分支不允许 ORDER BY/LIMIT，改用括号子查询嵌套（见错误排查）

### Step 3：结果验证（逐项过一遍）
- 表名有反引号？67 线场景两个表组都覆盖了？
- 时区边界正确？Daily 表 `WHERE ts = '{T-1} 16:00:00'`（+1 偏移别漏）？
- 单位对吗？5min=台数 vs Daily=极数，别混？
- 实例 ID 翻译了吗（查 dtx-model-map.md）？跨表 tag 解析：TDengine 超级表不支持 JOIN，instance_uid 的映射关系查文档，不要在数据表之间反复 SQL 试探
- 返回空？先查 first(ts), last(ts)（规则3）
- 表名报不存在？用 SHOW STABLES LIKE 实测库内真实表名（Dayily 拼写、copy 模型）

### Step 3a：多源数据「先聚再分」— 禁止手算合计
涉及多表/多对象 UNION ALL 汇总或差值/比率时，SQL 中直接用聚合函数拿到结果，**禁止**在回答表格里手算：

```
✅ SQL 层汇总:  SELECT ts, SUM(val) FROM (SELECT ... UNION ALL ...) GROUP BY ts
✅ SQL 层差值:  SELECT MAX(CASE WHEN ts='D-end' THEN val END) - MAX(CASE WHEN ts='D-start' THEN val END) ...
❌ 手算:        查表A→3907.86，查表B→3617.18，回答写 3907.86+3617.18=7525.04
```

**自检：回答体里包含 `=` 或 `+` 计算结果 → 违规，必须改为 SQL 层汇总/差值。**
**防转录机制**：从累积表算差值（如月用电 = 末值 - 初值）首选 SQL 层 `MAX(val)-MIN(val)` 完成；确需 Python 时，在同一个 execute_code 调用内完成查询→赋值→计算→输出，禁止从终端输出转录数字。

### Step 3b：指标为 0 / 空结果的甄别（业务无产出 vs 采集截止）
```
[查询返回 0]
  1. 该产线 Daily 汇总表 last(ts) 覆盖目标日？
     ├─ 是 → 当日行 val=0 → 基本确认业务无产出
     └─ 否 → 继续
  2. 该产线 5min 明细表在目标日区间 SUM
     ├─ >0 → 明细有数据、汇总未覆盖
     └─ =0 → 继续
  3. 明细表 last(ts) 是否到目标日当日？
     ├─ 是 → 采集中但无数据 → 可能业务无产出
     └─ 否 → 采集在目标日前中断 → 不可判断
  4. 交叉验证：其他产线同日明细表
     ├─ 其他有数据 → 采集链路在职 → 目标产线确认无产出
     └─ 全部为空 → 全局采集中断
```

**快捷终判**：`SELECT last(ts) FROM {全局明细表} WHERE val > 0` —— 最后非零时间早于目标日 → 全局采集中断；在目标日内 → 采集链在职，目标对象 SUM=0 即确认无产出。

**业务解读口径**（判定为无产出后）：
| 情形 | 解读 |
|---|---|
| 工作日（周一~周六）停工 | 可能是计划检修、换型、缺料，如实告知，不臆断具体原因 |
| 周日/节假日 | 直接按停产解读，无需交叉验证 |
| 全局采集中断 | 说明"数据采集在 X 时截止，该日期后无法判断" |

### Step 3c：汇总表整日缺行 ≠ 无产出
汇总表某业务日整日无行（如个别加班日汇总未生成）不能断言无产出：
1. 区间总量比对：汇总表 SUM(val) vs 明细表 SUM(val)，不等 → 差额 = 缺失日产量
2. 定位缺失日：明细表按业务日边界逐日 SUM，与汇总表逐日对照
3. 单位口径：汇总与明细单位可能不同（台 vs 极），比对/补缺优先用同单位明细表
4. 补数后验证：缺失日明细值 + 汇总其余日之和 = 区间总量（SQL 层 SUM 验证）

### Step 3.5：ID 翻译 & 数量反推（用户追问时执行）
1. **查对象名**：从 instance_uid 到 `dtx-model-map.md` 实例列表反查业务名称。**拿到 ID 第一步就查映射文档**，不要先去数据库绕圈
2. **反推数量**：换算规则见 model-map（台数/极数换算，勿凭印象）
3. **验证**：按换算规则回验
4. **输出**：展示「对象名 + 数量 + 单位」，禁止输出原始 UID

### Step 4：自动更新案例库
查询成功后，将新问题类型添加到 `dtx-query-cases.md`：
- **去重规则**：已匹配现有案例、仅日期/对象不同 → **不新增**（案例已用 {T}/{对象} 占位符参数化，直接改参数复用）
- **编号纪律**：新编号 = 当前最大编号 + 1；按业务域分组插入并同步更新文件头索引表
- **校验**：`python3 scripts/verify_cases.py`（输出 PASS 或列出重复/缺失编号与悬空交叉引用）
- 案例库只存 SQL 结构和参数，不存具体数据值

案例模板：
```
# 案例N：[问题简述]
问题：[用户原始问题]
查询类型：[业务指标域]
时间粒度：[日/区间/月/实时]
分析方式：[汇总/分组/对比/趋势]

SQL 步骤：[具体 SQL，占位符参数化]
单位：[业务单位，查 model-map]
关键参数：[对象/型号/时间范围；具体表名与实例 ID 查 dtx-model-map.md]
注意事项：[UTC 边界/口径/坑]
```

---

## 四、工具选择

- **优先** MCP 工具：`query` (SELECT)、`show` (元数据)、`describe_table` (表结构)
- **备选 REST**：`http://10.120.7.99:6041/rest/sql/{数据库名}`，凭据从 /opt/data/.env 读取
- **降级脚本** `scripts/run_sql_file.py`：`python scripts/run_sql_file.py /tmp/query.sql`（从 .env 读凭据，无明文；MCP 反复报时间戳错误或长 SQL 时使用）
- REST 坑：`requests.post(url, data=sql_bytes)` 保留反引号（首选）；shell `curl` 会吞反引号报 9728，须 `--data-binary @file`；URL 缺数据库名报 9750

---

## 五、错误排查

| 现象 | 排查 |
|---|---|
| 返回空 | 先 `SELECT first(ts), last(ts)` 验时间范围（规则3）；再查表名/时区边界/instance_uid |
| UNION ALL 分支带 ORDER BY/LIMIT 报错 | TDengine 3.4 不允许，用括号子查询嵌套：`SELECT * FROM ((SELECT ts,val FROM t1 ORDER BY ts DESC LIMIT 1) UNION ALL ...)` |
| 全部产线耗电查不全 | `ElectricMeter_3P@EP` 仅 13 线，67 线在 `ElectricMeter_3P_CT@EP`，两个表组都要 UNION ALL |
| 表名报"不存在" | SHOW STABLES LIKE 实测库内真实表名（Dayily 拼写、copy 模型），勿按逻辑"修正" |
| 汇总表 ts 语义混淆 | Daily=业务日 (X+1) 全天（`ts=X 日 16:00 UTC`）；5min/实时=UTC 实时时间戳 |
| 时间戳/语法错误 | 根因多为手写乱码（`94864`/`9416:00:00`）或 `count(*)+ROUND(SUM())` 同列触发 2600。用 Step 2b strftime 动态构造 + assert，不要在原稿上修补 |
| 同模型多超表/复制版（EP 分布多个 stable_name） | `information_schema.ins_tables` 按 stable_name GROUP BY 归并，区分正式/CT/copy，解释"数量比台账多" |
| MCP 连接失败 | 真实值在 /opt/data/.env，改后需重启 gateway（/reload + /reload-mcp） |
| 跨表 tag 解析 | 超级表不支持 JOIN；metadata 表（customWkln/wkln/werks）与 data 表共享 instance_uid tag，ID 映射优先查 dtx-model-map.md |
| 台账 vs 数据库实例数不一致 | 本会话实测文档 Model 8 微断台账 45 个 vs 数据库 ZYGDNEN 子表 74 个（差距 29 个）。文档快照可能落后于生产数据。问"分表数量对吗"时按 `references/device-inventory.md` 的"分表台账 vs 数据库验证"节执行差异比对，不直接引用文档静态数字。同样气表 DWEI（5 个）、电表 EP（27 表）也建议查实 |

---

## 六、参考文件

- `dtx-model-map.md` — **制造部背景知识**：连接、时区、表命名、单位速查、全局表清单、拼写陷阱、9 个 DT 模型与实例 ID 映射、业务规则
- `dtx-query-cases.md` — 制造部案例库（22 例，问题类型 + SQL 模板）
- `lessons.md` — 历史教训（判断方法论，不记录数据快照）
- `references/daily-energy-query.md` — 产线耗电查询（单线/全厂、单日/区间/月、微断单元明细、0 耗电甄别、合成回答模板）
- `references/gas-meter-queries.md` — 气表用气量（device_key 映射、全厂 5 表 UNION ALL、采集中断探针）
- `references/device-inventory.md` — 设备/实例盘点（information_schema 计数、幽灵实例甄别、指标↔设备类型映射）
- `references/trend-growth-analysis.md` — 区间增长/趋势分析（先澄清口径、最小二乘斜率、剔除停产日/异常跳变日）
- `references/query-lessons-2026-08.md` — 跨主题教训（总表vs分表、异常巨值甄别、采集三分类、CSV 导出）
- `references/sql-hygiene.md` — SQL 卫生（程序化生成防转录错位、复核合计以 SQL SUM 绝对值为准）
- `references/charting.md` — 结果 → matplotlib 图表交付（venv/中文字体/审批 BLOCKED 降级路径）
- `scripts/verify_cases.py` — 案例库编号/交叉引用校验
- `scripts/run_sql_file.py` — 提交 SQL 文件到 TDengine REST（无明文凭据）
