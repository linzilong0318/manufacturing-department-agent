# 查询案例库（20 例，按业务域排序，编号唯一）

> 使用方式：按用户问题的模糊匹配定位案例，复用 SQL 结构改参数（{T}/{线}/{实例ID}），不新增条目。
> 案例只存结构，不存数据值；具体查询结果在回答时给用户，不进案例库。
> 具体表名/单位/时区/实例 ID 速查统一见 **dtx-model-map.md**（本文件案例内保留 SQL 结构，不重复维护速查表）。

| 编号 | 案例 | 对应问题 |
|---|---|---|
| 1 | 某产线某日生产了哪些设备 | 47号产线6.1号生产了哪些设备 |
| 2 | 全厂产量日环比（昨天 vs 前天） | 昨天产量是不是比前天高？高多少？ |
| 3 | 某产线最近几天产量趋势 | 47线最近几天产量咋样，帮我看看趋势 |
| 4 | 某区间全厂累计产量（跨月汇总） | 咱们厂6月份到现在一共多少了？ |
| 5 | 判断哪些产线停产/未开机 | 有没有停产或没开机的线？ |
| 6 | 某系列型号最近是否有生产（全厂范围） | NXBLE-32 那个系列最近有生产吗？ |
| 7 | 2P 与 3P 产量结构占比变化 | 2P 和 3P 的产量结构变化大吗？ |
| 8 | 某系列（如 4P D 系列）各产线产量对比 | 4P 的 D 系列最近谁家做得多？ |
| 9 | 全产线近期产量稳定性分析 | 最近各条线产量稳定吗？有没有哪条忽高忽低？ |
| 10 | 某月全厂总产值 | 6月全厂产值多少 |
| 11 | 哪个型号产值最高（全厂型号产值排行） | 哪个型号最赚钱？（产值最高） |
| 12 | 哪条产线产值最高（全产线产值排行） | 哪条线产值最高？ |
| 13 | 某产线当前正在生产哪个型号（实时状态） | 47线现在正在生产哪个型号？ |
| 14 | 全厂万极能耗（每生产一万极用多少电） | 每生产一万极要多少电？ |
| 15 | 两条产线效率对比 | M01号产线和M03号产线 哪个效率更高 |
| 16 | 某产线每小时用电高峰时段分析 | 47线每小时用电高峰是几点？ |
| 17 | 全产线夜间/非生产时段能耗排查 | 最近有没有哪条线半夜还在耗电？ |
| 18 | 全产线能耗-产量对比 | 哪条线电用得多但产量还少？ |
| 19 | 全厂当前总功率（实时值） | 全厂现在的总功率多少？ |
| 20 | 某产线功率占全厂比例（虚拟总表直接指标） | M02线功率占全厂多少？ |
| 21 | 某产线近几天用气量（气表每日用气量） | M02号产线近五天的用气量是多少？ |
| 22 | 型号级万元产值能耗排行（成本结构分析） | 哪些型号耗电多产值少？（降本排产建议） |

# 案例21：某产线近几天用气量（气表每日用气量）
问题：M02号产线近五天的用气量是多少？
查询类型：能耗（用气量）
时间粒度：日（最近 N 天）
分析方式：汇总（多气表合计）

SQL 步骤：
  1. 先验证气表 Daily 表数据范围（判断采集截止点）：
     SELECT first(ts), last(ts), count(*) FROM `quota_sub_{气表实例ID}@project_dailyUsageNm3`
  2. 再查 hourly 表 last(ts) 交叉确认采集是否存活：
     SELECT first(ts), last(ts), count(*) FROM `quota_sub_{气表实例ID}@project_hourlyUsageNm3`
  3. 该产线多块气表 UNION ALL 按天汇总（Daily 表 ts={T} 16:00 UTC = BJT T 日全天）：
     SELECT ts, SUM(val) AS total FROM (
       SELECT ts, val FROM `quota_sub_{气表1}@project_dailyUsageNm3` WHERE ts >= '{起点UTC}' AND ts < '{终点UTC}'
       UNION ALL SELECT ts, val FROM `quota_sub_{气表2}@project_dailyUsageNm3` WHERE ts >= '{起点UTC}' AND ts < '{终点UTC}'
     ) GROUP BY ts ORDER BY ts
  4. 区间总合计：SELECT SUM(val) FROM (同上 UNION ALL)（多表合计必须在 SQL 层算，禁止手算）

单位：m³（project_dailyUsageNm3）
关键参数：气表实例 ID 见 dtx-model-map.md 模型6（M02=2082375796692541441/2082375796537352193、M12=2082375796604461057、47线=2082375796466049024/2082375796361191424）；UTC+8 边界（BJT T 日 = UTC (T-1) 16:00 ~ T 16:00）
注意事项：
  - 仅 M02（2块）、47（2块）、M12（1块）有气表；M01 等无气表产线直接回复\"该产线未安装气表\"
  - Daily 气表 ts 语义同产量 Daily 表：ts={T} 16:00 UTC = BJT T 日 00:00，代表当日全天汇总
  - 多块气表用 UNION ALL 在 SQL 层 SUM 出每日合计与区间合计，展示时逐数字核对
  - 采集截止判断：Daily 表与 hourly 表 last(ts) 互相印证（本例均止于 BJT 8/8），截止日后无数据，如实告知可查范围，不编造

---

# 案例1：某产线某日生产了哪些设备
问题：47号产线6.1号生产了哪些设备
查询类型：型号
时间粒度：特定日期
分析方式：汇总

SQL 步骤：
  -- 极数（Daily 表直接查）：
  SELECT instance_uid, ts, val FROM `quota_385318105131300357@project_ProductTypeAgg@project_Daily{线}ModelYield`
  WHERE ts >= '{T-1} 16:00:00' AND ts < '{T} 16:00:00' AND val > 0
  -- 补充验证（台数，5min 表 SUM）：
  SELECT instance_uid, SUM(val) AS total_yield FROM `quota_385318105131300357@project_ProductTypeAgg@project_5mins{线}ModelYield`
  WHERE ts >= '{T-1} 16:00:00' AND ts < '{T} 16:00:00' GROUP BY instance_uid HAVING SUM(val) > 0

