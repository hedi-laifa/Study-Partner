# Assessment Evaluation Suite (Phase 6)

Human-reviewed benchmark dataset and agreement evaluation runner for the **Study Partner AI Assessment Agent**.

## Contents
- `human_reviewed_benchmark.json`: 18 human-reviewed student answers across 4 university CS concepts (`Virtual Memory & MMU`, `TLB Effective Access Time`, `Raft Leader Election`, `Priority Scheduling & Starvation`) spanning all 6 required answer categories:
  1. `correct` (conceptual + numerical calculation)
  2. `partial` (incomplete reasoning without misconceptions)
  3. `incorrect` (supported misconceptions with quote evidence + deterministic numerical calculation errors)
  4. `vague` (non-answers, generic filler, ultra-short responses)
  5. `off-topic` (unrelated biology/database answers)
  6. `ambiguous` (hedged/self-contradictory answers requiring uncertain evaluation $\le 0.55$ confidence)
- `benchmark_assessment.py`: Executable runner that evaluates all 18 cases via `AssessmentAgentService` and writes `latest_benchmark_report.json`.
- `latest_benchmark_report.json`: Latest agreement metrics report (`verdict_accuracy = 1.0`, `cohens_kappa = 1.0`, `misconception_precision = 1.0`, `misconception_recall = 1.0`, `uncertainty_calibration_rate = 1.0`).

## Running the Benchmark
```powershell
.\backend\.venv\Scripts\python.exe evaluation/assessment/benchmark_assessment.py
```
