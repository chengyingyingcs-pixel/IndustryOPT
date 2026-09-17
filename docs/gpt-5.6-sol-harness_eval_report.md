# Codex + GPT-5.6-Sol Harness 评测报告

## 1. 实验概述

本报告总结 Codex CLI harness 调用 `gpt-5.6-sol`、`reasoning_effort=high` 完成 IndustryOPT 数学优化建模任务的结果。评测使用带 annotations 的中文输入，模型为每个问题类生成一份通用 Pyomo 候选 `model.py`，随后在全部数据实例上独立构建并求解。生成阶段已完成，求解阶段复用了已有候选代码，未重新调用模型生成代码。本文所称“候选 `model.py`”均指 Codex 的被测输出，不是数据集自带的参考模型 `domains/<问题类>/code/model.py`。第 1--9 节描述 with-ann 基线，第 10 节单独报告严格 no-ann 消融及两组对比。

评测批次：`gpt-5.6-sol-high-withann-pass1`。生成时间为 2026-09-11，评测结果目录为：

`/public/chengyingying/project/industry_mathopt_dataset/eval_results/harness_sweep/evals/gpt-5.6-sol-high-withann-pass1-timeout7200-sequential`

## 2. 测试设置

| 项目 | 设置 |
| --- | --- |
| 模型 | `gpt-5.6-sol` |
| 推理强度 | `high` |
| Harness | Codex CLI harness；每个问题类使用独立工作目录；允许在其中执行命令和修改候选代码 |
| 输入语言 | 中文；`with_annotations=true` |
| 问题类 | 19 个 |
| 生成次数 | 每个问题类 1 次，共 19 份通用候选 `model.py` |
| 建模接口 | Pyomo `ConcreteModel`，函数 `build(data: dict)` |
| 单个求解器时限 | 7200 秒（2 小时） |
| 求解器轮换 | 每类模型配置 2 个候选求解器；首选证明最优即停止，否则继续第二个 |
| 实例级硬超时 | `7200 × 3 + 60 = 21660` 秒，约 6 小时；其中第 3 档是进程保护余量，不是当前实际候选数 |
| MIP 相对/绝对 gap | `1e-6` / `1e-6` |
| HiGHS | `threads=1`，相对/绝对 gap 均为 `1e-6` |
| 求解器顺序 | LP/MILP：`appsi_highs` → `scip`；含整数非线性：`scip` → `couenne`；连续 QP/NLP：`ipopt` → `couenne` |
| 求解子进程内存上限 | 10 GB 地址空间 |

当前 `solver_order()` 对每类模型均返回两个候选求解器。通常只运行首选求解器；若首选未安装、报错、没有返回可行解，或在时限内未证明最优，才继续运行第二个。两个求解器各自拥有完整的 7200 秒时限，因此正常轮换的求解器累计上限约为 4 小时。外层 worker 的 21660 秒硬超时仍按 `MAX_SOLVERS_PER_INSTANCE=3` 计算，额外一档只用于防止子进程异常挂死并为实现留出安全余量，不能解释为每个实例实际配置了三个求解器。

在补测批次中，复用了本批次已生成的候选 `model.py`，没有重新调用模型生成代码；补测使用已安装的 SCIP 10.0.3、IPOPT 3.14.19 和 Couenne 0.5.8，单实例求解时限仍为 7200 秒。

### 2.1 生成建模代码的提示词

模型生成阶段由 Codex CLI harness 为每个问题类建立独立工作区，并分别调用一次模型。所有问题类使用同一条英文提示词；其中 Python 解释器路径已经展开后的原文如下：