单位：台数（5mins{线}ModelYield）+ 极数（Daily{线}ModelYield）
关键参数：产线（如 47 线）、目标日期 {T}、instance_uid 经 dtx-model-map.md 翻译为型号名
注意事项：UTC+8 边界（BJ T 日 = UTC (T-1) 16:00 ~ T 16:00）；1P 型号台数=极数；Daily 与 5min 表交叉验证；UID 必须翻译为型号名输出；返回空时先 first(ts)/last(ts) 验证数据范围

# 案例2：全厂产量日环比（昨天 vs 前天）
问题：昨天产量是不是比前天高？高多少？
查询类型：产量
时间粒度：日（两日对比）
分析方式：汇总+对比

SQL 步骤：
  1. 先验证全厂每日产量表覆盖范围（可能只覆盖早期数据，见注意）：
     SELECT first(ts), last(ts), count(*) FROM `quota_385318105131300357@project_ProductTypeAgg@project_DailyOutputStatistics`
  2. 若覆盖目标日期，按 BJT 日边界 SUM（全局汇总表，见 dtx-model-map.md）：
     SELECT SUM(val) FROM `...project_DailyOutputStatistics`
     WHERE ts >= '{T-1} 16:00:00' AND ts < '{T} 16:00:00'
  3. 若 DailyOutputStatistics 未覆盖，依次验证：分产线 Daily 表（project_Daily{线}ModelYield，14条线 UNION ALL）、
     5min 表（project_5mins{线}ModelYield 台数 / project_5minusProductionStatistics 极数）、
     设备级表（quota_sub_{线实例ID}@FINISH_YIELD 累计台数差 / project_5minsProductionQuantity）
  4. 所有表都未覆盖目标日期 → 数据采集截止，如实告知可查范围，不编造两日产量
  5. 覆盖时输出：两日产量（极数+台数口径，Lesson 4）、差值、增幅（(今日-昨日)/昨日），
     并注意周末（停产日 val=0）与工作日对比的解读

单位：极数（Daily/5min 全局表）/台数（5min 分线表、FINISH_YIELD）
关键参数：BJT T 日 = UTC (T-1) 16:00 ~ T 16:00；全厂表无产线后缀
注意事项：
  - 全厂汇总表（DailyOutputStatistics）与分产线 Daily 表可能只覆盖系统上线初期数据，查近远期先 first/last 验证范围（Lesson 7），不要直接断言"停产/无产量"
  - 5min 表与设备级表 last(ts) 相近，可交叉验证采集链路是否存活
  - 用户没说台数/极数时两口径都展示

# 案例3：某产线最近几天产量趋势
问题：47线最近几天产量咋样，帮我看看趋势
查询类型：产量
时间粒度：日（最近 N 天，多日趋势）
分析方式：趋势

SQL 步骤：
  1. 先验证产线 Daily 表覆盖范围（判断数据是否截止，防把"采集中断"当"停产"）：
     SELECT first(ts), last(ts), count(*) FROM `...project_Daily{线}ModelYield`
  2. 再查全库 5min 全局表 last(ts)：与产线表同期截止 = 全库采集中断（非单线问题）
     SELECT last(ts) FROM `...project_5minusProductionStatistics`
  3. 覆盖期内按天趋势（Daily 表 GROUP BY ts，BJT 日边界）：
     SELECT ts, SUM(val) AS daily_poles FROM `...project_Daily{线}ModelYield`
     WHERE ts >= '{起点UTC}' AND ts < '{终点UTC}' GROUP BY ts ORDER BY ts
  4. 末段补充：Daily 表无当日行时（当日汇总未生成即中断），用 5min 台数表查最后半天：
     SELECT instance_uid, SUM(val) FROM `...project_5mins{线}ModelYield` WHERE ts >= '{末段起点UTC}' GROUP BY instance_uid HAVING SUM(val) > 0

单位：极数（Daily）/台数（5min）
关键参数：产线后缀 {线}、UTC+8 边界（BJT T 日 = UTC (T-1) 16:00 ~ T 16:00）
注意事项：
  - 全库 5min 表与产线表 last(ts) 同期截止 → 采集链路中断，远期数据不可查，如实告知可查范围，不编造趋势
  - 中断当日 Daily 汇总行不存在（每日汇总未生成），只能用 5min 表看最后半天的实时数据
  - 周日（周末停产）val=0 属正常，作业务解读
  - 案例已用 {T}/{线} 占位符参数化，后续直接改参数复用，不新增条目
  - 若某业务日 Daily 汇总缺行（非 val=0 行），用 5min **极数表**（project_5mins{线}ExtremeNumber，与 Daily 同单位）按该日 UTC 边界 SUM 补数，并确认 instance_uid（型号）后标注"汇总未生成、按 5min 补数"；勿把缺行当停产（Step 3b+）

# 案例4：某区间全厂累计产量（跨月汇总，如"6月至今"）
问题：咱们厂6月份到现在一共多少了？
查询类型：产量
时间粒度：跨月区间（6/1 ~ 数据截止日）
分析方式：汇总（极数+台数双口径）

SQL 步骤：
  1. 先验证全厂 Daily 汇总表范围（first/last 验证，规则4）：SELECT first(ts), last(ts), count(*) FROM `...project_DailyOutputStatistics`
     （若 last 远早于当前日期 = 每日汇总只覆盖上线初期，还需查 5min 全局表确认实际采集截止点）
  2. 全厂 5min 表 last(ts) 确定最终数据截止时刻：
     SELECT last(ts) FROM `...project_5minusProductionStatistics`
  3. Daily 汇总部分极数：SELECT SUM(val) FROM `...project_DailyOutputStatistics` WHERE ts >= '{T-1} 16:00:00' AND ts < '{Daily截止}'
  4. 截止日当天补 5min 部分：SELECT SUM(val) FROM `...project_5minusProductionStatistics` WHERE ts >= '{T-1} 16:00:00' AND ts < '{5min last(ts)}'
  5. 台数折算：两段均按 instance_uid GROUP BY 拉型号明细，用 dtx-model-map.md P 数（1P÷1, 2P÷2, 3P÷3, 4P÷4）反推台数

