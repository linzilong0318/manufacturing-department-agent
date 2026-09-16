Database: `dtx_385318105131300357`
Updated: 2026-08-07

<!-- ===================== OVERVIEW ===================== -->

## 概述

制造部共有 **14条产线**，生产 **97个型号** 的断路器产品（NXB-63系列）。
每个产线可生产多个型号。
每种型号有固定的单台极数、单极价格、标准煤系数等属性。

**产量计量：**
- **台数** (Yield) — 产品数量(产量)
- **极数** (ExtremeNumber) — 台数 × 单台产品的极数（如2P就是2极，3P就是3极，4P就是4极）

### 14条产线

| 产线名 | 电表模型归属 | ElectricMeter_3P 实例ID | wkln (数字映射) |
|---|---|---|---|
| 67线 | ElectricMeter_3P_CT | 2008338015040446464 | 67 |
| M03线 | ElectricMeter_3P | 2008337904031825920 | 3 |
| 47线 | ElectricMeter_3P | 2008337903968911360 | 47 |
| M04线 | ElectricMeter_3P | 2008337903905996800 | 4 |
| M07线 | ElectricMeter_3P | 2008337903830499328 | 7 |
| M12线 | ElectricMeter_3P | 2008337903767584768 | 12 |
| 49线 | ElectricMeter_3P | 2008337903700475904 | 49 |
| M05线 | ElectricMeter_3P | 2008337903641755648 | 5 |
| 50线 | ElectricMeter_3P | 2008337903578841088 | 50 |
| M09线 | ElectricMeter_3P | 2008337903507537920 | 9 |
| M08线 | ElectricMeter_3P | 2008337903423651840 | 8 |
| M02线 | ElectricMeter_3P | 2008337903360737280 | 2 |
| M06线 | ElectricMeter_3P | 2008337903281045504 | 6 |
| M01线 | ElectricMeter_3P | 2008337903167799296 | 1 |

> **⚠️ 查询"所有产线/全部产线"时必须把两个电表模型表组 UNION ALL 起来**：ElectricMeter_3P 表（13条产线）+ ElectricMeter_3P_CT 表（仅67线，instance_uid=2008338015040446464）。只查 ElectricMeter_3P 会漏掉 67 线。

<!-- ===================== PROJECT CONFIG & QUICK REF ===================== -->

## 项目配置与速查（查询前必读）

### 连接
- **数据库:** `dtx_385318105131300357`
- **首选 MCP 工具**（config.yaml 的 mcp_servers.tdengine，只读 select/show/describe）
- **REST 备选:** `http://10.120.7.99:6041/rest/sql`，URL 需带数据库名（如 `/rest/sql/dtx_385318105131300357`）；凭据从 /opt/data/.env 读取（TDENGINE_*），**禁止把凭据写进技能文件或脚本**；反引号会被 shell 消费，须 `curl --data-binary @file` 提交

### 时区（UTC+8）
北京时间 T 日 = UTC (T-1)日 16:00 ~ T 日 16:00

| 北京日期 | UTC 起点 | UTC 终点 |
|---|---|---|
| T 日 | (T-1) 16:00:00 | T 16:00:00 |
| T1 ~ T2 | (T1-1) 16:00:00 | T2 16:00:00 |

边界规则：`ts >= 起点 AND ts < 终点`（左闭右开，避免重复计数）

### 表命名规则
- 单元级: `quota_385318105131300357@<模型类型>@<指标标识符>`（ProductTypeAgg 分线指标带产线后缀，如 `project_Daily47ModelYield`）
- 设备级: `quota_sub_<设备实例ID>@<指标标识符>`
- **产线后缀:** 47, 49, 50, 67, M01, M02, M03, M04, M05, M06, M07, M08, M09, M12（全厂汇总表无后缀）
- 所有表共用列: `ts(TIMESTAMP), val(FLOAT/VARCHAR), arrival_time, update_time`；tags: `instance_uid, device_key`
- **查询时表名必须用反引号包围**

### 单位速查（⚠️ 重点，易错）
| 粒度 | 表模式 | 单位 |
|---|---|---|
| 5min 产量 | `project_5mins{线}ModelYield` | **台数** |
| 5min 极数 | `project_5mins{线}ExtremeNumber` | **极数** |
| Daily 产量 | `project_Daily{线}ModelYield` | **极数** |
| Daily 产值 | `project_Daily{线}OutputValue` | 元 |
| 5min/Daily 能耗 | `project_{5mins\|Daily}{线}ModelEnergy` | kWh |

**⚠️ `ModelYield` 前缀单位随粒度不同：5min=台数, Daily=极数。** 用户没说清"产量"口径时，台数和极数都返回。
**⚠️ 5min 台数表可能为空而 Daily 极数表有数据**（采集口径差异）：以 Daily 极数表为基准，用型号极数(P数)反推台数，不要因 5min 表空就否定 Daily 表数据。

### 台数/极数换算规则（用户追问台数时用）

1. **直接取**：若 5min 台数表（`project_5mins{线}ModelYield`）有直接数据，直接取台数。
2. **反推**：若 5min 台数表为空（采集口径差异，常见），用 Daily 极数 ÷ 单台极数：
   - 单台极数从型号名提取：1P÷1, 2P÷2, 3P÷3, 4P÷4（如型号名 "2P C32" 中的 "2P"）
3. **验证**：极数 ÷ 台数应等于该对象单台极数。
4. **输出**：给业务用户呈现「对象名，台数 N 台，极数 N 极」，永远展示翻译后的名称。

### 全局汇总表（ProductTypeAgg，无产线后缀）
| 含义 | 标识符 | 单位 |
|---|---|---|
| 五分钟总产量 | `project_5minusProductionStatistics` | 极数 |
| 五分钟总产值 | `project_5minusOutputValue` | 元 |
| 五分钟总能耗 | `project_5minusModelTotalEnergy` | kWh |
| 每日总产量 | `project_DailyOutputStatistics` | 极数 |
| 每日总产值 | `project_DailyOutputValue` | 元 |
| **每日总能耗（⚠️ 拼写 Dayily）** | `project_DayilyModelEnergy` | kWh |
| 每月总能耗 | `project_MonthlyModelEnergy` | kWh |
| 每小时总能耗 | `project_HourlyModelEnergy` | kWh |
| 累计总产值 | `project_TotalOutputValueNew` | 元 |
| 累计总能耗 | `project_TotalProductionEnergyNew` | kWh |
| 累计总产量 | `project_TotalProductionYieldsNew` | 极数 |

**⚠️ `project_DayilyModelEnergy` 是库内真实拼写（Dayily 多一个 y），不要"纠正"成 Daily。** 产线级 `project_Daily{线}ModelEnergy` 拼写正常。
**⚠️ 静态表陷阱：** 累计类表（TotalOutputValueNew/TotalProductionEnergyNew/TotalProductionYieldsNew）与单耗指标表时间戳停在 2017-12-31，是静态初始值，**不可用于当前分析**，必须按区间 SUM 实测计算。

### 单耗/效率指标表（⚠️ 均为静态 2017 值，须实测计算）
| 含义 | 标识符 |
|---|---|
| 累计能耗/总产值 | `project_EnergyPerUnitOfOutputValue` |
| 累计能耗/总产量 | `project_EnergyPerUnitOfYields` |
| 万元产值能耗（kWh） | `project_TotalEnergyPerOfOutputValue` |
| 万极能耗（kWh） | `project_TotalEnergyPerOfYields` |
| 万元产值能耗（标准煤） | `project_TceEnergyEfficiency` |
| 万极能耗（标准煤） | `project_TceEnergyEfficiencyYields` |

### 产线气表覆盖
仅 **M02（2个）、47（2个）、M12（1个）** 有气表，其余产线无气表（实例 ID 见模型6）。
- M01 线**无**气表——用户问 M01 或其他无气表产线的用气量，直接回复"该产线未安装气表"。
- Daily 气量表 ts 语义同产量 Daily 表：`ts={T} 16:00 UTC` = BJT (T+1) 日 00:00，代表 BJT (T+1) 日全天。

### 汇总表 ts 语义（两条时间线勿混淆）
- **Daily 类汇总表**（产量/极数/产值/能耗，含气表）：ts = UTC 16:00 = **BJT 当日 0:00**，是该业务日全天汇总。例：ts=2026-05-31 16:00:00 UTC 代表 BJT **6月1号**全天（2026-05-31 16:00 UTC = 2026-06-01 00:00 BJT）。实测验证：Daily 行 ts=(T-1) 16:00 UTC 与 5min 表 BJT T 日台数×P数 精确相等（如 M05 线 2P D20：12600台×2=25200极 = Daily ts=5/31 16:00 行）。
- **Monthly 类表**：ts=月末最后一天 16:00 UTC = 当月。
- **5min/实时表**：ts 为 UTC 实时时间戳，与 BJT 差 8 小时。

### 业务无产出解读（判定为无产出后按此口径回答）

