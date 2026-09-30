# GPT-5.6-Sol Harness With-Annotation 消融实验报告

状态：**全量实验已完成：19/19 个问题类、146/146 个实例均已评测**

生成批次 ID：`gpt-5.6-sol-high-withann-pass1-20260926-124302`

评测批次 ID：`gpt-5.6-sol-high-withann-pass1-20260926-124302-timeout7200-sequential-mem32`

实际启动时间：`2026-09-26T12:49:01Z`

最终完成时间：`2026-09-29T21:38:21Z`

首次流水线日志：`/public/chengyingying/project/industryopt_harness_workspaces/gpt-5.6-sol-high-withann-pass1-20260926-124302.pipeline.log`

续跑日志：`/public/chengyingying/project/industryopt_harness_workspaces/gpt-5.6-sol-high-withann-pass1-20260926-124302.eval-resume.log`

首次流水线在生成完成后于 `2026-09-27T02:08:22Z` 发现
`CBG-HarmonyOS-CriticalThreadOpt` 没有生成候选；该类已在同一 generation batch 内补生成，
于 `2026-09-27T02:12:07Z` 成功得到 `model.py`。随后于 `2026-09-27T02:12Z` 从原评测
batch 续跑，已复用此前完成的 5 个问题类结果，不重新求解这些实例。

对照报告：[`gpt-5.6-sol-harness_noann_report.md`](gpt-5.6-sol-harness_noann_report.md)

## 1. 实验目标

本实验测量向 `gpt-5.6-sol` 提供领域专家补充说明 `nl/annotations.md` 后，问题类级
`pass@1` 候选在 IndustryOPT 全部 19 个问题类、146 个实例上的求解质量变化。

实验沿用 no-annotation 报告中的当前配置。唯一有意改变的生成输入是：

1. 每个问题类的独立工作区增加一份 `annotations.md`，内容逐字复制自该类的
   `nl/annotations.md`；
2. 生成提示词将 `Read statement.md and data_README.md.` 改为
   `Read statement.md, annotations.md, and data_README.md.`。

除上述一份输入文件和提示词中的对应文件名外，模型、推理强度、候选数量、工作区隔离、
其余提示词、数据集、评测器、求解器顺序、时限、内存、gap、判定规则和统计口径均保持不变。
本实验不复用历史 with-annotation 候选或结果，也不向模型提供实例样例或本地校验器。

## 2. 唯一实验变量

| 项目 | No-Annotation 对照 | With-Annotation 实验 |
| --- | --- | --- |
| `statement.md` | 提供 | 提供，内容相同 |
| `data_README.md` | 提供 | 提供，内容相同 |
| `annotations.md` | 不提供 | 提供 |
| 提示词读取指令 | `Read statement.md and data_README.md.` | `Read statement.md, annotations.md, and data_README.md.` |
| 其他提示词文本 | 基准 | 逐字相同 |
| 实例样例、校验器、参考模型和参考解 | 均不提供 | 均不提供 |

启动前已只读检查：19/19 个问题类均存在非空的 `nl/annotations.md`。正式生成时已将
每份 annotation 的路径、字节数和 SHA-256 写入该问题类的 `input_inventory.json`，确保
没有错配、遗漏或使用 `annotations.en.md`。本实验固定使用 `nl/annotations.md`，不使用
英文变体。

## 3. 固定实验配置

| 项目 | 设置 |
| --- | --- |
| 数据集根目录 | `/public/chengyingying/project/industry_mathopt_dataset` |
| 当前数据集提交 | `eb3aa39e2422c52e5aff937577be74bd5e1104c1` |
| 问题范围 | `domains/` 下 19 个问题类，共 146 个实例 |
| 模型 | `gpt-5.6-sol` |
| 推理强度 | `high` |
| 生成采样 | 每个问题类独立生成 1 次，即问题类级 `pass@1` |
| 建模接口 | `build(data: dict) -> pyomo.environ.ConcreteModel` |
| Python | `/public/chengyingying/conda_envs/inferopt-py311/bin/python` |
| 本地校验器 | 不提供、不运行 `validate_model.py` |
| 单求解器时限 | 7200 秒 |
| 实例级保护时限 | `7200 * 3 + 60` 秒，由评测器执行 |
| 子进程地址空间上限 | 32 GiB |
| MIP gap | 相对和绝对 gap 均为 `1e-6` |
| LP/MILP 求解器顺序 | `appsi_highs` -> `scip` |
| 整数非线性求解器顺序 | `scip` -> `couenne` |
| 连续 QP/NLP 求解器顺序 | `ipopt` -> `couenne` |
| 评测器快照 | `tools/run_eval_gpt56_noann_rerun.py` |
| 评测器 SHA-256 | `d450a4c287804489e4a11da427c91e179bc6ffe76e63373be54839f8bcd77a0d` |
| 评测方案指纹 | `1939da46299a` |
| 启动时 harness SHA-256 | `9d35df23861c3d24513ae6b49b9117a42e7ed3e4b570498db3c91a4296fbe5bf` |