单位：极数（Daily/5min 全局表）+ 台数（按 P 数反推）
关键参数：UTC+8 边界（BJT T 日 = UTC (T-1) 16:00 ~ T 16:00）、区间起点 6/1 = 5/31 16:00 UTC
注意事项：
  - Daily 汇总表与 5min 表截止点可能不同（Daily 到 6/3，5min 到 6/4 中午），分段取数再相加，勿只用一张表
  - 采集中断（本例 6/4 13:45 后）导致"至今"实际不可查，如实告知可查范围（6/1~6/4 中午），不编造后续产量
  - 用户没说口径时极数/台数都展示，注明数据截止时间

# 案例5：判断哪些产线停产/未开机
问题：有没有停产或没开机的线？
查询类型：产线运行状态
时间粒度：最近 N 天
分析方式：汇总+对比

SQL 步骤：
  1. 先验证全库数据覆盖范围（判断是"采集中断"还是"个别线停产"）：
     -- 全部 14 条产线 Daily 表 first/last/count（UNION ALL）
     SELECT '{线}' AS line, first(ts), last(ts), count(*) FROM `quota_385318105131300357@project_ProductTypeAgg@project_Daily{线}ModelYield`
     -- 全部产线 5min 表 first/last（实时采集是否存活）
     SELECT '{线}' AS line, first(ts), last(ts) FROM `quota_385318105131300357@project_ProductTypeAgg@project_5mins{线}ModelYield`
  2. 若全库 last(ts) 停在同一天 → 全局采集中断，不能判断当前停产线，如实告知
  3. 若数据存活：查最近 N 天各线产量 SUM，SUM=0 或 NULL 的线=停产/未开机：
     SELECT '{线}' AS line, SUM(val) AS poles FROM `...project_Daily{线}ModelYield`
     WHERE ts >= '{T-N} 16:00:00' AND ts < '{T} 16:00:00'
  4. 交叉验证：5min 表最后 24h 台数 SUM 确认无产量线

单位：极数（Daily）/台数（5min）
关键参数：14条产线后缀 {47,49,50,67,M01~M09,M12}、UTC+8 边界
注意事项：
  - 判断"停产"前必须先验数据时间范围（Lesson 7）：全部产线数据同时截止 = 采集中断 ≠ 停产
  - 采集中断期间当前状态无法从数据库获知，需提示排查采集链路
  - 数据覆盖期内各线有产量即全部在运行，直接回答无停产线
  - 查"今天"：Daily 汇总表通常滞后——当天生产结束次日凌晨才写入。若 Daily 表 last(ts) 早于今天，
    先用 5min 实时表（SELECT COUNT(*) FROM `...5mins{线}ModelYield` WHERE ts >= '{T-1} 16:00:00' AND val > 0）；
    仍无记录则如实告知"当天数据尚未采集入库，无法判断"，不要断言停产

# 案例6：某系列型号最近是否有生产（全厂范围）
问题：NXBLE-32 那个系列最近有生产吗？
查询类型：型号/产量
时间粒度：最近窗口（数据覆盖期）
分析方式：汇总+存在性判断

SQL 步骤：
  1. 验证全厂每日产量表数据范围（判断覆盖窗口）：
     SELECT first(ts), last(ts), count(*) FROM `quota_385318105131300357@project_ProductTypeAgg@project_DailyOutputStatistics`
  2. 全厂每日极数按系列 UID 列表过滤（系列=多个型号）：
     SELECT instance_uid, ts, val FROM `quota_385318105131300357@project_ProductTypeAgg@project_DailyOutputStatistics`
     WHERE instance_uid IN ('{UID1}','{UID2}',...) AND val > 0 ORDER BY ts DESC
  3. 用 5min 全局表确认最新采集状态：SELECT instance_uid, last(ts) FROM `...project_5minusProductionStatistics` WHERE instance_uid IN (...) GROUP BY instance_uid
  4. 判断"系列停产" vs "全库采集中断"：对比全库 last(ts)（SELECT last(ts) FROM 5min 全局表）——全库同时截止 = 采集链路中断，如实告知数据范围，不编造截止后的状态
  5. 系列内逐型号比对：覆盖期内无任何记录（val>0 过滤后为空）的型号 = 未生产

单位：极数（Daily 与 5min 全局表均为极数）
关键参数：系列型号 UID 列表（从 dtx-model-map.md 的 ProductTypeAgg 实例列表提取，如 NXBLE-32 系列 = 4 个 2P 型号 C20/C25/C32/C40）
注意事项：
  - Daily 表 ts={T} 16:00 UTC = BJT T 日；5min 表 ts=UTC 实时，BJT=UTC+8h
  - 2P 型号台数 = 极数÷2；用户没明确口径时台数/极数都展示
  - 全库采集截止后（本例 6/4 之后）"最近是否生产"无法从数据库确认，须提示排查采集链路，不臆断停产
  - 5min 表末段可能存在 val=0 的占位记录，最后一个非零记录才是最后生产时刻

# 案例7：2P 与 3P 产量结构占比变化（按极数类别分组）
问题：2P 和 3P 的产量结构变化大吗？（全厂范围、某区间内）
查询类型：产量（极数/台数）
时间粒度：多日区间（按天展开）
分析方式：分组（按 P 数类别）+ 趋势对比