| 情形 | 解读口径 |
|---|---|
| 工作日（周一~周六）停工 | 可能是计划检修、换型、缺料等原因，如实告知即可，不臆断具体原因 |
| 周日/节假日 | 直接按停产解读，无需交叉验证（业务节奏本身如此） |
| 全局采集中断 | 说明"数据采集在 X 时截止，该日期后无法判断"，不编造停产结论 |

**判定流程**（业务停止 vs 采集截止的甄别判断树）见 SKILL.md Step 3b；本节只定义判定为停止后的业务解读口径。

### 实测表名核查
上述表名均已通过 SHOW STABLES LIKE 实测确认存在（2026-08-07）。复用前如怀疑表名，直接实测：
```sql
SHOW STABLES LIKE 'quota_385318105131300357@project_ProductTypeAgg@project_%'
```
以实测为准，勿按逻辑推断拼写。

<!-- ===================== 9 DT MODELS ===================== -->

## 9 个 DT 模型 → 9 组超级表

| DT 模型 | 模型类型 | 实例数 | 含义 |
|---|---|---|---|
| **三相电表 (ElectricMeter_3P)** | 设备级DT | 14 | 每条产线一个实例，含用能+产量统计 |
| **虚拟总表 (proportionPower)** | 单元级DT | 1 | 整合所有三相电表，含用能统计+各产线占比 |
| **设备型号 (EquipmentModel)** | 设备级DT | 97 | 每个型号一个实例，含产量+产值统计 |
| **型号统计 (ProductTypeAgg)** | 单元级DT | 97 | 每个型号一个实例，按产线分拆的产量/产值/能耗 |
| **产线型号总统计 (OverallStatisticalModel)** | 单元级DT | 1 | 全制造部汇总的产量+产值+能耗指标 |
| **产线气表 (GasMeter)** | 设备级DT | 若干 | 各产线气表数据（用气量） |
| **型号统计单元级嵌套模型** | 单元级DT | 1 | 每个型号的标准煤系数+累计总能耗指标 |
| **单相智能微断** | 设备级DT | 若干 | 智能微型断路器（产线设备单元）数据 |
| **产线总功率表** | 单元级DT | 3 | 各产线的总功率数据 |
<!-- ===================== SUPER TABLE NAMING ===================== -->

## 表命名规则
单元级DT实例指标数据库 表命名格式：
```
quota_385318105131300357@<单元级模型类型>@<指标标识符>  

```
示例：`quota_385318105131300357@project_proportionPower13@project_13powerMeterEnergyAdd`


设备级DT实例指标数据库 表命名格式:
```
quota_sub_<设备实例ID>@<指标标识符>

```
示例： `quota_sub_2008337903281045504@public_monthlyEnergyConsumption_qoq`

所有表共用列结构: `ts(TIMESTAMP), val(FLOAT/VARCHAR), arrival_time(TIMESTAMP), update_time(TIMESTAMP)`
Tags: `instance_uid, device_key`
**注意：查询时表名必须使用反引号包围**


<!-- ===================== MODEL 1:三相电表（project_ ElectricMeter_3P) ===================== -->

## 模型1：三相电表 (project_ElectricMeter_3P)

**类型:** 设备级DT
**含义:** 每个实例代表一条产线，包含该产线的用能 + 产量统计
**实例数:** 14 (14条产线)

### 实例

| 实例名称 | 实例标识符 | 电表模型归属 |
|---|---|---|
| 67线 | 2008338015040446464 | ElectricMeter_3P_CT |
| M03线 | 2008337904031825920 | ElectricMeter_3P |
| 47线 | 2008337903968911360 | ElectricMeter_3P |
| M04线 | 2008337903905996800 | ElectricMeter_3P |
| M07线 | 2008337903830499328 | ElectricMeter_3P |
| M12线 | 2008337903767584768 | ElectricMeter_3P |
| 49线 | 2008337903700475904 | ElectricMeter_3P |
| M05线 | 2008337903641755648 | ElectricMeter_3P |
| 50线 | 2008337903578841088 | ElectricMeter_3P |
| M09线 | 2008337903507537920 | ElectricMeter_3P |
| M08线 | 2008337903423651840 | ElectricMeter_3P |
| M02线 | 2008337903360737280 | ElectricMeter_3P |
| M06线 | 2008337903281045504 | ElectricMeter_3P |
| M01线 | 2008337903167799296 | ElectricMeter_3P |

> **注意** 67线对应的三相电表模型是三相电表CT（`project_ElectricMeter_3P_CT`），不在 `project_ElectricMeter_3P` 表组内；其余 13 条产线均在 `project_ElectricMeter_3P` 表组内。
### 指标

| 指标名称 | 指标标识符 | 指标类型 | 指标单位 |
|---|---|---|---|
| 设备连接状态 | @online_status | 测点类 | - |
| 有功总电能 | EP | 测点类 | kWh |
| 有功总功率 | P | 测点类 | W |
| 工厂号 | werks | 测点类 | - |
| 产线号-数字映射 | wkln | 测点类 | - |
| 产线号-原始 | customWkln | 测点类 | - |
| 批次号 | SAP_ORDER | 测点类 | - |
| 生产设备型号-数字映射 | PEM | 测点类 | - |
| 生产设备型号-原始 | maktx | 测点类 | - |
| 所有型号产品累计产量（台数） | FINISH_YIELD | 测点类 | - |
| 每5分钟耗能 | project_5minsEnergyConsumption | 累计用量类 | kWh |
| 所有型号产品每五分钟产量（台数） | project_5minsProductionQuantity | 累计用量类 | - |
| 累计用能 | public_accumulatedEnergyConsumption | 累计用量类 | kWh |
| 每日用能 | public_dailyEnergyConsumption | 累计用量类 | kWh |
| 每小时用能 | public_hourEnergyConsumption | 累计用量类 | kWh |
| 每月用能 | public_monthlyEnergyConsumption | 累计用量类 | kWh |
| 每年用能 | public_yearlyEnergyConsumption | 累计用量类 | kWh |
| 日度环比 | public_dailyEnergyConsumption_ytd | 计算类 | % |
| 月度环比 | public_monthlyEnergyConsumption_qoq | 计算类 | % |
| 月度同比 | public_monthlyEnergyConsumption_yoy | 计算类 | % |
| 年度同比 | public_yearlyEnergyConsumption_yoy | 计算类 | % |

<!-- ===================== MODEL 2:虚拟总表（project_ proportionPower) ===================== -->

## 模型2：虚拟总表 (project_proportionPower)

**类型:** 单元级DT
**含义:** 整合所有14个三相电表模型，包含全厂用能+各产线占比
**实例数:** 1

### 实例

| 实例名称 | 实例ID |
|---|---|
| 终端数字化车间虚拟总表 | 2011661969354465280 |

### 指标

| 指标名称 | 指标标识符 | 指标类型 | 指标单位 |
|---|---|---|---|
| 总有功功率 | project_14powerMeterAdd | 计算类 | W |
| 总有功电能 | project_14powerMeterEnergyAdd | 计算类 | kWh |
| 总碳排放 | project_carbonEmission | 计算类 | kg |
| M01线功率占总功率比重 | project_proportion01 | 计算类 | % |
| M02线功率占总功率比重 | project_proportion02 | 计算类 | % |
| M03线功率占总功率比重 | project_proportion03 | 计算类 | % |
| M04线功率占总功率比重 | project_proportion04 | 计算类 | % |
| M05线功率占总功率比重 | project_proportion05 | 计算类 | % |
| M06线功率占总功率比重 | project_proportion06 | 计算类 | % |
| M07线功率占总功率比重 | project_proportion07 | 计算类 | % |
| M08线功率占总功率比重 | project_proportion08 | 计算类 | % |
| M09线功率占总功率比重 | project_proportion09 | 计算类 | % |
| M12线功率占总功率比重 | project_proportion12 | 计算类 | % |
| 47线功率占总功率比重 | project_proportion47 | 计算类 | % |
| 49线功率占总功率比重 | project_proportion49 | 计算类 | % |
| 50线功率占总功率比重 | project_proportion50 | 计算类 | % |
| 67线功率占总功率比重 | project_proportion67 | 计算类 | % |
| 月度环比 | public_monthlyEnergyConsumption_qoq | 计算类 | % |
| 月度同比 | public_monthlyEnergyConsumption_yoy | 计算类 | % |
| 年度同比 | public_yearlyEnergyConsumption_yoy | 计算类 | % |
| 每5分钟耗能 | project_5minsEnergyConsumption | 累计用量类 | kWh |
| 每小时用能 | public_hourEnergyConsumption | 累计用量类 | kWh |
| 每日用能 | public_dailyEnergyConsumption | 累计用量类 | kWh |
| 每月用能 | public_monthlyEnergyConsumption | 累计用量类 | kWh |
| 每年用能 | public_yearlyEnergyConsumption | 累计用量类 | kWh |
| 每年碳排 | public_yearlyCarbonEmission | 累计用量类 | kg |
| 累计用能 | public_accumulatedEnergyConsumption | 累计用量类 | kWh |
| 累计碳排 | public_accumulatedCarbonEmission | 累计用量类 | kg |

<!-- ===================== MODEL 3: 设备型号（project_EquipmentModel) ===================== -->