数据集工作树当时只有 `tools/eval/run_eval.py` 存在未提交修改；本实验没有修改或使用该文件，
而是使用上表列出的批次专用评测器快照。启动时已记录数据集提交、数据清单、评测器 SHA-256、
harness SHA-256、Codex CLI 版本和求解器版本。

## 4. 输入边界与隔离

每个问题类使用数据集目录之外的独立工作区：

```text
/public/chengyingying/project/industryopt_harness_workspaces/<BATCH_ID>/<问题类>/workspace/
```

工作区中只允许出现：

```text
statement.md       <- domains/<问题类>/nl/statement.md
annotations.md     <- domains/<问题类>/nl/annotations.md
data_README.md     <- domains/<问题类>/data/README.md
```

不得复制或提供：

- `sample_data/` 或任何实例数据；
- `validate_model.py` 或其他本地校验器；
- `formulation/model.md`；
- `code/model.py`；
- `solution/*.json`；
- 其他实例数据或原始仓库工作目录。

沿用 no-annotation 实验的路径隔离检查：工作区与数据集目录不能互为父子目录，工作区内不得
存在指向数据集的软链接、硬链接或 bind mount；`codex exec -C`、当前进程工作目录和
`--output-last-message` 均不得指向数据集源目录。仍使用 `danger-full-access` 运行 Codex CLI，
因此这是输入材料和工作目录隔离，不是操作系统强制的文件系统沙箱；完整保留
`events.jsonl` 供越界访问审计。

## 5. With-Annotation 生成提示词

实际使用的完整提示词如下。与 no-annotation 报告第 5 节的最新版提示词相比，唯一文本差异是
读取指令中增加 `annotations.md`。实际提示词 SHA-256 为
`1e9e15de45de2a152814da36a4ab7fca1a41abd8f0c577216699aacee5274862`；对应 no-annotation
提示词 SHA-256 为 `2b95913545f576620a532b17d08248f4788e45422f295451ed40f992a2f6f2a7`。

```text
You are being evaluated as a Codex modeling harness.

Work only in the current workspace. Do not inspect parent directories, absolute paths,
environment variables, network resources, hidden reference models, or reference solutions.
Do not modify the input files.

Read statement.md, annotations.md, and data_README.md. Implement a general Pyomo model for every instance of
this problem in model.py. The required API is:

    def build(data: dict) -> pyomo.environ.ConcreteModel

Use only Python's standard library and pyomo.environ. Do not invoke a solver inside build().
Do not hard-code values from any particular instance. When an instance has one JSON file,
build(data) receives its parsed JSON dictionary. If that JSON has matrix_path pointing to a
separate .mtx file, the loader resolves matrix_path against the instance directory and passes
the resulting absolute path; it does not put the matrix contents in data. During evaluation,
build(data) must open that path and parse the Matrix Market file to construct the model.
The workspace/absolute-path inspection restrictions above apply to code generation, not to
reading a path supplied in data at evaluation time. For instances with multiple JSON/CSV
files, data is keyed by filename stem; CSV rows are dictionaries of strings. Use actual
identifiers from the data instead of assuming consecutive integer indices.

Before finishing, inspect model.py for Pyomo reserved component names, invalid indexing,
empty extrema, and constraints that accidentally evaluate to a Python bool. No sample data
or local validation script is provided in this condition; reason from the statement and data
schema, and ensure that model.py is the evaluated artifact. Your final response should
briefly report completion.
```

归档的逐行差异为：

```diff
-Read statement.md and data_README.md. Implement a general Pyomo model for every instance of
+Read statement.md, annotations.md, and data_README.md. Implement a general Pyomo model for every instance of
```

