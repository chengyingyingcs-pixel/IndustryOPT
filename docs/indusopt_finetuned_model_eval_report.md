# IndusOPT 微调模型闭卷评测中期报告

生成时间：2026-09-02 03:33 UTC  
数据集：`dataset/industry_mathopt_dataset`  
结果根目录：`dataset/industry_mathopt_dataset/eval_results/finetuned_sweep/`  
评测状态：**已按要求暂停**。9 个检查点完整结束；`SIRL-Qwen2.5-32B-Gurobi` 和 `SIRL-Qwen2.5-32B-COPT` 为部分结果。

## 1. 结论摘要

- 本次覆盖 **11 个公开权重检查点**。
- 数据集当前有 **18 个问题类**、**138 个数据实例**；其中 **123 个实例**有可判定的参考最优值。
- 每个问题类独立采样 **6 次**，因此完整模型的生成次数为 **18 × 6 = 108**。
- 到暂停时刻，所有已落盘的判定中：
  - 可判定 instance-run：**7507**
  - 通过：**6**
  - 总体 Pass@1：**0.08%**
- 9 个完整结束的检查点 Pass@1 和 Pass@6 均为 **0.00%**。
- 目前唯一产生通过记录的是两个 SIRL-32B 变体，但二者尚未完成全量 108 次生成评测，指标只能视为中期结果。
- 失败主要发生在**代码执行与 API 适配层**，而不是全部都能归结为数学建模错误。

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
- 单实例求解上限：**900 秒**。
- 通过条件：
  1. 生成代码能构建并求解；
  2. 解代回模型或参考模型时可行；
  3. 求解目标值与参考最优值相对误差不超过 `1e-6`。

### 指标定义

- **Pass@1**：通过数 / 可判定 instance-run 数。
- **Pass@6**：至少有一次通过的问题实例数 / 可判定实例数。
- 一个完整模型有：
  - 138 × 6 = **828** 个 model-instance 组合；
  - 123 × 6 = **738** 个可判定 instance-run；
  - 15 × 6 = **90** 个不可判定 instance-run。

需要强调：108 是“问题类级生成次数”，不是“实例级判定次数”。模型为每个问题类生成一份通用建模代码，该代码会在该问题类的多个实例上执行。

### Composer 与 Opus 的提示词

论文主实验中的 `composer-2.5` 和 `claude-opus-5` 使用相同的提示词模板，区别仅在传给 Cursor Cloud Agent 的模型 ID。该实验与本报告 11 个公开权重 checkpoint 的 vLLM 微调模型实验不是同一次实验：Composer/Opus 通过无仓库访问权限的 Cloud Agent 调用，未显式设置 temperature、seed 或最大输出 token；11 个微调模型则按本节前述参数进行本地单次生成。

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

| 模型 | 生成文件 | 评测 run 数 | 可判定 instance-run | 通过数 | Pass@1 | Pass@6 | 状态 |
|---|---:|---:|---:|---:|---:|---:|---|
| OptMATH-Qwen2.5-7B | 108 | 108 | 738 | 0 | 0.00% | 0.00% | 完成 |
| OptMATH-Qwen2.5-32B | 108 | 108 | 738 | 0 | 0.00% | 0.00% | 完成 |
| SIRL-Qwen2.5-7B-Gurobi | 108 | 108 | 738 | 0 | 0.00% | 0.00% | 完成 |
| SIRL-Qwen2.5-7B-COPT | 108 | 108 | 738 | 0 | 0.00% | 0.00% | 完成 |
| **SIRL-Qwen2.5-32B-Gurobi** | 108 | 73 | 457 | 2 | 0.44% | 0.98% | 部分 |
| **SIRL-Qwen2.5-32B-COPT** | 108 | 68 | 408 | 4 | 0.98% | 2.30% | 部分 |
| ORLM-LLaMA-3-8B | 108 | 108 | 738 | 0 | 0.00% | 0.00% | 完成 |
| LLMOPT-Qwen2.5-14B | 108 | 108 | 738 | 0 | 0.00% | 0.00% | 完成 |
| OptiMind-SFT | 108 | 108 | 738 | 0 | 0.00% | 0.00% | 完成 |
| StepORLM-Qwen3-8B | 108 | 108 | 738 | 0 | 0.00% | 0.00% | 完成 |
| Qwen3-SIRL-4B | 108 | 108 | 738 | 0 | 0.00% | 0.00% | 完成 |

说明：

