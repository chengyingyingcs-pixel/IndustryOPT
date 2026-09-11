# IndusOPT 微调模型闭卷评测中期报告

更新时间：2026-09-10 UTC<br>
数据集：`/public/chengyingying/project/industry_mathopt_dataset`<br>
结果根目录：`/public/chengyingying/project/industry_mathopt_dataset/eval_results/finetuned_sweep/`<br>
评测状态：第 5.3–5.10 节所列 **8 个检查点已完成新一轮重测**；其余 3 个公开权重检查点尚未纳入本轮汇总。

## 1. 结论摘要

- 本报告登记了 **11 个公开权重检查点**；其中第 5.3–5.10 节给出了 **8 个模型**的新一轮完整重测结果，OptiMind-SFT、StepORLM-Qwen3-8B 和 Qwen3-SIRL-4B 尚未纳入本轮结果汇总。
- 当前重测数据集有 **19 个问题类**、**146 个数据实例**；其中 **131 个实例**有可判定的参考最优值，另有 15 个实例不进入准确率分母。
- 每个问题类独立采样 **6 次**，因此每个完整重测模型有 **19 × 6 = 114** 次问题级生成。
- 8 个已完成重测的模型合计得到：
  - 可判定 instance-run：**6071**
  - 通过：**1**
  - 总体 Pass@1：**1/6071 = 0.016%**（按两位小数为 **0.02%**）
- 其中 7 个模型的 Pass@1 和 Pass@6 均为 **0.00%**。
- 唯一产生通过记录的是 `SIRL-Qwen2.5-32B-Gurobi`：Pass@1 为 **0.14%**，Pass@6 为 **0.76%**；通过项对应 `Energy-VPP-DayAheadAdjustableLoadScheduling / inst_007`。
- 失败主要发生在**代码执行阶段**：6070 次失败中有 4842 次（79.77%）属于 API、
  Pyomo 构造、数据结构、索引或其他运行时错误，不能全部归结为数学建模错误。

本报告使用的 11 个权重已经下载到本机 Hugging Face 缓存目录。具体部署方式、权重目录和加载代码见 **附录 A**。

## 2. 评测口径

### 输入与生成

- 使用闭卷 prompt：不提供 `nl/annotations.md`、`formulation/`、参考代码或参考解。
- 每个问题类提供业务描述、数据说明和第一个实例的数据样例。
- 要求模型输出一个通用 Pyomo 函数：

  ```python
  def build(data: dict) -> pyomo.environ.ConcreteModel:
      ...
  ```

- 生成参数：
  - temperature：`0.6`
  - top_p：`0.95`
  - seed：`20260901`
  - 通常 `max_tokens = 12288`
  - 通常 `max_model_len = 32768`
  - 例外：`ORLM-LLaMA-3-8B` 原生上下文为 8192，使用 `max_model_len = 8192`、`max_tokens = 4096`

### 执行与判定

- 使用仓库的 `tools/eval/run_eval.py` 逻辑执行生成代码。
- 每个求解器的求解上限为 **900 秒**。评测程序对一个实例最多轮换 3 个候选
  求解器，因此包含 60 秒余量的进程级硬超时上限为 `900 × 3 + 60 = 2760` 秒；
  900 秒不是一个实例跨所有求解器的总时限。
- 通过条件：
  1. 生成代码能构建并求解；
  2. 解必须通过生成模型自身的逐变量、变量域、约束和目标值一致性复核；
  3. 评测程序进一步尝试把候选解代入参考模型：若明确违反参考模型约束则失败；
     若因变量命名或合法的等价建模方式不同而无法映射，则交叉验证记为 abstain，
     不单独阻止该运行通过；
  4. 求解目标值与参考最优值满足绝对/相对混合容差：
     `|a-b| <= max(1e-6, 1e-6 × max(|a|, |b|))`。

### 指标定义

- **Pass@1**：通过数 / 可判定 instance-run 数。
- **Pass@6**：至少有一次通过的问题实例数 / 可判定实例数。
- 按当前 19 个问题类、146 个实例和每问题 6 次采样，一个完整重测模型理论上有：
  - 146 × 6 = **876** 个 model-instance 组合；
  - 131 × 6 = **786** 个参考状态为 `optimal` 的候选 instance-run；
  - 15 × 6 = **90** 个参考状态非 `optimal`、不进入分母的 instance-run。

这里的 786 是理论候选数，不保证等于每个结果文件的实际 Pass@1 分母。若某次运行
因缺少适用求解器、结果缺失或其他原因被记为 `unjudgeable`，它不会进入
`runs_scored`；因此第 3 节各模型的实际可判定 instance-run 为 691–786。

需要强调：**114** 是“问题类级生成次数”，不是“实例级判定次数”。每个问题类
独立采样 6 份通用建模代码，每份代码随后在该问题类的全部实例上执行。

### Composer 与 Opus 的提示词

论文主实验中的 `composer-2.5` 和 `claude-opus-5` 使用相同的提示词模板，区别仅在传给 Cursor Cloud Agent 的模型 ID。该实验与本报告公开权重 checkpoint 的 vLLM 微调模型实验不是同一次实验：Composer/Opus 通过无仓库访问权限的 Cloud Agent 调用，未显式设置 temperature、seed 或最大输出 token。本报告共登记 11 个公开权重，其中第 5.3–5.10 节的 8 个已完成新一轮重测；这些模型按本节前述参数在本地运行。每个问题一次采样 6 个 completion；各 completion 生成过程中不执行代码、不接收报错反馈，也不进行 agent 式迭代修复。

Composer 和 Opus 的完整模板如下，其中尖括号内容会替换为当前问题的实际文件内容：

````text
你是运筹优化专家。下面给出一个业务问题的自然语言描述和配套数据，请你建立数学模型并写出可求解的代码。

# 业务问题描述

<nl/statement.md 内容>

# 补充说明

<nl/annotations.md 内容；仅在 with-annotations 条件出现>

# 数据说明

<data/README.md 内容>

# 数据文件

以下是一个实例（`inst_001`）的数据文件，供你了解格式。你的代码需要能处理该问题的全部 N 个实例。

`<文件名>.json`:

```json
<inst_001 中该 JSON 文件的内容>
```

`<文件名>.csv`:

```csv
<inst_001 中该 CSV 文件的内容>
```

# 你要输出什么

只输出一个 Python 代码块，不要有其他内容。代码块里必须定义一个函数：

```python
def build(data: dict):
    """从 data 构建并返回一个 pyomo ConcreteModel。"""
```

硬性要求：

1. 用 Pyomo 建模，返回 `ConcreteModel`，其中包含决策变量、唯一的 `Objective`、以及全部约束。
2. **不要在 build 里求解**，只负责建模。求解由调用方完成。
3. 所有数值都从 `data` 里读，不许硬编码。
4. `data` 的结构：单个 JSON 文件时就是该文件解析后的内容；多个文件时是一个字典，
   键为文件名去掉扩展名，JSON 值为解析后的对象，CSV 值为 `list[dict[str, str]]`
   （注意 CSV 读出来全是字符串，需要自己转类型）。