## 6. 正式运行前完成的脚本修正

正式运行前已在 `tools/run_codex_harness.py` 中完成以下两处修正：

1. 根据 `with_annotations` 选择第 5 节提示词，并将实际文本及 SHA-256 写入
   `prompt.txt`、`record.json` 和 `generation.json`；提示词的其他行没有改变。
2. `withann-eval` 不传递 `--no-annotations`，使 19 份 `result.json` 的
   `with_annotations` 元数据均为 `true`。由于评测使用 `--from-code`，这项修正只影响实验
   标签和审计信息，不改变候选代码或求解过程。

同时增加并通过了启动前断言：with-ann 的 `input_inventory.json` 恰好包含
`statement.md`、`annotations.md`、`data_README.md`；generation record 的 stage 必须为
`with_annotations`；评测阶段必须拒绝读取 no-ann generation batch。除此之外不修改生成或
评测逻辑。

## 7. 生成、求解与归档方案

本次使用以下 UTC 时间戳批次，没有覆盖历史目录：

```text
BATCH_ID=gpt-5.6-sol-high-withann-pass1-20260926-124302
EVAL_BATCH_ID=gpt-5.6-sol-high-withann-pass1-20260926-124302-timeout7200-sequential-mem32
```

实际命令为：

```bash
/public/chengyingying/conda_envs/inferopt-py311/bin/python \
  tools/run_codex_harness.py withann \
  --batch-id gpt-5.6-sol-high-withann-pass1-20260926-124302

/public/chengyingying/conda_envs/inferopt-py311/bin/python \
  tools/run_codex_harness.py withann-eval \
  --batch-id gpt-5.6-sol-high-withann-pass1-20260926-124302 \
  --eval-batch-id gpt-5.6-sol-high-withann-pass1-20260926-124302-timeout7200-sequential-mem32 \
  --timeout 7200
```

生成阶段从零开始，为 19 个问题类分别调用一次 `codex exec`，不得复用或筛选历史候选。
19 份候选全部生成并完成输入审计后，才启动全量求解。若评测因外部原因中断，只允许在同一
评测批次中复用已经落盘的实例解继续执行；不得重新生成候选、挑选更好的第二份候选或将不同
generation batch 拼接为 `pass@1`。候选代码错误也应按失败保留，不能定向重新生成。

归档位置：

```text
生成：/public/chengyingying/project/industry_mathopt_dataset/eval_results/harness_sweep/generations/<BATCH_ID>/
评测：/public/chengyingying/project/industry_mathopt_dataset/eval_results/harness_sweep/evals/<EVAL_BATCH_ID>/
工作区：/public/chengyingying/project/industryopt_harness_workspaces/<BATCH_ID>/
```

每个问题类至少保留 `prompt.txt`、`prompt.sha256`、`input_inventory.json`、`events.jsonl`、
`response.md`、`codex_stderr.log`、`record.json`、候选 `model.py`、`eval_stdout.log`、
`eval_stderr.log`、逐实例日志、解文件和 `result.json`。

## 8. 判定与统计口径

完全沿用 no-annotation 最终报告的判定规则：

- 参考状态为 `optimal` 时，候选须成功构建、得到可用解、通过自身可行性检查，并使候选目标
  与参考最优目标满足 `1e-6` 绝对/相对混合容差；变量空间兼容时执行参考模型交叉检查。
- 参考状态不是 `optimal` 时仍纳入可判定分母。候选可行且目标严格优于参考或在容差内相等
  则通过；候选更差则失败。严格更优时记录
  `passed_by_better_than_nonoptimal_reference: true`。
- 目标方向不一致、缺少必要比较信息等情况按同一评测器规则记为失败或不可判定。
- `optimal` 参考下的超时、内存错误、模型不可行、目标不匹配和候选代码错误均记为失败。

最终统计直接汇总评测目录中的 19 份 `result.json`，不依据流水线控制台文本二次推断。

## 9. 最终实验结果

全量评测于 `2026-09-29T21:38:21Z` 完成。19 个问题类的 146 个实例全部进入可判定分母，
没有不可判定实例。

