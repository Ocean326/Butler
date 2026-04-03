# loop_spec 模板

> 用于定义一次 `idea_loop` run 的输入边界与完成标准。

## 1. 基本信息

- `run_id`:
- `task_slug`:
- `created_at`:
- `owner`:
- `baseline_ref`:

## 2. 研究问题

- `problem_statement`: 这次要解决什么问题？
- `current_baseline`: 当前 baseline 是什么？
- `hypothesis`: 这次方法改进的核心假设是什么？
- `expected_signal`: 预期看到什么变化？

## 3. 作用域

### 允许改动

- `editable_scope`:
  - 

### 禁止改动

- `frozen_scope`:
  - 

## 4. 评测设置

- `primary_metric`:
- `secondary_metrics`:
  - 
- `eval_entrypoint`:
- `smoke_test_entrypoint`:
- `final_verify_entrypoint`:

## 5. 预算与护栏

- `max_iterations`: 3
- `time_budget_sec`:
- `compute_budget`:
- `risk_notes`:
  - 

## 6. 完成标准

- `done_criteria`:
  - 
- `fail_fast_criteria`:
  - 
- `pivot_trigger`:
  - 

## 7. 交付物

- `required_outputs`:
  - `plan.md`
  - `metrics.json`
  - `acceptance.json`
  - `decision.json`
  - `lesson.md`
  - `final_report.md`