SQL 步骤：
  1. 全厂每日极数：SELECT instance_uid, ts, val FROM `quota_385318105131300357@project_ProductTypeAgg@project_DailyOutputStatistics`
     （ts={T} 16:00 UTC = BJT T 日，val=极数；该表只含在产型号，每天行数固定，停产日 val=0）
  2. 型号 UID → P 数类别：解析 dtx-model-map.md 的 ProductTypeAgg 实例列表，从型号名提取 \b[1-4]P\b
  3. 本地按天汇总各 P 数类别极数；台数 = 极数 ÷ P 数（2P÷2、3P÷3）
  4. 分段对比（如区间前/后半段）：分别汇总 2P+3P 内部占比（台数口径、极数口径各一）
  5. 验证单日异常放量：按 ts 过滤该日，列出具体型号明细，排除数据异常

单位：极数（极）+ 台数（台）
关键参数：区间边界（UTC+8）、P 数类别映射（来自 model-map 型号名）
注意事项：
  - 占比口径要统一：占全厂（含1P/4P） vs 占 2P+3P 内部，两者数值不同，回答时说明口径
  - 台数占比与极数占比不同（2P 台折算极数 ×2，3P ×3），两种口径都展示
  - 停产日（周末）无数据，按生产日对比，不把停产日算进均值
  - DailyOutputStatistics 行数固定（每天 N 行，停产日 val=0），不要用 count 判断覆盖，用 val>0 过滤
  - 单日放量需拉该日型号明细验证真实性（防止汇总口径异常）

# 案例8：某系列（按极数+特性过滤，如 4P D 系列）各产线产量对比
问题：4P 的 D 系列最近谁家做得多？
查询类型：产量
时间粒度：日（最近 N 天/覆盖期）
分析方式：分组（按产线）+ 系列过滤（UID 列表）

SQL 步骤：
  1. 先验证该系列 UID 列表在全局 Daily 表（project_DailyOutputStatistics）的 first/last/count
     WHERE instance_uid IN ('{系列UID列表}')，确定可查窗口；再查全局 5min 表 last(ts) 确认采集截止点
  2. 14 条产线 UNION ALL，每线各自 SUM：SELECT '{线}' AS line, SUM(val) FROM `...project_Daily{线}ModelYield`
     WHERE instance_uid IN ('{系列UID列表}') AND ts >= '{起点UTC}' AND ts < '{终点UTC}'
  3. 有产量的线再拉明细：SELECT instance_uid, ts, val ... WHERE val > 0 ORDER BY ts，翻译型号名

单位：极数（Daily 表）；台数 = 极数 ÷ P 数（4P ÷4）
关键参数：系列 UID 列表从 dtx-model-map.md ProductTypeAgg 实例列表提取（4P D 系列 = 8 个型号：D10/D16/D20/D25/D32/D40/D50/D63）、14 条产线后缀、UTC+8 边界
注意事项：
  - "谁家做得多"= 按产线分组比产量，先验全库采集截止点（本例 6/4 中午中断），数据截止日后不可查，如实告知窗口
  - 该系列可能只有个别线在生产（本例仅 M06 线），其余线 SUM=0 属正常，直接给出在产线与明细型号
  - 台数/极数口径：用户没说明时两口径都展示

# 案例9：全产线近期产量稳定性分析（哪条线忽高忽低）
问题：最近各条线产量稳定吗？有没有哪条忽高忽低？
查询类型：产量
时间粒度：日（最近 N 天，多日趋势）
分析方式：全产线对比 + 波动分析（CV/单日最大涨跌幅）

SQL 步骤：
  1. 先验数据范围：任一线 Daily 表 first(ts)/last(ts) + 全局 5min 表 last(ts)（判断采集截止点）
  2. 14 线 UNION ALL 逐日 SUM（Daily 表 GROUP BY ts，BJT 日边界）：
     SELECT '{线}' AS line, ts, SUM(val) FROM `...project_Daily{线}ModelYield` WHERE ts >= '{起点UTC}' AND ts <= '{终点UTC}' GROUP BY ts
  3. 本地分析：剔除周末停产日（全线 0）与首日/周六半天爬坡日，只统计完整生产日；
     计算各线日均/最小/最大/CV（变异系数），CV 高者即波动大
  4. 相邻完整生产日之间最大单日涨跌幅，识别"忽高忽低"线；最后日如 Daily 无行（汇总未生成），
     用 5min 极数表补当日部分：SELECT SUM(val) FROM `...project_5mins{线}ExtremeNumber`
     WHERE ts >= '{UTC起点}' AND ts <= '{5min last}'（注意与 5min 台数表 ModelYield 区分）
  5. 输出：最稳/最不稳产线、典型波动线逐日序列、全厂共性（如周一爬坡）

单位：极数（Daily 与 5min ExtremeNumber 均为极数）
关键参数：14 条产线后缀、UTC+8 边界、完整生产日过滤（周末 0 不参与统计）
注意事项：
  - 采集截止后无法判断"现在"的实际生产，如实告知可查窗口
  - 首日（Daily 表 first(ts) 那天）与周六（周五夜班跨天尾段）数值偏低，属半天数据，勿当异常
  - "连续几天 0 后突然恢复"（如 M08）是开机爬坡，不是随机波动，需业务解读区分
  - 周一普遍偏低（周末后爬坡）是全厂共性，勿误判为单线异常

# 案例10：某月全厂总产值
问题：6月全厂产值多少
查询类型：产值
时间粒度：月
分析方式：汇总

SQL 步骤：
  1. 先查月度汇总表覆盖范围，确认当月是否有月度记录：
     SELECT first(ts), last(ts), count(*) FROM `quota_385318105131300357@project_OverallStatisticalModel@project_MonthlyOutputValue`
     （ts=月末最后一天 16:00 UTC，val=当月产值，单位元；无当月记录 = 月度汇总未生成）
  2. 无月度记录时，用每日全厂产值表按 UTC 边界 SUM 当月数据：
     SELECT SUM(val) AS total FROM `quota_385318105131300357@project_ProductTypeAgg@project_DailyOutputValue`
     WHERE ts >= '{T-1月最后一天} 16:00:00' AND ts < '{T月最后一天} 16:00:00'
     （每行 ts={T} 16:00 UTC 代表 BJT T 日，val=该日全厂产值，单位元）
  3. 逐日明细：GROUP BY ts ORDER BY ts（同上区间）
  4. 数据完整性验证：Daily 全厂表（650行/线）与 OverallStatisticalModel DailyOutputValue（14行=14天）、5min 表（project_5minusOutputValue）的 last(ts) 是否覆盖目标月；分产线表（project_Daily{线}OutputValue）范围与全厂表一致