| 指标 | 数量 | 比例 |
| --- | ---: | ---: |
| 总实例 | 146 | 100% |
| 参考解为 `optimal` | 131 | 89.73% |
| 参考解非最优（`feasible`/`heuristic`） | 15 | 10.27% |
| 可判定实例 | 146 | 100% |
| 通过 | 125 | 85.62% |
| 失败 | 21 | 14.38% |
| 不可判定 | 0 | 0% |
| 因严格优于非最优参考而通过 | 7 | 已计入 125 个通过 |

标准 `optimal` 参考口径下，115/131 个实例通过，通过率为 **87.79%**。15 个非最优参考
实例全部可判定，其中 10 个通过：7 个严格优于参考，3 个在 `1e-6` 绝对/相对容差内与参考
相等；其余 5 个失败。因此扩展口径为 125/146，即 **85.62%**。

逐问题类结果及与 no-annotation 最终结果的差异如下。`变化` 为
“with-annotation 通过数 - no-annotation 通过数”，两列分母相同。

| 问题类 | With-Annotation | No-Annotation | 变化 |
| --- | ---: | ---: | ---: |
| Auto-Vehicle-ActiveSuspensionBalance | 0/8 | 0/8 | 0 |
| CBG-Camera-JPEGQuantizationTable | 8/8 | 8/8 | 0 |
| CBG-Camera-VideoStabilization-L1 | 8/8 | 8/8 | 0 |
| CBG-Camera-VideoStabilization-L2 | 8/8 | 6/8 | +2 |
| CBG-Communication-RailCellHandover | 5/5 | 5/5 | 0 |
| CBG-HarmonyOS-CriticalThreadOpt | 5/5 | 5/5 | 0 |
| CBG-HarmonyOS-MemoryEviction | 8/8 | 8/8 | 0 |
| Compute-CAE-SparseLA-LDLSymmetricPivoting | 0/6 | 6/6 | -6 |
| Compute-CAE-SparseLA-LUPivotReordering | 6/6 | 6/6 | 0 |
| Compute-Cluster-CrossPodLoadBalancing | 9/10 | 8/10 | +1 |
| Compute-LLM-MoEExpertLoadBalance | 2/5 | 3/5 | -1 |
| Compute-TBE-MemoryAllocation | 5/8 | 2/8 | +3 |
| Energy-Microgrid-SizingAndOperation | 10/10 | 4/10 | +6 |
| Energy-VPP-DayAheadAdjustableLoadScheduling | 15/15 | 15/15 | 0 |
| ICT-DataCom-LoadBalancing-SingleAndMultitimestamp | 8/8 | 8/8 | 0 |
| ICT-DataCom-NetworkPlanning-CapacityExpansion | 8/8 | 8/8 | 0 |
| ICT-OpticalNetwork-NetworkPlanning-LinkProtection | 5/5 | 4/5 | +1 |
| ICT-OpticalNetwork-NetworkPlanning-PathProtection | 5/5 | 5/5 | 0 |
| ICT-Wireless-ChannelEstimation-SparseDelay | 10/10 | 10/10 | 0 |
| **合计** | **125/146** | **119/146** | **+6** |

### 9.1 各问题类的实例求解时间分布

本节统计 with-annotation 批次的实例求解时间，单位为秒。优先使用实例
`result.json` 中的 `solve_seconds`（107/146 个实例）；其余 39 个实例从同一运行目录的
求解器日志补齐：IPOPT 使用 `Total seconds in IPOPT`，HiGHS 使用 `HiGHS run time`，
SCIP/Couenne 使用 `Timing` 或 `Solving Time (sec)`。因此所有 146 个实例都有时间记录。
对于没有可接受解的 MoE `inst_004` 和 TBE `inst_008`，时间表示最后一次求解器尝试，分别为
约 7200.32 秒和 7200.00 秒，不能解释为成功求解时间。分位数采用线性插值；时间分布也包含
失败实例，因为它描述的是评测器实际花费的求解时间，而不是仅描述通过实例。

