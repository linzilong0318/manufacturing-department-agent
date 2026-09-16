# 设备/实例数量盘点（元数据统计）

> 2026-08 会话确立。当用户问"有多少设备 / 盘点设备 / 有哪些实例"时使用。
> 已按 Step 4 编号为**案例 22**（统计系统设备/实例数量），但因案例库文件
> `dtx-query-cases.md` 位于技能根目录不受 skill_manage 管理，先存为 references 支持文件，
> 待 curator 合并进案例库正文。

问题：查看目前有多少设备
查询类型：元数据（设备实例盘点）
时间粒度：当前状态
分析方式：统计

## SQL 步骤（占位符 {库名} = dtx_385318105131300357，{指标} 见下方映射）

1. 统计各类设备实例数——**关键技巧：每个实例在某指标下只有一张子表，直接 COUNT(*) 即实例数，无需去重**：
```sql
SELECT '三相电表' AS type, COUNT(*) AS num FROM information_schema.ins_tables
WHERE db_name = '{库名}' AND table_name LIKE 'quota_sub_%@EP'            -- 电表
UNION ALL SELECT '单相智能微断', COUNT(*) FROM information_schema.ins_tables
WHERE db_name = '{库名}' AND table_name LIKE 'quota_sub_%@ZYGDNEN'       -- 微断
UNION ALL SELECT '产线气表', COUNT(*) FROM information_schema.ins_tables
WHERE db_name = '{库名}' AND table_name LIKE 'quota_sub_%@DWEI'          -- 气表
UNION ALL SELECT '产线总功率表', COUNT(*) FROM information_schema.ins_tables
WHERE db_name = '{库名}' AND table_name LIKE 'quota_sub_%@project_Power' -- 总功率
UNION ALL SELECT '设备型号', COUNT(*) FROM information_schema.ins_tables
WHERE db_name = '{库名}' AND table_name LIKE 'quota_sub_%@YIELD'         -- 型号档案
```

2. 同模型多版本细分归属（区分正式/CT/copy 模型，解释"数量比台账多"）：
```sql
SELECT stable_name, COUNT(*) FROM information_schema.ins_tables
WHERE db_name = '{库名}' AND table_name LIKE 'quota_sub_%@EP' GROUP BY stable_name
```

3. **甄别"幽灵实例"（已建表未采集）**：对台账外的实例逐查 first(ts)/last(ts)/count(*)
   → 全部 `<nil>`/0 = 预建未启用（预留/残留/测试复制），不计入在用设备，如实报告"在用 N + 已建未用 M"，
   不要直接给表总数。

4. （可选）识别额外电表归属：查 `quota_sub_{ID}@wkln` / `@customWkln` 最后值；
   无产线号数据 = 未绑定产线，标注"未配置产线号"。

## 典型指标 ↔ 设备类型映射

| 指标后缀 | 设备类型 | 实测数量（2026-08） |
|---|---|---|
| `@EP` | 三相电表（含 CT/copy 模型） | 27 表（在用 14 + 空表 13） |
| `@ZYGDNEN` | 单相智能微断（工序单元） | 74（文档台账仅录 45 个，落后约 29 个，见"分表数量验证"节） |
| `@DWEI` | 产线气表 | 5 |
| `@project_Power` | 产线总功率表 | 3 |
| `@YIELD` | 设备型号（EquipmentModel 档案） | 97 |

## 产线级计量配置（哪些产线有分表/微断）

**14 条产线中仅 3 条装有单相智能微断单元分表**，其余 11 条只有主三相电表（总表），无单元级分表、无气表、无总功率表：

| 产线 | 微断分表数 | 其他计量 |
|---|---|---|
| M02线 | 13（台账） | 主电表 + 2 气表 + 1 总功率表 |
| M12线 | 16（台账） | 主电表 + 1 气表 + 1 总功率表 |
| 47线 | 16（台账） | 主电表 + 2 气表 + 1 总功率表 |
| 其余 11 条（67/M01/M03/M04/M05/M06/M07/M08/M09/49/50） | **0** | 仅主三相电表 |