## 模型3：设备型号 (project_EquipmentModel)

**类型:** 设备级DT
**含义:** 每个实例代表一个具体型号的产品，包含总产量+产值
**实例数:** 97 (97个型号)

### 指标

| 指标名称 | 指标标识符 | 指标类型 |
|---|---|---|
| 设备连接状态 | @online_status | 测点类 |
| 生产设备型号-数字映射 | PEM | 测点类 |
| 生产设备型号-原始 | maktx | 测点类 |
| 该型号总产量（台数） | YIELD | 测点类 |
| 该型号总产量（极数） | project_5minsExtremeNumber | 计算类 |
| 该型号总产值 | project_TotalOutputValueNew | 计算类 |
| 该型号每五分钟产量（极数） | project_5minsProductionQuantity | 累计用量类 |

### 实例列表 (97个型号)

| 实例名称 | 实例标识符 |
|---|---|
| DT_双极小型断路器 NXB-63 2P D25 全制程 环保 |  2047228072829628416|
| DT_单极小型断路器 NXB-63 1P C25A 全制程 环保 | 2047228072754130944|
| DT_双极小型断路器 NXB-63 2P D32 全制程 环保 |  2047228072661856256|
| DT_双极小型断路器 NXB-63 2P D20 全制程 环保 |  2047228072586358784|
| DT_三极小型断路器 NXB-63 3P C20A 全制程 环保 |  2047228072506667008|
| DT_双极小型断路器 NXBLE-32 2P C25 环保 |  2047228072443752448|
| DT_三极小型断路器 NXB-63 3P C25A 全制程 环保 |  2047228072372449280|
| DT_双极小型断路器 NXBLE-32 2P C40 环保 |  2047228072301146112|
| DT_单极小型断路器 NXB-63 1P C20A 全制程 环保 |  2047228072225648640|
| DT_三极小型断路器 NXB-63 3P C40A 全制程 环保 |  2047228072150151168|
| DT_三极小型断路器 NXB-63 3P C32A 全制程 环保 |  2047228072074653696|
| DT_双极小型断路器 NXBLE-32 2P C20 环保 |  2047228071936241664|
| DT_NXB-63 2P D4 |  2046401445954134016|
| DT_NXB-63 2P C4 |  2046401445870247936|
| DT_NXB-63 1P D16 |  2046401445647949824|
| DT_NXB-63 3P D4 |  2046401445572452352|
| DT_NXB-63 1P C1 |  2046401445337571328|
| DT_NXB-63 1P D3 |  2046401445245296640|
| DT_NXB-63 2P C10 |  2046401445161410560|
| DT_NXB-63 1P C3 |  2046401445073330176|
| DT_NXB-63 4P C6 |  2046401445002027008|
| DT_NXB-63 2P C1 |  2046401444926529536|
| DT_NXB-63 2P D16 |  2046401444855226368|
| DT_NXB-63 1P C63 | 2046401444783923200| 
| DT_NXB-63 4P C50 | 2046401444708425728 |
| DT_NXB-63 3P C10 | 2046401444628733952 |
| DT_NXB-63 2P D63 | 2046401444477739008 |
| DT_NXB-63 3P C50 | 2046401444398047232 |
| DT_双极小型断路器 NXBLE-32 2P C32 环保 | 2046401444242857984 |
|DT_NXB-63 3P D3|2046401444171554816|
|DT_NXB-63 3P C1|2046401444100251648|
|DT_NXB-63 3P C2|2046401443949256704|
|DT_NXB-63 1P C4|2046401443865370624|
|DT_NXB-63 3P C3|2046401443789873152|
|DT_NXB-63 3P D50|2046401443710181376|
|DT_NXB-63 1P C10|2046401443626295296|
|DT_NXB-63 4P D16|2046401443550797824|
|DT_NXB-63 1P D10|2046401443391414272|
|DT_NXB-63 2P C3|2046401443320111104|
|DT_NXB-63 3P C4|2046401443236225024|
|DT_NXB-63 2P C63|2046401443072647168|
|DT_NXB-63 3P D2|2046401442992955392|
|DT_NXB-63 3P D10|2046401442833571840|
|DT_NXB-63 4P D63|2046401442762268672|
|DT_NXB-63 4P D10|2046401442682576896|
|DT_NXB-63 4P D50|2046401442586107904|
|DT_NXB-63 2P D10|2046401442430918656|
|DT_NXB-63 4P C10|2046401442267340800|
|DT_NXB-63 3P C63|2046401442179260416|
|DT_NXB-63 1P C2|2046401442011488256|
|DT_NXB-63 2P C2|2046401441856299008|
|DT_NXB-63 4P C63|2046401441759830016|
|DT_NXB-63 1P C50|2046401441667555328|
|DT_NXB-63 2P C50|2046401441478811648|
|DT_NXB-63 4P C16|2042173618233466880|
|DT_NXB-63 1P C20|2042173618057306112|
|DT_NXB-63 2P D20|2042173617658847232|
|DT_NXB-63 3P D20|2042173617583349760|
|DT_NXB-63 3P D16|2042173617436549120|
|DT_NXB-63 2P C16|2042173617063256064|
|DT_NXB-63 4P D40|2042173616828375040|
|DT_NXB-63 3P D32|2042173616266338304|
|DT_NXB-63 4P C32|2042173615951765504|
|DT_NXB-63 2P D25|2042173615779799040|
|DT_NXB-63 3P C6|2042173615326814208|
|DT_NXB-63 1P C25|2042173615171624960|
|DT_NXB-63 4P D32|2042173615024824320|
|DT_NXB-63 1P C32|2042173614936743936|
|DT_NXB-63 2P D6|2042173614777360384|
|DT_NXB-63 1P C16|2042173614697668608|
|DT_NXB-63 2P C25|2042173614617976832|
|DT_NXB-63 1P C6|2042173614538285056|
|DT_NXB-63 3P C32|2042173614303404032|
|DT_NXB-63 3P D40|2042173614227906560|
|DT_NXB-63 3P C16|2042173614148214784|
|DT_NXB-63 4P C25|2042173614072717312|
|DT_NXB-63 2P C40|2042173613917528064|
|DT_NXB-63 1P D32|2042173613758144512|
|DT_NXB-63 1P C40|2042173613678452736|
|DT_NXB-63 1P D20|2042173613602955264|
|DT_NXB-63 1P D25|2042173613447766016|
|DT_NXB-63 3P C20|2042173613363879936|
|DT_NXB-63 3P D25|2042173613204496384|
|DT_NXB-63 1P D6|2042173613061890048|
|DT_NXB-63 3P D6|2042173612986392576|
|DT_NXB-63 4P C20|2042173612902506496|
|DT_NXB-63 3P C25|2042173612818620416|
|DT_NXB-63 3P C40|2042173612424355840|
|DT_NXB-63 2P D32|2042173612088811520|
|DT_NXB-63 2P D40|2042173612000731136|
|DT_NXB-63 3P D63|2042173611883290624|
|DT_NXB-63 4P C40|2042173611799404544|
|DT_NXB-63 2P C20|2042173611711324160|
|DT_NXB-63 2P C6|2042173611644215296|
|DT_NXB-63 2P C32|2042173611388362752|
|DT_NXB-63 4P D25|2042173611145093120|
|DT_NXB-63 4P D20|2042173610566279168|


> **⚠️ 注意：** EquipmentModel 实例名前缀为 `DT_`，而 ProductTypeAgg 实例名不带 `DT_` 前缀。
> 同一物理型号在 EquipmentModel 和 ProductTypeAgg 中的实例ID不同，需通过 PEM 或产量交叉关联。

<!-- ===================== MODEL 4: 型号统计（project_ProductTypeAgg） ===================== -->

# 模型4：型号统计 (project_ProductTypeAgg)

**类型:** 单元级DT
**含义:** 每个实例代表一个型号，包含该型号在不同产线的产量/产值/能耗+全厂汇总
**实例数:** 97 (97个型号)

### 指标 (各产线指标模式同47线)

**分产线指标（以47线为例，M01~M09, M12, 49, 50, 67同理）:**