| 问题类 | 有计时/总数 | 最小 | P25 | 中位数 | P75 | 最大 | 均值 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Auto-Vehicle-ActiveSuspensionBalance | 8/8 | 20.864 | 24.573 | 26.439 | 35.436 | 39.485 | 29.171 |
| CBG-Camera-JPEGQuantizationTable | 8/8 | 0.370 | 0.730 | 1.100 | 1.363 | 1.820 | 1.090 |
| CBG-Camera-VideoStabilization-L1 | 8/8 | 0.000 | 0.010 | 0.010 | 0.013 | 0.020 | 0.011 |
| CBG-Camera-VideoStabilization-L2 | 8/8 | 11.130 | 23.505 | 31.774 | 46.672 | 68.544 | 36.570 |
| CBG-Communication-RailCellHandover | 5/5 | 0.000 | 0.020 | 0.130 | 6.190 | 8.730 | 3.014 |
| CBG-HarmonyOS-CriticalThreadOpt | 5/5 | 0.331 | 0.364 | 0.399 | 0.414 | 0.532 | 0.408 |
| CBG-HarmonyOS-MemoryEviction | 8/8 | 0.341 | 0.360 | 0.379 | 0.389 | 0.396 | 0.374 |
| Compute-CAE-SparseLA-LDLSymmetricPivoting | 6/6 | 0.399 | 0.414 | 0.428 | 0.450 | 0.481 | 0.434 |
| Compute-CAE-SparseLA-LUPivotReordering | 6/6 | 0.365 | 0.371 | 0.403 | 0.430 | 0.603 | 0.429 |
| Compute-Cluster-CrossPodLoadBalancing | 10/10 | 1.189 | 1955.361 | 7200.358 | 7200.753 | 7201.537 | 5061.940 |
| Compute-LLM-MoEExpertLoadBalance | 5/5 | 0.647 | 1.482 | 7200.320 | 7201.960 | 7207.931 | 4322.468 |
| Compute-TBE-MemoryAllocation | 8/8 | 1.060 | 2.450 | 370.797 | 7200.569 | 7205.448 | 2794.383 |
| Energy-Microgrid-SizingAndOperation | 10/10 | 4.923 | 21.718 | 114.127 | 7212.454 | 7267.278 | 2921.356 |
| Energy-VPP-DayAheadAdjustableLoadScheduling | 15/15 | 0.544 | 0.772 | 2.848 | 33.361 | 44.997 | 14.937 |
| ICT-DataCom-LoadBalancing-SingleAndMultitimestamp | 8/8 | 0.381 | 0.395 | 0.402 | 0.417 | 0.449 | 0.408 |
| ICT-DataCom-NetworkPlanning-CapacityExpansion | 8/8 | 0.386 | 0.903 | 1.042 | 7.085 | 9.386 | 3.544 |
| ICT-OpticalNetwork-NetworkPlanning-LinkProtection | 5/5 | 0.438 | 1.366 | 3.761 | 5.766 | 14.109 | 5.088 |
| ICT-OpticalNetwork-NetworkPlanning-PathProtection | 5/5 | 0.384 | 0.471 | 0.482 | 0.792 | 3.849 | 1.196 |
| ICT-Wireless-ChannelEstimation-SparseDelay | 10/10 | 1.227 | 8.385 | 25.279 | 67.410 | 295.958 | 77.049 |

按第 7.1 节相同的六个时间区间统计，with-annotation 的总体分布如下：

| 求解时间范围 | 实例数量 | 占 146 个实例 |
| --- | ---: | ---: |
| `<=1 s` | 62 | 42.47% |
| `(1,60] s` | 58 | 39.73% |
| `(60,100] s` | 4 | 2.74% |
| `(100,1000] s` | 5 | 3.42% |
| `(1000,7200) s` | 0 | 0.00% |
| `>=7200 s` | 17 | 11.64% |
| **合计** | **146** | **100%** |

各问题类的六档计数如下。达到或略超 7200 秒的记录包括时限级求解以及外层 wall-clock
计时带来的轻微超出；它们不表示已经证明最优。

