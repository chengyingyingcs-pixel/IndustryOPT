# GPT-5.6-Sol Harness With-Annotation 消融实验报告

状态：**实验设置已确认；全量生成与求解流水线于 2026-09-26 启动**

生成批次 ID：`gpt-5.6-sol-high-withann-pass1-20260926-124302`

评测批次 ID：`gpt-5.6-sol-high-withann-pass1-20260926-124302-timeout7200-sequential-mem32`

实际启动时间：`2026-09-26T12:49:01Z`

流水线会话 PID：`44428`

流水线日志：`/public/chengyingying/project/industryopt_harness_workspaces/gpt-5.6-sol-high-withann-pass1-20260926-124302.pipeline.log`

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

启动前已只读检查：19/19 个问题类均存在非空的 `nl/annotations.md`。正式生成时仍须将
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

数据集工作树当前只有 `tools/eval/run_eval.py` 存在未提交修改；本实验不修改、不使用该文件，
继续使用上表列出的批次专用评测器快照。正式启动前须再次记录数据集提交、数据清单、评测器
SHA-256、harness SHA-256、Codex CLI 版本和求解器版本。如果其中任何会影响实验语义的项目
发生变化，应暂停并更新本报告，而不是静默继续。

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

拟使用的完整提示词如下。与 no-annotation 报告第 5 节的最新版提示词相比，唯一文本差异是
读取指令中增加 `annotations.md`。拟定提示词 SHA-256 为
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

逐行差异必须保持为：

```diff
-Read statement.md and data_README.md. Implement a general Pyomo model for every instance of
+Read statement.md, annotations.md, and data_README.md. Implement a general Pyomo model for every instance of
```

## 6. 正式运行前的最小脚本修正

当前 `tools/run_codex_harness.py` 已支持 `withann` 阶段并会复制 `annotations.md`，但仍有两处
必须在确认后、运行前修正：

1. 当前所有阶段共用 no-annotation `PROMPT`。应根据 `with_annotations` 选择第 5 节提示词，
   并将实际选中的文本及 SHA-256 分别写入 `prompt.txt`、`record.json` 和
   `generation.json`；不得修改提示词的其他行。
2. 当前 `run_evaluation()` 固定传递 `--no-annotations`。对 `withann-eval` 应去掉该参数，
   使 `result.json` 的 `with_annotations` 元数据为 `true`。由于评测使用 `--from-code`，这项
   修正不改变候选代码或求解过程，只纠正实验标签和审计信息。

同时增加启动前断言：with-ann 的 `input_inventory.json` 必须恰好包含
`statement.md`、`annotations.md`、`data_README.md`；generation record 的 stage 必须为
`with_annotations`；评测阶段必须拒绝读取 no-ann generation batch。除此之外不修改生成或
评测逻辑。

## 7. 生成、求解与归档方案

本次使用以下新的 UTC 时间戳批次，不覆盖任何历史目录：

```text
BATCH_ID=gpt-5.6-sol-high-withann-pass1-20260926-124302
EVAL_BATCH_ID=gpt-5.6-sol-high-withann-pass1-20260926-124302-timeout7200-sequential-mem32
```

计划命令为：

```bash
/public/chengyingying/conda_envs/inferopt-py311/bin/python \
  tools/run_codex_harness.py withann --batch-id <BATCH_ID>

/public/chengyingying/conda_envs/inferopt-py311/bin/python \
  tools/run_codex_harness.py withann-eval \
  --batch-id <BATCH_ID> \
  --eval-batch-id <EVAL_BATCH_ID> \
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

最终报告至少给出：146 个实例的通过、失败和不可判定数量；131 个 `optimal` 参考实例的
标准口径通过率；15 个非最优参考实例的扩展判定；19 个问题类逐类结果；失败原因；实例求解
时间分布；以及相对 no-annotation 最终结果的逐类变化。

## 9. 对照基线与解释边界

当前 no-annotation 最终结果为：119/146 通过（81.51%）、27 个失败、0 个不可判定；其中
`optimal` 参考实例通过 109/131（83.21%），非最优参考实例通过 10/15。

需要提前披露：该最终结果是合并口径。17 个非 CAE 类来自原始全量生成批次，当时提示词尚未
加入详细的 `matrix_path` 运行时契约；两个 CAE 类则使用报告第 5 节的最新版提示词定向重测。
拟议 with-annotation 批次会对全部 19 类使用最新版提示词。因此，与当前已发布 no-ann 数字的
对比并非 19 类全部都具有逐字节配对的历史提示词；`matrix_path` 新增说明只直接针对 CAE
输入，但仍应将这一差异作为实验限制披露，不能把全部差值无条件解释为 annotations 的因果
贡献。此外，Codex 生成不固定 seed，单次 `pass@1` 差异也包含生成随机性。

本方案不擅自重跑 no-annotation 全量基线。若要求严格的逐字节单变量配对，需要另行授权使用
当前最新版 no-ann 提示词重新生成全部 19 类，再与本实验比较。

## 10. 待确认清单

- [x] 确认使用第 5 节完整提示词及其唯一一行差异。
- [x] 确认只新增 `annotations.md`，仍不提供实例样例和本地校验器。
- [x] 确认使用 19 类、146 实例、每类 1 份候选的 `pass@1` 设置。
- [x] 确认继续使用 7200 秒单求解器时限、32 GiB 地址空间上限和既定求解器顺序。
- [x] 确认沿用非最优参考“候选不劣于参考即通过”的最终判定口径。
- [x] 确认接受第 9 节所述历史 no-ann 提示词版本差异，且本轮不额外重跑 no-ann 全量基线。
- [x] 确认批准后修改 harness、创建正式批次并启动实验。

上述设置已由用户确认。启动前检查确认 19/19 个问题类的三份输入文件均非空，146 个实例
清单完整，`appsi_highs`、SCIP、IPOPT 和 Couenne 均可用，且正式 generation/eval 目录
均为新目录。