```text
You are being evaluated as a Codex modeling harness.

Work only in the current workspace. Do not inspect parent directories, absolute paths,
environment variables, network resources, hidden reference models, or reference solutions.
Do not modify task files or validate_model.py.

Read statement.md, annotations.md when present, data_README.md, and sample_data/. Implement
a general Pyomo model for every instance of this problem in model.py. The required API is:

    def build(data: dict) -> pyomo.environ.ConcreteModel

Use only Python's standard library and pyomo.environ. Do not invoke a solver inside build().
Do not hard-code values from the sample instance. Multi-file input is keyed by filename stem,
and CSV rows are dictionaries of strings. Use actual identifiers from the data instead of
assuming consecutive integer indices.

Iterate with this command until syntax, import, data parsing, construction, and structural
validation pass:

    /public/chengyingying/conda_envs/inferopt-py311/bin/python validate_model.py

Before finishing, inspect model.py for Pyomo reserved component names, invalid indexing,
empty extrema, and constraints that accidentally evaluate to a Python bool. Your final
response should briefly report completion; model.py is the evaluated artifact.
```

提示词本身不内联题面和数据，而是要求 Codex 在工作区读取文件。本报告对应的 `with_annotations=true` 批次为每个问题类提供：`statement.md`（来自 `nl/statement.md`）、`annotations.md`（来自 `nl/annotations.md`）、`data_README.md`（来自 `data/README.md`）、第一个实例的完整 JSON/CSV/MTX 文件（位于 `sample_data/`），以及通用的 `validate_model.py`。提示词要求模型反复运行该校验器，直到语法、导入、数据解析、模型构建和结构检查均通过。

#### 工作区位置与隔离边界

每个问题类的 Codex 工作区位于以下路径，其中 `<问题类>` 替换为数据集问题类名称：

```text
/public/chengyingying/project/industry_mathopt_dataset/eval_results/harness_sweep/generations/gpt-5.6-sol-high-withann-pass1/<问题类>/workspace/
```

例如，主动悬架问题使用：

```text
/public/chengyingying/project/industry_mathopt_dataset/eval_results/harness_sweep/generations/gpt-5.6-sol-high-withann-pass1/Auto-Vehicle-ActiveSuspensionBalance/workspace/
```

该目录虽然位于 `industry_mathopt_dataset` 仓库树下的 `eval_results/` 中，但与原始数据集目录 `domains/<问题类>/` 是两个不同目录。Harness 先把允许使用的题面、annotations、数据说明和第一个实例复制到工作区，Codex 的当前工作目录通过 `-C <workspace>` 指向该处；候选代码也只在工作区内生成。因此，本实验实现了**工作目录和输入材料层面的隔离**，Codex 看到的是经过筛选的副本，而不是直接在原始 `domains/` 目录中工作。

需要说明的是，这一批正式生成因受限沙箱曾出现 Linux namespace 创建失败，最终使用 Codex CLI 的 `danger-full-access` 文件系统权限运行。因此上述隔离不是操作系统权限强制的安全沙箱：理论上进程仍有能力访问工作区以外的路径，越界限制主要由提示词明确规定，并由 `events.jsonl` 审计。对本批 19 个问题类的工具事件复核未发现打开 `domains/`、参考 `code/model.py` 或 `solution/*.json` 内容的命令；工作区外的显式绝对路径用于调用指定 Python 解释器。不过，9 个问题类的会话运行过 `git status` 或包含该命令的检查，它们能够向上发现外层仓库并显示部分文件路径及状态，说明本批并未做到对原始仓库完全不可感知。故本报告将其表述为“独立工作目录/输入材料隔离”，不将其表述为“文件系统硬隔离”或“严格闭卷沙箱”。