5. 只用标准库和 pyomo，不要 pandas、numpy。
````

两种模型都分别测试了两个输入条件：

| 条件 | 提供给模型的内容 |
|---|---|
| `with-ann` | `nl/statement.md`、`nl/annotations.md`、`data/README.md` 和 `inst_001` 数据样例 |
| `no-ann` | `nl/statement.md`、`data/README.md` 和 `inst_001` 数据样例，不提供 annotations |

#### 条件一：with-ann（含业务注释）

该条件按以下顺序拼接输入：

1. `nl/statement.md`：面向模型的业务问题描述；
2. `nl/annotations.md`：领域工程师整理的隐含约束、术语解释和易错点，在 prompt 中显示为“补充说明”；
3. `data/README.md`：实例文件、字段、单位和数据关系说明；
4. `data/inst_001/`：第一个实例的 JSON/CSV 内容，用于展示实际数据格式。

该条件衡量的是：当业务描述、数据说明以及专家整理的领域知识均可获得时，Composer 或 Opus 能否生成正确且可泛化到该问题全部实例的 Pyomo 模型。annotations 不是参考数学模型或答案，但可能显式说明仅靠题面不容易推断的业务约束。

#### 条件二：no-ann（不含业务注释）

该条件从上述输入中移除整个 `nl/annotations.md` 及“补充说明”章节，只保留：

1. `nl/statement.md`；
2. `data/README.md`；
3. `data/inst_001/` 的 JSON/CSV 格式样例。

该条件衡量的是：模型在没有专家补充说明时，能否仅根据原始业务描述和数据定义识别隐含业务规则并完成建模。`with-ann` 与 `no-ann` 的结果差异用于观察 annotations 对建模结果的影响，但单次运行的差异也可能包含模型随机性，不能全部解释为 annotations 的因果贡献。

除是否包含 `nl/annotations.md` 外，两组实验保持以下条件一致：使用同一个问题版本、同一个 `inst_001` 数据样例、同一输出格式要求、同一模型 ID、同一 Cloud Agent 运行方式以及同一执行和判定流程。Composer 与 Opus 各自都运行这两个条件，而不是 Composer 只运行其中一组、Opus 运行另一组。

每个样例数据文件最多内联 4000 个字符，超过部分以 `... (已截断)` 标记。两种条件均不提供 `formulation/model.md`、参考 `code/model.py`、`solution/*.json`、其他实例数据或仓库工作目录。提示词由 `tools/eval/run_eval.py` 的 `build_prompt()` 构造，并直接作为一个 user prompt 传给 `Agent.prompt()`；仓库中没有为 Composer 和 Opus 分别设置不同的 system prompt。

## 3. 主结果

本节仅汇总第 5.3–5.10 节已有新一轮重测明细的 8 个模型。新一轮评测覆盖
**19 个问题类**，每个问题类采样 6 次，因此每个完整模型有 **114 份问题级生成**。
各模型的“有效 instance-run”会因参考解状态而略有不同；只有参考状态为
`optimal` 的运行进入 Pass@1 分母。未在第 5.3–5.10 节给出新重测明细的
OptiMind-SFT、StepORLM-Qwen3-8B 和 Qwen3-SIRL-4B 不再混入本表。

| 模型 | 问题级生成 | 评测 run 数 | 可判定 instance-run | 通过数 | Pass@1 | Pass@6 | 状态 |
|---|---:|---:|---:|---:|---:|---:|---|
| OptMATH-Qwen2.5-7B | 114 | 114 | 786 | 0 | 0.00% | 0.00% | 完成 |
| OptMATH-Qwen2.5-32B | 114 | 114 | 781 | 0 | 0.00% | 0.00% | 完成 |
| SIRL-Qwen2.5-7B-Gurobi | 114 | 114 | 777 | 0 | 0.00% | 0.00% | 完成 |
| SIRL-Qwen2.5-7B-COPT | 114 | 114 | 786 | 0 | 0.00% | 0.00% | 完成 |
| **SIRL-Qwen2.5-32B-Gurobi** | 114 | 114 | 691 | 1 | **0.14%** | **0.76%** | 完成 |
| SIRL-Qwen2.5-32B-COPT | 114 | 114 | 711 | 0 | 0.00% | 0.00% | 完成 |
| ORLM-LLaMA-3-8B | 114 | 114 | 786 | 0 | 0.00% | 0.00% | 完成 |
| LLMOPT-Qwen2.5-14B | 114 | 114 | 753 | 0 | 0.00% | 0.00% | 完成 |

说明：

- “问题级生成”指 19 个问题 × 6 次采样产生的回复数；未成功提取
  `build()` 的回复仍作为一次生成和评测 run 计入。
- “评测 run 数”指已经写出 `result.json` 的问题级运行数。
- Pass@6 的分母为 131 个可判定实例；SIRL-Qwen2.5-32B-Gurobi 仅有 1 个唯一实例
  至少一次通过，因此为 1/131 = 0.76%。
- “可判定 instance-run”采用结果文件的 `runs_scored`。因缺少适用求解器而记为
  `unjudgeable` 的记录不计入该列，也不计入失败明细；因此第 5.4、5.5 节分别为
  781 和 777，而不是理论候选数 786。

## 4. 通过实例

按照第 5.3–5.10 节的新一轮重测结果，8 个模型合计只有 **1 个通过的
instance-run**，对应 **1 个唯一实例**。从第 5.7 节所引用的结果文件进一步定位，
该实例为 `Energy-VPP-DayAheadAdjustableLoadScheduling / inst_007`。

| 模型 | 通过实例 | 通过次数 | Pass@6 |
|---|---|---:|---:|
| **SIRL-Qwen2.5-32B-Gurobi** | `Energy-VPP-DayAheadAdjustableLoadScheduling / inst_007` | **1** | **1/131 = 0.76%** |
| 其余 7 个模型 | — | 0 | 0.00% |

因此，旧版“6 个通过、分布在 2 个唯一实例上”以及
SIRL-Qwen2.5-32B-COPT 有通过记录的结论，均已被第 5.7、5.8 节的新重测结果取代。

## 5. 失败原因分析

### 5.1 总体失败分布

失败按“问题类 run × 数据实例”统计，即一份生成代码在一个实例上失败记一次。
下表汇总第 5.3–5.10 节的 8 个新重测模型，并按评测流水线中最先确定的最终失败
阶段互斥归类。API、Pyomo 组件构造、数据结构、业务索引及其他运行时异常统一计入
“代码执行错误”，避免依赖人工解释错误签名而造成各节口径漂移。