**应用**：用户问\"某产线分表数量/所有电表\"时，先查本表判断该线有无微断——无分表的线（如 M03）用电只能到产线总表粒度，不能拆分单元；\"所有没有分表的产线\"= 上表 11 条。全厂仅此 3 条线做了单元级能耗监测。

## 数据驱动判断"哪些产线有/没有分表"（不依赖文档快照）

当用户问"哪些产线有分表"、"哪些产线没有分表"、"所有没有分表的产线"等时，不要仅凭文档静态列表回答，而是执行以下数据驱动的验证流程。文档快照可能过时，数据库实测才是唯一权威来源。

### 判断流程

**前置知识：** 14条产线的instance_uid已记录在dtx-model-map.md模型1的表格中。微断子表（NB2LE_80ZT）的表名格式为 `quota_sub_{instance_uid}@@online_status`（或任何微断指标，如 @ZYGDNEN）。

**Step A — 获取所有微断子表的 TBNAME（即 instance_uid）：**
```sql
SELECT DISTINCT TBNAME FROM `quota_385318105131300357@project_NB2LE_80ZT@@online_status`
```
返回结果类似 `quota_sub_2082375003432214528@@online_status`，从中提取 instance_uid 部分。

**Step B — 获取微断实例名称（含产线前缀）：**
微断实例名格式如 `DT_M02线-自动成品参数检测单元`，产线前缀在实例名中。
查询任一微断指标表实例的 tags 可获取 instance_uid 映射（但 TDengine 不支持 JOIN 且 information_schema 不暴露子表 tag 值）。直接走备用路径：

**Step C — 从 dtx-model-map.md 模型8（微断实例列表）正向映射：**
模型8的实例名含产线前缀（`DT_M02线-xxx` / `DT_M12线-xxx` / `DT_47线-xxx`），每个实例有对应的 instance_uid。将 Step A 查到的所有子表 instance_uid 与模型8实例列表交叉比对，即可确认哪些产线在数据库中有实际微断子表。

注意：模型8实例表是台账，有的实例可能已注册但无实际数据。交叉验证时对每个匹配的产线查 `SELECT last(ts) FROM 'quota_sub_{uid}@online_status'` 确认是否有活跃数据。

**Step D — 无分表产线的判定：**
14条产线全量列表（从模型1获取）减去 Step C 确认有活跃微断子表的产线 = 无分表产线。

**简化版快捷判断（日常复用）：**
当已知文档比较新且用户未要求精确实时验证时：
- 查 `SELECT COUNT(*) FROM information_schema.ins_tables WHERE db_name = 'dtx_385318105131300357' AND table_name LIKE '%@@online_status'` 看微断子表总数以确认文档中约45个的数量没有大幅变化。
- 若总数在 40~50 之间（与文档一致），则"3条线有分表、11条线无分表"的结论仍有效，可放心引用文档。
- 若总数剧烈变化（如新增到60+或减少到20-），必须执行 Step A~D 重算。

## 分表台账 vs 数据库验证（用户问"数量对吗"时使用）

当用户问"分表数量对吗"、"台账与实际一致吗"等校验型问题时，执行以下流程。核心原则：**数据库实际子表数为权威源，文档台帐为辅助参考，两者差异需逐UID交叉比对。**

### 判断流程

**Step 1 — 获取数据库微断子表总数：**
```sql
SELECT COUNT(*) FROM information_schema.ins_tables
WHERE db_name = 'dtx_385318105131300357' AND table_name LIKE 'quota_sub_%@ZYGDNEN'
```
**Step 2 — 获取数据库所有微断子表的 instance_uid 列表：**
```sql
SELECT DISTINCT TBNAME FROM `quota_385318105131300357@project_NB2LE_80ZT@@online_status`
```
或（online_status可能因该表无数据报错）：
```sql
SELECT DISTINCT TBNAME FROM `quota_385318105131300357@project_NB2LE_80ZT@ZYGDNEN`
```
返回结果如 `quota_sub_2082375003432214528@@online_status`，提取 `2082375003432214528` 部分作为UID。
**注意**：DISTINCT 可能去重不足（同UID不同指标有不同TBNAME），改用 `information_schema.ins_tables` 按 instance_uid tag 分组是更精确的方式，但TDengine 3.4 不支持 information_schema 暴露子表 tag 值。