| 问题类 | `<=1 s` | `(1,60] s` | `(60,100] s` | `(100,1000] s` | `(1000,7200) s` | `>=7200 s` |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Auto-Vehicle-ActiveSuspensionBalance | 0 | 8 | 0 | 0 | 0 | 0 |
| CBG-Camera-JPEGQuantizationTable | 3 | 5 | 0 | 0 | 0 | 0 |
| CBG-Camera-VideoStabilization-L1 | 8 | 0 | 0 | 0 | 0 | 0 |
| CBG-Camera-VideoStabilization-L2 | 0 | 6 | 2 | 0 | 0 | 0 |
| CBG-Communication-RailCellHandover | 3 | 2 | 0 | 0 | 0 | 0 |
| CBG-HarmonyOS-CriticalThreadOpt | 5 | 0 | 0 | 0 | 0 | 0 |
| CBG-HarmonyOS-MemoryEviction | 8 | 0 | 0 | 0 | 0 | 0 |
| Compute-CAE-SparseLA-LDLSymmetricPivoting | 6 | 0 | 0 | 0 | 0 | 0 |
| Compute-CAE-SparseLA-LUPivotReordering | 6 | 0 | 0 | 0 | 0 | 0 |
| Compute-Cluster-CrossPodLoadBalancing | 0 | 2 | 0 | 1 | 0 | 7 |
| Compute-LLM-MoEExpertLoadBalance | 1 | 1 | 0 | 0 | 0 | 3 |
| Compute-TBE-MemoryAllocation | 0 | 4 | 0 | 1 | 0 | 3 |
| Energy-Microgrid-SizingAndOperation | 0 | 4 | 1 | 1 | 0 | 4 |
| Energy-VPP-DayAheadAdjustableLoadScheduling | 6 | 9 | 0 | 0 | 0 | 0 |
| ICT-DataCom-LoadBalancing-SingleAndMultitimestamp | 8 | 0 | 0 | 0 | 0 | 0 |
| ICT-DataCom-NetworkPlanning-CapacityExpansion | 3 | 5 | 0 | 0 | 0 | 0 |
| ICT-OpticalNetwork-NetworkPlanning-LinkProtection | 1 | 4 | 0 | 0 | 0 | 0 |
| ICT-OpticalNetwork-NetworkPlanning-PathProtection | 4 | 1 | 0 | 0 | 0 | 0 |
| ICT-Wireless-ChannelEstimation-SparseDelay | 0 | 7 | 1 | 2 | 0 | 0 |
| **合计** | **62** | **58** | **4** | **5** | **0** | **17** |

总体上，`<=60 s` 的实例有 120 个，占 82.19%；中位数较低的问题类主要是 L1 视频稳定、
两类 CAE、HarmonyOS、DataCom 和光网络保护。长尾集中在 CrossPod、MoE、TBE 和 Microgrid：
这四类共有 17 个实例达到 7200 秒级，占全部时限级记录，说明 annotations 能改善部分模型的
语义还原，但不能消除大规模离散模型的组合搜索和时限风险。

## 10. 失败原因分析

21 个失败实例可分为五类。下表中的“候选自身可行性失败”专指评测器把解重新代回候选模型
后未通过域或约束校验；“目标不匹配”则表示候选解通过自身可行性校验，但目标值没有达到
相应参考判据。

| 失败类型 | 数量 | 问题类/实例 | 直接证据 |
| --- | ---: | --- | --- |
| 候选解在变量边界处超过校验容差 | 8 | ActiveSuspension `inst_001`--`inst_008` | IPOPT 均返回 `optimal` 且目标匹配参考，但部分 `force_command` 超出上下界约 `1e-6`--`3e-5`，大于域检查的 `1e-6` 绝对容差 |
| 最优参考目标值不匹配 | 7 | CAE-LDL 6 个实例；MoE `inst_002` | CAE-LDL 的候选目标被系统性增加常数；MoE 在时限内只有比参考差 9.64% 的可行解 |
| 非最优参考下候选目标更差 | 4 | CrossPod `inst_005`；MoE `inst_005`；TBE `inst_006`、`inst_007` | 均有候选可行解，但在 7200 秒级求解后仍劣于 `feasible`/`heuristic` 参考 |
| 求解子进程被 `SIGKILL` 终止 | 1 | MoE `inst_004` | SCIP 完成耗时较长的对称性分析后，worker 以 `exit -9` 结束，未形成可接受结果 |
| 时限内没有可行 incumbent | 1 | TBE `inst_008` | HiGHS 达时限且 `Primal bound = inf`；SCIP 也没有变量解，目标求值触发 `ValueError` |
| **合计** | **21** |  | 8 + 7 + 4 + 1 + 1 |

### 10.1 ActiveSuspension：目标正确，但数值解未通过边界校验