| 指标名称 | 标识符 | 指标类型 |
|---|---|---|
| 该型号在47线五分钟产量（极数） | project_5mins47ExtremeNumber | 计算类 |
| 该型号在47线五分钟能耗 | project_5mins47ModelEnergy | 统计类 |
| 该型号在47线五分钟产量（台数） | project_5mins47ModelYield | 统计类 |
| 该型号在47线每日能耗 | project_Daily47ModelEnergy | 计算类 |
| 该型号在47线每日产量（极数） | project_Daily47ModelYield | 计算类 |
| 该型号在47线每日产值 | project_Daily47OutputValue | 计算类 |
| 该型号在47线累计能耗/产值 | project_EnergyPerUnitOfOutputValue47 | 计算类 |
| 该型号在47线累计能耗/产量 | project_EnergyPerUnitOfYields47 | 计算类 |
| 该型号在47线每小时能耗 | project_Hourly47ModelEnergy | 计算类 |
| 该型号在47线每小时产量（极数） | project_Hourly47ModelYield | 计算类 |
| 该型号在47线每小时产值 | project_Hourly47OutputValue | 计算类 |
| 该型号在47线每月能耗 | project_Monthly47ModelEnergy | 计算类 |
| 该型号在47线每月产量（极数） | project_Monthly47ModelYield | 计算类 |
| 该型号在47线每月产值 | project_Monthly47OutputValue | 计算类 |
| 该型号在47线累计产值 | project_TotalOutputValue47 | 计算类 |
| 该型号在47线累计能耗 | project_TotalProductionEnergy47 | 计算类 |
| 该型号在47线累计产量（极数） | project_TotalProductionYields47 | 计算类 |
| 47线万元产值能耗（标准煤） | project_TceEnergyEfficiency47 | 计算类 |
| 47线万极能耗（标准煤） | project_TceEnergyEfficiencyYields47 | 计算类 |
| 47线万元产值能耗（kWh） | project_TotalEnergyPerOfOutputValue47 | 计算类 |
| 47线万极能耗（kWh） | project_TotalEnergyPerOfYields47 | 计算类 |

**全厂汇总指标:**

| 指标名称 | 标识符 | 指标类型 |
|---|---|---|
| 该型号五分钟总产量（极数） | project_5minusProductionStatistics | 统计类 |
| 该型号五分钟总产值 | project_5minusOutputValue | 计算类 |
| 该型号五分钟总能耗 | project_5minusModelTotalEnergy | 计算类 |
| 该型号五分钟能耗（排除67线） | project_5minsModelEnergy | 统计类 |
| 该型号五分钟能耗（67线） | project_5minsModelEnergy2 | 统计类 |
| 该型号每小时总能耗 | project_HourlyModelEnergy | 计算类 |
| 该型号每小时总产量（极数） | project_HourlyOutputStatistics | 计算类 |
| 该型号每小时总产值 | project_HourlyOutputValue | 计算类 |
| 该型号每日总产量（极数） | project_DailyOutputStatistics | 计算类 |
| 该型号每日总产值 | project_DailyOutputValue | 计算类 |
| 该型号每日总能耗 | project_DayilyModelEnergy | 计算类 |
| 该型号每月总能耗 | project_MonthlyModelEnergy | 计算类 |
| 该型号每月总产值 | project_MonthlyOutputValue | 计算类 |
| 该型号每月总产量（极数） | project_MonthlyProductionStatistics | 计算类 |
| 该型号总能耗/总产值 | project_EnergyPerUnitOfOutputValue | 计算类 |
| 该型号总能耗/总产量 | project_EnergyPerUnitOfYields | 计算类 |
| 该型号万元产值能耗（kWh） | project_TotalEnergyPerOfOutputValue | 计算类 |
| 该型号万极能耗（kWh） | project_TotalEnergyPerOfYields | 计算类 |
| 该型号万元产值能耗（标准煤） | project_TceEnergyEfficiency | 计算类 |
| 该型号万极能耗（标准煤） | project_TceEnergyEfficiencyYields | 计算类 |
| 该型号累计总产值 | project_TotalOutputValueNew | 计算类 |
| 该型号累计总能耗 | project_TotalProductionEnergyNew | 计算类 |
| 该型号累计总产量（极数） | project_TotalProductionYieldsNew | 计算类 |
| 评价等级 | project_EvaluationLevel | 条件类 |

**产线后缀对照（用于 project_5mins{线名}ModelYield 等）:**
47, 49, 50, 67, M01, M02, M03, M04, M05, M06, M07, M08, M09, M12

示例:
- `project_5mins47ModelYield` = "该型号在47线五分钟产量(台数)"
- `project_5mins47ExtremeNumber` = "该型号在47线五分钟产量(极数)"
- `project_5minsM01ModelYield` = "该型号在M01线五分钟产量(台数)"
- `project_Hourly47ModelYield` = "该型号在47线每小时产量(极数)"
- `project_Daily47ModelEnergy` = "该型号在47线每日能耗"

### ProductTypeAgg 实例列表 (97个型号)

|实例名称|实例标识符|
|---|---|
|单极小型断路器 NXB-63 1P C20A 全制程 环保|2047232172321386496|
|单极小型断路器 NXB-63 1P C25A 全制程 环保|2047231866107834368|
|双极小型断路器 NXBLE-32 2P C20 环保|2047231665779486720|
|双极小型断路器 NXBLE-32 2P C25 环保|2047231482463236096|
|双极小型断路器 NXBLE-32 2P C40 环保|2047231282281259008|
|三极小型断路器 NXB-63 3P C20A 全制程 环保|2047231009333161984|
|三极小型断路器 NXB-63 3P C25A 全制程 环保|2047230782253543424|
|三极小型断路器 NXB-63 3P C32A 全制程 环保|2047230550979190784|
|三极小型断路器 NXB-63 3P C40A 全制程 环保|2047230317012955136|
|双极小型断路器 NXB-63 2P D20 全制程 环保|2047229966432055296|
|双极小型断路器 NXB-63 2P D25 全制程 环保|2047229510682746880|
|双极小型断路器 NXB-63 2P D32 全制程 环保|2047228857407746048|
|NXB-63 1P C1|2046455167950331904|
|NXB-63 1P C2|2046454934512148480|
|NXB-63 1P C3|2046454266627956736|
|NXB-63 1P C4|2046454053679378432|
|NXB-63 1P C10|2046453815220183040|
|NXB-63 1P C50|2046452920608694272|
|NXB-63 1P C63|2046452722608615424|
|NXB-63 1P D3|2046452514289688576|
|NXB-63 1P D10|2046452310509858816|
|NXB-63 1P D16|2046452125607731200|
|NXB-63 2P C1|2046451878341357568|
|NXB-63 2P C2|2046451672132595712|
|NXB-63 2P C3|2046451396390662144|
|NXB-63 2P C4|2046451164584062976|
|NXB-63 2P C10|2046450922979569664|
|NXB-63 2P C50|2046428140601942016|
|NXB-63 2P C63|2046427962553737216|
|NXB-63 2P D4|2046426811289022464|
|NXB-63 2P D10|2046426612566663168|
|NXB-63 2P D16|2046426412486209536|
|NXB-63 2P D63|2046426221779165184|
|NXB-63 3P C1|2046426013674577920|
|NXB-63 3P C2|2046425730765008896|
|NXB-63 3P C3|2046425498815373312|
|NXB-63 3P C4|2046425287221555200|
|NXB-63 3P C10|2046425073974751232|
|NXB-63 3P C50|2046424858098118656|
|NXB-63 3P C63|2046424467818131456|
|NXB-63 3P D2|2046421660922785792|
|NXB-63 3P D3|2046421433952219136|
|NXB-63 3P D4|2046421232075743232|
|NXB-63 3P D10|2046421039301337088|
|NXB-63 3P D50|2046420592331567104|
|NXB-63 4P C6|2046420356024049664|
|NXB-63 4P C10|2046420091434770432|
|NXB-63 4P C50|2046412610616762368|
|NXB-63 4P C63|2046412427615084544|
|NXB-63 4P D10|2046412074383814656|
|NXB-63 4P D50|2046411876467191808|
|NXB-63 4P D63|2046411504583421952|
|NXB-63 4P D16|2046410975186759680|
|双极小型断路器 NXBLE-32 2P C32 环保|2046405179308748800|
|NXB-63 4P D40|2042845792627777536|
|NXB-63 4P C40|2042845616938180608|
|NXB-63 4P D32|2042845399023116288|
|NXB-63 4P C32|2042845254179807232|
|NXB-63 4P D25|2042845120148037632|
|NXB-63 4P C25|2042844542725185536|
|NXB-63 4P D20|2042844363986329600|
|NXB-63 4P C20|2042844217528213504|
|NXB-63 4P C16|2042844055418363904|
|NXB-63 3P D63|2042843864503443456|
|NXB-63 3P D40|2042843654247178240|
|NXB-63 3P C40|2042843485472579584|
|NXB-63 3P D32|2042843330912477184|
|NXB-63 3P C32|2042843161406660608|
|NXB-63 3P D25|2042843011804225536|
|NXB-63 3P C25|2042842850453544960|
|NXB-63 3P D20|2042842697696993280|
|NXB-63 3P C20|2042842552431468544|
|NXB-63 3P D16|2042842402975834112|
|NXB-63 3P C16|2042842254767316992|
|NXB-63 3P D6|2042841992791089152|
|NXB-63 3P C6|2042841789480591360|
|NXB-63 2P D40|2042841641484574720|
|NXB-63 2P C40|2042841474533089280|
|NXB-63 2P D32|2042841307181768704|
|NXB-63 2P C32|2042841124683407360|
|NXB-63 2P D25|2042840929898520576|
|NXB-63 2P C25|2042840762508042240|
|NXB-63 2P D20|2042840585321078784|
|NXB-63 2P C20|2042840421838282752|
|NXB-63 2P C16|2042840108785229824|
|NXB-63 2P D6|2042839911345348608|
|NXB-63 2P C6|2042839747004129280|
|NXB-63 1P C40|2042839119768346624|
|NXB-63 1P D32|2042838868475011072|
|NXB-63 1P C32|2042838695471144960|
|NXB-63 1P D25|2042838506338803712|
|NXB-63 1P C25|2042838349067771904|
|NXB-63 1P D20|2042838193152909312|
|NXB-63 1P C16|2042837890412240896|
|NXB-63 1P D6|2042837656487518208|
|NXB-63 1P C20|2042539752656920576|
|NXB-63 1P C6|2042536476118376448|


