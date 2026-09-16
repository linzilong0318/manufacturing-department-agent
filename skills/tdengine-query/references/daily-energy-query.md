# 产线耗电量查询（未来案例 23：单线/全厂、单日/区间/月/阈值排行，含微断单元明细）

> 2026-08 会话确立——用户高频查询模式，本次实测 5 种变体：
> 单线单日 / 单线区间多日 / 全部产线单日 / 全部产线月汇总 / 单线"所有电表明细"（主三相电表 + 单相微断单元）。
> 因案例库文件 dtx-query-cases.md 位于技能根目录不受 skill_manage 管理，先存为 references 支持文件，
> 待 curator 合并进案例库正文（编号接案例 22 之后）。

问题：查询2号产线2026年8月7日的耗电；查询3号产线2026年8月1日至8月8日的耗电量；查询全部产线2026年8月8日的耗电量；查询2号产线所有电表2026年8月8日的明细
查询类型：能耗（电）
时间粒度：日 / 区间 / 月
分析方式：汇总（单线、全厂、按设备分项）

## SQL 步骤（占位符 {T}=目标BJT日期、{线}=产线后缀）

**核心表：`quota_sub_{产线ElectricMeter_3P实例ID}@public_dailyEnergyConsumption`（每日用能，kWh）**
- ts 语义同产量 Daily 表：`ts = X 日 16:00 UTC = BJT X+1 日全天`，单日查询即 `WHERE ts = '{T-1} 16:00:00'`
- 产线→实例ID 见 dtx-model-map.md 模型1

1. 单线单日：
```sql
SELECT ts, val FROM `quota_sub_{产线实例ID}@public_dailyEnergyConsumption` WHERE ts = '{T-1} 16:00:00'
```
2. 单线区间逐日（如 3号线 8/1~8/8）：同表 `WHERE ts >= '2026-07-31 16:00:00' AND ts < '2026-08-08 16:00:00' ORDER BY ts`
3. 全部产线单日/区间：14 线 UNION ALL 各自取数，**全厂合计必须 SQL 层嵌套 SUM**：
```sql
SELECT ROUND(SUM(val), 2) AS total_kwh FROM (
  SELECT val FROM `quota_sub_{线1ID}@public_dailyEnergyConsumption` WHERE ts = '{T-1} 16:00:00'
  UNION ALL SELECT val FROM `quota_sub_{线2ID}@public_dailyEnergyConsumption` WHERE ts = '{T-1} 16:00:00'
  ... 共 14 线)   -- SQL 层 ROUND 规整浮点（规则0操作注解）
```
4. 某产线"所有电表"明细 = 主三相电表（上表）+ 该线各**单相智能微断单元**：
   `quota_sub_{微断实例ID}@project_DailyEnergyConsumption`（微断实例见 model-map 模型8，如 M02 线 11~13 个单元）
   - 微断 Daily ts 语义与气表 Daily 同期（实测覆盖 BJT 7/29~8/8）——先 first/last 验证再取数
   - 微断合计同样 UNION ALL 后 SQL 层 SUM
   - ⚠️ **微断分表耗电取数必须用 `ZYGDNEN`（总有功电能）首末差分，不能用 `project_DailyEnergyConsumption` 直接 SUM**——见下方"微断计量数据质量"甄别，否则会把累计值当增量算出错（实测直接 SUM 得 75万 kWh 而整线一个月才 9千多）

## 微断（单相智能微断 NB2LE_80ZT）分表计量数据质量 ⚠️（2026-08 实测）

微断单元的能耗计量表**不可直接当"日耗电"用**，是深坑：

- `project_DailyEnergyConsumption` / `project_TotalEnergyConsumption` / `project_MonthlyEnergyConsumption` 的 val 是**累计值且中途多次归零重置、非单调**——单单元显示数万 kWh、月累计 7 万+，而**整条 M02 产线三相总表一个月才约 9,682 kWh**，物理上分表合计不可能远超总表。**凡分表 SUM ≫ 总表即计量异常，不可采信。**
- `ZYGDNEN`（总有功电能累计）同样会中途归零（首 44 万 → 末 500 这种），**跨长区间首末差分会失真**；但对**单日**（当天内不再重置）差分可得靠谱的当日增量。
- **可靠取数法（单日）**：`SELECT 当天最早/最晚 ZYGDNEN，差分 = 当日用能`。每个微断单元当日增量在 0~15 kWh 量级属正常。
- 给用户呈现微断分表数字前，**必须先校验"分表合计 ≪ 总表"**（分表仅覆盖部分设备负荷，应小于总表）；若分表合计反而远超总表，如实说明分表计量不可靠，不给误导性合计，建议现场核查计量倍率 / 累计值重置问题。

