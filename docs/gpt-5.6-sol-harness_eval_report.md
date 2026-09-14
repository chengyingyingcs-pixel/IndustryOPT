# Codex + GPT-5.6-Sol Harness 评测报告

## 1. 实验概述

本报告总结 Codex CLI harness 调用 `gpt-5.6-sol`、`reasoning_effort=high` 完成 IndustryOPT 数学优化建模任务的结果。评测使用带 annotations 的中文输入，模型为每个问题类生成一份通用 Pyomo `model.py`，随后在全部数据实例上独立构建并求解。生成阶段已完成，求解阶段复用了已有代码，未重新调用模型生成代码。

评测批次：`gpt-5.6-sol-high-withann-pass1`。生成时间为 2026-09-11，评测结果目录为：

`/public/chengyingying/project/industry_mathopt_dataset/eval_results/harness_sweep/evals/gpt-5.6-sol-high-withann-pass1-timeout7200-sequential`

## 2. 测试设置

| 项目 | 设置 |
| --- | --- |
| 模型 | `gpt-5.6-sol` |
| 推理强度 | `high` |
| Harness | Codex CLI harness；隔离工作区；允许命令执行和文件修改 |
| 输入语言 | 中文；`with_annotations=true` |
| 问题类 | 19 个 |
| 生成次数 | 每个问题类 1 次，共 19 份通用 `model.py` |
| 建模接口 | Pyomo `ConcreteModel`，函数 `build(data: dict)` |
| 单个求解器时限 | 7200 秒（2 小时） |
| 求解器轮换 | 每个实例最多 3 个候选求解器 |
| 实例级硬超时 | `7200 × 3 + 60 = 21660` 秒，约 6 小时 |
| MIP 相对/绝对 gap | `1e-6` / `1e-6` |
| HiGHS | `threads=1`，相对/绝对 gap 均为 `1e-6` |
| 求解器顺序 | LP/MILP：`appsi_highs` → `scip`；含整数非线性：`scip` → `couenne`；连续 QP/NLP：`ipopt` → `couenne` |
| 求解子进程内存上限 | 10 GB 地址空间 |

在补测批次中，复用了本批次已生成的 `model.py`，没有重新调用模型生成代码；补测使用已安装的 SCIP 10.0.3、IPOPT 3.14.19 和 Couenne 0.5.8，单实例求解时限仍为 7200 秒。

## 3. 评测判定标准

只有参考解 `status == optimal` 的实例进入准确率分母。模型代码成功构建模型、求解器返回可用解、解通过可行性检查，且模型目标值与参考最优目标值满足以下混合容差时记为通过：

`|a-b| <= max(1e-6, 1e-6 × max(|a|, |b|))`

参考解不是最优，或运行环境没有适用求解器的实例记为 `unjudgeable`，不计入通过率分母，也不记为模型失败。模型可运行但超时、内存错误或目标值不匹配的实例记为失败。

## 4. 总体结果

| 指标 | 数量 |
| --- | ---: |
| 实例总数 | 146 |
| 可判定实例 | 131 |
| 通过 | 118 |
| 失败 | 13 |
| 不可判定 | 15 |
| 准确率 | **118/131 = 90.0763%** |

分母关系为 `146 = 131 + 15`，可判定实例满足 `131 = 118 + 13`。因此 90.0763% 是在可判定实例上的求解准确率，而不是按全部 146 个实例计算的比例。相较初始批次，补测新增了 17 个可判定实例：其中 8 个通过、9 个失败。

## 5. 分问题结果