<!-- ===================== MODEL 5: 产线型号总统计（project_OverallStatisticalModel） ===================== -->

## 模型5：产线型号总统计 (project_OverallStatisticalModel)

**类型:** 单元级DT
**含义:** 全制造部所有产线+所有型号的汇总统计
**实例数:** 1

### 实例

| 实例名称 | 实例ID |
|---|---|
| 产线型号总统计实例 | 2042858045204783104 |

### 指标

| 指标名称 | 标识符 | 指标类型 |
|---|---|---|
| 每小时产量（极数） | project_HourlyOutput | 累计用量类 |
| 每小时产值 | project_HourlyOutputValue | 累计用量类 |
| 每小时能耗 | public_hourEnergyConsumption | 累计用量类 |
| 每小时能耗/产值 | project_HourlyEnergyPerUnitOfOutputValue | 计算类 |
| 每小时能耗/产量 | project_HourlyEnergyPerUnitOfYields | 计算类 |
| 每小时万元产值能耗（kWh） | project_HourlyEnergyPerUnitOfTenThousandOutputValue | 计算类 |
| 每小时万极能耗（kWh） | project_HourlyEnergyPerUnitOfTenThousandYields | 计算类 |
| 每日产量（极数） | project_DailyOutput | 累计用量类 |
| 每日产值 | project_DailyOutputValue | 累计用量类 |
| 每日能耗 | public_dailyEnergyConsumption | 累计用量类 |
| 每日能耗/产值 | project_DailyEnergyPerUnitOfOutputValue | 计算类 |
| 每日能耗/产量 | project_DailyEnergyPerUnitOfYields | 计算类 |
| 每日万元产值能耗（kWh） | project_DailyEnergyPerUnitOfTenThousandOutputValue | 计算类 |
| 每日万极能耗（kWh） | project_DailyEnergyPerUnitOfTenThousandYields | 计算类 |
| 每月产量（极数） | project_MonthlyOutput | 累计用量类 |
| 每月产值 | project_MonthlyOutputValue | 累计用量类 |
| 每月能耗 | public_monthlyEnergyConsumption | 累计用量类 |
| 每月能耗/产值 | project_MonthlyEnergyPerUnitOfOutputValue | 计算类 |
| 每月能耗/产量 | project_MonthlyEnergyPerUnitOfYields | 计算类 |
| 每月万元产值能耗（kWh） | project_MonthlyEnergyPerUnitOfTenThousandOutputValue | 计算类 |
| 每月万极能耗（kWh） | project_MonthlyEnergyPerUnitOfTenThousandYields | 计算类 |
| 每月万元产值能耗（标准煤） | project_MonthlyTceEnergyEfficiencyOutputValue | 计算类 |
| 每月万极能耗（标准煤） | project_MonthlyTceEnergyEfficiencyYields | 计算类 |
| 每年产量（极数） | public_yearlyOutputYields | 累计用量类 |
| 每年产值 | public_yearlyOutputValue | 累计用量类 |
| 每年能耗 | public_yearlyEnergyConsumption | 累计用量类 |
| 每年能耗/产值 | project_YearlyEnergyPerUnitOfOutputValue | 计算类 |
| 每年能耗/产量 | project_YearlyEnergyPerUnitOfYields | 计算类 |
| 每年万元产值能耗（kWh） | project_YearlyEnergyPerUnitOfTenThousandOutputValue | 计算类 |
| 每年万极能耗（kWh） | project_YearlyEnergyPerUnitOfTenThousandYields | 计算类 |
| 每年万元产值能耗（标准煤） | project_YearlyTceEnergyEfficiencyOutputValue | 计算类 |
| 每年万极能耗（标准煤） | project_YearlyTceEnergyEfficiencyYields | 计算类 |
| 累计产量（极数） | project_allProductionQuantityAdd | 累计用量类 |
| 累计产值 | project_allProductionOutputValueAdd | 累计用量类 |
| 累计能耗 | public_accumulatedEnergyConsumption | 累计用量类 |
| 累计能耗/产值 | project_TotalEnergyPerUnitOfOutputValue | 计算类 |
| 累计能耗/产量 | project_TotalEnergyPerUnitOfYields | 计算类 |
| 基础总产量（极数） | project_TotaYieldsStatistics | 统计类 |
| 基础总产值 | project_TotalOutputValueStatics | 统计类 |
| 基础总能耗 | project_TotalEnergyStatisticsNew1 | 计算类 |
| 基础总能耗（67线） | project_TotalEnergyStatistics67lineNew | 统计类 |
| 基础总能耗（非67线） | project_TotalEnergyStatisticsOtherLineNew | 统计类 |
| 万元产值能耗（kWh） | project_TotalEnergyPerUnitOfTenThousandOutputValue | 计算类 |
| 万极能耗（kWh） | project_TotalEnergyPerUnitOfTenThousandYields | 计算类 |
| 万元产值能耗（标准煤） | project_TceEnergyEfficiencyOutputValue | 计算类 |
| 万极能耗（标准煤） | project_TceEnergyEfficiencyYields | 计算类 |

<!-- ===================== MODEL 6: 产线气表（project_Flowmeter) ===================== -->

## 模型6：产线气表 (project_Flowmeter)

**类型:** 设备级DT
**含义:** 各产线气表数据记录

### 指标

| 指标名称 | 指标标识符 | 指标类型 | 指标单位 |
|---|---|---|---|
| 设备连接状态 | @online_status | 测点类 | - |
| 当前瞬时流量使用单位 | DWEI | 测点类 | - |
| 介质温度 | JZWDU | 测点类 | ℃ |
| 累计流量（百位以上） | LJLLIANG-S | 测点类 | - |
| 累计流量（百位以下） | LJLLIANG-X | 测点类 | - |
| 频率 | PLI | 测点类 | - |
| 瞬时流量 | SSLLIANG | 测点类 | - |
| 压力 | YLI | 测点类 | - |
| 累计流量 | project_cumulativeFlowRaw | 计算类 | - |
| 总用气量 | project_TotalUsageNm3 | 累计用量类 | m³ |
| 每小时用气量 | project_hourlyUsageNm3 | 累计用量类 | m³ |
| 每日用气量 | project_dailyUsageNm3 | 累计用量类 | m³ |
| 每月用气量 | project_monthlyUsageNm3 | 累计用量类 | m³ |
| 每年用气量 | project_yearUsageNm3 | 累计用量类 | m³ |

### 实例

| 实例名称 | 实例标识符 |
|---|---|
| DT_M02线-气表1 | 2082375796692541441 |
| DT_M02线-气表2 | 2082375796537352193 |
| DT_M12线-气表1 | 2082375796604461057 |
| DT_47线-气表1 | 2082375796466049024 |
| DT_47线-气表2 | 2082375796361191424 |

<!-- ===================== MODEL 7: 型号统计单元级嵌套模型(project_project_EquipmentModelNestingNew) ===================== -->

## 模型7：型号统计单元级嵌套模型(project_project_EquipmentModelNestingNew)

**类型:** 单元级DT
**含义:** 每个型号的万元产值能耗(标准煤)+累计总能耗指标
**实例数:** 1（嵌套模型实例）

**说明：** 此模型将所有型号的指标放在同一个表中，每个型号对应一个指标标识符。包含两类指标体系：
- **C_系列**: 标准煤系数 — `project_TceEnergyEfficiency_<型号名>`
- **T_系列**: 累计总能耗 — `project_TotalProductionEnergyNew_<型号名>`

### 指标