工作区不提供 `formulation/model.md`、数据集参考模型 `domains/<问题类>/code/model.py`、`solution/*.json` 或其他实例的数据。提示词还明确禁止查看父目录、绝对路径、环境变量、网络资源、隐藏参考模型和参考解，也禁止修改任务文件及校验器。Codex 可以在该独立工作区内查看给定文件、执行命令并迭代修改候选 `workspace/model.py`；校验通过后，harness 将它复制为该问题类生成目录下的候选 `model.py` 归档副本，后续批量求解评测使用该副本。数据集的 `domains/<问题类>/code/model.py` 是单独保存的标准参考实现，仅供参考解生成和交叉验证使用，不是 Codex 生成或修改的文件。终端回复只用于简要报告完成情况。每个问题类生成目录中的 `prompt.txt`、`events.jsonl`、`response.md` 和 `record.json` 分别保存了原始提示词、完整工具事件、最终回复和生成元数据，因而可以逐次审计生成过程。

### 2.2 工具调用与完整执行流程

从输入文件到最终判定分为 Codex 建模和外层 harness 求解两个阶段。需要特别说明：**Codex 会话本身不调用优化求解器**，提示词也明确禁止在 `build()` 内求解；HiGHS、SCIP、IPOPT 和 Couenne 均由 Codex 会话结束后的评测程序调用。因此，求解器运行不属于 `events.jsonl` 中的 Codex 工具调用。

1. **Harness 准备输入。** Harness 为每个问题类创建独立工作目录，复制 `statement.md`、`annotations.md`、`data_README.md`、第一个实例的 `sample_data/` 和 `validate_model.py`，然后以该目录作为 Codex CLI 的当前工作区并提交第 2.1 节所列提示词。
2. **Codex 使用命令执行工具读取和检查材料。** 实际事件记录中的工具类型为 `command_execution` 和 `file_change`。命令执行主要通过 Bash 调用 `pwd`、`rg`、`sed`、`ls`、`find`、`wc` 等工具，查看文件清单、题面、annotations、数据字段及样例规模；部分会话还用短 Python 程序检查 JSON/CSV/MTX 的结构、索引集合和数值范围。个别会话执行了 `git status` 或 `git diff`，其隔离影响见上一小节。
3. **Codex 使用文件修改工具生成候选代码。** Codex 新建并迭代修改工作区中的候选 `workspace/model.py`，实现 `build(data: dict)`、Pyomo 变量、目标和约束。该阶段只修改候选代码，不修改题面、数据、annotations 或 `validate_model.py`。
4. **Codex 调用本地 Python 做结构校验。** Codex 通过命令执行工具反复运行指定的 `python validate_model.py`；部分会话还运行 `python -m py_compile model.py` 或短 Python 自检脚本。校验覆盖语法和导入、样例数据解析、`ConcreteModel` 构建、目标数量、变量和约束规模、整数性及多项式次数等，但不在这里证明全量实例的最优目标正确。校验通过后，Codex 给出简短终端回复，harness 保存 `events.jsonl`、`response.md`、`record.json`、`validation.log`，并归档候选 `model.py`。
5. **外层评测程序加载全量实例并求解。** Harness 以 `run_eval.py --from-code <候选 model.py>` 启动评测。每个实例在独立 Python worker 子进程中读取完整数据、动态导入候选模块并调用 `build(data)`；程序根据模型的线性/非线性与连续/整数属性，按第 2 节表中的顺序通过 Pyomo 接口轮换调用 `appsi_highs`、`scip`、`ipopt` 或 `couenne`。每个求解器的时间上限为 7200 秒，worker 另受实例级硬超时和 10 GB 地址空间限制。
6. **评测程序验证并落盘结果。** 求解器返回后，评测程序把变量值重新代入候选模型，检查变量域、全部约束和目标值自洽性；若变量表示兼容，还会将解代入数据集参考模型做交叉可行性验证。最后将候选目标值与 `solution/<实例>.json` 中的参考最优目标按第 3 节容差比较，生成 `pass`、`fail` 或 `unjudgeable` 判定。逐实例求解日志、变量解和最终汇总分别保存在 `logs/<实例>.log`、`solutions/<实例>.json` 和 `result.json` 中。

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

### 5.1 各问题类的实例求解时间分布