单位：元
关键参数：目标月份 {T}、UTC 边界（BJ T月 = UTC 上月最后一天 16:00 ~ 本月最后一天 16:00）
注意事项：
  - 月度表（MonthlyOutputValue）与每日表（DailyOutputValue）ts 语义不同：Monthly ts=月末 16:00 UTC=当月；Daily ts={T} 16:00 UTC=BJT T 日
  - ProductTypeAgg 版与 OverallStatisticalModel 版 DailyOutputValue 数值口径可能不一致（97型号汇总 vs 全厂汇总），同日值会有差异，需注明数据来源
  - 某月无当月数据时，先验证全部产值表 last(ts) 判断是"月度汇总未生成"还是"采集中断"，如实告知用户可查范围（如仅 1~4 日），不编造全月数字
  - 各表 last(ts) 截止状态属易变信息，不入案例库

# 案例11：哪个型号产值最高（全厂型号产值排行）
问题：哪个型号最赚钱？（产值最高）
查询类型：产值
时间粒度：多日区间（全量可用数据）
分析方式：汇总+排序

SQL 步骤：
  -- 1. 先验证每日产值表数据范围（project_TotalOutputValueNew 累计表是 2017 静态值，不可用）：
  SELECT first(ts), last(ts), count(*) FROM `quota_385318105131300357@project_ProductTypeAgg@project_DailyOutputValue`
  -- 2. 按型号 GROUP BY 汇总产值，取 TOP：
  SELECT instance_uid, SUM(val) AS total_value
  FROM `quota_385318105131300357@project_ProductTypeAgg@project_DailyOutputValue`
  WHERE ts >= '{起点UTC}' AND ts < '{终点UTC}'
  GROUP BY instance_uid ORDER BY total_value DESC LIMIT 10

单位：元
关键参数：全厂汇总表无产线后缀（project_DailyOutputValue）、instance_uid 经 dtx-model-map.md 翻译为型号名
注意事项：累计产值表 project_TotalOutputValueNew 是静态初始值（停在 2017 年），不可用，必须用每日产值表按区间 SUM；UTC+8 边界；返回空时先 first(ts)/last(ts) 验证数据范围；输出只给型号名+金额，禁止 UID

# 案例12：哪条产线产值最高（全产线产值排行）
问题：哪条线产值最高？
查询类型：产值
时间粒度：多日区间（覆盖期内全量）
分析方式：分组（按产线）+ 排序

SQL 步骤：
  1. 先验证产线级每日产值表数据范围（任选一条线即可，各线范围一致）：
     SELECT first(ts), last(ts), count(*) FROM `quota_385318105131300357@project_ProductTypeAgg@project_Daily47OutputValue`
     （ts={T} 16:00 UTC = BJT T 日，val=元；650 行 = 13天 × 50 在产型号）
  2. 14 条产线 UNION ALL 各自 SUM（覆盖区间全量）：
     SELECT '{线}' AS line, SUM(val) AS v FROM `...project_Daily{线}OutputValue`
     WHERE ts >= '{起点UTC}' AND ts < '{终点UTC}'
     （14 线后缀：47, 49, 50, 67, M01~M09, M12）
  3. 按 SUM 降序排序取 TOP，金额换算为万元输出

单位：元（换算万元）
关键参数：14 条产线后缀、UTC+8 边界、产线级表 project_Daily{线}OutputValue
注意事项：输出只给产线名+金额，禁止 UID/表名/UTC 时间戳；注意个别线产值可能完全相同（如 M01 与 47 线），属数据特征，如实呈现；返回空时先 first(ts)/last(ts) 验证范围

# 案例13：某产线当前正在生产哪个型号（实时状态）
问题：47线现在正在生产哪个型号？
查询类型：型号（实时）
时间粒度：当前时刻
分析方式：实时状态判断

SQL 步骤：
  1. 最直接：设备级电表「生产设备型号」测点，产线最新值即当前在产型号：
     SELECT ts, val FROM `quota_sub_{产线ElectricMeter_3P实例ID}@maktx` ORDER BY ts DESC LIMIT 3
     （maktx=型号原始文本如 "NXB-63 1P C32"；PEM=数字映射，同查询可交叉验证）
  2. 产量交叉验证：5min 台数表最后非零窗口：
     SELECT last(ts), instance_uid, val FROM `...project_5mins{线}ModelYield` WHERE val > 0 GROUP BY instance_uid, val ORDER BY last(ts) DESC LIMIT 10
  3. 判断采集存活：5min 表 last(ts) 是否到今天（SELECT last(ts), first(ts), count(*) FROM 5min 表）；
     last(ts) 停在旧日期 = 全库采集中断，实时状态不可查，如实告知（如 6/4 后中断，最后在产型号即 maktx 最后值）
  4. 注意：采集中断前最后时段窗口可能全为 0（产量先停、型号字段后停），以 maktx 最后值 + 最后非零产量窗口综合判断

单位：台数（5min ModelYield）；型号名（maktx 直接是文本）
关键参数：产线→ElectricMeter_3P 实例ID（47线=2008337903968911360，全部见 dtx-model-map.md 模型1）、UTC 转 BJT（+8h）
注意事项：
  - maktx/PEM 是测点类，只在采集存活时更新；两者同时截止 = 采集中断
  - 回答给型号名即可，不出现 maktx/PEM/UID/UTC 时间戳