| 指标名称 | 指标标识符 | 指标类型 | 指标单位 |
|---|---|---|---|
| C_NXB-63 1P C1 | project_TceEnergyEfficiency_NXB-63-1P-C1 | 计算类 | -- |
| C_NXB-63 1P C10 | project_TceEnergyEfficiency_NXB-63-1P-C10 | 计算类 | -- |
| C_NXB-63 1P C16 | project_TceEnergyEfficiency_NXB-63-1P-C16 | 计算类 | -- |
| C_NXB-63 1P C2 | project_TceEnergyEfficiency_NXB-63-1P-C2 | 计算类 | -- |
| C_NXB-63 1P C20 | project_TceEnergyEfficiency_NXB-63-1P-C20 | 计算类 | -- |
| C_NXB-63 1P C20A | project_TceEnergyEfficiency_NXB-63-1P-C20A | 计算类 | -- |
| C_NXB-63 1P C25 | project_TceEnergyEfficiency_NXB-63-1P-C25 | 计算类 | -- |
| C_NXB-63 1P C25A | project_TceEnergyEfficiency_NXB-63-1P-C25A | 计算类 | -- |
| C_NXB-63 1P C3 | project_TceEnergyEfficiency_NXB-63-1P-C3 | 计算类 | -- |
| C_NXB-63 1P C32 | project_TceEnergyEfficiency_NXB-63-1P-C32 | 计算类 | -- |
| C_NXB-63 1P C4 | project_TceEnergyEfficiency_NXB-63-1P-C4 | 计算类 | -- |
| C_NXB-63 1P C40 | project_TceEnergyEfficiency_NXB-63-1P-C40 | 计算类 | -- |
| C_NXB-63 1P C50 | project_TceEnergyEfficiency_NXB-63-1P-C50 | 计算类 | -- |
| C_NXB-63 1P C6 | project_TceEnergyEfficiency_NXB-63-1P-C6 | 计算类 | -- |
| C_NXB-63 1P C63 | project_TceEnergyEfficiency_NXB-63-1P-C63 | 计算类 | -- |
| C_NXB-63 1P D10 | project_TceEnergyEfficiency_NXB-63-1P-D10 | 计算类 | -- |
| C_NXB-63 1P D16 | project_TceEnergyEfficiency_NXB-63-1P-D16 | 计算类 | -- |
| C_NXB-63 1P D20 | project_TceEnergyEfficiency_NXB-63-1P-D20 | 计算类 | -- |
| C_NXB-63 1P D25 | project_TceEnergyEfficiency_NXB-63-1P-D25 | 计算类 | -- |
| C_NXB-63 1P D3 | project_TceEnergyEfficiency_NXB-63-1P-D3 | 计算类 | -- |
| C_NXB-63 1P D32 | project_TceEnergyEfficiency_NXB-63-1P-D32 | 计算类 | -- |
| C_NXB-63 1P D6 | project_TceEnergyEfficiency_NXB-63-1P-D6 | 计算类 | -- |
| C_NXB-63 2P C1 | project_TceEnergyEfficiency_NXB-63-2P-C1 | 计算类 | -- |
| C_NXB-63 2P C10 | project_TceEnergyEfficiency_NXB-63-2P-C10 | 计算类 | -- |
| C_NXB-63 2P C16 | project_TceEnergyEfficiency_NXB-63-2P-C16 | 计算类 | -- |
| C_NXB-63 2P C2 | project_TceEnergyEfficiency_NXB-63-2P-C2 | 计算类 | -- |
| C_NXB-63 2P C20 | project_TceEnergyEfficiency_NXB-63-2P-C20 | 计算类 | -- |
| C_NXB-63 2P C25 | project_TceEnergyEfficiency_NXB-63-2P-C25 | 计算类 | -- |
| C_NXB-63 2P C3 | project_TceEnergyEfficiency_NXB-63-2P-C3 | 计算类 | -- |
| C_NXB-63 2P C32 | project_TceEnergyEfficiency_NXB-63-2P-C32 | 计算类 | -- |
| C_NXB-63 2P C4 | project_TceEnergyEfficiency_NXB-63-2P-C4 | 计算类 | -- |
| C_NXB-63 2P C40 | project_TceEnergyEfficiency_NXB-63-2P-C40 | 计算类 | -- |
| C_NXB-63 2P C50 | project_TceEnergyEfficiency_NXB-63-2P-C50 | 计算类 | -- |
| C_NXB-63 2P C6 | project_TceEnergyEfficiency_NXB-63-2P-C6 | 计算类 | -- |
| C_NXB-63 2P C63 | project_TceEnergyEfficiency_NXB-63-2P-C63 | 计算类 | -- |
| C_NXB-63 2P D4 | project_TceEnergyEfficiency_NXB-63-2P-D4 | 计算类 | -- |
| C_NXB-63 2P D10 | project_TceEnergyEfficiency_NXB-63-2P-D10 | 计算类 | -- |
| C_NXB-63 2P D16 | project_TceEnergyEfficiency_NXB-63-2P-D16 | 计算类 | -- |
| C_NXB-63 2P D20 | project_TceEnergyEfficiency_NXB-63-2P-D20 | 计算类 | -- |
| C_NXB-63 2P D20-双极 | project_TceEnergyEfficiency_NXB-63-2P-D20-double | 计算类 | -- |
| C_NXB-63 2P D25 | project_TceEnergyEfficiency_NXB-63-2P-D25 | 计算类 | -- |
| C_NXB-63 2P D25-双极 | project_TceEnergyEfficiency_NXB-63-2P-D25-double | 计算类 | -- |
| C_NXB-63 2P D32 | project_TceEnergyEfficiency_NXB-63-2P-D32 | 计算类 | -- |
| C_NXB-63 2P D40 | project_TceEnergyEfficiency_NXB-63-2P-D40 | 计算类 | -- |
| C_NXB-63 2P D63 | project_TceEnergyEfficiency_NXB-63-2P-D63 | 计算类 | -- |
| C_NXB-63 3P C1 | project_TceEnergyEfficiency_NXB-63-3P-C1 | 计算类 | -- |
| C_NXB-63 3P C10 | project_TceEnergyEfficiency_NXB-63-3P-C10 | 计算类 | -- |
| C_NXB-63 3P C16 | project_TceEnergyEfficiency_NXB-63-3P-C16 | 计算类 | -- |
| C_NXB-63 3P C2 | project_TceEnergyEfficiency_NXB-63-3P-C2 | 计算类 | -- |
| C_NXB-63 3P C20 | project_TceEnergyEfficiency_NXB-63-3P-C20 | 计算类 | -- |
| C_NXB-63 3P C20A | project_TceEnergyEfficiency_NXB-63-3P-C20A | 计算类 | -- |
| C_NXB-63 3P C25 | project_TceEnergyEfficiency_NXB-63-3P-C25 | 计算类 | -- |
| C_NXB-63 3P C25A | project_TceEnergyEfficiency_NXB-63-3P-C25A | 计算类 | -- |
| C_NXB-63 3P C3 | project_TceEnergyEfficiency_NXB-63-3P-C3 | 计算类 | -- |
| C_NXB-63 3P C32 | project_TceEnergyEfficiency_NXB-63-3P-C32 | 计算类 | -- |
| C_NXB-63 3P C32A | project_TceEnergyEfficiency_NXB-63-3P-C32A | 计算类 | -- |
| C_NXB-63 3P C4 | project_TceEnergyEfficiency_NXB-63-3P-C4 | 计算类 | -- |
| C_NXB-63 3P C40 | project_TceEnergyEfficiency_NXB-63-3P-C40 | 计算类 | -- |
| C_NXB-63 3P C40A | project_TceEnergyEfficiency_NXB-63-3P-C40A | 计算类 | -- |
| C_NXB-63 3P C6 | project_TceEnergyEfficiency_NXB-63-3P-C6 | 计算类 | -- |
| C_NXB-63 3P D2 | project_TceEnergyEfficiency_NXB-63-3P-D2 | 计算类 | -- |
| C_NXB-63 3P D3 | project_TceEnergyEfficiency_NXB-63-3P-D3 | 计算类 | -- |
| C_NXB-63 3P D4 | project_TceEnergyEfficiency_NXB-63-3P-D4 | 计算类 | -- |
| C_NXB-63 3P D10 | project_TceEnergyEfficiency_NXB-63-3P-D10 | 计算类 | -- |
| C_NXB-63 3P D16 | project_TceEnergyEfficiency_NXB-63-3P-D16 | 计算类 | -- |
| C_NXB-63 3P D20 | project_TceEnergyEfficiency_NXB-63-3P-D20 | 计算类 | -- |
| C_NXB-63 3P D25 | project_TceEnergyEfficiency_NXB-63-3P-D25 | 计算类 | -- |
| C_NXB-63 3P D32 | project_TceEnergyEfficiency_NXB-63-3P-D32 | 计算类 | -- |
| C_NXB-63 3P D40 | project_TceEnergyEfficiency_NXB-63-3P-D40 | 计算类 | -- |
| C_NXB-63 3P D50 | project_TceEnergyEfficiency_NXB-63-3P-D50 | 计算类 | -- |
| C_NXB-63 3P D63 | project_TceEnergyEfficiency_NXB-63-3P-D63 | 计算类 | -- |
| C_NXB-63 4P C6 | project_TceEnergyEfficiency_NXB-63-4P-C6 | 计算类 | -- |
| C_NXB-63 4P C10 | project_TceEnergyEfficiency_NXB-63-4P-C10 | 计算类 | -- |
| C_NXB-63 4P C16 | project_TceEnergyEfficiency_NXB-63-4P-C16 | 计算类 | -- |
| C_NXB-63 4P C20 | project_TceEnergyEfficiency_NXB-63-4P-C20 | 计算类 | -- |
| C_NXB-63 4P C25 | project_TceEnergyEfficiency_NXB-63-4P-C25 | 计算类 | -- |
| C_NXB-63 4P C32 | project_TceEnergyEfficiency_NXB-63-4P-C32 | 计算类 | -- |
| C_NXB-63 4P C40 | project_TceEnergyEfficiency_NXB-63-4P-C40 | 计算类 | -- |
| C_NXB-63 4P C50 | project_TceEnergyEfficiency_NXB-63-4P-C50 | 计算类 | -- |
| C_NXB-63 4P C63 | project_TceEnergyEfficiency_NXB-63-4P-C63 | 计算类 | -- |
| C_NXB-63 4P D10 | project_TceEnergyEfficiency_NXB-63-4P-D10 | 计算类 | -- |
| C_NXB-63 4P D16 | project_TceEnergyEfficiency_NXB-63-4P-D16 | 计算类 | -- |
| C_NXB-63 4P D20 | project_TceEnergyEfficiency_NXB-63-4P-D20 | 计算类 | -- |
| C_NXB-63 4P D25 | project_TceEnergyEfficiency_NXB-63-4P-D25 | 计算类 | -- |
| C_NXB-63 4P D32 | project_TceEnergyEfficiency_NXB-63-4P-D32 | 计算类 | -- |
| C_NXB-63 4P D40 | project_TceEnergyEfficiency_NXB-63-4P-D40 | 计算类 | -- |
| C_NXB-63 4P D50 | project_TceEnergyEfficiency_NXB-63-4P-D50 | 计算类 | -- |
| C_NXB-63 4P D63 | project_TceEnergyEfficiency_NXB-63-4P-D63 | 计算类 | -- |
| C_NXBLE-32 2P C20 | project_TceEnergyEfficiency_NXBLE-32-2P-C20 | 计算类 | -- |
| C_NXBLE-32 2P C25 | project_TceEnergyEfficiency_NXBLE-32-2P-C25 | 计算类 | -- |
| C_NXBLE-32 2P C32 | project_TceEnergyEfficiency_NXBLE-32-2P-C32 | 计算类 | -- |
| C_NXBLE-32 2P C40 | project_TceEnergyEfficiency_NXBLE-32-2P-C40 | 计算类 | -- |
| T_NXB-63 1P C1 | project_TotalProductionEnergyNew_NXB-63-1P-C1 | 计算类 | -- |
| T_NXB-63 1P C10 | project_TotalProductionEnergyNew_NXB-63-1P-C10 | 计算类 | -- |
| T_NXB-63 1P C16 | project_TotalProductionEnergyNew_NXB-63-1P-C16 | 计算类 | -- |
| T_NXB-63 1P C2 | project_TotalProductionEnergyNew_NXB-63-1P-C2 | 计算类 | -- |
| T_NXB-63 1P C20 | project_TotalProductionEnergyNew_NXB-63-1P-C20 | 计算类 | -- |
| T_NXB-63 1P C20A | project_TotalProductionEnergyNew_NXB-63-1P-C20A | 计算类 | -- |
| T_NXB-63 1P C25 | project_TotalProductionEnergyNew_NXB-63-1P-C25 | 计算类 | -- |
| T_NXB-63 1P C25A | project_TotalProductionEnergyNew_NXB-63-1P-C25A | 计算类 | -- |
| T_NXB-63 1P C3 | project_TotalProductionEnergyNew_NXB-63-1P-C3 | 计算类 | -- |
| T_NXB-63 1P C32 | project_TotalProductionEnergyNew_NXB-63-1P-C32 | 计算类 | -- |
| T_NXB-63 1P C4 | project_TotalProductionEnergyNew_NXB-63-1P-C4 | 计算类 | -- |
| T_NXB-63 1P C40 | project_TotalProductionEnergyNew_NXB-63-1P-C40 | 计算类 | -- |
| T_NXB-63 1P C50 | project_TotalProductionEnergyNew_NXB-63-1P-C50 | 计算类 | -- |
| T_NXB-63 1P C6 | project_TotalProductionEnergyNew_NXB-63-1P-C6 | 计算类 | -- |
| T_NXB-63 1P C63 | project_TotalProductionEnergyNew_NXB-63-1P-C63 | 计算类 | -- |
| T_NXB-63 1P D10 | project_TotalProductionEnergyNew_NXB-63-1P-D10 | 计算类 | -- |
| T_NXB-63 2P C4 | project_TotalProductionEnergyNew_NXB-63-2P-C4 | 计算类 | -- |
| T_NXB-63 2P C40 | project_TotalProductionEnergyNew_NXB-63-2P-C40 | 计算类 | -- |
| T_NXB-63 2P C50 | project_TotalProductionEnergyNew_NXB-63-2P-C50 | 计算类 | -- |
| T_NXB-63 2P C6 | project_TotalProductionEnergyNew_NXB-63-2P-C6 | 计算类 | -- |
| T_NXB-63 2P C63 | project_TotalProductionEnergyNew_NXB-63-2P-C63 | 计算类 | -- |
| T_NXB-63 2P D10 | project_TotalProductionEnergyNew_NXB-63-2P-D10 | 计算类 | -- |
| T_NXB-63 2P D16 | project_TotalProductionEnergyNew_NXB-63-2P-D16 | 计算类 | -- |
| T_NXB-63 2P D20 | project_TotalProductionEnergyNew_NXB-63-2P-D20 | 计算类 | -- |
| T_NXB-63 2P D20-双极 | project_TotalProductionEnergyNew_NXB-63-2P-D20-double | 计算类 | -- |
| T_NXB-63 2P D25 | project_TotalProductionEnergyNew_NXB-63-2P-D25 | 计算类 | -- |
| T_NXB-63 2P D25-双极 | project_TotalProductionEnergyNew_NXB-63-2P-D25-double | 计算类 | -- |
| T_NXB-63 2P D32 | project_TotalProductionEnergyNew_NXB-63-2P-D32 | 计算类 | -- |
| T_NXB-63 2P D32-双极 | project_TotalProductionEnergyNew_NXB-63-2P-D32-double | 计算类 | -- |
| T_NXB-63 3P D32 | project_TotalProductionEnergyNew_NXB-63-3P-D32 | 计算类 | -- |
| T_NXB-63 3P D4 | project_TotalProductionEnergyNew_NXB-63-3P-D4 | 计算类 | -- |
| T_NXB-63 3P D40 | project_TotalProductionEnergyNew_NXB-63-3P-D40 | 计算类 | -- |
| T_NXB-63 3P D50 | project_TotalProductionEnergyNew_NXB-63-3P-D50 | 计算类 | -- |
| T_NXB-63 3P D6 | project_TotalProductionEnergyNew_NXB-63-3P-D6 | 计算类 | -- |
| T_NXB-63 3P D63 | project_TotalProductionEnergyNew_NXB-63-3P-D63 | 计算类 | -- |
| T_NXB-63 4P C10 | project_TotalProductionEnergyNew_NXB-63-4P-C10 | 计算类 | -- |
| T_NXB-63 4P C16 | project_TotalProductionEnergyNew_NXB-63-4P-C16 | 计算类 | -- |
| T_NXB-63 4P C20 | project_TotalProductionEnergyNew_NXB-63-4P-C20 | 计算类 | -- |
| T_NXB-63 4P C25 | project_TotalProductionEnergyNew_NXB-63-4P-C25 | 计算类 | -- |
| T_NXB-63 4P C32 | project_TotalProductionEnergyNew_NXB-63-4P-C32 | 计算类 | -- |
| T_NXB-63 4P C40 | project_TotalProductionEnergyNew_NXB-63-4P-C40 | 计算类 | -- |
| T_NXB-63 4P C50 | project_TotalProductionEnergyNew_NXB-63-4P-C50 | 计算类 | -- |
| T_NXB-63 4P C6 | project_TotalProductionEnergyNew_NXB-63-4P-C6 | 计算类 | -- |
| T_NXB-63 4P C63 | project_TotalProductionEnergyNew_NXB-63-4P-C63 | 计算类 | -- |
| T_NXB-63 4P D10 | project_TotalProductionEnergyNew_NXB-63-4P-D10 | 计算类 | -- |
| T_NXB-63 4P D16 | project_TotalProductionEnergyNew_NXB-63-4P-D16 | 计算类 | -- |
| T_NXB-63 4P D20 | project_TotalProductionEnergyNew_NXB-63-4P-D20 | 计算类 | -- |
| T_NXB-63 4P D25 | project_TotalProductionEnergyNew_NXB-63-4P-D25 | 计算类 | -- |
| T_NXB-63 4P D32 | project_TotalProductionEnergyNew_NXB-63-4P-D32 | 计算类 | -- |
| T_NXB-63 4P D40 | project_TotalProductionEnergyNew_NXB-63-4P-D40 | 计算类 | -- |
| T_NXB-63 4P D50 | project_TotalProductionEnergyNew_NXB-63-4P-D50 | 计算类 | -- |
| T_NXB-63 4P D63 | project_TotalProductionEnergyNew_NXB-63-4P-D63 | 计算类 | -- |
| T_NXBLE-32 2P C20 | project_TotalProductionEnergyNew_NXBLE-32-2P-C20 | 计算类 | -- |
| T_NXBLE-32 2P C25 | project_TotalProductionEnergyNew_NXBLE-32-2P-C25 | 计算类 | -- |
| T_NXBLE-32 2P C32 | project_TotalProductionEnergyNew_NXBLE-32-2P-C32 | 计算类 | -- |
| T_NXBLE-32 2P C40 | project_TotalProductionEnergyNew_NXBLE-32-2P-C40 | 计算类 | -- |