| 失败阶段 | 次数 | 占失败比例 |
|---|---:|---:|
| 代码执行错误 | 4842 | 79.77% |
| 未提取出 `build()` | 656 | 10.81% |
| 代码语法错误 | 490 | 8.07% |
| 模型不可行 | 38 | 0.63% |
| 执行超时 | 10 | 0.16% |
| 可行性/交叉验证失败 | 0 | 0.00% |
| 目标值不一致 | 34 | 0.56% |
| **合计** | **6070** | **100.00%** |

以上计数仅汇总最终 verdict 为 `fail` 的运行，不包含 `unjudgeable`。8 个结果文件
共有 **6071** 个可判定 instance-run，其中通过 1 次、失败 6070 次，总体 Pass@1
为 **1/6071 = 0.016%**，失败率为 **99.984%**。此外有 217 个参考状态为 `optimal`
但因缺少适用求解器而记为 `unjudgeable` 的运行，以及 720 个参考状态不是 `optimal`
的运行；二者均不进入 Pass@1 和本表的失败分母。

### 5.2 各模型失败类型

| 模型 | 代码执行错误 | 未提取 `build()` | 语法错误 | 模型不可行 | 超时 | 可行性/交叉验证失败 | 目标值不一致 | 失败合计 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| OptMATH-Qwen2.5-7B | 633 | 68 | 85 | 0 | 0 | 0 | 0 | 786 |
| OptMATH-Qwen2.5-32B | 736 | 18 | 27 | 0 | 0 | 0 | 0 | 781 |
| SIRL-Qwen2.5-7B-Gurobi | 692 | 0 | 73 | 5 | 1 | 0 | 6 | 777 |
| SIRL-Qwen2.5-7B-COPT | 544 | 56 | 186 | 0 | 0 | 0 | 0 | 786 |
| SIRL-Qwen2.5-32B-Gurobi | 634 | 0 | 15 | 17 | 9 | 0 | 15 | 690 |
| SIRL-Qwen2.5-32B-COPT | 680 | 0 | 16 | 7 | 0 | 0 | 8 | 711 |
| ORLM-LLaMA-3-8B | 266 | 509 | 11 | 0 | 0 | 0 | 0 | 786 |
| LLMOPT-Qwen2.5-14B | 657 | 5 | 77 | 9 | 0 | 0 | 5 | 753 |

#### 5.2.1 失败类型定义与示例

本表按“问题类 run × 数据实例”统计：一份生成代码在一个实例上失败记一次，而不是每份生成代码只记一次。下列类别按评测流水线中的最终失败原因互斥归类，一次 instance-run 只计入一个类别；`unjudgeable` 实例不进入这些失败统计。

- **代码执行错误**：代码已经通过提取和语法解析，但在加载、模型构建或执行过程中抛出异常。该类统一包含 API/依赖、Pyomo 组件构造、数据读取、业务索引和其他运行时错误。例如使用 GurobiPy/COPT 风格的方法构造 Pyomo 模型、访问错误的数据键，或把字典直接传给 `Set`。这些具体错误仍可用于诊断，但不再作为相互排斥的主统计类别。
- **未提取 `build()`**：模型回复中没有包含可提取的 Python 代码块，或没有定义指定的 `def build(data):`。例如只输出建模解释、定义 `create_model(data)`，或输出未闭合的代码块。此类失败发生在执行代码之前。
- **代码语法错误**：Python 文件无法被解释器解析，例如缩进错误、括号未闭合或字符串未结束：

  ```python
  def build(data):
      model = pyo.ConcreteModel(
      return model
  ```

- **模型不可行**：模型构建成功，但求解器没有返回可行解，或生成模型自身的解检查判定为不可行。例如把“每个任务恰好分配一次”错误写成 `sum(assign[t,m]) == 0`，或把容量上限与需求下限绑定到错误索引。
- **执行超时**：代码进入求解阶段，但在规定的求解时间内没有完成。当前默认每个求解器上限为 900 秒；大规模 MILP、MINLP、过大的 Big-M 或搜索空间过大都可能触发此类失败。超时不必然说明模型数学上错误，也可能是求解难度超出预算。
- **可行性/交叉验证失败**：求解器返回了解，但该解未通过生成模型自身的变量域、约束与目标一致性复核，或在能够映射到参考模型时明确违反参考约束。无法映射而记为 abstain 不属于失败。本轮该类别为 0。
- **目标值不一致**：生成模型成功构建、求解并得到可检查的解，但其目标值与参考最优值不满足绝对/相对混合容差 `|a-b| <= max(1e-6, 1e-6 × max(|a|, |b|))`。常见原因是目标方向、目标项、数据列或索引映射写错，或遗漏约束导致目标过优。

实际归类以 `generation.json` 的 `code_extracted` 以及 `result.json` 的 `verdict`、
`reason` 和 `solver_timeout` 为准；人工诊断出的 API、数据或索引子类型不改变主统计
类别。缺少适用求解器的记录属于 `unjudgeable`，不作为代码执行错误或其他失败计数。

## 5.3 OptMATH-Qwen2.5-7B 重测结果与失败原因

在当前数据集版本（19 个问题类、131 个参考最优实例、15 个参考非最优实例）上，
`OptMATH-Qwen2.5-7B` 完成了 6 次采样，共 114 份问题级生成。103/114 份回复
成功提取出 `build(data)`；每份代码随后在该问题的全部实例上执行。最终得到
786 个可判定 instance-run，0 个通过，Pass@1 和 Pass@6 均为 0.00%。另有 90 个
instance-run 因参考状态不是 `optimal` 而不进入准确率分母，其中 66 个为
`feasible`、24 个为 `heuristic`。

早期结果曾因评测环境缺少 Pyomo 而无效；补齐 `pyomo 6.10.1` 和 `highspy 1.15.1`
后，使用同一批生成代码完成了干净重测。下面的失败统计仅来自依赖修复后的有效运行，
不包含旧的基础设施失败记录。786 个失败按最终阶段归类如下：

| 失败阶段 | 次数 | 占失败比例 |
|---|---:|---:|
| 代码执行错误 | 633 | 80.53% |
| 未提取出 `build()` | 68 | 8.65% |
| 代码语法错误 | 85 | 10.81% |
| **合计** | **786** | **100%** |

高频错误签名进一步显示，主要问题集中在以下几类：

- **Pyomo 与求解器 API 混用**：例如对 `ConcreteModel` 调用 `addVars`，或导入不存在的 Pyomo 属性；
- **数据 schema 误读**：访问 `data['parameters.json']`、`data['node.csv']`、`data['config.json']`，而协议要求使用去掉扩展名的键；
- **集合、变量和业务索引错误**：把整数、字典或错误维度的列表传给 `Set`，或用整数 `0` 访问字符串/稀疏业务索引；
- **表达式构造错误**：错误调用 `sum_product`、重复初始化 `Var`，或把 Python 布尔值、内置 `max`/`abs` 混入 Pyomo 表达式；
- **生成质量不足**：语法/生成器错误，或回复没有可提取的 `build(data)`。