# 案例14：全厂万极能耗（每生产一万极用多少电）
问题：每生产一万极要多少电？
查询类型：能耗效率（单耗）
时间粒度：多日区间（全量可用数据）
分析方式：汇总+逐日校验

SQL 步骤：
  1. 验证两张全局 Daily 表数据范围（须同范围才可比）：
     SELECT first(ts), last(ts), count(*) FROM `quota_385318105131300357@project_ProductTypeAgg@project_DayilyModelEnergy`（⚠️ 拼写 Dayily，全局每日总能耗，kWh）
     SELECT first(ts), last(ts), count(*) FROM `quota_385318105131300357@project_ProductTypeAgg@project_DailyOutputStatistics`（全局每日总极数）
     （两表 ts={T} 16:00 UTC = BJT T 日；last(ts) 那行要包含进区间，边界用 ts < last+1天）
  2. 区间 SUM：能耗表 SUM(val)，极数表 SUM(val)，同 UTC 边界
  3. 万极能耗 = 总能耗 / 总极数 × 10000（kWh/万极）
  4. 逐日校验：GROUP BY ts 两表分别 SUM，逐日算单耗，识别异常日（能耗 3 倍于平时但产量正常 → 提示数据质量，给出剔除异常日后的稳健值）
  5. 备用静态表 project_TotalEnergyPerOfYields（万极能耗）时间戳停在 2017-12-31，是静态初始值，不可用，必须实测计算
  6. 万元产值能耗（kWh/万元）同法：能耗 SUM ÷ 产值 SUM × 10000，产值用 ProductTypeAgg 全局每日产值表 project_DailyOutputValue（每行 ts={T}16:00 UTC=BJT T 日，val=元，SUM 后=全厂产值）；
     另有现成指标可交叉验证：OverallStatisticalModel 的 project_TotalEnergyPerUnitOfTenThousandOutputValue（累计万元产值能耗，5min 实时更新非静态，最新值即累计单耗）与
     project_DailyEnergyPerUnitOfTenThousandOutputValue（每日万元产值能耗，周末停产日无行）

单位：能耗 kWh、极数 极、单耗 kWh/万极（万元产值能耗单位 kWh/万元）
关键参数：全局无产线后缀表、Dayily 拼写陷阱、UTC+8 边界（含 last(ts) 当天）
注意事项：回答只给单耗结论（如"每生产一万极约 XX 度电"），注明是全厂平均口径；能耗异常日需提示数据质量并给剔除后的区间

# 案例15：两条产线效率对比
问题：M01号产线和M03号产线 哪个效率更高
查询类型：能耗效率
时间粒度：多日区间
分析方式：对比

SQL 步骤：
  1. 确认两线数据范围：分别查 `SELECT first(ts), last(ts), count(*) FROM` 产线每日能耗表和产线 Daily 产量表，取交集区间
  2. 产线每日能耗（ElectricMeter_3P 设备级表，单位 kWh）：
     SELECT ts, val FROM `quota_sub_{产线实例ID}@public_dailyEnergyConsumption`
     WHERE ts >= '{起点}' AND ts < '{终点}' ORDER BY ts
     （M01线=2008337903167799296，M03线=2008337904031825920，其余查 dtx-model-map.md 模型1）
  3. 产线每日产量-极数（ProductTypeAgg Daily 表按天 SUM）：
     SELECT ts, SUM(val) AS daily_poles FROM `quota_385318105131300357@project_ProductTypeAgg@project_Daily{线}ModelYield`
     WHERE ts >= '{起点}' AND ts < '{终点}' GROUP BY ts ORDER BY ts
  4. 产线每日产值-元（可选，同样按天 SUM）：`project_Daily{线}OutputValue`
  5. 效率指标：万极能耗(kWh/万极) = 总能耗/总极数*10000；万元产值能耗 = 总能耗/总产值*10000。越低越高效

单位：能耗 kWh、极数 极、产值 元
关键参数：两条产线名+对应 ElectricMeter_3P 实例ID、统一 UTC+8 区间
注意事项：
  - 两条线数据覆盖范围可能不同（本例产量到 6/3、能耗到 6/4），取交集，避免不可比
  - 能耗出现连续 0 值但产量非零（采集缺失/补记）时，如实提示数据质量，并用全期总额兜底验证结论稳健性
  - 现成的累计单耗指标表（project_TotalEnergyPerOfYields{线} 等）时间戳停在 2017 年，是静态初始值，不可用于当前对比，必须用实测能耗/产量计算
  - 产品结构不同（M01 以 1P 为主、M03 以 2P 为主）时，台数不可直接对比，用极数和产值口径

# 案例16：某产线每小时用电高峰时段分析
问题：47线每小时用电高峰是几点？
查询类型：能耗
时间粒度：多日区间（小时粒度）
分析方式：分组（按小时）+ 趋势

SQL 步骤：
  1. 定位产线每小时用能表（设备级）：`quota_sub_{ElectricMeter_3P实例ID}@public_hourEnergyConsumption`（47线实例=2008337903968911360），单位 kWh，ts 为 UTC 整点（每小时一条）
  2. 验证数据范围：SELECT first(ts), last(ts), count(*) FROM 该表
  3. 拉全量原始数据（ts, val），本地换算北京时间（UTC+8h）后按小时聚合。⚠️ TDengine 无 HOUR() 函数，不能直接在 SQL 里按小时分组（TIMETRUNCATE 分组也会报 "Not a GROUP BY expression"），须 REST API 拉数据 + Python 处理
  4. 剔除停产/半生产日：先按 BJT 日期聚合日用电，仅保留满负荷日（日用电 > 180 kWh 的完整生产日），避免周末停产日/夜班跨天日（日用电 50-70 kWh）污染均值
  5. 满负荷日内按 BJT 小时求平均，排序取 TOP；另算全局单小时峰值和各天各自高峰小时，验证高峰是否稳定