### 实例

| 实例名称 | 实例标识符 |
|---|---|
| 型号统计单元级嵌套实例 | 2069356979499175936 |

<!-- ===================== MODEL 8: 单相智能微断（project_NB2LE_80ZT） ===================== -->

## 模型8：单相智能微断（project_NB2LE_80ZT）

**类型:** 设备级DT
**含义:** 智能微型断路器相关信息统计
**实例数:** 若干

### 指标

| 指标名称 | 指标标识符 | 指标类型 | 指标单位 |
|---|---|---|---|
| 设备连接状态 | @online_status | 测点类 | - |
| 分闸次数 | FZCSU | 测点类 | 次 |
| 漏电分闸次数 | LDFZCSU | 测点类 | 次 |
| 总功率因数 | ZGLYSU | 测点类 | - |
| 总视在电能 | ZSZDNEN | 测点类 | kVAh |
| 总视在功率 | ZSZGLI | 测点类 | VA |
| 总无功电能 | ZWGDNEN | 测点类 | kvarh |
| 总无功功率 | ZWGGLI | 测点类 | kvar |
| 总有功电能 | ZYGDNEN | 测点类 | kWh |
| 总有功功率 | ZYGGLI | 测点类 | W |
| 日-耗电量 | project_DailyEnergyConsumption | 累计用量类 | kWh |
| 月-耗电量 | project_MonthlyEnergyConsumption | 累计用量类 | kWh |
| 年-耗电量 | project_yearlyEnergyConsumption | 累计用量类 | kWh |
| 总耗电量 | project_TotalEnergyConsumption | 累计用量类 | kWh |
| 每小时累计 | public_hourEnergyConsumption | 累计用量类 | kWh |
| 每年累计 | public_yearlyEnergyConsumption | 累计用量类 | kWh |

