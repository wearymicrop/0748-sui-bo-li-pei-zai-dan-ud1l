# 碎玻璃配载单深度登记

料场配载员按磅单和实验抽样复算干料，再根据车次配比和分级证据签单。

## 功能模块

| 模块 | 使用者动作 | 入口 | 核心文件 | 测试 |
|---|---|---|---|---|
| M1 磅单采集 | 检查净重、重复或冲突单号 | `GET /api/weighing/{source}` | `app/modules/m1_weighing/service.py` | `tests/test_weighing.py` |
| M2 含水抽样 | 复核上下层及加权含水 | `GET /api/moisture/{source}` | `app/modules/m2_moisture/service.py` | `tests/test_moisture.py` |
| M3 色级判定 | 查基色与最不利杂质测值 | `GET /api/grading/{source}` | `app/modules/m3_grading/service.py` | `tests/test_grading.py` |
| M4 干重折算 | 核对逐批湿、干、水重 | `GET /api/drymass/{source}` | `app/modules/m4_drymass/fold.py` | `tests/test_drymass.py` |
| M5 目标配载 | 看每车分装片段、预算与欠装 | `GET /api/loading/{source}` | `app/modules/m5_loading/allocator.py` | `tests/test_loading.py` |
| M6 装车对账 | 检查湿干双账与分装连续性 | `GET /api/reconcile/{source}` | `app/modules/m6_reconcile/verify_load.py` | `tests/test_reconcile.py` |
| M7 签单凭证 | 签单、重跑与导出证据 | `POST /api/runs` | `app/modules/m7_archive/signoff.py` `app/modules/m7_archive/service.py` | `tests/test_archive.py` `tests/test_bundle.py` |
| M8 批次结算 | 暂估登记、质量扣减重算、正式确认与版本对比 | `POST /api/settlements` | `app/modules/m8_settlement/service.py` `app/modules/m8_settlement/statement.py` | `tests/test_settlement.py` `tests/test_settlement_api.py` |

## 陷阱登记

| TRAP | 现象 | 朴素实现 | 处理 | 位置 | 测试 |
|---|---|---|---|---|---|
| TRAP-06 | 重量带千分位及全角数字 | 数值解析失败 | 先归一到数值再转克 | `app/modules/m1_weighing/mass.py` | `tests/test_weighing.py::test_thousands_and_subgram` |
| TRAP-07 | 下层含水以 N/A 回传 | 当作零水重 | 留下缺样并记待折干湿重 | `app/modules/m2_moisture/service.py` | `tests/test_moisture.py::test_missing_position_is_not_zero` |
| TRAP-08 | 磅单前导零 | 数字化损失 | 单号保持字符 | `app/modules/m1_weighing/service.py` | `tests/test_weighing.py::test_zero_net_isolated_and_identifier_kept` |
| TRAP-10 | 代表样加权保留小数 | 提前截断比率 | 只在最终水重按克舍入 | `app/modules/m4_drymass/fold.py` | `tests/test_drymass.py::test_fraction_precision_carried_to_final_gram` |
| TRAP-14 | 同编号重量不同 | 后写覆盖 | 同号全部隔离 | `app/modules/m1_weighing/service.py` | `tests/test_weighing.py::test_conflicting_ticket_rejects_both_not_just_later` |
| TRAP-15 | 含水混用小数、百分比与 ppm | 倍率错用 | 按单位归一 | `app/modules/m2_moisture/ratio.py` | `tests/test_moisture.py::test_mixed_unit_converted_same_ratio` |
| TRAP-19 | 同批多个杂质测值 | 最后值覆盖或平均 | 按最不利值控制 | `app/modules/m3_grading/service.py` | `tests/test_grading.py::test_worst_case_impurity_across_valid_samples` |
| TRAP-22 | 白、透明等颜色别名 | 资格错判 | 固定归一色类 | `app/modules/m3_grading/classes.py` | `tests/test_grading.py::test_aliases_normalize_transparent_to_white` |
| TRAP-23 | 同批分给两车 | 重复占用交界 | 连续左闭右开 | `app/modules/m5_loading/allocator.py` | `tests/test_loading.py::test_one_lot_contiguous_across_vehicles` |
| TRAP-24 | 杂质预算剩半克 | 多配一克超限 | 整除取下界并核账 | `app/modules/m5_loading/allocator.py` | `tests/test_loading.py::test_budget_limits_exact_last_gram` |
| TRAP-25 | 磅单冲突批次被部分采信 | 用未隔离磅单估出应付 | 同批任一隔离磅单即整批 `BLOCKED`，不计价不进应付 | `app/modules/m8_settlement/service.py` | `tests/test_settlement.py::test_ticket_conflict_blocks_whole_lot_from_payable` |
| TRAP-26 | 分级证据后到，车队当天要数 | 缺分级也按色级价放款 | 降级为湿料暂估价并按比例暂扣，应付保持 0 | `app/modules/m8_settlement/service.py` | `tests/test_settlement.py::test_missing_grade_keeps_dry_basis_but_holds_quality_risk` |
| TRAP-27 | 分级测值变化 | 沿用上版质量扣减 | 异色+杂质 ppm 重算扣减，毛额不变只挤压应付 | `app/modules/m8_settlement/service.py` | `tests/test_settlement.py::test_quality_deduction_recalculates_when_grade_evidence_changes` |
| TRAP-28 | 同批重复点击登记 | 生成多张结算单 | 同证据 `reused`、新证据升版，批次维度唯一且单事务归并 | `app/store.py` `app/modules/m8_settlement/statement.py` | `tests/test_settlement_api.py::test_concurrent_register_does_not_duplicate` |
| TRAP-29 | 正式确认时点到缺证/冲突 | 失败写入覆盖旧版 | 确认失败抛 409，旧版结算单与历史完整保留 | `app/modules/m8_settlement/register.py` | `tests/test_settlement_api.py::test_confirm_failure_keeps_old_statement` |

## 对账

脏样例的 6930 千克有效湿重折为 6444.900 千克干重和 485.100 千克水重。装载 3797.050 千克，余料 2647.850 千克。另有 1080 千克待折干湿重。