单位：kWh（每小时用能）
关键参数：产线 ElectricMeter_3P 实例ID（47线=2008337903968911360，其余查 dtx-model-map.md 模型1）、UTC+8 边界
注意事项：
  - ts 语义：该表 ts 为 UTC 整点，BJT 小时 = (UTC 小时 + 8) % 24，须先换算再聚合，直接用 UTC 小时会整体错位 8 小时
  - 连续生产线的用电曲线通常全天平稳（峰谷差 <20%），"高峰"结论要基于满负荷日均值，且要检查各天高峰小时是否稳定；单点峰值日可能只是个别波动
  - 傍晚低谷（如 17:00-20:00 略低）可能对应交接班/保养时段，可作业务解读
  - 数据截止到采集中断日时，如实告知用户数据范围，不推断中断后的高峰模式

# 案例17：全产线夜间/非生产时段能耗排查（哪条线半夜还在耗电）
问题：最近有没有哪条线半夜还在耗电？（非生产时段有能耗）
查询类型：能耗（产线级 hourly）
时间粒度：多日区间（小时粒度）
分析方式：全产线对比 + 夜间时段聚合

SQL 步骤：
  1. 产线级每小时用能表：`quota_sub_{ElectricMeter_3P实例ID}@public_hourEnergyConsumption`
     （14 条产线 ID 见 dtx-model-map.md 模型1，单位 kWh，ts 为 UTC 整点 = BJT 该小时，每小时一条）
  2. 14 线 UNION ALL 一次性拉全量（ORDER BY line, ts），REST API --data-binary @file 方式
  3. 本地 Python：ts 转 BJT，按 BJT 日期聚合「全天能耗」与「半夜(0-6点)能耗」对比
  4. 夜间时段判据：
     - 工作日 0-6 点全线有 ~6-11 kWh/h 稳定能耗 = 24h 连续生产/夜班，属正常，不是异常耗电
     - 停产日（如周日）全线 0 = 停产即断电，无待机耗电
     - 周六凌晨 0-5 点能耗 = 周五夜班跨天尾段，正常
  5. 异常值甄别：单小时巨值（正常 6-9 kWh/h 却出现 400-4100 kWh）→ 用 Daily 能耗表
     （`quota_sub_{ID}@public_dailyEnergyConsumption`，ts={T}16:00 UTC=BJT T 日）交叉验证；
     若 Daily 同日一致 + 该日白天全 0 + 单小时集中 = 计量补录/跳变，非真实用电，需提示核查采集链路

单位：kWh（每小时/每日）
关键参数：14 条产线 ElectricMeter_3P 实例ID、UTC+8（hourly ts=UTC 整点，BJT 小时=UTC+8；Daily ts={T}16:00 UTC=BJT T 日）
注意事项：
  - TDengine 无 HOUR() 函数，须拉原始数据本地按 BJT 小时聚合（同案例16）
  - 数据范围先验 first(ts)/last(ts)，注意个别线（如 M06）数据起始日可能晚于其他线，缺失期无法判断
  - 5min 表与 hourly/Daily 能耗表口径不同，勿混用
  - 停产日判断要先确认是"全线停产"（如周日）还是"个别线数据缺失/采集中断"

# 案例18：全产线能耗-产量对比（哪条线电用得多产量还少）
问题：哪条线电用得多但产量还少？（能耗高产量低）
查询类型：能耗+产量双指标
时间粒度：多日区间（13天，BJT 5/22~6/3）
分析方式：14线分组对比 + 单耗排序

SQL 步骤：
  1. 先验范围：任一线能耗表（quota_sub_{ID}@public_dailyEnergyConsumption）与产线 Daily 产量表（project_Daily{线}ModelYield）first/last，取交集窗口（本例产量止于 BJT 6/3，能耗止于 6/4，交集 13 天）
  2. 14 线 UNION ALL 能耗 SUM（设备级每日能耗表，ts 窗口统一）：
     SELECT '{线}' AS line, count(*) AS n, SUM(val) FROM `quota_sub_{ElectricMeter_3P实例ID}@public_dailyEnergyConsumption`
     WHERE ts >= '{起点UTC}' AND ts < '{终点UTC}'
  3. 14 线 UNION ALL 产量 SUM（极数，Daily 表按模型行求和）：
     SELECT '{线}' AS line, count(*), SUM(val) FROM `quota_385318105131300357@project_ProductTypeAgg@project_Daily{线}ModelYield`
     WHERE ts >= '{起点UTC}' AND ts < '{终点UTC}'
  4. 效率 = 能耗(kWh) / 极数 × 10000 = 万极耗电（度/万极），越高越"电多用少"；同时看能耗绝对排名与产量排名错位
  5. 异常甄别：某线能耗总量异常高（如 67线 13天 4959 度）时拉逐日明细——若多数生产日 val=0 + 单日巨值，再用小时表（public_hourEnergyConsumption）定位单小时跳变 → 计量补录/异常，剔除后重新排名（同案例17 夜间排查的甄别法）

单位：能耗 kWh、产量 极数、单耗 度/万极
关键参数：14 条产线 ElectricMeter_3P 实例ID（dtx-model-map.md 模型1）、14 线后缀、UTC+8 边界（Daily ts=(T-1)16:00 UTC=BJT T 日）
注意事项：
  - 67线是 CT 电表（project_ElectricMeter_3P_CT），其能耗链路曾出现单小时 4000+ 度跳变，总量不可直接采信，须先甄别再入排名
  - 能耗/产量两表覆盖窗口可能不同，取交集才可比
  - 周末停产日全线能耗 0 属正常，不影响横向对比（所有线同窗口）

# 案例19：全厂当前总功率（实时值）
问题：全厂现在的总功率多少？
查询类型：功率（实时）
时间粒度：当前时刻
分析方式：实时值