| 问题类 | 总实例 | 可判定 | 通过 | 失败 | 不可判定 | 准确率 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Auto-Vehicle-ActiveSuspensionBalance | 8 | 8 | 0 | 8 | 0 | 0% |
| CBG-Camera-JPEGQuantizationTable | 8 | 8 | 8 | 0 | 0 | 100% |
| CBG-Camera-VideoStabilization-L1 | 8 | 8 | 8 | 0 | 0 | 100% |
| CBG-Camera-VideoStabilization-L2 | 8 | 8 | 8 | 0 | 0 | 100% |
| CBG-Communication-RailCellHandover | 5 | 5 | 5 | 0 | 0 | 100% |
| CBG-HarmonyOS-CriticalThreadOpt | 5 | 5 | 5 | 0 | 0 | 100% |
| CBG-HarmonyOS-MemoryEviction | 8 | 8 | 8 | 0 | 0 | 100% |
| Compute-CAE-SparseLA-LDLSymmetricPivoting | 6 | 6 | 3 | 3 | 0 | 50% |
| Compute-CAE-SparseLA-LUPivotReordering | 6 | 6 | 6 | 0 | 0 | 100% |
| Compute-Cluster-CrossPodLoadBalancing | 10 | 3 | 3 | 0 | 7 | 100% |
| Compute-LLM-MoEExpertLoadBalance | 5 | 4 | 2 | 2 | 1 | 50% |
| Compute-TBE-MemoryAllocation | 8 | 5 | 5 | 0 | 3 | 100% |
| Energy-Microgrid-SizingAndOperation | 10 | 6 | 6 | 0 | 4 | 100% |
| Energy-VPP-DayAheadAdjustableLoadScheduling | 15 | 15 | 15 | 0 | 0 | 100% |
| ICT-DataCom-LoadBalancing-SingleAndMultitimestamp | 8 | 8 | 8 | 0 | 0 | 100% |
| ICT-DataCom-NetworkPlanning-CapacityExpansion | 8 | 8 | 8 | 0 | 0 | 100% |
| ICT-OpticalNetwork-NetworkPlanning-LinkProtection | 5 | 5 | 5 | 0 | 0 | 100% |
| ICT-OpticalNetwork-NetworkPlanning-PathProtection | 5 | 5 | 5 | 0 | 0 | 100% |
| ICT-Wireless-ChannelEstimation-SparseDelay | 10 | 10 | 10 | 0 | 0 | 100% |

补测后，`CBG-Camera-VideoStabilization-L2` 的 8 个实例因补齐 IPOPT/Couenne 而全部可判定且通过；`Auto-Vehicle-ActiveSuspensionBalance` 的 8 个实例也变为可判定，但均未通过当前严格可行性检查。除悬架、LDL 和 MoE 三个问题类外，其余可判定问题类均为 100% 通过。总体失败由 LDL 的 3 个失败、悬架的 8 个失败和 MoE 的 2 个失败构成。

## 6. 失败明细与原因

### 6.1 `Auto-Vehicle-ActiveSuspensionBalance`

补齐 IPOPT 后，8 个实例均能在约 7--23 秒内返回 `optimal`，且目标值全部与参考值匹配。然而，IPOPT 返回的 `command_force` 在力限幅边界附近出现数值越界，最大越界量约为 `1.8e-6`--`3.7e-5`，超过评测器 `1e-6` 的边界容差；因此 8 个实例均被记为失败。

此外，生成模型使用 `command_force[wheel,time]`，参考模型使用 `f_cmd[index,time]`，变量命名和索引形式不同，无法进行参考模型交叉可行性验证。对 `inst_001` 和 `inst_004` 使用更严格的 IPOPT 参数（`tol=1e-10`、`constr_viol_tol=1e-10`、`acceptable_tol=1e-10`）后，最大边界违约为 0，目标值分别与参考值一致。这表明当前 8 个失败主要由求解精度和交叉验证兼容性造成，不能直接解释为悬架数学公式错误。

### 6.2 `Compute-CAE-SparseLA-LDLSymmetricPivoting`

- `inst_004`：HiGHS 先达到 7200 秒，目标值 `2452.440519862483`；随后 SCIP 运行 7200 秒，得到更好的可行解 `2546.283112011178`，但仍低于参考目标值 `2549.463458035061`，SCIP gap 约 `0.12%`。
- `inst_005`：HiGHS 先达到 7200 秒，目标值 `3839.9310429386082`；随后 SCIP 运行 7200 秒，得到 `3976.1047625999363`，仍低于参考目标值 `3977.8965220691643`；SCIP 最终报告 gap 为 `0.05%`（按 primal/dual bound 计算约 `0.045%`）。
- `inst_006`：HiGHS 报 `MemoryError`；随后 SCIP 运行约 7200 秒，得到可行解 `7512.441248588728`，参考目标值为 `7647.513894469273`，SCIP gap 约 `1.80%`。