这些失败几乎全部发生在求解前，说明 0% 主要衡量的是模型对“Pyomo + 结构化工业
数据 + 通用 `build(data)`”协议的适配能力，而不是在正确模型已经构建后对目标值或
约束语义的纯优化能力。结果文件为
`/public/chengyingying/project/industry_mathopt_dataset/eval_results/finetuned_sweep/scores/OptMATH-Qwen2.5-7B.json`。

## 5.4 OptMATH-Qwen2.5-32B 重测结果与失败原因

在同一评测协议和数据集版本下，`OptMATH-Qwen2.5-32B` 完成了 6 次采样，覆盖
19 个问题类、114 份问题级生成和 131 个参考最优实例。结果文件中共有 781 个可判定
instance-run，全部失败，因此 Pass@1 和 Pass@6 均为 **0.00%**。另有 5 个参考状态
为 `optimal` 的运行因环境缺少适用求解器而记为 `unjudgeable`；另有 90 个运行因
参考状态不是 `optimal` 而不进入准确率分母。

失败并非由评测环境缺少 Pyomo 引起：本次结果是在已安装 `pyomo 6.10.1` 和
`highspy 1.15.1` 的环境中获得的。失败按最终错误签名统计如下：

| 失败阶段 | 次数 | 占失败比例 |
|---|---:|---:|
| 代码执行错误 | 736 | 94.24% |
| 未提取出 `build()` | 18 | 2.30% |
| 代码语法错误 | 27 | 3.46% |
| **合计** | **781** | **100%** |

最常见的具体错误是：对 Pyomo `ConcreteModel` 调用 Gurobi 风格的
`addConstr`（127 次）、`addVars`（55 次）或 `addVar`（55 次）；向 `IndexedVar`
传入不支持的 `vtype` 参数（98 次）；读取不存在的 `nodes.csv`、`parameters.json`
或 `config.json` 键（75 次合计）；以及用整数访问字符串或稀疏业务索引（至少
24 次明确的 `Index '0' is not valid`）。此外，`pyomo.environ` 中不存在的
`INTEGER`、`BOOL`、`BOOLEAN` 等名称也反复出现。

这些结果表明，32B 模型通常能够输出较完整的代码，但没有稳定遵守评测要求的
`build(data)`、数据 schema 和 Pyomo 统一接口。全部失败均发生在代码提取、语法
或执行阶段，没有进入模型不可行、超时、可行性复核或目标值比较阶段；
因此 0% 主要反映协议适配和代码可执行性不足，而不是在已正确构建的优化模型上的
纯求解性能。结果文件为
`/public/chengyingying/project/industry_mathopt_dataset/eval_results/finetuned_sweep/scores/OptMATH-Qwen2.5-32B.json`。

## 5.5 SIRL-Qwen2.5-7B-Gurobi 重测结果与失败原因

该模型已完成 6 次采样，覆盖 19 个问题类、114 份问题级生成和 131 个参考最优实例。
共得到 777 个可判定 instance-run，全部失败，因此 Pass@1 和 Pass@6 均为
**0.00%**。另有 9 个参考状态为 `optimal` 的运行因环境缺少适用求解器而记为
`unjudgeable`；另有 90 个运行因参考状态不是 `optimal` 而不进入准确率分母。

777 个失败按最终错误原因归类如下：

| 失败阶段 | 次数 | 占失败比例 |
|---|---:|---:|
| 代码执行错误 | 692 | 89.06% |
| 代码语法错误 | 73 | 9.40% |
| 模型不可行 | 5 | 0.64% |
| 执行超时 | 1 | 0.13% |
| 目标值不一致 | 6 | 0.77% |
| **合计** | **777** | **100%** |

失败主要集中在求解前。模型经常误用 Pyomo 组件或求解器接口，错误读取数据文件
键名，或将字符串/稀疏业务 ID 当作连续整数索引；部分生成还包含语法、变量构造
和运行时异常。另有 5 个 instance-run 被判定为模型不可行，6 个成功进入目标值
比较阶段但目标不一致，1 个超过求解时间限制。这表明该模型在当前统一 Pyomo、
`build(data)` 和结构化工业数据协议下的代码适配性不足，0% 主要反映可执行性与接口遵循问题，而非
单纯的优化求解质量。

结果文件为 `/public/chengyingying/project/industry_mathopt_dataset/eval_results/finetuned_sweep/scores/SIRL-Qwen2.5-7B-Gurobi.json`。

## 5.6 SIRL-Qwen2.5-7B-COPT 重测结果与失败原因

`SIRL-Qwen2.5-7B-COPT` 已完成 6 次采样，覆盖 19 个问题类、114 份问题级生成和
131 个参考最优实例。共有 786 个可判定 instance-run，全部未通过，因此 Pass@1 和
Pass@6 均为 **0.00%**。另有 90 个运行对应的参考状态不是 `optimal`，不进入准确率
分母。

786 个失败按最终错误签名归类如下：

| 失败阶段 | 次数 | 占失败比例 |
|---|---:|---:|
| 代码执行错误 | 544 | 69.21% |
| 未提取出 `build()` | 56 | 7.12% |
| 代码语法错误 | 186 | 23.66% |
| **合计** | **786** | **100%** |

最常见的错误包括：生成代码对 Pyomo `ConcreteModel` 调用不兼容的 `addVars`（73
次）；从 `pyomo.environ` 导入不存在的 `Dict`（55 次）、`Continuous`（26 次）或
`BINARY`（21 次）；导入不存在的 `pyomo.gt`、`pyomo.common.create_model` 等模块
（合计至少 65 次）；以及生成 Python 语法错误（包括 85 次 `invalid syntax` 和
43 次生成器表达式未加括号）。此外还出现把列表当作字典调用 `.keys()`、读取
`data['node.csv']` 等错误数据结构访问。

与 Gurobi 版本相比，该 COPT 微调模型的失败全部发生在代码提取、语法或执行阶段，
没有进入模型不可行、超时、可行性复核或目标值比较阶段。这说明在统一 Pyomo、
`build(data)` 和当前依赖环境下，模型尚未稳定遵循可执行代码协议；0% 主要反映
接口、依赖和代码生成质量问题，而非
COPT 求解器本身的性能。结果文件为
`/public/chengyingying/project/industry_mathopt_dataset/eval_results/finetuned_sweep/scores/SIRL-Qwen2.5-7B-COPT.json`。

## 5.7 SIRL-Qwen2.5-32B-Gurobi 重测结果与失败原因

该模型已完成 19 个问题类的 6 次采样和全部实例评测，共覆盖 131 个参考最优实例和 691 个可判定 instance-run，其中 1 个通过、690 个失败；Pass@1 为 **0.14%**，Pass@6 为 **0.76%**。另有 95 个参考状态为 `optimal` 的运行因环境缺少适用求解器而记为 `unjudgeable`，另有 90 个运行因参考状态不是 `optimal` 而不进入准确率分母。