**Step 3 — 从 dtx-model-map.md 模型8（微断实例列表）取出文档台账的所有UID：**
模型8实例表列出了45个实例及其UID。用 execute_code 在Python中将两个UID集合做差集比较：文档有但数据库无 = 已注册未建表（极少）；数据库有但文档无 = 台账遗漏（常见，本会话实测约29个）。

**Step 4 — 输出差异报告：**

| 指标 | 值 |
|---|---|
| 数据库DISTINCT UID总数 | N（例：74） |
| 文档台账UID数 | 45 |
| 台账&数据库交集 | M（例：45） |
| 台账有但数据库无 | N/A（例极少） |
| 数据库有但台账无 | N-M（例：约29） |

数据库有但台账无的UID说明台账未及时更新。如用户要求，可补充查这些额外UID是否产生产量/能耗数据（`SELECT count(*), last(ts) FROM 'quota_sub_{uid}@ZYGDNEN'`），区分"真正在用" vs "预留/空表"。

**Step 5 — 按产线归集（进阶）：**
文档模型8实例名含产线前缀（`DT_M02线-xxx` / `DT_M12线-xxx` / `DT_47线-xxx`），数据库多出的UID无法直接映射产线（TDengine无JOIN）。如需按产线逐一核对，使用 `SHOW TABLE TAGS` 逐UID查询产线信息（不适用于大量UID的批量查）。替代方案：查 `quota_sub_{uid}@wkln` 表按产线号数字分组归集。

### 注意事项
- 本流程同样适用于**气表分表数量验证**（GasMeter 模型），只需把指标从 `ZYGDNEN` 换成 `DWEI` 即可。
- 本流程也适用于**三相电表数量验证**（ElectricMeter_3P），把指标从 `ZYGDNEN` 换成 `EP` 即可。三相电表14个产线实例（含67线CT）是稳定的，但可能存在多出的 copy 模型空表。
- 简言之，`{指标}` 替换为对应设备类型的指标标识符即可复用整套流程：`EP`（三相电表）、`ZYGDNEN`（微断）、`DWEI`（气表）、`project_Power`（总功率表）。

## 坑与注意事项

- ⚠️ **TDengine 3.4 不支持 SPLIT_PART / REGEXP_REPLACE / INSTR 等字符串函数**（information_schema 查询中报
  "function 'xxx' is not defined"），禁止用它们解析表名提取实例 ID；"每实例一表"的指标直接 COUNT(*) 即可。
- **SHOW TABLES LIKE 输出超长会被截断**（max_rows 场景），不能用手动数列表的方式统计总数；一律走
  `information_schema.ins_tables` 计数。
- 台账口径（model-map 的实例列表）与库内实测可能不符：**以实测为准**，差异多为空表/复制模型，需甄别后分类呈现。
- 单元级统计类实例（虚拟总表、产线型号总统计、嵌套模型）也以 `quota_sub_` 前缀建表，数量少可直接数；
  用户问"设备"时默认指物理计量设备（电表/微断/气表/功率表），型号档案单列并说明是产品档案。
- 展示用 SQL 层 `ROUND(SUM(val), 2)` 规整浮点表示误差（如 7521.969999999999 → 7521.97），
  属查询加工非篡改（规则 0 操作注解）；对单日巨值（如 M07 平日 0~86 突现 2103.7）先重查验证再解读为计量异常。
- 关联规则 2b：设备断流时间各链路不同（实测气表先断、产量/功率延后），盘点时按链路分别给 last(ts)。