## 单位与解读

- 单位：kWh
- 正常范围业务解读：工作日各线约 150~250 kWh/天（生产）；周末停产日约 50~90 kWh/天（待机）；
  停产日骤降为工作日的 1/3 左右是正常待机特征，可据此佐证"当天停产"
- 断流甄别：删除某线 Daily 提前断流（如 M09 止于 8/6）时，该线后续日无数据 = 该线电表链路故障，非停产，先验 first/last 再作答（规则2b）
- 单日巨值（如 M07 平日 0~86 突现 2103.7）先重查验证，确认计量异常后如实标注，不"修正"数字（规则0）

## 耗电量为 0 的记录（停产日 vs 单线异常）

用户问"耗电量为 0 的记录"时，先用 `GROUP BY COUNT(*) WHERE val = 0` 拿到各线 0 天数（与正常停产基线 7~11 天对比，见 lessons 教训 D），**再按需拉日期级明细**：

```sql
-- 日期级明细（可加 {起步UTC} AND < {截止UTC} 限定单月/区间）
SELECT ts, '{线}' AS line FROM `quota_sub_{线ID}@public_dailyEnergyConsumption`
WHERE ts >= '{起点UTC}' AND ts < '{终点UTC}' AND val = 0
-- ... 14 线 UNION ALL，外层 ORDER BY ts, line
```

**停产日基线常识（重要甄别）**：全厂停产日（如 8/8）各线仍保持最低待机（56~86 kWh），**通常不会落到 0**。因此：
- 停产日各线都是几十 kWh → **0 记录基本不是停产造成**，而是**单线电表断流/计量故障**（如某线 8 月初连续 0）或**全厂某个正常停产日全 0**
- 若"某线月初连续 0 + 后来某日突发巨值"（如 M07 月初全 0 → 8/7 跳变 2103.7）＝计量故障的特征组合，该线整段数据不可信，优先提示现场核查
- 出明细表时按产线分组、标注"正常停产日同步 0（多条线同日）" vs "单线异常 0"，帮用户区分正常与故障

**合成回答模板——"哪条线最耗电 / 哪些线能耗异常"**：
这类最终结论常把多个异常信号综合：① 单日巨值跳变（M07 2103.7 十倍级）→ 首要排查电表；② 电表链路断流（M09 全月无数据）；③ 分表累计重复/一致（M02 两单元 14,411 相同）→ 疑共用计量。逐一列出异常信号 + 建议动作，正常排名要剔除异常后给出。

## 备选方案：从 EP（有功电能）分钟级累积值推算日耗电

当 `public_dailyEnergyConsumption` 数据不可用或需交叉验证时，可直接查 `ElectricMeter_3P@EP` 分钟级累积电能 kWh：

```sql
SELECT min(val) AS start_kwh, max(val) AS end_kwh,
       ROUND(max(val) - min(val), 2) AS consumption_kwh
FROM `quota_385318105131300357@project_ElectricMeter_3P@EP`
WHERE instance_uid = '{产线_instance_uid}'
  AND ts >= '2026-08-07 00:00:00' AND ts < '2026-08-08 00:00:00'
```

**原理**：EP 是有功总电能累积值（kWh，每 1 分钟一个读数），当日耗电 = 当日结束最大读数 - 当日开始最小读数。EP 持续增长说明产线在用电；日末持平时段（读数不再增长）即产线停机。

**产线名称 → instance_uid 映射**：通过 `ElectricMeter_3P@customWkln` 查询：
```sql
SELECT instance_uid, val AS line_code
FROM `quota_385318105131300357@project_ElectricMeter_3P@customWkln`
WHERE val = '{线名如 M02}' LIMIT 1
```
- `customWkln` 的 `val` 存储产线原始编号（M01~M12, 47, 49, 50, 67 等）
- `wkln`（project_ElectricMeter_3P@wkln）存储数字映射（1~67）
- 拿到的 `instance_uid` 可用于 EP/P/其他指标共用

## 案例变体：产线用电量阈值排行（超过 N kWh 的产线）

**问题：** "查询用电量超过 200,000 kWh 的产线"

**方法：** 直接取各线 **EP 累计值 `LAST(val)`**（EP 是自投产起的有功总电能累计值，最新值即投产至今总用电量），按阈值过滤。