失败按最终原因归类如下：

| 失败阶段 | 次数 | 占失败比例 |
|---|---:|---:|
| 代码执行错误 | 634 | 91.88% |
| 代码语法错误 | 15 | 2.17% |
| 模型不可行 | 17 | 2.46% |
| 执行超时 | 9 | 1.30% |
| 目标值不一致 | 15 | 2.17% |
| **合计** | **690** | **100%** |

最高频错误签名为：`子进程失败（exit -6）:   Bound   [1e+00, 1e+00] |   RHS     [1e+00, 1e+00] | terminate called without an active exception`（51 次）；`TypeError: unhashable type: 'dict'`（35 次）；`子进程失败（exit -6）: Running HiGHS 1.15.1 (git hash: 04024d7): Copyright (c) 2026 under MIT licence terms | Includes third-party software compone`（28 次）；`子进程失败（exit 1）:     >>> if m.y in [m.x, m.y]: |     ...     pass | would both cause this exception.`（27 次）；`子进程失败（exit 1）: pyomo.common.errors.InvalidConstraintError: Invalid constraint expression. The constraint expression resolved to a trivial Bo`（23 次）。总体上，失败集中在上述占比最高的阶段，说明当前结果同时受到代码可执行性、数据 schema/索引理解和数学模型正确性的影响。

结果文件为 `/public/chengyingying/project/industry_mathopt_dataset/eval_results/finetuned_sweep/scores/SIRL-Qwen2.5-32B-Gurobi.json`。

## 5.8 SIRL-Qwen2.5-32B-COPT 重测结果与失败原因

该模型已完成 19 个问题类的 6 次采样和全部实例评测，共覆盖 131 个参考最优实例和 711 个可判定 instance-run，全部失败；Pass@1 和 Pass@6 均为 **0.00%**。另有 75 个参考状态为 `optimal` 的运行因环境缺少适用求解器而记为 `unjudgeable`，另有 90 个运行因参考状态不是 `optimal` 而不进入准确率分母。

失败按最终原因归类如下：

| 失败阶段 | 次数 | 占失败比例 |
|---|---:|---:|
| 代码执行错误 | 680 | 95.64% |
| 代码语法错误 | 16 | 2.25% |
| 模型不可行 | 7 | 0.98% |
| 目标值不一致 | 8 | 1.13% |
| **合计** | **711** | **100%** |

最高频错误签名为：`子进程失败（exit 1）:     raise ValueError( | ValueError: Attempting to declare a block component using the name of a reserved attribute: | 	load`（80 次）；`子进程失败（exit 1）:     >>> if m.y in [m.x, m.y]: |     ...     pass | would both cause this exception.`（51 次）；`TypeError: unhashable type: 'dict'`（31 次）；`TypeError: Cannot create a Set from data that does not support __contains__.  Expected set-like object supporting collections.abc.Collection`（24 次）；`子进程失败（exit 1）: pyomo.common.errors.InvalidConstraintError: Invalid constraint expression. The constraint expression resolved to a trivial Bo`（23 次）。总体上，失败集中在上述占比最高的阶段，说明当前结果同时受到代码可执行性、数据 schema/索引理解和数学模型正确性的影响。

结果文件为 `/public/chengyingying/project/industry_mathopt_dataset/eval_results/finetuned_sweep/scores/SIRL-Qwen2.5-32B-COPT.json`。

## 5.9 ORLM-LLaMA-3-8B 重测结果与失败原因

该模型已完成 19 个问题类的 6 次采样和全部实例评测，共覆盖 131 个参考最优实例和 786 个可判定 instance-run，全部失败；Pass@1 和 Pass@6 均为 **0.00%**。另有 90 个运行因参考状态不是 `optimal` 而不进入准确率分母。

失败按最终原因归类如下：

| 失败阶段 | 次数 | 占失败比例 |
|---|---:|---:|
| 代码执行错误 | 266 | 33.84% |
| 未提取出 `build()` | 509 | 64.76% |
| 代码语法错误 | 11 | 1.40% |
| **合计** | **786** | **100%** |

在能够提取 `build()` 的回复中，常见执行错误包括
`NameError: name 'pyomo' is not defined`（53 次）和
`AttributeError: 'ConcreteModel' object has no attribute 'addVars'`（48 次）。但更主要的
问题仍是未提取出 `build()`：该阶段占 509/786（64.76%）。本轮没有 ORLM 运行进入
模型不可行、超时、可行性复核或目标值比较阶段，因此不能从这些结果单独判断其在
可执行模型上的数学建模正确率。

结果文件为 `/public/chengyingying/project/industry_mathopt_dataset/eval_results/finetuned_sweep/scores/ORLM-LLaMA-3-8B.json`。

## 5.10 LLMOPT-Qwen2.5-14B 重测结果与失败原因

该模型已完成 19 个问题类的 6 次采样和全部实例评测，共覆盖 131 个参考最优实例和 753 个可判定 instance-run，全部失败；Pass@1 和 Pass@6 均为 **0.00%**。另有 33 个参考状态为 `optimal` 的运行因环境缺少适用求解器而记为 `unjudgeable`，另有 90 个运行因参考状态不是 `optimal` 而不进入准确率分母。

失败按最终原因归类如下：

| 失败阶段 | 次数 | 占失败比例 |
|---|---:|---:|
| 代码执行错误 | 657 | 87.25% |
| 未提取出 `build()` | 5 | 0.66% |
| 代码语法错误 | 77 | 10.23% |
| 模型不可行 | 9 | 1.20% |
| 目标值不一致 | 5 | 0.66% |
| **合计** | **753** | **100%** |

最高频错误签名为：`TypeError: unhashable type: 'dict'`（113 次）；`KeyError: 'node.csv'`（40 次）；`SyntaxError: invalid syntax`（32 次）；`TypeError: list indices must be integers or slices, not str`（24 次）；`TypeError: 'int' object is not iterable`（21 次）。总体上，失败集中在上述占比最高的阶段，说明当前结果同时受到代码可执行性、数据 schema/索引理解和数学模型正确性的影响。

结果文件为 `/public/chengyingying/project/industry_mathopt_dataset/eval_results/finetuned_sweep/scores/LLMOPT-Qwen2.5-14B.json`。

## 5.11 GPT-5.6-Sol 单轮无工具实验

为估计基础模型在没有执行反馈和 agent 工具的条件下的表现，使用
`gpt-5.6-sol` 完成了一轮独立控制实验。模型通过 `/home/chengyingying/.codex/config.toml`
中的 `teamorouter` Responses provider 调用，reasoning effort 为 `low`。每个问题只生成
1 份回复，不提供 `nl/annotations.md`，不授予 shell、文件读取或其他工具权限，也不将
traceback 返回给模型。严格来说，这是 Codex CLI 单轮无工具条件，而不是脱离系统提示的
原始 API bare model；因此本节结果用于控制比较，不直接替代第 5.3–5.10 节的微调模型
Pass@6 结果。