下表统计每个实例在本报告最终结果口径下的**累计求解器运行时间**：若一个实例依次尝试多个求解器，则将 `solver_attempts[].seconds` 相加，而不是只取最后一个求解器的 `solve_seconds`；没有写入 `seconds` 的失败尝试不计入数值。因此单实例累计时间可能超过 7200 秒，例如 LDL 的部分实例先由 HiGHS 运行约 2 小时，再由 SCIP 运行约 2 小时。该指标不包含候选代码生成时间，也不包含 worker 启动、模型构建、解回代校验和参考目标比对的额外墙钟时间。P25、P50 和 P75 采用线性插值分位数；全部数值单位均为秒。

| 问题类 | 有计时/总实例 | 最小值 | P25 | P50（中位数） | P75 | 均值 | 最大值 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Auto-Vehicle-ActiveSuspensionBalance | 8/8 | 12.127 | 13.580 | 15.015 | 19.935 | 16.411 | 21.656 |
| CBG-Camera-JPEGQuantizationTable | 8/8 | 0.805 | 1.109 | 1.467 | 1.772 | 1.476 | 2.182 |
| CBG-Camera-VideoStabilization-L1 | 8/8 | 0.349 | 0.354 | 0.381 | 0.392 | 0.376 | 0.403 |
| CBG-Camera-VideoStabilization-L2 | 8/8 | 6.268 | 12.837 | 17.432 | 25.839 | 19.977 | 36.985 |
| CBG-Communication-RailCellHandover | 5/5 | 0.301 | 0.337 | 0.409 | 5.442 | 3.426 | 10.643 |
| CBG-HarmonyOS-CriticalThreadOpt | 5/5 | 0.297 | 0.298 | 0.303 | 0.319 | 0.316 | 0.362 |
| CBG-HarmonyOS-MemoryEviction | 8/8 | 0.279 | 0.304 | 0.317 | 0.324 | 0.313 | 0.335 |
| Compute-CAE-SparseLA-LDLSymmetricPivoting | 6/6 | 0.370 | 2.455 | 3604.573 | 12602.224 | 6002.540 | 14402.533 |
| Compute-CAE-SparseLA-LUPivotReordering | 6/6 | 0.352 | 0.355 | 0.366 | 0.381 | 0.396 | 0.551 |
| Compute-Cluster-CrossPodLoadBalancing | 10/10 | 0.790 | 2008.294 | 7200.545 | 7200.650 | 5068.852 | 7201.110 |
| Compute-LLM-MoEExpertLoadBalance | 4/5 | 0.371 | 0.380 | 0.440 | 1828.786 | 1828.726 | 7313.651 |
| Compute-TBE-MemoryAllocation | 8/8 | 0.821 | 1.208 | 236.578 | 7203.891 | 2761.701 | 7208.809 |
| Energy-Microgrid-SizingAndOperation | 10/10 | 4.582 | 38.808 | 136.381 | 5448.157 | 2226.792 | 7287.498 |
| Energy-VPP-DayAheadAdjustableLoadScheduling | 15/15 | 0.509 | 0.740 | 3.817 | 47.177 | 21.119 | 65.298 |
| ICT-DataCom-LoadBalancing-SingleAndMultitimestamp | 8/8 | 0.308 | 0.311 | 0.316 | 0.326 | 0.321 | 0.349 |
| ICT-DataCom-NetworkPlanning-CapacityExpansion | 8/8 | 0.311 | 0.806 | 1.384 | 8.615 | 5.041 | 16.892 |
| ICT-OpticalNetwork-NetworkPlanning-LinkProtection | 5/5 | 0.446 | 1.454 | 12.016 | 24.130 | 12.510 | 24.505 |
| ICT-OpticalNetwork-NetworkPlanning-PathProtection | 5/5 | 0.341 | 0.356 | 0.410 | 0.475 | 0.656 | 1.696 |
| ICT-Wireless-ChannelEstimation-SparseDelay | 10/10 | 0.987 | 8.216 | 23.822 | 47.288 | 61.459 | 256.908 |