- “生成文件”指从 18 个问题 × 6 次采样中提取出的 `model_run*.py` 文件数。
- “评测 run 数”指已经写出 `result.json` 的问题级运行数。
- 部分模型的 Pass@1 / Pass@6 只基于当前已落盘结果，不能与完整结果直接等同排名。

## 4. 通过实例

目前共有 6 个通过的 instance-run，分布在 2 个唯一实例上：

| 模型 | 通过实例 | 通过次数 |
|---|---|---:|
| SIRL-Qwen2.5-32B-Gurobi | `CBG-Camera-VideoStabilization-L2 / inst_006` | 2 |
| SIRL-Qwen2.5-32B-COPT | `CBG-Camera-VideoStabilization-L2 / inst_006` | 2 |
| SIRL-Qwen2.5-32B-COPT | `Compute-LLM-MoEExpertLoadBalance / inst_001` | 2 |

因此，按唯一实例看：

- SIRL-Qwen2.5-32B-Gurobi：1 个实例至少一次通过；
- SIRL-Qwen2.5-32B-COPT：2 个实例至少一次通过；
- 其余完整模型：0 个实例通过。

## 5. 失败原因分析

### 5.1 总体失败分布

失败按“问题类 run × 数据实例”统计，即一个生成 run 在一个实例上失败记一次。

| 失败类型 | 次数 | 占失败比例 |
|---|---:|---:|
| 代码执行错误 | 4666 | 62.21% |
| 未提取出 `build()` | 1255 | 16.73% |
| 依赖/API 不匹配 | 929 | 12.39% |
| 代码语法错误 | 429 | 5.72% |
| 目标值不一致 | 145 | 1.93% |
| 求解器无可行解 | 74 | 0.99% |
| 执行超时 | 2 | 0.03% |
| 约束不可行 / 交叉验证失败 | 1 | 0.01% |
| **合计** | **7501** | **100%** |

同期的通过数为 6，因此可判定 instance-run 的总失败率约为 **99.92%**。

### 5.2 各模型失败类型

| 模型 | 代码执行错误 | 未提取 `build()` | API 不匹配 | 语法错误 | 目标值不一致 | 求解器无可行解 | 超时 | 交叉验证失败 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| OptMATH-Qwen2.5-7B | 626 | 52 | 34 | 25 | 1 | 0 | 0 | 0 |
| OptMATH-Qwen2.5-32B | 669 | 18 | 18 | 33 | 0 | 0 | 0 | 0 |
| SIRL-Qwen2.5-7B-Gurobi | 657 | 3 | 0 | 46 | 11 | 19 | 2 | 0 |
| SIRL-Qwen2.5-7B-COPT | 384 | 18 | 170 | 166 | 0 | 0 | 0 | 0 |
| SIRL-Qwen2.5-32B-Gurobi | 337 | 0 | 0 | 8 | 82 | 28 | 0 | 0 |
| SIRL-Qwen2.5-32B-COPT | 335 | 0 | 9 | 7 | 32 | 21 | 0 | 0 |
| ORLM-LLaMA-3-8B | 272 | 404 | 49 | 13 | 0 | 0 | 0 | 0 |
| LLMOPT-Qwen2.5-14B | 621 | 0 | 0 | 100 | 11 | 6 | 0 | 0 |
| OptiMind-SFT | 255 | 46 | 429 | 8 | 0 | 0 | 0 | 0 |
| StepORLM-Qwen3-8B | 46 | 692 | 0 | 0 | 0 | 0 | 0 | 0 |
| Qwen3-SIRL-4B | 464 | 22 | 220 | 23 | 8 | 0 | 0 | 1 |

#### 5.2.1 失败类型定义与示例

本表按“问题类 run × 数据实例”统计：一份生成代码在一个实例上失败记一次，而不是每份生成代码只记一次。下列类别按评测流水线中的最终失败原因归类，一次 instance-run 只计入一个类别；`unjudgeable` 实例不进入这些失败统计。

