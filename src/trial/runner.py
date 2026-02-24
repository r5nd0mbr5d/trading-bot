"""Batch runner for executing multiple paper trial manifests."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, pstdev
from typing import Callable

from src.trial.manifest import TrialManifest


@dataclass
class TrialRunResult:
    name: str
    strategy: str
    status: str
    exit_code: int
    output_dir: str
    metrics: dict
    error: str | None = None


class TrialAndRunner:
    """Runs a batch of TrialManifest configs and produces aggregate report."""

    def __init__(
        self,
        trial_executor: Callable[[TrialManifest], dict],
        *,
        parallel: bool = False,
        max_workers: int = 4,
    ):
        self._trial_executor = trial_executor
        self._parallel = parallel
        self._max_workers = max(1, max_workers)

    def run(self, manifests: list[TrialManifest], output_dir: str) -> dict:
        if not manifests:
            raise ValueError("No manifests provided for trial batch run")

        if self._parallel and len(manifests) > 1:
            results = self._run_parallel(manifests)
        else:
            results = [self._run_one(manifest) for manifest in manifests]

        aggregate = self._aggregate_metrics(results)
        pass_thresholds = {
            "win_rate_mean_gt": 0.50,
            "profit_factor_mean_gt": 1.10,
        }
        overall_passed = bool(
            aggregate.get("win_rate", {}).get("mean", -1) > pass_thresholds["win_rate_mean_gt"]
            and aggregate.get("profit_factor", {}).get("mean", -1)
            > pass_thresholds["profit_factor_mean_gt"]
        )

        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "trial_count": len(results),
            "successful_trials": sum(1 for result in results if result.status == "passed"),
            "failed_trials": sum(1 for result in results if result.status != "passed"),
            "parallel": self._parallel,
            "pass_thresholds": pass_thresholds,
            "overall_passed": overall_passed,
            "aggregate_metrics": aggregate,
            "trials": [asdict(result) for result in results],
        }

        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        report_path = out_dir / "trial_batch_report.json"
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        report["report_path"] = str(report_path)
        return report

    def _run_parallel(self, manifests: list[TrialManifest]) -> list[TrialRunResult]:
        ordered_results: dict[int, TrialRunResult] = {}
        with ThreadPoolExecutor(max_workers=min(self._max_workers, len(manifests))) as pool:
            future_map = {
                pool.submit(self._run_one, manifest): idx for idx, manifest in enumerate(manifests)
            }
            for future in as_completed(future_map):
                idx = future_map[future]
                ordered_results[idx] = future.result()
        return [ordered_results[idx] for idx in range(len(manifests))]

    def _run_one(self, manifest: TrialManifest) -> TrialRunResult:
        try:
            execution = self._trial_executor(manifest)
            exit_code = int(execution.get("exit_code", 1))
            summary = execution.get("summary", {}) or {}
            metrics = {
                "fill_rate": summary.get("fill_rate"),
                "win_rate": summary.get("win_rate"),
                "avg_slippage_pct": summary.get("avg_slippage_pct"),
                "profit_factor": summary.get("profit_factor"),
            }
            status = "passed" if exit_code == 0 else "failed"
            return TrialRunResult(
                name=manifest.name,
                strategy=manifest.strategy,
                status=status,
                exit_code=exit_code,
                output_dir=execution.get("output_dir", manifest.output_dir),
                metrics=metrics,
                error=execution.get("error"),
            )
        except Exception as exc:
            return TrialRunResult(
                name=manifest.name,
                strategy=manifest.strategy,
                status="failed",
                exit_code=1,
                output_dir=manifest.output_dir,
                metrics={},
                error=str(exc),
            )

    def _aggregate_metrics(self, results: list[TrialRunResult]) -> dict:
        metric_names = ["fill_rate", "win_rate", "avg_slippage_pct", "profit_factor"]
        aggregate: dict[str, dict] = {}
        for metric in metric_names:
            values = [
                float(result.metrics[metric])
                for result in results
                if metric in result.metrics and isinstance(result.metrics[metric], (int, float))
            ]
            if not values:
                aggregate[metric] = {
                    "count": 0,
                    "mean": None,
                    "std": None,
                    "min": None,
                    "max": None,
                }
                continue
            aggregate[metric] = {
                "count": len(values),
                "mean": mean(values),
                "std": pstdev(values) if len(values) > 1 else 0.0,
                "min": min(values),
                "max": max(values),
            }
        return aggregate