共 145/146 个实例具有可恢复的求解器计时。唯一缺失的是 `Compute-LLM-MoEExpertLoadBalance/inst_004`：HiGHS 发生 `MemoryError`，SCIP 在对称性预处理阶段因内存不足退出，两次失败均未写入结构化的 solver seconds，因此不进入该类分位数计算。MoE `inst_002` 的 0.382 秒来自 Couenne 日志中的 `Total solve time`；LDL 前 3 个快速实例的 6.28、1.18 和 0.37 秒来自保留的 HiGHS `Timing` 日志。主批次复用缓存而未重新求解的五个快速问题类，采用其原始顺序运行记录中的 `solver_attempts[].seconds`；这些实例均在 11 秒内结束，原运行的 900 秒上限没有触发。

从中位数看，`CBG-HarmonyOS-CriticalThreadOpt` 最短，为 0.303 秒；`CBG-HarmonyOS-MemoryEviction`、`ICT-DataCom-LoadBalancing-SingleAndMultitimestamp`、`Compute-CAE-SparseLA-LUPivotReordering` 和 `CBG-Camera-VideoStabilization-L1` 的中位数也均低于 0.4 秒。最明显的长尾出现在 LDL、CrossPod、TBE 和 Microgrid：CrossPod 的中位数已接近单求解器 7200 秒时限，LDL 最大累计 14402.533 秒，对应两个求解器先后达到时限；因此这些类别的均值会被少数超时实例显著抬高，中位数和四分位数比均值更能描述其典型耗时。

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

- `inst_002`：补装求解器后 Couenne 返回了 `optimal` 状态，但生成解未通过自身模型的可行性检查。生成模型将均匀路由的 `p` 直接定义为表达式 `x/y`，不把 `p` 作为显式变量导出；求解结果中的 `w` 与由 `p=x/y` 和负载参数计算出的卡负载不一致，例如 `card_load_definition[1,1,1]` 的违反量约为 `20.1`。同时，生成目标值为 `6.5644106667`，参考目标值为 `48.5779766667`，二者明显不一致。因此，`p` 变量族缺失只是导致参考模型无法交叉验证的兼容性问题，实例失败的本质是求解返回结果与生成模型自身约束不一致（并伴随目标值错误）。
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
- 候选生成代码：上述生成元数据目录下各问题类的 `model.py`（由对应 `workspace/model.py` 校验后复制归档；不同于 `domains/<问题类>/code/model.py` 参考实现）
- 评测结果：`/public/chengyingying/project/industry_mathopt_dataset/eval_results/harness_sweep/evals/gpt-5.6-sol-high-withann-pass1-timeout7200-sequential/*/run1/result.json`
- 补测结果：`/public/chengyingying/project/industry_mathopt_dataset/eval_results/harness_sweep/reruns/gpt-5.6-sol-high-withann-pass1-scip-couenne-timeout7200-20260913/`
- 评测日志：同目录各问题类下的 `run1/eval_stdout.log`
- 评测实现：`/public/chengyingying/project/industry_mathopt_dataset/tools/eval/run_eval.py`

本轮求解使用现成候选代码，可通过 `--from-code` 复跑；若仅调整求解器、资源或 `--timeout`，无需重新生成候选模型代码。

## 10. `annotations` 严格消融对比

### 10.1 对照设计与统计口径

为衡量 `annotations.md` 对 Codex 建模结果的影响，另运行一组严格 no-ann 对照。对照组继续使用 `gpt-5.6-sol`、`reasoning_effort=high`，每个问题类独立生成一次候选代码；原始提示词与 with-ann 组逐字节一致，SHA-256 均为 `2262bea50ba45a2652d28e0a13be529f32fe6fcaa17be249dfe3723338c2ff4f`。对照工作区中的 `statement.md`、`data_README.md`、`sample_data/` 和 `validate_model.py` 也与 with-ann 组逐文件一致，19 个问题类的输入清单差异均为空；唯一有意删除的输入是 `annotations.md`。