### 实例

| 实例名称 | 实例标识符 |
|---|---|
|DT_47线-手柄机构组装与检测合盖单元|2084176868075560961|
|DT_47线-自动铆合单元|2084176867970703361|
|DT_47线-喷码单元|2084176867891011585|
|DT_47线-自动穿钉单元|2084176867790348289|
|DT_47线-止动件组装单元|2084176867714850817|
|DT_47线-操作机构与热系统组装单元|2084176867643547648|
|DT_47线-触头支持组件装配单元|2084176867563855873|
|DT_47线-贴塞子单元|2084176867484164096|
|DT_47线-延时校验单元|2084176867354140672|
|DT_M12线-自动移印单元(侧面)|2082375004971524097|
|DT_M12线-自动包装单元(前)|2082375004900220928|
|DT_M12线-自动延时校验单元|2082375004828917761|
|DT_M02线-自动成品参数检测单元|2082375004753420289|
|DT_M02线-自动止动件组装单元|2082375004673728513|
|DT_M02线-调解螺钉与磁系统组装单元上料机|2082375004606619649|
|DT_M12线-触头支持组件装配单元|2082375004535316481|
|DT_M12线-操作机构与热系统组装单元上料机|2082375004468207617|
|DT_M12线-自动成品参数检测单元|2082375004392710145|
|DT_M12线-自动贴塞子单元|2082375004317212672|
|DT_47线-操作机构与热系统组装单元上料机|2082375004241715201|
|DT_M12线-自动穿钉与铆合单元|2082375004170412033|
|DT_M02线-调解螺钉与磁系统组装单元|2082375004099108865|
|DT_M02线-手柄机构组装与检测合盖单元|2082375004027805697|
|DT_47线-成品参数检测单元|2082375003952308225|
|DT_M12线-多极拼装与喷码单元|2082375003881005057|
|DT_47线-调节螺钉装配与预调上料机|2082375003809701889|
|DT_M02线-自动穿钉与铆合单元|2082375003738398721|
|DT_47线-螺钉退出单元|2082375003658706944|
|DT_M12线-操作机构与热系统组装单元|2082375003583209472|
|DT_M02线-自动移印单元(侧面)|2082375003511906304|
|DT_M02线-自动贴塞子单元|2082375003432214528|
|DT_M02线-操作机构与热系统组装单元|2082375003348328449|
|DT_M12线-自动止动件组装单元|2082375003272830977|
|DT_M12线-调节螺钉装配与磁系统组装单元|2082375003193139201|
|DT_47线-人工整理与磁系统组装单元|2082375003117641729|
|DT_47线-调节螺钉装配与预调单元|2082375003046338561|
|DT_M12线-自动移印单元(正面)|2082375002975035393|
|DT_M12线-调节螺钉装配与磁系统组装单元上料机|2082375002895343617|
|DT_M12线-自动包装单元(后)|2082375002819846145|
|DT_M02线-自动包装单元|2082375002731765761|
|DT_47线-移印单元|2082375002660462593|
|DT_M12线-手柄机构组装与检测合盖单元|2082375002572382209|
|DT_M02线-多极拼装与喷码单元|2082375002488496129|
|DT_M02线-自动延时校验单元|2082375002412998656|
|DT_M02线-操作机构与热系统组装单元上料机|2082375002299752448|


<!-- ===================== MODEL 9: 产线总功率表（project_LinePower） ===================== -->
## 模型9：产线总功率（project_LinePower）

**类型:** 单元级DT
**含义:** 各产线的总功率信息统计
**实例数:** 3

### 指标
指标名称|指标标识符|指标类型|指标单位|
|---|---|---|---|
|设备连接状态|@online_status|测点类||
|总功率|project_Power|统计类|W|

## 实例表

|实例名称|实例标识符|
|---|---|
|M12线总功率|2084524712020074496|
|M02线总功率|2084524480471818240|
|47线总功率|2084524152665989120|

<!-- ===================== CROSS-MODEL MAPPING ===================== -->

## 跨模型ID映射

同一个物理型号在 **EquipmentModel** (DT_xxx 命名) 和 **ProductTypeAgg** (无 DT_ 前缀) 下使用不同的实例ID。

- EquipmentModel 实例名前缀: `DT_` (e.g. "DT_单极小型断路器 NXB-63 1P C20A 全制程 环保")
- ProductTypeAgg 实例名: 无 `DT_` 前缀 (e.g. "单极小型断路器 NXB-63 1P C20A 全制程 环保")

通过 `PEM` (设备型号-数字映射) 或匹配总产量/总极数可交叉关联。

<!-- ===================== KEY METRIC IDENTIFIERS ===================== -->

## 关键指标标识符索引

| 标识符 | 含义 | 所属模型 | 单位 |
|---|---|---|---|
| EP | 有功总电能 | ElectricMeter_3P | kWh |
| P | 有功总功率 | ElectricMeter_3P | W |
| FINISH_YIELD | 所有型号累计产量(台数) | ElectricMeter_3P | 台 |
| project_5minsEnergyConsumption | 每5分钟耗能 | ElectricMeter_3P/proportionPower | kWh |
| project_5minsProductionQuantity | 每5分钟产量(台数) | ElectricMeter_3P | 台 |
| @online_status | 设备连接状态 | ElectricMeter_3P/EquipmentModel/GasMeter | - |
| YIELD | 该型号总产量(台数) | EquipmentModel | 台 |
| project_5minsExtremeNumber | 产量(极数) | EquipmentModel | 极 |
| project_TotalOutputValueNew | 总产值 | EquipmentModel/ProductTypeAgg | 元 |
| project_5mins{线}ModelYield | 该型号在某线5分钟产量(台数) | ProductTypeAgg | 台 |
| project_5mins{线}ExtremeNumber | 该型号在某线5分钟产量(极数) | ProductTypeAgg | 极 |
| project_5mins{线}ModelEnergy | 该型号在某线5分钟能耗 | ProductTypeAgg | kWh |
| project_Daily{线}ModelYield | 该型号在某线日产量(极数) | ProductTypeAgg | 极 |
| project_proportion{01-67} | 某线功率占总功率比重 | proportionPower | % |
| project_14powerMeterAdd | 总有功功率 | proportionPower | W |
| project_14powerMeterEnergyAdd | 总有功电能 | proportionPower | kWh |
| project_carbonEmission | 总碳排放 | proportionPower | kg |
| project_TceEnergyEfficiency_<型号> | 某型号万元产值能耗(标准煤) | 型号统计单元级嵌套模型 | -- |
| project_TotalProductionEnergyNew_<型号> | 某型号累计总能耗 | 型号统计单元级嵌套模型 | -- |
| project_TotalUsageNm3 | 总用气量 | GasMeter | m³ |
| project_hourlyUsageNm3 | 每小时用气量 | GasMeter | m³ |
| project_dailyUsageNm3 | 每日用气量 | GasMeter | m³ |
| ZYGDNEN | 总有功电能(智能微断) | 单相智能微断 | kWh |
| ZYGGLI | 总有功功率(智能微断) | 单相智能微断 | W |