- **代码执行错误**：代码已提取且能通过 Python 语法解析，但在读取数据、构建 Pyomo 组件或运行过程中抛出运行时异常。例如，实际数据没有对应键时写出 `data["parameters.json"]` 会触发 `KeyError`；把字典直接传给 `Set` 可能触发 `TypeError: unhashable type: 'dict'`。这类错误通常反映对数据层级、索引或 Pyomo 组件语义的误解。
- **未提取 `build()`**：模型回复中没有包含可提取的 Python 代码块，或没有定义指定的 `def build(data):`。例如只输出建模解释、定义 `create_model(data)`，或输出未闭合的代码块。此类失败发生在执行代码之前。
- **API 不匹配**：代码使用了当前协议不支持的求解器接口或依赖，通常是把 GurobiPy/COPT 写法用于要求 Pyomo 的评测。例如 `import gurobipy as gp; model = gp.Model()`，或从 `pyomo.environ` 导入不存在的 `GRB`/`COPT`；也包括对 Pyomo 对象调用 `addConstr()`、`optimize()` 等 Gurobi 风格方法。
- **代码语法错误**：Python 文件无法被解释器解析，例如缩进错误、括号未闭合或字符串未结束：

  ```python
  def build(data):
      model = pyo.ConcreteModel(
      return model
  ```

- **目标值不一致**：生成模型成功构建、求解并得到可检查的解，但其目标值与参考解的 `objective` 相对误差超过 `1e-6`。例如生成模型得到目标值 `1`，参考值为 `8`。常见原因是目标方向、目标项、数据列或索引映射写错，或遗漏约束导致目标过优。
- **求解器无可行解**：模型构建成功，但求解器报告 `infeasible`，没有满足全部约束的解。例如把“每个任务恰好分配一次”错误写成 `sum(assign[t,m]) == 0`，或把容量上限与需求下限绑定到错误索引，都会造成模型不可行。
- **执行超时**：代码进入求解阶段，但在规定的求解时间内没有完成。当前默认每个求解器上限为 900 秒；大规模 MILP、MINLP、过大的 Big-M 或搜索空间过大都可能触发此类失败。超时不必然说明模型数学上错误，也可能是求解难度超出预算。
- **约束不可行 / 交叉验证失败**：生成模型自身能够求解且解满足其自身约束，但把同一解代入参考模型时违反参考约束。这通常说明漏掉或错误实现了约束。例如漏写“同一链路同一波长不能被多个请求同时使用”的互斥约束，候选模型可能仍得到与参考值相同的目标，但参考模型会报告具体约束违反。

这些类别反映失败发生在流水线的不同阶段：语法/API/运行时错误发生在求解前，求解器无可行解和超时发生在求解阶段，目标值不一致和交叉验证失败则表示代码已经推进到结果核验阶段。第 5.3 节进一步把其中的“代码执行错误”细分为数据结构/参数访问、其他运行时以及 Pyomo 组件构造错误。

### 5.3 OptMATH-Qwen2.5-7B 失败原因细分

以下统计来自 `max_tokens=24576` 的复测结果，共 738 个失败 instance-run。

| 失败原因 | 次数 | 占总失败比例 |
|---|---:|---:|
| 数据结构 / 参数访问错误 | 270 | 36.59% |
| 其他运行时错误 | 210 | 28.46% |
| Pyomo 集合 / 变量 / 约束构造错误 | 146 | 19.78% |
| 未提取出 `build()` | 52 | 7.05% |
| API / 依赖不匹配 | 34 | 4.61% |
| 代码语法错误 | 25 | 3.39% |
| 目标值不一致 | 1 | 0.14% |
| **合计** | **738** | **100%** |

高频错误签名包括：

| 错误签名 | 次数 |
|---|---:|
| `Cannot create a Set from data ... received 'int'` | 36 |
| `KeyError: 'node.csv'` | 32 |
| `KeyError: 'parameters.json'` | 30 |
| `AttributeError: module 'pyomo.environ' has no attribute 'infinity'` | 30 |
| `TypeError: unhashable type: 'dict'` | 28 |
| `KeyError: 'config.json'` | 20 |
| `IndexedVar[0] ... has not been constructed` | 19 |
| `invalid literal for int() with base 10: '%%MatrixMarket'` | 18 |
| `TypeError: list indices must be integers or slices, not dict` | 18 |

这些错误说明主要瓶颈不是“模型完全没有输出代码”：98/108 个生成可提取 `build()`，但代码经常错误理解 IndusOPT 的数据层级和 Pyomo 组件语义。最典型的失败链路是：读取 `parameters.json` 或 CSV 的方式与实际 schema 不一致，随后把标量、列表、字典错误地传给 Pyomo `Set` / `Param` / `Var`，导致模型在构造或求解阶段崩溃。唯一一次进入目标值比较的 run 也得到 `目标值不一致：1 vs 参考 8`。

### 5.4 OptMATH-Qwen2.5-32B-no-ann 失败原因