两组均为每个问题类生成一份通用候选 `model.py`，再用于该类全部实例。no-ann 组沿用相同的求解器顺序、评测判据、10 GB 内存限制和单求解器 7200 秒时限。with-ann 数值采用本报告前文的最终合并口径，即主批次加第 6、7 节所述 SCIP/Couenne 补测；其中五个快速问题类复用了早期 900 秒上限下的缓存结果，但所有这些实例都在 11 秒内证明最优，时限差异没有实际触发。no-ann 批次从生成到求解于 2026-09-14 至 2026-09-16 连续完成，共覆盖 19 类、146 个实例。

严格批次生成时系统尚未安装 `jq`，且外层脚本第一次调用 `validate_model.py` 时未切换到对应工作区，导致最初的 `record.json` 为空、`validation.log` 记录错误路径。2026-09-17 已在不修改候选代码和求解结果的前提下修复元数据，并在各自工作区重新运行校验；19/19 份候选均通过结构校验。原始空记录和错误日志分别保留为 `record.pre_repair.json`、`generation.pre_repair.json` 和 `validation.pre_repair.log`，修复信息及时间恢复依据写入新 `record.json` 的 `repair` 字段。

### 10.2 总体结果

| 指标 | with annotations | strict no annotations | no-ann 相对变化 |
| --- | ---: | ---: | ---: |
| 实例总数 | 146 | 146 | 0 |
| 可判定实例 | 131 | 131 | 0 |
| 通过 | 118 | 115 | -3 |
| 失败 | 13 | 16 | +3 |
| 不可判定 | 15 | 15 | 0 |
| 可判定实例准确率 | **90.0763%** | **87.7863%** | **-2.2901 个百分点** |
| 全部实例通过比例 | 80.8219% | 78.7671% | -2.0548 个百分点 |

移除 annotations 后，可判定分母没有变化，准确率从 `118/131` 降至 `115/131`，净减少 3 个通过实例。15 个不可判定实例在两组中完全相同，仍由参考解不是 `optimal` 导致，不是 annotations 或求解环境造成。

### 10.3 分问题类对比

下表中的分母只包含参考解为 `optimal` 的可判定实例；“变化”是 no-ann 准确率减去 with-ann 准确率。

| 问题类 | with-ann 通过/可判定 | no-ann 通过/可判定 | 变化 |
| --- | ---: | ---: | ---: |
| Auto-Vehicle-ActiveSuspensionBalance | 0/8 | 0/8 | 0 |
| CBG-Camera-JPEGQuantizationTable | 8/8 | 8/8 | 0 |
| CBG-Camera-VideoStabilization-L1 | 8/8 | 8/8 | 0 |
| CBG-Camera-VideoStabilization-L2 | 8/8 | 8/8 | 0 |
| CBG-Communication-RailCellHandover | 5/5 | 5/5 | 0 |
| CBG-HarmonyOS-CriticalThreadOpt | 5/5 | 5/5 | 0 |
| CBG-HarmonyOS-MemoryEviction | 8/8 | 8/8 | 0 |
| Compute-CAE-SparseLA-LDLSymmetricPivoting | 3/6 | 6/6 | +50 个百分点 |
| Compute-CAE-SparseLA-LUPivotReordering | 6/6 | 0/6 | -100 个百分点 |
| Compute-Cluster-CrossPodLoadBalancing | 3/3 | 3/3 | 0 |
| Compute-LLM-MoEExpertLoadBalance | 2/4 | 2/4 | 0 |
| Compute-TBE-MemoryAllocation | 5/5 | 5/5 | 0 |
| Energy-Microgrid-SizingAndOperation | 6/6 | 6/6 | 0 |
| Energy-VPP-DayAheadAdjustableLoadScheduling | 15/15 | 15/15 | 0 |
| ICT-DataCom-LoadBalancing-SingleAndMultitimestamp | 8/8 | 8/8 | 0 |
| ICT-DataCom-NetworkPlanning-CapacityExpansion | 8/8 | 8/8 | 0 |
| ICT-OpticalNetwork-NetworkPlanning-LinkProtection | 5/5 | 5/5 | 0 |
| ICT-OpticalNetwork-NetworkPlanning-PathProtection | 5/5 | 5/5 | 0 |
| ICT-Wireless-ChannelEstimation-SparseDelay | 10/10 | 10/10 | 0 |