19 个问题类、146 个数据实例全部完成生成；19/19 份回复成功提取出 `build(data)`，
审计事件中没有工具调用。131 个实例的参考状态为 `optimal`，其中 115 个运行可判定，
16 个运行因当前环境缺少 `ipopt` 或 `couenne` 而记为 `unjudgeable`；另有 15 个实例的
参考状态不是 `optimal`，不进入准确率分母。

| 指标 | 数值 |
|---|---:|
| 问题级生成 | 19 |
| 参考最优实例 | 131 |
| 可判定 instance-run | 115 |
| `unjudgeable` instance-run | 16 |
| 通过 | 4 |
| 失败 | 111 |
| Pass@1（可判定分母） | **4/115 = 3.48%** |
| 保守 Pass@1（全部参考最优实例） | **4/131 = 3.05%** |

4 个通过实例为：

- `CBG-Camera-JPEGQuantizationTable / inst_001`；
- `CBG-Camera-JPEGQuantizationTable / inst_003`；
- `ICT-DataCom-NetworkPlanning-CapacityExpansion / inst_005`；
- `ICT-OpticalNetwork-NetworkPlanning-LinkProtection / inst_001`。

失败按最终阶段归类如下：

| 失败阶段 | 次数 | 占失败比例 |
|---|---:|---:|
| 代码执行错误 | 110 | 99.10% |
| 目标值不一致 | 1 | 0.90% |
| 未提取 `build()` | 0 | 0.00% |
| 代码语法错误 | 0 | 0.00% |
| 模型不可行 | 0 | 0.00% |
| 执行超时 | 0 | 0.00% |
| 可行性/交叉验证失败 | 0 | 0.00% |
| **合计** | **111** | **100.00%** |

代码执行错误主要来自 Pyomo 组件构造、变量/约束索引以及求解器子进程异常。例如，
生成代码将 `load` 用作 ConcreteModel 组件名，触发 Pyomo 保留属性冲突；部分大规模
实例还出现 HiGHS 子进程 `exit -6`。除 1 个目标值不一致的运行外，其余失败没有
进入稳定的数学目标比较阶段，因此本轮 3.48% 的结果主要反映一次性代码生成和协议
适配能力。

评测初始并发运行得到 3/115，随后按与微调模型相同的单进程（`workers=1`）设置完整
复评得到 4/115；两个结果的差异来自 HiGHS 子进程异常退出的资源/数值不稳定，而非
模型重新生成。正式结果采用单进程复评值。由于每个问题只有一次 completion，本节
不报告有统计意义的 Pass@6。

生成、事件审计和实例结果分别保存在：

- `/public/chengyingying/project/industry_mathopt_dataset/eval_results/bare_llm_sweep/generations/gpt-5.6-sol-low-noann-pass1/`；
- `/public/chengyingying/project/industry_mathopt_dataset/eval_results/bare_llm_sweep/evals/gpt-5.6-sol-low-noann-pass1-sequential/`；
- `/public/chengyingying/project/industry_mathopt_dataset/eval_results/bare_llm_sweep/scores/gpt-5.6-sol-low-noann-pass1-sequential.json`。

## 6. 关键观察

### 6.1 失败集中在代码适配层

最常见的问题是模型没有按本评测要求的 Pyomo 接口输出，或使用了当前执行环境不支持的 API。典型例子包括：

```python
from pyomo.environ import GRB
from pyomo.environ import COPT
import gurobipy as gp
```

前两个导入不是有效的 Pyomo 接口；`gurobipy` 本身是有效的 Gurobi 原生接口，但不符合
本评测要求的 Pyomo `build(data)` 协议。部分模型还会把 Gurobi API 和 Pyomo API
混用，例如同时出现 `gp.ConcreteModel()`、`addVars()`、
`pyomo.environ.ConcreteModel` 等风格。

因此，0% 不应机械理解为这些模型的数学建模能力完全为零；它表示在当前 IndusOPT 闭卷、一次性生成、Pyomo 统一执行协议下无法通过。

### 6.2 `build()` 提取失败非常突出

按第 5.3–5.10 节 8 个重测模型的 `generation.json` 统计，问题级回复中的代码提取
结果如下。这里统计的是 114 份回复能否提取 `build()`，不同于第 5 节按数据实例
统计的失败次数。

| 模型 | 可提取 `build()` / 114 | 提取率 |
|---|---:|---:|
| OptMATH-Qwen2.5-7B | 103 | 90.35% |
| OptMATH-Qwen2.5-32B | 110 | 96.49% |
| SIRL-Qwen2.5-7B-Gurobi | 114 | 100.00% |
| SIRL-Qwen2.5-7B-COPT | 108 | 94.74% |
| SIRL-Qwen2.5-32B-Gurobi | 114 | 100.00% |
| SIRL-Qwen2.5-32B-COPT | 114 | 100.00% |
| ORLM-LLaMA-3-8B | 40 | 35.09% |
| LLMOPT-Qwen2.5-14B | 113 | 99.12% |

最明显的是 `ORLM-LLaMA-3-8B`，仅 40/114 份回复能提取出合规 `build()`。
未纳入本轮重测汇总的 OptiMind-SFT、StepORLM-Qwen3-8B 和 Qwen3-SIRL-4B 不在
本表列出。

提取失败通常是模型输出了过长推理、错误模板或没有包含指定 Python 函数，而不是
求解阶段失败。

### 6.3 SIRL-32B-Gurobi 是唯一产生通过记录的模型

8 个模型均已完成 114 份问题级生成和全部实例评测。其中：

- `SIRL-Qwen2.5-32B-Gurobi` 产生 1 次通过，Pass@1 为 0.14%，Pass@6 为 0.76%；
- `SIRL-Qwen2.5-32B-COPT` 和其余 6 个模型均为 0 次通过。

因此当前结果不支持旧版“两种 SIRL-32B 均产生通过”的结论。由于只有 1 次通过，
也不足以据此将优势稳定归因于模型规模或求解器反馈强化学习。

### 6.4 32B 模型有更多运行进入目标值比较阶段

`SIRL-Qwen2.5-32B-Gurobi` 有 15 次“目标值不一致”，
`SIRL-Qwen2.5-32B-COPT` 有 8 次。这说明相比多数 7B 模型，它们有更多生成代码能
运行到求解和目标值比较阶段，但仍存在建模目标、约束或数据映射错误。

### 6.5 工业级实例比常见 OR 基准更难

这些实例不是单一实例的小规模教科书题，而是要求模型根据业务描述和数据格式写出能泛化到多个实例的 Pyomo 代码。常见错误包括：

- 把整数下标当成集合；
- 索引从 0 或 1 的假设错误；
- 变量命名与参考模型不一致；
- 误判数据嵌套结构；
- 约束维度或求和范围错误；
- 非线性表达式表达错误。

## 7. 解释与限制

