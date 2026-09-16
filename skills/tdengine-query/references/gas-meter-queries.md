# 气表（用气量）查询扩展笔记

补充案例21（单线近几天用气量）与模型6之外的两类场景。

## 全厂/全部产线用气量

全厂 14 条产线中，**仅 M02（2块）、M12（1块）、47线（2块）装有气表**，其余 11 条线无气表——用户问"全部产线用气量"时，无气表产线直接回复"未安装气表"，不是零用量。

整厂查询 = 5 块气表 daily 表 UNION ALL，按产线标签分组 SUM：

```sql
SELECT '{线}' AS line, SUM(val) AS total FROM (
  SELECT val FROM `quota_sub_{气表A}@project_dailyUsageNm3` WHERE ts >= '{起点UTC}' AND ts < '{终点UTC}'
  UNION ALL SELECT val FROM `quota_sub_{气表B}@project_dailyUsageNm3` WHERE ts >= '{起点UTC}' AND ts < '{终点UTC}'
  ...
) GROUP BY line
```

多表汇总在 SQL 层 SUM，禁止手算。气表实例 ID 见 dtx-model-map.md 模型6。

## 某具体日用气量 = 空时："采集中断" vs "当日零用量"的判别探针

当目标日查询为空时，用以下探针区分"采集已中断"与"当日确实零用量"：

1. **Daily 表判别**：`SELECT count(*) FROM 各气表 daily 表 WHERE ts >= '{目标日} 16:00:00'`
   - count=0 → 目标日 Daily 汇总行不存在 = 采集已止于前一业务日，非零用量。
2. **hourly 表交叉印证**：查 hourly 表 last(ts)，若也远早于目标日（如止于前一晚）→ 采集链路在该日中断。
3. 判为采集中断后，如实告知"该日无数据、非零用量"，并说明可查范围（截止到哪一天），不编造停产/零用量结论。

## device_key → 产线映射（2026-08 实测）

Flowmeter 超级表下子表使用 device_key（非 instance_uid）作为标识。查询结果的 device_key 需翻译为产线名：

| device_key | 对应产线 | instance_uid |
|---|---|---|
| `cybnewrtspznuuk` | M02线-气表1 | 2082375796692541441 |
| `cybnelfniyk2iux` | M02线-气表2 | 2082375796537352193 |
| `cybnesbizisdcus` | M12线-气表1 | 2082375796604461057 |
| `cybne6p7lhm8kvx` | 47线-气表1 | 2082375796466049024 |
| `cybne1wqdgssi8v` | 47线-气表2 | 2082375796361191424 |

**注意**：device_key 与 instance_uid 同时存在于 Tags 中，查询时用 `SELECT DISTINCT tbname, device_key, instance_uid` 可以获取完整映射关系。查询结果向用户展示时应翻译为产线名，禁止直接输出 device_key。

## ts 语义陷阱（易错）

气表 daily 表 `ts = {T} 16:00 UTC = BJT (T+1) 日 00:00`，代表 BJT **(T+1) 日全天**汇总（与产量/能耗 Daily 表同一句式）。

- 查询区间 `[BJT {T-1} = UTC {T-2}16:00, BJT {T} = UTC {T-1}16:00)` 内，区间**起点处**那条 `ts={T-2}16:00 UTC` 的行实际代表 BJT **{T-1}** 日，不是 {T-2} 日。
- 判断 BJT {T} 日有无数据，必须往后找 `ts = (T) 16:00 UTC` 的行是否存在（即 `ts >= '{T} 16:00:00'` 探针），**勿把区间首行的前一日常量误读为目标日**。

## 长 SQL 用程序化构造

手写 5 块气表 UNION ALL 极易出错（实测出现 `2026-08-087`、`3583:00:00`、`94864` 等字符手误，触发 `[0x127] Invalid timestamp format`）。用 execute_code 拼接片段、打印出干净 SQL 再执行，并在循环中断言每行都以正确 `end` 时间戳结尾（Step 2b 已述，气表多表场景同样适用）。