19 个问题类中有 17 个保持相同的类级通过数。净变化完全来自两个稀疏线性代数问题：LDL 增加 3 个通过实例，LU 减少 6 个通过实例。两组各有 16 个问题类在其可判定实例上达到 100%，但其中一个问题类发生了互换：with-ann 是 LU 全部通过，no-ann 则是 LDL 全部通过。

### 10.4 逐实例状态迁移

| with-ann \ no-ann | 通过 | 失败 | 不可判定 | 合计 |
| --- | ---: | ---: | ---: | ---: |
| 通过 | 112 | 6 | 0 | 118 |
| 失败 | 3 | 10 | 0 | 13 |
| 不可判定 | 0 | 0 | 15 | 15 |
| **合计** | **115** | **16** | **15** | **146** |

在 131 个可判定实例中，122 个判定一致，一致率为 93.1298%；9 个不一致实例包括 6 个 `pass -> fail` 和 3 个 `fail -> pass`。计入不可判定实例后，137/146 个实例状态一致，一致率为 93.8356%。全部 9 个状态变化都集中在 LDL 和 LU；不可判定状态没有发生迁移。

### 10.5 关键差异与原因

#### LDL：no-ann 模型更小，3 个长时限失败转为通过

with-ann 候选除了选择 $1\times1$/$2\times2$ pivot，还显式引入完整置换、位置变量和成对相邻约束；no-ann 候选识别出目标只依赖 pivot 划分，直接构造集合划分/匹配模型，省去了不影响目标值的排列变量。后三个大实例的差异如下，其中时间为同一实例内全部求解器尝试的累计时间。

| 实例 | with-ann 变量/约束 | with-ann 时间与结果 | no-ann 变量/约束 | no-ann 时间与结果 |
| --- | ---: | --- | ---: | --- |
| inst_004 | 22949 / 2680 | 14402.010 秒，失败 | 1265 / 147 | 0.324 秒，通过 |
| inst_005 | 56955 / 1573 | 14402.533 秒，失败 | 627 / 238 | 0.325 秒，通过 |
| inst_006 | 180453 / 8106 | 7202.866 秒，失败 | 4035 / 420 | 0.424 秒，通过 |

no-ann 候选在 6 个实例上均由 HiGHS 证明最优，目标值与参考值一致；with-ann 候选的后三个实例虽得到可行解，但未能在时限内收敛到参考最优值。这说明本次生成中 annotations 对“对称置换”语义的强调伴随了不必要的显式排序建模，扩大了模型规模。该现象是本次候选代码的具体结果，不能据此推断 annotations 必然使 LDL 建模变慢。

#### LU：6 个通过全部退化为模型加载失败

no-ann 候选的 `_matrix_file()` 明确拒绝绝对 `matrix_path`，而全量评测器向 `build(data)` 提供的是实例目录中矩阵文件的绝对路径，因此 6 个实例都在构建模型前抛出 `ValueError: matrix_path must be relative to the instance directory`。with-ann 候选接受绝对路径，6 个实例全部通过。