1. **这是闭卷一次性生成评测，不是 agent loop。**  
   模型没有机会根据 traceback 修复代码，也没有多轮代码修复机会。

2. **没有使用业务注释。**  
   `nl/annotations.md` 未进入 prompt，避免泄露额外建模提示。

3. **统一使用 Pyomo 接口。**  
   这对习惯 GurobiPy / COPT 的微调模型不利，但保证了所有模型在同一个执行器、同一组求解器和同一判定规则下比较。

4. **求解器可用性会改变 Pass@1 分母。**<br>
   8 个模型均已完成生成和实例评测，但部分生成模型需要当前环境没有安装的求解器。
   共有 217 个参考状态为 `optimal` 的运行因此记为 `unjudgeable`；各模型的
   `runs_scored` 为 691–786，横向比较时必须同时查看分母。

5. **0% 不等于原生 pipeline 能力为 0。**  
   例如未纳入本轮重测汇总的 OptiMind-SFT，其模型卡明确面向 `gurobipy` 输出。
   若使用原生 Gurobi 执行器和对应 prompt，结果可能显著不同。

6. **结果受上下文窗口影响。**  
   `ORLM-LLaMA-3-8B` 原生上下文为 8192，比其他模型短；这会影响其长 prompt 生成质量。

## 8. 后续建议

1. **完成其余 3 个检查点的新版本重测**<br>
   在当前 19 个问题类、146 个实例的版本上重测 OptiMind-SFT、StepORLM-Qwen3-8B
   和 Qwen3-SIRL-4B，再扩展主结果表。

2. **补齐缺失的求解器后复判**<br>
   当前有 217 个参考状态为 `optimal` 的运行因缺少适用求解器而不可判定。补齐
   Ipopt、SCIP 或 Couenne 后，应仅复跑这些记录并重新生成分母和失败统计。

3. **增加“原生 solver pipeline”对照**<br>
   对 GurobiPy / COPT 风格模型使用其原生 prompt 与执行器，区分“建模错误”和“协议适配错误”。

4. **增加格式归一化层**<br>
   在不改变数学语义的前提下，尝试把 `gurobipy`、`coptpy` 输出转换成 Pyomo 或直接接原生求解器。

5. **增加一轮受限 traceback 修复**<br>
   当前结果主要衡量一次性建模能力。可以另设 1–3 轮修复协议，观察执行失败能被恢复的比例。

6. **报告分层指标**<br>
   建议同时给出：
   - 代码提取率；
   - 可执行率；
   - 求解成功率；
   - 参考模型可行性率；
   - 目标值匹配率；
   - 最终 Pass@1 / Pass@6。

## 9. 结果位置

### 9.1 历史长输出复测（旧数据版本，不纳入主结果）

在此前 18 个问题类、138 个实例的数据版本上，曾为检验输出截断对
`OptMATH-Qwen2.5-7B` 的影响，将 `max_tokens` 从 12288 提高到 24576。该实验使用
108 份问题级生成和 738 个可判定 instance-run，结果如下：

| 配置 | 可提取 `build()` / 108 | 可判定 instance-run | 通过数 | Pass@1 | Pass@6 | 结论 |
|---|---:|---:|---:|---:|---:|---|
| `max_tokens=12288` | 94 | 738 | 0 | 0.00% | 0.00% | 原结果 |
| `max_tokens=24576` | 98 | 738 | 0 | 0.00% | 0.00% | 复测 |

提高生成长度后，提取失败从 14 个生成降到 10 个生成，但 108/108 个生成仍因
`length` 截断，平均输出约 24551 token。Pass@1 / Pass@6 保持为 0。该结果仅用于
历史长度消融，不能与第 3 节当前数据版本的结果合并；其原备份路径在当前结果根目录
中已无法检出。

| 内容 | 路径 |
|---|---|
| 生成 prompt / response / model | `/public/chengyingying/project/industry_mathopt_dataset/eval_results/finetuned_sweep/generations/` |
| 每个模型执行结果 | `/public/chengyingying/project/industry_mathopt_dataset/eval_results/finetuned_sweep/evals/` |
| 模型分数 | `/public/chengyingying/project/industry_mathopt_dataset/eval_results/finetuned_sweep/scores/` |
| 数据集问题目录 | `/public/chengyingying/project/industry_mathopt_dataset/domains/` |

## 10. 检查点对应关系

| 本报告别名 | Hugging Face 权重 |
|---|---|
| OptMATH-Qwen2.5-7B | `Aurora-Gem/OptMATH-Qwen2.5-7B` |
| OptMATH-Qwen2.5-32B | `Aurora-Gem/OptMATH-Qwen2.5-32B-Instruct` |
| SIRL-Qwen2.5-7B-Gurobi | `chenyitian-shanshu/SIRL-Gurobi` |
| SIRL-Qwen2.5-7B-COPT | `chenyitian-shanshu/SIRL-COPT` |
| SIRL-Qwen2.5-32B-Gurobi | `chenyitian-shanshu/SIRL-Gurobi32B` |
| SIRL-Qwen2.5-32B-COPT | `chenyitian-shanshu/SIRL-COPT32B` |
| ORLM-LLaMA-3-8B | `CardinalOperations/ORLM-LLaMA-3-8B` |
| LLMOPT-Qwen2.5-14B | `ant-opt/LLMOPT-Qwen2.5-14B` |
| OptiMind-SFT | `microsoft/OptiMind-SFT` |
| StepORLM-Qwen3-8B | `Chenyu-Zhou/StepORLM-Qwen3-8B` |
| Qwen3-SIRL-4B | `chenyitian-shanshu/Qwen3-SIRL-4B` |

## 附录 A：11 个模型的部署与权重加载

### A.1 本机权重根目录

本次评测没有把权重复制到项目仓库中，而是统一下载到以下 Hugging Face 缓存根目录：

```bash
/public/chengyingying/hf_cache
```

对应的标准缓存结构是：

```text
/public/chengyingying/hf_cache/hub/models--<org>--<repo>/snapshots/<revision>/
```

每个 `snapshots/<revision>/` 目录都可以直接作为 `model_path` 使用，里面包含：

```text
config.json
generation_config.json
tokenizer.json / tokenizer_config.json
model*.safetensors
model.safetensors.index.json
```

加载前建议先设置：

```bash
export HF_HOME=/public/chengyingying/hf_cache
export HF_TOKEN=hf_xxx
```

如果权重已完整下载，也可以设置：

```bash
export HF_HUB_OFFLINE=1
```

### A.2 权重目录映射

下表中的 `本地权重目录` 就是本次评测实际加载的目录。部署时可直接把该路径传给 `vllm.LLM(model=...)`、`AutoModelForCausalLM.from_pretrained(...)` 或其他推理框架。