SQL 步骤：
  1. 全厂总有功功率（14电表全厂口径，W）：`quota_385318105131300357@project_proportionPower14@project_14powerMeterAdd`
     SELECT ts, val FROM 该表 ORDER BY ts DESC LIMIT 5
  2. 先验范围：SELECT first(ts), last(ts), count(*) FROM 该表（判断数据是否截止）
  3. 若 last(ts) 停在旧日期：交叉验证 14 条产线电表 P 测点（quota_sub_{实例ID}@P）的 last(ts)，
     全部同期截止 = 全库电表采集中断，当前功率不可查，如实告知，可给最后已知值（各线 P 之和 ≈ 汇总表值，交叉验证）
  4. 数据存活时直接给最新 val（W 换算 kW）

单位：W（换算 kW）
关键参数：14电表全厂口径（用户说"全厂"用 project_14powerMeterAdd，13 版少一条线）；产线 ElectricMeter_3P 实例ID 见 dtx-model-map.md 模型1
注意事项：
  - 汇总表与产线 P 测点同期截止 = 采集链路中断，不是停产，不编造当前值
  - 各线 P 之和与汇总表值应基本一致（同分钟差 <1%），可作交叉验证

# 案例20：某产线功率占全厂比例（虚拟总表 proportionPower 直接指标）
问题：M02线功率占全厂多少？
查询类型：功率占比（%）
时间粒度：区间（实时+均值）
分析方式：占比

SQL 步骤：
  1. 找现成占比指标：虚拟总表（proportionPower）有各线"功率占总功率比重"指标 project_proportion{线}，
     表名实测存在两个实例：`...@project_proportionPower13@project_proportion{线}`（1分钟粒度）与
     `...@project_proportionPower14@project_proportion{线}`（5分钟粒度）
  2. 先验数据范围：SELECT first(ts), last(ts), count(*) FROM `quota_385318105131300357@project_proportionPower14@project_proportion{线}`
  3. 最新占比：SELECT ts, val FROM 该表 ORDER BY ts DESC LIMIT 5
  4. 全期均值：SELECT AVG(val), MIN(val), MAX(val) FROM 该表 WHERE val > 0
  5. 交叉验证：M02线电能表 P（quota_sub_{M02实例ID}@P，W）÷ 全厂总有功功率
     （project_14powerMeterAdd=14线全口径 / project_13powerMeterAdd=13线口径，W）≈ 占比指标值
  6. 判断口径：model-map 模型2 官方"总有功功率"= project_14powerMeterAdd（14电表全厂）；
     13 版分母少一条线（可能为排除67线/CT表），占比略高；用户说"全厂"用 14 版

单位：%（功率占比，val=6.1 即 6.1%）；功率 W
关键参数：产线→proportion 编号（M02=02）、ElectricMeter_3P 实例ID（M02=2008337903360737280）
注意事项：
  - 占比是实时计算值，随产线启停波动大（生产期可在 0.1%~11% 波动），回答给"最近值+区间均值"
  - 两实例粒度不同（13版1min/14版5min），行数不同属正常，勿用行数判断哪个有数据
  - 数据范围先验（占比链路可能与产量链路同期截止），截止后不编造实时占比
  - 单位换算：P 表 val 单位 W（8259.2=8.26kW），总功率表同理

# 案例22：型号级万元产值能耗排行（成本结构分析）
问题：哪些型号耗电多产值少？（降本排产建议）
查询类型：能耗效率（型号级单耗）
时间粒度：多日区间（全量可用数据）
分析方式：分组（按型号）+ 排序 + 双指标交叉

SQL 步骤：
  1. 先验数据范围：型号级每日能耗表（project_DayilyModelEnergy）与每日产值表（project_DailyOutputValue）first(ts)/last(ts)，取同区间
  2. ⚠️ 先查产线级每日能耗（quota_sub_{实例ID}@public_dailyEnergyConsumption）逐日明细找计量异常日
     （如 7/13-14 三条线各出现 25万~28万 kWh 单日巨值，为计量跳变/补录，非真实用电），
     后续型号级查询用 ts NOT IN ('{异常日1}','{异常日2}') 排除，防止污染排行
  3. 型号能耗 TOP：SELECT instance_uid, SUM(val) AS e FROM `...project_DayilyModelEnergy`
     WHERE ts >= '{起点UTC}' AND ts < '{终点UTC}' AND ts NOT IN ('{异常日}') GROUP BY instance_uid ORDER BY e DESC LIMIT 25
  4. 型号产值 TOP：SELECT instance_uid, SUM(val) AS o FROM `...project_DailyOutputValue`
     WHERE ts >= '{起点UTC}' AND ts < '{终点UTC}' AND ts NOT IN ('{异常日}') GROUP BY instance_uid ORDER BY o DESC LIMIT 25
  5. 万元产值能耗 = 能耗 SUM ÷ 产值 SUM × 1e4（kWh/万元），对两 TOP 列表交叉计算；
     按 P 数类别（1P/2P/3P/4P，从型号名提取）归并求类别均值，识别高耗低值类别
  6. 全厂分月单耗趋势（6/7/8月）：能耗 SUM ÷ 产量 SUM × 1e4（万极能耗）与 ÷ 产值 SUM × 1e4（万元产值能耗）

单位：能耗 kWh、产值 元（万元换算）、单耗 kWh/万元
关键参数：全局无产线后缀表（Dayily 拼写陷阱同案例14）、instance_uid 翻译为型号名（dtx-model-map.md 模型4）、UTC+8 边界
注意事项：
  - 型号级能耗表也可能含计量异常日，先用产线级 Daily 表定位异常日再排除（教训：17/18 案例的 67 线跳变是同一类问题）
  - 1P 型号万元产值能耗通常数倍于 3P/4P（生产同样产值，1P 占线时间长、单耗高）——这是排产结构优化信号，
    但只给数据结论，不越权下经营决策
  - 7月产量↑而能耗持平（万极能耗 43.5→33.5）是满负荷摊薄固定能耗效应，可作排产集中化的论据
  - 气表近期链路上线后（如仅最近 10 天数据），用气量只能按覆盖期给，不给全月推算