这一退化属于数据接口兼容错误，而不是 LU 指派模型的数学公式错误。轻量 `validate_model.py` 使用工作区内的相对样例路径，所以 no-ann 候选仍能通过生成阶段结构校验；这也说明仅用一个样例做相对路径校验不足以覆盖全量评测的数据装载方式。annotations 提到了 Matrix Market 文件和 `matrix_path`，但没有明确规定评测器会传入绝对路径，因此这 6 个差异不能完全解释为领域知识缺失，也可能包含独立生成的实现随机性。

#### 主动悬架：二元判定不变，但数学语义明显退化

两组主动悬架均为 0/8，但失败性质不同。with-ann 候选的 8 个目标值均与参考值匹配，只因 IPOPT 在力边界处产生约 `1.8e-6`--`3.7e-5` 的数值越界而未通过严格可行性检查。no-ann 候选把减振器阻尼写入路面力，使用 $k h + c\,\Delta h / \Delta t$，并使路面力与作动器力经过不一致的运动比折算；其 8 个目标值为参考值的约 162.1 倍至 `2.1261e8` 倍，属于模型公式错误。

对应 annotations 明确说明减振器阻尼等整车参数是本题不使用的干扰项，并要求路面弹簧力和作动器力采用一致的运动比折算。因此，annotations 在该问题上提供了实质性的正向语义约束；仅比较 `fail -> fail` 会完全掩盖这一收益。

#### MoE 与不可判定实例

MoE 在两组中均为 2 个通过、2 个失败、1 个不可判定，但失败机制并不完全相同。with-ann 的 `inst_002` 由 Couenne 返回“最优”后未通过候选模型自身约束检查；no-ann 的同一实例则由 SCIP 报错、Couenne 达到硬超时，未返回可行解。`inst_004` 两组都受内存或求解器错误影响。其余 15 个不可判定实例的参考状态及实例集合完全一致，不能用于衡量 annotations 对准确率的作用。

### 10.6 结论与解释边界

按最终实例级指标，移除 annotations 后准确率下降 **2.2901 个百分点**。但这一净值不能简单解释为“annotations 稳定贡献 2.29 个百分点”：负向变化集中在 LU 的一个候选代码接口错误，正向变化则来自 LDL 候选的模型精简；同时，主动悬架显示出未反映在通过率中的显著语义收益。更准确的结论是，annotations 的影响具有明显的问题依赖性：它能排除题面中的诱导参数和补足隐含业务规则，也可能使单次生成选择更复杂的等价建模方式。

此外，每个条件对每个问题类都只生成一次候选代码，19 对候选代码也全部不同。两批调用没有固定可复现随机种子，且生成日期不同，因此当前结果同时包含“是否提供 annotations”和模型生成随机性的影响。146 个实例也不是 146 次独立建模试验，而是由 19 份类级候选代码成组产生。若要估计 annotations 的稳定因果效应，应对每个问题类在两种条件下进行多次配对生成，并同时报告类级均值、方差和失败机制分布。

### 10.7 消融实验产物

- no-ann 生成元数据：`/public/chengyingying/project/industry_mathopt_dataset/eval_results/harness_sweep/strict_noann/gpt-5.6-sol-high-strict-noann-pass1-20260914-101020/generations/generation.json`
- no-ann 候选代码和生成审计记录：上述 `generations/<问题类>/` 下的 `model.py`、`events.jsonl`、`response.md`、`record.json` 和 `validation.log`
- no-ann 求解结果：`/public/chengyingying/project/industry_mathopt_dataset/eval_results/harness_sweep/strict_noann/gpt-5.6-sol-high-strict-noann-pass1-20260914-101020/evals/<问题类>/runs/<运行目录>/result.json`
- no-ann 主日志：`/public/chengyingying/project/industry_mathopt_dataset/eval_results/harness_sweep/strict_noann/gpt-5.6-sol-high-strict-noann-pass1-20260914-101020/strict_noann_harness.log`
- with-ann 主批次和补测结果路径见第 9 节；消融对比采用其合并后的最终判定，而不是未安装 SCIP/Couenne 时的早期结果。
