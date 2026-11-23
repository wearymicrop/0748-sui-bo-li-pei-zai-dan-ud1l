# 碎玻璃配载数据字典

| 输入段 | 字段 | 定义 |
|---|---|---|
| `batch` | 批次编号 | 字符串，保留前导零 |
| `tickets` | `ticket`、`lot`、`gross`、`tare`、`unit` | 单号唯一，重量单位 g、kg、t，最大 100 吨且精确到克，毛重必须大于皮重 |
| `moisture` | `lot`、`sample`、`position`、`mass`、`mass_unit`、`water`、`unit` | 批料内样号唯一，样重为 1 克至 30 千克，上层和下层均须有有效样 |
| `grades` | `lot`、`color`、`offcolor`、`impurity`、`unit` | 基色按白、绿、棕归并，同批有效样须颜色一致。杂质和异色各取最不利值 |
| `targets` | `target`、`colors`、`grades`、`mass`、`unit`、`max_impurity`、`impurity_unit`、`priority` | 车次标识唯一，按优先级由小到大执行，平级按输入顺序 |
| `contract` | `currency`、`wet_floor_price`、`grade_prices`（A/B/C）、`provisional_reserve_rate` | 结算合同；缺段时只出管线结果，不出计价结算单。单价为每千克金额，暂扣比例在 0 至 1 之间 |

比例必须带单位 `%`、`fraction` 或 `ppm`，支持精确到 ppm。样品含水上限 30%。各样按样重加权，按批料先四舍五入计水克数，余量全计干重。
异色不大于 3% 且杂质不大于 1% 为 A，异色不大于 10% 且杂质不大于 3% 为 B，其余为 C。色级缺证的干料留作余料。
每车仅考虑符合色级的批料，按杂质由低到高分配。高于预算的批料可借较纯材料的剩余预算配入，最多到整数克。
装载区间为 `[start_g,end_g)`，对每批按从零开始的连续范围切分。干重与水重均按克保存，界面按千克展示。配载供装车复核，司机及过磅操作由外部系统记录。
空磅单无湿重、空抽样全为待折干、空目标无装车指令。输入为 UTF-8 JSON，可带 BOM。

## 批次结算（M8）

供应商按接收批次结款，结算单按批料（lot）逐项裁决，金额以元计并四舍五入到分：

| 磅单证据 | 含水证据 | 分级证据 | 裁决 | 金额口径 |
|---|---|---|---|---|
| 存在冲突或隔离磅单（`TICKET_CONFLICT`、`NEGATIVE_NET`、`BAD_TICKET`） | 任意 | 任意 | `BLOCKED` 暂扣 | 冲突来源不计价、不进应付，仅登记冻结湿重 `blocked_wet_g` |
| 干净 | 齐 | 齐 | `READY` 可结算 | 干重 × 色级单价 − 质量扣减，进入应付 |
| 干净 | 齐 | 缺样或颜色冲突 | `PROVISIONAL` 可暂估 | 干重 × 湿料暂估价，按 `provisional_reserve_rate` 暂扣质量风险，应付为 0 |
| 干净 | 缺上下层代表样 | 任意 | `PROVISIONAL` 可暂估 | 湿重 × 湿料暂估价，同比例暂扣，应付为 0 |

- 质量扣减 = 毛额 ×（异色 ppm + 杂质 ppm）/ 10⁶；分级证据每次变化都随测值重算，毛额不变时只挤压应付。
- 色级降级（A/B/C）切换对应单价；暂估行统一用 `wet_floor_price`，不套用任何色级价。
- `payable_amount`（可支付/应付）、`provisional_amount`（当天可暂估）、`withheld_amount`（暂扣）三个口径互斥不重叠；暂估与暂扣均不进应付。
- 批次状态：任一批料 `BLOCKED` 则整单 `BLOCKED`；否则有 `PROVISIONAL` 为 `PROVISIONAL`；全部 `READY` 才可正式确认。
- 同批次只有一张结算单：同证据重试返回原版本（`reused`）；新证据递增版本并把旧版连同逐批料差异 `diff` 存入 `history`。
- 正式确认仅在整单 `READY` 时成功；缺证（`CONFIRM_INCOMPLETE`）或磅单冲突（`CONFIRM_BLOCKED`）一律 409 失败，旧版结算单原样保留，缺证与冲突来源不进入应付。确认后批次锁定，后续登记返回 `confirmed` 不产生新单。
