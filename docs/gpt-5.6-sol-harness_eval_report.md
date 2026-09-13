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

## 3. 评测判定标准

只有参考解 `status == optimal` 的实例进入准确率分母。模型代码成功构建模型、求解器返回可用解、解通过可行性检查，且模型目标值与参考最优目标值满足以下混合容差时记为通过：

`|a-b| <= max(1e-6, 1e-6 × max(|a|, |b|))`

参考解不是最优，或运行环境没有适用求解器的实例记为 `unjudgeable`，不计入通过率分母，也不记为模型失败。模型可运行但超时、内存错误或目标值不匹配的实例记为失败。

## 4. 总体结果

| 指标 | 数量 |
| --- | ---: |
| 实例总数 | 146 |
| 可判定实例 | 114 |
| 通过 | 110 |
| 失败 | 4 |
| 不可判定 | 32 |
| 准确率 | **110/114 = 96.4912%** |

分母关系为 `146 = 114 + 32`，可判定实例满足 `114 = 110 + 4`。因此 96.4912% 是在可判定实例上的求解准确率，而不是按全部 146 个实例计算的比例。

## 5. 分问题结果

| 问题类 | 总实例 | 可判定 | 通过 | 失败 | 不可判定 | 准确率 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Auto-Vehicle-ActiveSuspensionBalance | 8 | 0 | 0 | 0 | 8 | - |
| CBG-Camera-JPEGQuantizationTable | 8 | 8 | 8 | 0 | 0 | 100% |
| CBG-Camera-VideoStabilization-L1 | 8 | 8 | 8 | 0 | 0 | 100% |
| CBG-Camera-VideoStabilization-L2 | 8 | 0 | 0 | 0 | 8 | - |
| CBG-Communication-RailCellHandover | 5 | 5 | 5 | 0 | 0 | 100% |
| CBG-HarmonyOS-CriticalThreadOpt | 5 | 5 | 5 | 0 | 0 | 100% |
| CBG-HarmonyOS-MemoryEviction | 8 | 8 | 8 | 0 | 0 | 100% |
| Compute-CAE-SparseLA-LDLSymmetricPivoting | 6 | 6 | 3 | 3 | 0 | 50% |
| Compute-CAE-SparseLA-LUPivotReordering | 6 | 6 | 6 | 0 | 0 | 100% |
| Compute-Cluster-CrossPodLoadBalancing | 10 | 3 | 3 | 0 | 7 | 100% |
| Compute-LLM-MoEExpertLoadBalance | 5 | 3 | 2 | 1 | 2 | 66.67% |
| Compute-TBE-MemoryAllocation | 8 | 5 | 5 | 0 | 3 | 100% |
| Energy-Microgrid-SizingAndOperation | 10 | 6 | 6 | 0 | 4 | 100% |
| Energy-VPP-DayAheadAdjustableLoadScheduling | 15 | 15 | 15 | 0 | 0 | 100% |
| ICT-DataCom-LoadBalancing-SingleAndMultitimestamp | 8 | 8 | 8 | 0 | 0 | 100% |
| ICT-DataCom-NetworkPlanning-CapacityExpansion | 8 | 8 | 8 | 0 | 0 | 100% |
| ICT-OpticalNetwork-NetworkPlanning-LinkProtection | 5 | 5 | 5 | 0 | 0 | 100% |
| ICT-OpticalNetwork-NetworkPlanning-PathProtection | 5 | 5 | 5 | 0 | 0 | 100% |
| ICT-Wireless-ChannelEstimation-SparseDelay | 10 | 10 | 10 | 0 | 0 | 100% |

除两个存在求解失败的问题类外，所有可判定问题类均为 100% 通过。加权总体准确率受 `LDLSymmetricPivoting` 的 3 个失败和 `MoEExpertLoadBalance` 的 1 个失败影响。

## 6. 失败明细与原因

### 6.1 `Compute-CAE-SparseLA-LDLSymmetricPivoting`