对 `OptMATH-Qwen2.5-32B` 在不提供 `nl/annotations.md` 的条件下的 108 个问题级生成进行复核。该模型有 105/108 次成功提取出 `build()`，但在 738 个可判定 instance-run 中通过数为 0，因此 `Pass@1` 和 `Pass@6` 均为 0.00%。失败主要发生在数据绑定和 Pyomo 模型构建阶段，而不是没有输出代码。

**数据文件键名使用错误。** 评测器将多文件实例加载为以去掉扩展名的文件名为键的字典，例如 `nodes.csv` 对应 `data["nodes"]`，`parameters.json` 对应 `data["parameters"]`。生成代码却多次访问 `data["nodes.csv"]`、`data["demands.csv"]`、`data["config.json"]` 或 `data["parameters.json"]`，触发 `KeyError`。这说明模型没有稳定遵循 prompt 中的 data schema 约定。

**CSV 的列表-字典结构处理错误。** CSV 文件的值是 `list[dict[str, str]]`，应先遍历记录再按字段名取值。模型有时把列表当作字典或把字典当作整数索引，产生 `TypeError: list indices must be integers or slices, not str` 等错误，导致网络、负载均衡和内存分配等问题无法完成数据读取。

**Pyomo 索引假设错误。** 许多实例使用字符串或稀疏业务 ID 作为集合元素，模型却定义集合后用 `0`、`1` 等整数访问变量，例如 `model.x[0]`。典型错误为 `KeyError: Index '0' is not valid for indexed component 'x'`、`'t'` 或 `'t_pointwise'`。这类错误反映模型把业务索引错误地假设成从零开始的连续整数。

**符号表达式与 Python 布尔值混用。** 在虚拟电厂等代码中出现 `TypeError: unsupported operand type(s) for *: 'LinearExpression' and 'bool'`。这通常是将 `t in set` 或 Python 条件表达式直接乘到 Pyomo 表达式上，而不是使用 Pyomo 参数或显式约束表达逻辑，导致模型构造失败。

**字段名和数据层级猜测错误。** 除顶层键名外，代码还会猜测不存在的字段，例如 `KeyError: 'capex_cny_per_unit'`。其根因是把数学符号或其他问题的字段名当成当前实例字段，或忽略 `data/README.md` 的字段字典。

**失败所处阶段及含义。** 105/108 份生成结果包含可提取的 `build()`，但大量代码在读取数据或构造 Pyomo 集合、变量和约束时就退出，几乎没有进入目标值比较阶段。因此，0% 通过率主要衡量的是 OptMATH-32B 在统一 Pyomo 接口下对工业数据 schema、业务索引和模型构造语义的适配失败，不能单独解释为其数学优化能力完全为零。由于本实验是闭卷一次性生成，没有把 traceback 返回给模型进行修复，这些早期错误会在该问题的全部实例上重复出现。

## 6. 关键观察

### 6.1 失败集中在代码适配层

最常见的问题是模型没有按本评测要求的 Pyomo 接口输出，或使用了当前执行环境不支持的 API。典型例子包括：

```python
from pyomo.environ import GRB
from pyomo.environ import COPT
import gurobipy as gp
```

这些不是 Pyomo 的可用接口。部分模型还会把 Gurobi API 和 Pyomo API 混用，例如同时出现 `gp.ConcreteModel()`、`addVars()`、`pyomo.environ.ConcreteModel` 等风格。

因此，0% 不应机械理解为这些模型的数学建模能力完全为零；它表示在当前 IndusOPT 闭卷、一次性生成、Pyomo 统一执行协议下无法通过。

### 6.2 `build()` 提取失败非常突出

按生成文件统计，代码提取成功率如下：

| 模型 | 可提取 `build()` / 108 |
|---|---:|
| OptMATH-Qwen2.5-7B | 98 |
| OptMATH-Qwen2.5-32B | 105 |
| SIRL-Qwen2.5-7B-Gurobi | 107 |
| SIRL-Qwen2.5-7B-COPT | 105 |
| SIRL-Qwen2.5-32B-Gurobi | 108 |
| SIRL-Qwen2.5-32B-COPT | 108 |
| ORLM-LLaMA-3-8B | 46 |
| LLMOPT-Qwen2.5-14B | 108 |
| OptiMind-SFT | 100 |
| StepORLM-Qwen3-8B | 6 |
| Qwen3-SIRL-4B | 104 |

最明显的是：

- `StepORLM-Qwen3-8B` 仅 6/108 次能提取出合规 `build()`；
- `ORLM-LLaMA-3-8B` 仅 46/108 次能提取出合规 `build()`。