```
1. 确定所有产线的 EP 子表（14 条，其中 67 线在 ElectricMeter_3P_CT 模型）
2. 逐线查询 SELECT LAST(val) FROM `quota_sub_{实例ID}@EP`
3. 按阈值筛选，结果按 val 降序排
```

**注意事项：**
- EP 是**累计读数**，最新 `LAST(val)` = 投产至查询时刻的总用电量，**不是某区间消耗**。适用于\"总用电量超过X\"的筛选。若要区间耗电（某月/某日），用 `public_dailyEnergyConsumption` 或首末 EP 差分，不可用 `LAST(val)` 相减（跨产线无意义）。
- **EP 可能被重置归零**：实测 M09 线 EP 从 182,991 kWh 突降至 0（表底数重置）。如果某产线 LAST(val)=0，必须查 `first(ts), last(ts)` 确认时间跨度，再用 `SELECT MAX(val) WHERE ts < 0产生时间` 获取重置前的最大值，避免误判该线长期用电为 0。
- 每条线查完统一汇总，大结果集用 execute_code 程序化循环（避免手写 14 条 UNION ALL 出错），时间粒度用 strftime 生成防手误（Step 2b）。

```sql
-- 单线单次
SELECT LAST(val) FROM `quota_sub_{产线ElectricMeter_3P实例ID}@EP`

-- EP 为 0 时查重置前最大值
SELECT MAX(val) FROM `quota_sub_{产线ElectricMeter_3P实例ID}@EP` WHERE ts < '{疑似重置时间}'
```

**展示给业务用户：** 线名 + 累计用电量 (kWh) + 是否超阈值，注明\"投产至今总用电量\"口径。若某线 EP 归零过，标注\"该线电表曾重置，历史最高约 X kWh\"。

## 月查询：Daily 表未覆盖全月时的处理（2026-09 实测补充）

用户问"上月耗电"时，Daily 能耗表可能只覆盖上旬（如 M02 8月仅 8 天数据），后续因每日汇总链路中断而无行。**不要直接给"前 N 天合计"当"月合计"混淆用户。**

**正确处理顺序：**
1. 查 `public_dailyEnergyConsumption` 在目标月的 `first(ts)/last(ts)/count(*)` 确定覆盖天数
2. 同时查 EP 在目标月的 `MAX(val)-MIN(val)` 交叉验证覆盖日期的合计
3. 若覆盖天数不足整月（如 8 天 vs 31 天），查 EP 在目标月剩馀区间 `min/max` 看是否有数据但未被 Daily 汇总：
   - EP 在剩馀区间内有增长 → 采集链路仍在，但 Daily 汇总未生成 → 用 EP 差分算剩馀部分
   - EP 在剩馀区间内无增长（数值冻结）→ 链路心跳在但真无数据
4. 输出时明确标注：
   - 月内实际覆盖天数（如 8/1~8/8 共 8 天）
   - 该覆盖期总耗电
   - 未覆盖区间的状态（"EP 数值停滞，后续无用电数据，无法推算全月"）
   - 逐日明细供用户参考
5. 不使用 EP 差分推算全月（中间断档不可补插）

## 坑与注意事项

- 全厂/多表合计禁止手算，一律 SQL 层嵌套 SUM
- 微断单元个别某日可能无记录（采集缺失）：如实标注"无数据"，不补造
- 用户说"XX线所有电表"时：主三相电表 + 该线微断单元电表都查；产线总功率表（LinePower）是功率监测非电度表，默认不并入耗电列表，可说明存在
- 跨月查询先说明数据可查范围（本例气表/微断数据止于某日），按月汇总只给覆盖期内数字，不推算全月
- EP 小时级/分钟级查询走超级表（`quota_385318105131300357@project_ElectricMeter_3P@EP`），通过 `instance_uid` 过滤；表名必须反引号包围
- **全部产线耗电查不全——14线 ≠ 13线**：`ElectricMeter_3P@EP` 只有 13 个产线实例（M01~M12, 47, 49, 50）。第14条线 **67线** 不在 `ElectricMeter_3P` 组，而是在 **`ElectricMeter_3P_CT`** 模型中（`quota_385318105131300357@project_ElectricMeter_3P_CT@EP`，instance_uid=2008338015040446464）。查"全部产线耗电"时必须同时查询这两个表组再 UNION ALL，⚠️ 仅查 `ElectricMeter_3P` 会遗漏 67 线而被用户指出数据不全（实测教训）。备用 copy 表 `ElectricMeter_3P_copy_1780882179370` 数据止于 6 月（8 月无数据），不需要包含。