这 8 个实例不是目标建模错误。候选目标与参考目标全部满足 `1e-6` 混合容差，绝对差仅为
`1.44e-8`--`4.39e-7`。失败来自 `verify_solution.py` 的变量域检查：域边界使用固定
`ABS_TOL=1e-6`，而 IPOPT 返回的若干作动器指令略微越过 `1200`、`2500` 或 `4000` 的上下界。

| 实例 | 候选目标 | 参考目标 | 绝对差 | 日志中的边界违反示例 |
| --- | ---: | ---: | ---: | --- |
| `inst_001` | 3.753871518 | 3.753871566 | 4.81e-8 | `-4000.00003 < -4000` |
| `inst_002` | 2.362407344 | 2.362407377 | 3.31e-8 | `-4000.00003 < -4000` |
| `inst_003` | 2.272486949 | 2.272486984 | 3.55e-8 | `4000.00002 > 4000` |
| `inst_004` | 12.554969578 | 12.554969139 | 4.39e-7 | 输出按 9 位有效数字显示为 `4000 > 4000`，未显示的差值超过 `1e-6` |
| `inst_005` | 3.426954739 | 3.426954576 | 1.63e-7 | `2500.00001 > 2500` |
| `inst_006` | 0.660675134 | 0.660675098 | 3.61e-8 | `-2500.00002 < -2500` |
| `inst_007` | 2.857504129 | 2.857504144 | 1.44e-8 | `-1200.00001 < -1200` |
| `inst_008` | 16.305728461 | 16.305728399 | 6.21e-8 | `-2500.00001 < -2500` |

`result.json` 的简短 `reason` 显示“变量命名与参考模型不一致”，但这不是直接失败原因。
评测流程先由上述域违反将 `feasible` 置为 `false`，随后参考模型交叉检查因变量命名不同而
abstain；生成 reason 时实现优先选择了 `reference_issues`，从而掩盖了先前记录在
`feasibility_issues` 中的边界违反。严格按既定评测器，这 8 个实例仍记为失败；解释结果时应
将它们标为**数值可行性容差失败**，而不是业务模型目标失败。

### 10.2 CAE-LDL：人为加入的常数改变了报告目标值

CAE-LDL 候选正确读取了 `matrix_path`，6 个实例也都由 HiGHS 证得候选模型最优且通过候选
自身可行性检查。问题在于候选把题目要求的
`sum(log(s(B)))` 改成了
`weight_span * positive_product + sum(log(s(B)))`。这些实例中 `positive_product=1`，因此
额外项成为一个随实例变化的正常数。它可能不改变最优块划分，却改变了必须与参考解一致的
目标数值，导致 6/6 全部失败。

| 实例 | 候选目标 | 参考最优目标 | gap（候选 - 参考） | 相对 gap |
| --- | ---: | ---: | ---: | ---: |
| `inst_001` | 7522.014800 | 865.042431 | +6656.972369 | 769.55% |
| `inst_002` | 17558.458015 | 545.720665 | +17012.737350 | 3117.48% |
| `inst_003` | 379.901397 | -114.818219 | +494.719616 | 430.87% |
| `inst_004` | 38724.402635 | 2549.463458 | +36174.939177 | 1418.92% |
| `inst_005` | 19353.900933 | 3977.896522 | +15376.004411 | 386.54% |
| `inst_006` | 102367.989325 | 7647.513894 | +94720.475430 | 1238.58% |

这是一处确定的候选代码目标定义错误，不是 Matrix Market 输入解析问题，也不是求解器精度
问题。修复方法是删除报告目标中的词典序常数；如果确实需要处理零乘积，应采用不改变题目
目标值的约束或分阶段求解方式。

### 10.3 时限内解质量不足

以下 5 个实例都得到了候选可行解，但在时限内没有达到参考判据。正 gap 对这些最小化问题
表示候选更差。

| 问题类/实例 | 参考状态 | 候选目标 | 参考目标 | gap | 相对 gap | 终止情况 |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| CrossPod `inst_005` | `feasible` | 0.309450595 | 0.303570513 | +0.005880082 | 1.937% | HiGHS、SCIP 均达到时限 |
| MoE `inst_002` | `optimal` | 53.261945 | 48.577977 | +4.683968 | 9.642% | SCIP 达时限，Couenne `hardTimeout` |
| MoE `inst_005` | `heuristic` | 5196.896455 | 3415.537111 | +1781.359344 | 52.155% | SCIP 达时限，Couenne `hardTimeout` |
| TBE `inst_006` | `feasible` | 504.160958 | 503.240967 | +0.919991 | 0.183% | HiGHS、SCIP 均达到时限 |
| TBE `inst_007` | `feasible` | 654.924294 | 653.465794 | +1.458500 | 0.223% | HiGHS、SCIP 均达到时限 |