- `inst_004`：HiGHS 达到 `TerminationCondition.maxTimeLimit`，约 7201.29 秒；返回可行解目标值 `2452.440519862483`，参考目标值 `2549.463458035061`，目标值不匹配。
- `inst_005`：HiGHS 达到 `maxTimeLimit`，约 7201.56 秒；返回可行解目标值 `3839.9310429386082`，参考目标值 `3977.8965220691643`，目标值不匹配。
- `inst_006`：HiGHS 报 `MemoryError`；备用 SCIP 未安装，因而没有得到可用解。

该问题的前 3 个实例通过，后 3 个实例受到大规模求解资源限制影响。前两例的失败不能直接归因于模型公式错误，因为求解器返回了可行但未达到参考最优值的解；需要更强求解器、更多内存或更长时限进一步区分模型错误与搜索未完成。

### 6.2 `Compute-LLM-MoEExpertLoadBalance`

- `inst_004`：HiGHS 报 `MemoryError`；备用 SCIP 未安装；参考解状态为 `optimal`，因此该实例属于可判定失败。

## 7. 不可判定实例

32 个不可判定实例不进入准确率分母，构成为：

| 原因 | 问题类/实例 | 数量 |
| --- | --- | ---: |
| 缺少适用求解器 | `Auto-Vehicle-ActiveSuspensionBalance`（需 IPOPT/Couenne） | 8 |
| 缺少适用求解器 | `CBG-Camera-VideoStabilization-L2`（需 IPOPT/Couenne） | 8 |
| 缺少适用求解器 | `Compute-LLM-MoEExpertLoadBalance` 的 `inst_002`、`inst_005`（需 SCIP/Couenne） | 2 |
| 参考解不是最优 | `Compute-Cluster-CrossPodLoadBalancing`（`feasible`） | 7 |
| 参考解不是最优 | `Compute-TBE-MemoryAllocation`（`feasible`） | 3 |
| 参考解不是最优 | `Energy-Microgrid-SizingAndOperation`（`feasible`/`heuristic`） | 4 |
| **合计** |  | **32** |

其中 18 个实例受求解器安装状况影响，14 个实例因参考解为可行解或启发式解而没有可靠的最优性标准。它们反映的是评测基础设施或基准质量限制，不应与模型失败混合统计。

## 8. 结论

在当前可判定集合上，Codex + `gpt-5.6-sol`（`reasoning_effort=high`）达到 **96.49%** 的实例级准确率，110 个通过实例中覆盖了 17 个问题类。模型在大多数 LP/MILP、网络规划、能源调度和通信优化任务上稳定得到与参考解一致的目标值。

剩余 4 个失败全部集中在两个计算类问题，且均与大规模求解阶段有关：2 个超时目标不匹配，2 个 HiGHS 内存错误。后续优先事项是补齐 SCIP/IPOPT/Couenne 等求解器并增加可用内存，再复跑这 4 个失败实例；同时保持 `unjudgeable` 与模型失败分开报告。若复跑仍失败，再针对 LDL/MoE 模型代码进行数学约束和数据索引审查。

## 9. 结果与复现信息

- 生成元数据：`/public/chengyingying/project/industry_mathopt_dataset/eval_results/harness_sweep/generations/gpt-5.6-sol-high-withann-pass1/generation.json`
- 生成代码：上述目录下各问题类的 `model.py`
- 评测结果：`/public/chengyingying/project/industry_mathopt_dataset/eval_results/harness_sweep/evals/gpt-5.6-sol-high-withann-pass1-timeout7200-sequential/*/run1/result.json`
- 评测日志：同目录各问题类下的 `run1/eval_stdout.log`
- 评测实现：`/public/chengyingying/project/industry_mathopt_dataset/tools/eval/run_eval.py`

本轮求解使用现成生成代码，可通过 `--from-code` 复跑；若仅调整求解器、资源或 `--timeout`，无需重新生成模型代码。