| 报告别名 | Hugging Face 权重 | 本地权重目录 | 磁盘占用 |
|---|---|---|---:|
| OptMATH-Qwen2.5-7B | `Aurora-Gem/OptMATH-Qwen2.5-7B` | `/public/chengyingying/hf_cache/hub/models--Aurora-Gem--OptMATH-Qwen2.5-7B/snapshots/617fe77f2e930ccb518c081ea4faace9677bb6ab` | 14.2 GiB |
| OptMATH-Qwen2.5-32B | `Aurora-Gem/OptMATH-Qwen2.5-32B-Instruct` | `/public/chengyingying/hf_cache/hub/models--Aurora-Gem--OptMATH-Qwen2.5-32B-Instruct/snapshots/063f6ed850f9b7677f792dab41639b73167cc302` | 61.0 GiB |
| SIRL-Qwen2.5-7B-Gurobi | `chenyitian-shanshu/SIRL-Gurobi` | `/public/chengyingying/hf_cache/hub/models--chenyitian-shanshu--SIRL-Gurobi/snapshots/50e55892e5cc6a77bfed1a677f0926674b017649` | 14.2 GiB |
| SIRL-Qwen2.5-7B-COPT | `chenyitian-shanshu/SIRL-COPT` | `/public/chengyingying/hf_cache/hub/models--chenyitian-shanshu--SIRL-COPT/snapshots/c7ec27d6537e6ee9533c79c7509da536bc30fd87` | 14.2 GiB |
| SIRL-Qwen2.5-32B-Gurobi | `chenyitian-shanshu/SIRL-Gurobi32B` | `/public/chengyingying/hf_cache/hub/models--chenyitian-shanshu--SIRL-Gurobi32B/snapshots/78b9b642cffbec0f707d078f5270f2c678fe57c9` | 61.0 GiB |
| SIRL-Qwen2.5-32B-COPT | `chenyitian-shanshu/SIRL-COPT32B` | `/public/chengyingying/hf_cache/hub/models--chenyitian-shanshu--SIRL-COPT32B/snapshots/1bccf5d7bf054942317c600567c8f5f4303aa861` | 61.0 GiB |
| ORLM-LLaMA-3-8B | `CardinalOperations/ORLM-LLaMA-3-8B` | `/public/chengyingying/hf_cache/hub/models--CardinalOperations--ORLM-LLaMA-3-8B/snapshots/94fdc3c5738c6536d4880dc19a78f215529181c5` | 15.0 GiB |
| LLMOPT-Qwen2.5-14B | `ant-opt/LLMOPT-Qwen2.5-14B` | `/public/chengyingying/hf_cache/hub/models--ant-opt--LLMOPT-Qwen2.5-14B/snapshots/ed0ae2dd051aec57989eedef064ce7e445b6726a` | 55.0 GiB |
| OptiMind-SFT | `microsoft/OptiMind-SFT` | `/public/chengyingying/hf_cache/hub/models--microsoft--OptiMind-SFT/snapshots/817e06666a39155f9352d00354b3227d230da46d` | 39.0 GiB |
| StepORLM-Qwen3-8B | `Chenyu-Zhou/StepORLM-Qwen3-8B` | `/public/chengyingying/hf_cache/hub/models--Chenyu-Zhou--StepORLM-Qwen3-8B/snapshots/8018adb0aab6020c393924d379e154cf849b2bf0` | 15.3 GiB |
| Qwen3-SIRL-4B | `chenyitian-shanshu/Qwen3-SIRL-4B` | `/public/chengyingying/hf_cache/hub/models--chenyitian-shanshu--Qwen3-SIRL-4B/snapshots/2bd4dcfcde634c88818788a1493b9288f49d73b5` | 7.5 GiB |

### A.3 使用 vLLM 部署

本次评测的生成脚本已经内置了别名到 Hugging Face 权重的映射。设置缓存目录后，可直接运行：

```bash
cd /public/chengyingying/project/industry_mathopt_dataset
export HF_HOME=/public/chengyingying/hf_cache
export HF_TOKEN=hf_xxx

python3 tools/eval/generate_finetuned.py \
  --model OptMATH-Qwen2.5-7B \
  --runs 6 \
  --max-model-len 32768 \
  --max-tokens 12288
```

`tools/eval/generate_finetuned.py` 中的 `MODELS` 字典会自动把报告别名映射到 Hugging Face 权重；权重若已在上述缓存目录中，就不会重新下载。

如果要用某个显式本地目录启动 vLLM，可以写：

```python
from vllm import LLM, SamplingParams

model_path = "/public/chengyingying/hf_cache/hub/models--Aurora-Gem--OptMATH-Qwen2.5-7B/snapshots/617fe77f2e930ccb518c081ea4faace9677bb6ab"

llm = LLM(
    model=model_path,
    dtype="bfloat16",
    trust_remote_code=True,
    max_model_len=32768,
    gpu_memory_utilization=0.92,
    enable_prefix_caching=True,
    seed=20260901,
)

sampling_params = SamplingParams(
    n=6,
    temperature=0.6,
    top_p=0.95,
    max_tokens=12288,
)
```

### A.4 使用 Transformers 部署

显式加载本地快照目录的方式如下：

```python
from pathlib import Path
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

model_path = "/public/chengyingying/hf_cache/hub/models--Aurora-Gem--OptMATH-Qwen2.5-7B/snapshots/617fe77f2e930ccb518c081ea4faace9677bb6ab"

tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
model = AutoModelForCausalLM.from_pretrained(
    model_path,
    dtype=torch.bfloat16,
    device_map="auto",
    trust_remote_code=True,
)
```

若想按 Hugging Face 仓库名自动从缓存加载，可以先设置：

```bash
export HF_HOME=/public/chengyingying/hf_cache
export HF_HUB_OFFLINE=1
```

然后把 `model_path` 替换成对应的仓库 ID，例如 `Aurora-Gem/OptMATH-Qwen2.5-7B`。

### A.5 部署建议

- 单卡显存约 140 GiB 时，14B 及以下模型可以按 BF16 直接加载；32B 模型也可以在约 140 GiB 显存的 L20X/A100/H100 上按 BF16 加载。
- 若显存不足，应使用 vLLM / SGLang 的多卡张量并行，或使用对应仓库提供的量化权重；本次报告均使用原始 BF16 权重。
- `OptiMind-SFT` 是 GPT-OSS 20B MoE 架构，建议使用 vLLM 或 SGLang 等支持该架构的推理框架。
- 不要只复制 `model*.safetensors`，要复制或链接整个 snapshot 目录，否则容易缺少 tokenizer 或 config。
- 如果要固定长期部署路径，建议把 snapshot 复制或软链接到不含 revision hash 的稳定目录，例如：

  ```bash
  mkdir -p /public/chengyingying/models
  ln -sfn /public/chengyingying/hf_cache/hub/models--Aurora-Gem--OptMATH-Qwen2.5-7B/snapshots/617fe77f2e930ccb518c081ea4faace9677bb6ab \
    /public/chengyingying/models/OptMATH-Qwen2.5-7B
  ```