其中 TBE 两例已经非常接近参考，但“参考非最优”规则只接受不劣于参考的候选，不能因为 gap
较小就算通过。MoE `inst_002` 的参考为 `optimal`，也必须满足统一的 `1e-6` 目标容差。

### 10.4 没有形成可接受解的两个实例

- **MoE `inst_004`：** HiGHS 在 7200 秒时得到目标 1146.354883 的可行 incumbent，参考最优
  目标为 1146.350130；随后 SCIP 使用 warm start，在约 814.7 秒完成 1500 个对称生成元的
  分析后，worker 被信号 9 终止（`exit -9`）。归档没有记录是谁发送了 `SIGKILL`，也没有足够
  证据把它确定归因于 OOM；因此只能归类为子进程异常终止，而不能宣称候选模型不可行。
- **TBE `inst_008`：** HiGHS 在 7200 秒内没有找到 incumbent，日志为
  `Primal bound = inf`。SCIP 同样在 7200 秒内没有可行解，随后因变量未初始化而无法计算目标。
  这是明确的“时限内无可行解”，不是目标值比较失败。

## 11. 与 No-Annotation 基线的比较

with-annotation 从 119/146（81.51%）提高到 125/146（85.62%），增加 6 个通过实例，绝对
提升 **4.11 个百分点**。在 `optimal` 参考子集上，从 109/131（83.21%）提高到 115/131
（87.79%），同样增加 6 个通过实例，提升 **4.58 个百分点**。非最优参考子集保持 10/15，
因此本次净提升全部来自 `optimal` 参考实例。

逐类变化并非全部为正：Camera-L2、CrossPod、TBE、Microgrid 和 LinkProtection 合计增加
13 个通过实例；CAE-LDL 和 MoE 合计减少 7 个，净变化为 +6。Microgrid 从 4/10 提升到
10/10，是最大正向变化；CAE-LDL 因候选自行修改报告目标而从 6/6 降至 0/6，是最大负向变化。
这说明 annotations 总体有帮助，但不能阻止生成代码引入题意之外的目标变换，也不能消除大型
组合优化实例的时限和资源风险。

因果解释仍有两项限制。第一，Codex 生成不固定 seed，单次 `pass@1` 的差异同时包含生成
随机性。第二，当前 no-annotation 数字是合并口径：17 个非 CAE 类来自较早的全量提示词，
两个 CAE 类来自加入 `matrix_path` 契约后的定向重测；with-annotation 的 19 类全部使用最新
提示词。因此不能把全部 +6 无条件归因于 `annotations.md`。若要做严格的单变量配对，需要用
同一最新版提示词重新生成完整 no-annotation 基线，并进行多 seed 重复实验。

## 12. 完成与审计清单

- [x] 使用第 5 节完整提示词，和 no-annotation 只保留一行读取指令差异。
- [x] 只新增 `annotations.md`，没有提供实例样例、本地校验器、参考模型或参考解。
- [x] 完成 19 类、146 实例、每类 1 份候选的评测。
- [x] 使用 7200 秒单求解器时限、32 GiB 地址空间上限和既定求解器顺序。
- [x] 沿用非最优参考“候选不劣于参考即通过”的最终判定口径。
- [x] 19 份 `result.json` 均标记 `with_annotations: true`。
- [x] 19 份生成记录的 stage 均为 `with_annotations`，提示词 SHA-256 均为
  `1e9e15de45de2a152814da36a4ab7fca1a41abd8f0c577216699aacee5274862`。
- [x] 最终汇总为 125 通过、21 失败、0 不可判定，合计 146 个实例。

首次流水线在生成后因 CriticalThread 候选缺失而停止；该类在同一 generation batch 内补生成
后，求解阶段从同一 eval batch 续跑，已落盘实例只复用解并重新判定，没有重新生成其他候选或
挑选多个成功候选。首次日志、补生成日志、续跑日志、19 份候选和逐实例求解归档均已保留。