这两类失败大多是模型输出了过长推理、错误模板或没有包含指定 Python 函数，而不是求解阶段失败。

### 6.3 SIRL-32B 相对最好，但结果未完成

在已落盘结果中：

- `SIRL-Qwen2.5-32B-Gurobi` 已产生 2 次通过；
- `SIRL-Qwen2.5-32B-COPT` 已产生 4 次通过；
- 其余完整模型均为 0 通过。

这与这两个模型使用了求解器反馈的 RL 训练目标相符。但二者只完成 73/108 和 68/108，不能作为最终排名。

### 6.4 32B 模型更多进入目标值比较阶段

`SIRL-Qwen2.5-32B-Gurobi` 有 82 次“目标值不一致”，`SIRL-Qwen2.5-32B-COPT` 有 32 次。这说明相比多数 7B 模型，它们有更多生成代码能跑到求解和目标值比较阶段，但仍然存在建模目标、约束或数据映射错误。

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

4. **部分结果不可直接排名。**  
   SIRL-32B 两个变体尚未完成 108/108，其 Pass@6 只基于当前已评测到的实例子集。

5. **0% 不等于原生 pipeline 能力为 0。**  
   例如 OptiMind-SFT 的模型卡明确面向 `gurobipy` 输出。若使用原生 Gurobi 执行器和对应 prompt，结果可能显著不同。

6. **结果受上下文窗口影响。**  
   `ORLM-LLaMA-3-8B` 原生上下文为 8192，比其他模型短；这会影响其长 prompt 生成质量。

## 8. 后续建议

1. **补完两个 SIRL-32B 变体**  
   将 73/108 和 68/108 跑到 108/108 后再出最终排名。

2. **增加“原生 solver pipeline”对照**  
   对 GurobiPy / COPT 风格模型使用其原生 prompt 与执行器，区分“建模错误”和“协议适配错误”。

3. **增加格式归一化层**  
   在不改变数学语义的前提下，尝试把 `gurobipy`、`coptpy` 输出转换成 Pyomo 或直接接原生求解器。

4. **增加一轮受限 traceback 修复**  
   当前结果主要衡量一次性建模能力。可以另设 1–3 轮修复协议，观察执行失败能被恢复的比例。

5. **报告分层指标**  
   建议同时给出：
   - 代码提取率；
   - 可执行率；
   - 求解成功率；
   - 参考模型可行性率；
   - 目标值匹配率；
   - 最终 Pass@1 / Pass@6。

## 9. 结果位置

### 9.1 OptMATH-Qwen2.5-7B 高生成长度复测

为检验输出截断对 `OptMATH-Qwen2.5-7B` 的影响，另跑一次 `max_tokens=24576`（原为 `12288`）。旧结果已备份在：

- `eval_results/finetuned_sweep/generations/OptMATH-Qwen2.5-7B_max12288_20260903-173122/`
- `eval_results/finetuned_sweep/evals/OptMATH-Qwen2.5-7B_max12288_20260903-173122/`
- `eval_results/finetuned_sweep/scores/OptMATH-Qwen2.5-7B_max12288_20260903-173122.json`

| 配置 | 可提取 `build()` / 108 | 可判定 instance-run | 通过数 | Pass@1 | Pass@6 | 结论 |
|---|---:|---:|---:|---:|---:|---|
| `max_tokens=12288` | 94 | 738 | 0 | 0.00% | 0.00% | 原结果 |
| `max_tokens=24576` | 98 | 738 | 0 | 0.00% | 0.00% | 复测 |

提高生成长度后，提取失败从 14 个生成降到 10 个生成，但 108/108 个生成仍因 `length` 截断，平均输出约 24551 token。Pass@1 / Pass@6 保持为 0；738 个失败 instance-run 的细分见第 5.3 节。该复测说明单纯提高 `max_tokens` 不能解决该模型在本协议下的适配与建模错误。

| 内容 | 路径 |
|---|---|
| 生成 prompt / response / model | `dataset/industry_mathopt_dataset/eval_results/finetuned_sweep/generations/` |
| 每个模型执行结果 | `dataset/industry_mathopt_dataset/eval_results/finetuned_sweep/evals/` |
| 汇总日志 | `dataset/industry_mathopt_dataset/eval_results/finetuned_sweep/*.log` |
| 数据集问题目录 | `dataset/industry_mathopt_dataset/domains/` |

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
cd /public/chengyingying/project/IndustryOPT/dataset/industry_mathopt_dataset
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