该问题的前 3 个实例通过，后 3 个实例均已由 SCIP 返回可行解，但在 2 小时内未达到参考最优目标值。失败主要表现为大规模分支定界搜索未收敛，不能仅凭当前结果归因于模型公式错误。

### 6.3 `Compute-LLM-MoEExpertLoadBalance`

- `inst_002`：补装求解器后可以求解，但生成模型缺少参考模型的 `p` 变量族，无法进行参考模型交叉验证；参考解状态为 `optimal`，因此按当前判定规则记为失败。
- `inst_004`：HiGHS 报 `MemoryError`，SCIP 在对称性预处理阶段也报 `Insufficient memory`，没有返回可行解；参考解状态为 `optimal`，因此记为失败。
- `inst_005`：SCIP 报 `ApplicationError`，Couenne 运行约 7314 秒后硬超时；参考解状态为 `heuristic`，因此仍属于不可判定，不进入准确率分母。

## 7. 不可判定实例

15 个不可判定实例不进入准确率分母，构成为：

| 原因 | 问题类/实例 | 数量 |
| --- | --- | ---: |
| 参考解不是最优 | `Compute-LLM-MoEExpertLoadBalance/inst_005`（`heuristic`；补测时 SCIP/Couenne 仍未返回可用解） | 1 |
| 参考解不是最优 | `Compute-Cluster-CrossPodLoadBalancing`（`feasible`） | 7 |
| 参考解不是最优 | `Compute-TBE-MemoryAllocation`（`feasible`） | 3 |
| 参考解不是最优 | `Energy-Microgrid-SizingAndOperation`（`feasible`/`heuristic`） | 4 |
| **合计** |  | **15** |

补测后，所有不可判定实例均因参考解不是 `optimal` 而不进入分母；求解器安装问题已不再是这批结果的主要不可判定原因。它们反映的是基准答案质量限制，不应与模型失败混合统计。

## 8. 结论

在合并初始批次和补测结果后，Codex + `gpt-5.6-sol`（`reasoning_effort=high`）在 131 个可判定实例上通过 118 个，实例级准确率为 **90.0763%**。模型在大多数 LP/MILP、网络规划、能源调度和通信优化任务上稳定得到与参考解一致的目标值；补齐非线性求解器后，L2 视频稳定任务的 8 个实例全部通过。

当前 13 个失败集中在三个问题类：悬架 8 个、LDL 3 个、MoE 2 个。悬架实例目标值全部匹配，但严格边界检查受到 IPOPT 数值误差以及变量命名不兼容影响；LDL 实例由 SCIP 返回可行解但在 2 小时内未收敛；MoE `inst_002` 存在变量族不一致，`inst_004` 受到内存限制。后续应分别收紧或合理化连续求解器的数值校验、改进参考模型交叉映射，并为大规模 MILP 增加内存或采用更强的求解配置。

## 9. 结果与复现信息

- 生成元数据：`/public/chengyingying/project/industry_mathopt_dataset/eval_results/harness_sweep/generations/gpt-5.6-sol-high-withann-pass1/generation.json`
- 生成代码：上述目录下各问题类的 `model.py`
- 评测结果：`/public/chengyingying/project/industry_mathopt_dataset/eval_results/harness_sweep/evals/gpt-5.6-sol-high-withann-pass1-timeout7200-sequential/*/run1/result.json`
- 补测结果：`/public/chengyingying/project/industry_mathopt_dataset/eval_results/harness_sweep/reruns/gpt-5.6-sol-high-withann-pass1-scip-couenne-timeout7200-20260913/`
- 评测日志：同目录各问题类下的 `run1/eval_stdout.log`
- 评测实现：`/public/chengyingying/project/industry_mathopt_dataset/tools/eval/run_eval.py`

本轮求解使用现成生成代码，可通过 `--from-code` 复跑；若仅调整求解器、资源或 `--timeout`，无需重新生成模型代码。
