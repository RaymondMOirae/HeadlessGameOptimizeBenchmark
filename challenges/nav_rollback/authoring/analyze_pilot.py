#!/usr/bin/env python3
"""Aggregate DSBench Code Grade results for threshold calibration."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import re
import statistics
from typing import Any


FAMILY_PATTERN = re.compile(r"([a-z_]+)=(?:ok|wrong):([0-9.]+)x")
SEMANTIC_PATTERN = re.compile(r"semantics (\d+)/(\d+)")
WORKFLOW_PATTERN = re.compile(r"workflow ([0-9.]+)/25")


def percentile(values: list[float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = quantile * (len(ordered) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def wilson(successes: int, total: int) -> list[float] | None:
    if total == 0:
        return None
    z = 1.959963984540054
    rate = successes / total
    denominator = 1.0 + z * z / total
    center = (rate + z * z / (2.0 * total)) / denominator
    radius = z * math.sqrt(rate * (1.0 - rate) / total + z * z / (4.0 * total * total)) / denominator
    return [max(0.0, center - radius), min(1.0, center + radius)]


def load_results(directory: Path) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for path in sorted(directory.rglob("code_result.json")):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(value, dict) and isinstance(value.get("resolved"), bool):
            value = dict(value)
            value["_path"] = str(path)
            results.append(value)
    return results


def summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
    resolved = sum(bool(item["resolved"]) for item in results)
    scores = [float(item.get("score", 0.0)) for item in results]
    semantic_full = 0
    workflow_gate = 0
    families: dict[str, list[float]] = {}
    for item in results:
        reason = str(item.get("reason", ""))
        semantic = SEMANTIC_PATTERN.search(reason)
        if semantic and semantic.group(1) == semantic.group(2):
            semantic_full += 1
        workflow = WORKFLOW_PATTERN.search(reason)
        if workflow and float(workflow.group(1)) >= 18.0:
            workflow_gate += 1
        for family, ratio in FAMILY_PATTERN.findall(reason):
            families.setdefault(family, []).append(float(ratio))

    family_summary = {
        family: {
            "samples": len(values),
            "p25_speedup": percentile(values, 0.25),
            "median_speedup": statistics.median(values),
            "p75_speedup": percentile(values, 0.75),
        }
        for family, values in sorted(families.items())
    }
    total = len(results)
    return {
        "runs": total,
        "resolved": resolved,
        "pass_rate": resolved / total if total else None,
        "pass_rate_wilson_95": wilson(resolved, total),
        "score_median": statistics.median(scores) if scores else None,
        "score_p25": percentile(scores, 0.25),
        "score_p75": percentile(scores, 0.75),
        "full_semantics_rate": semantic_full / total if total else None,
        "workflow_gate_rate": workflow_gate / total if total else None,
        "families": family_summary,
    }


def parse_group(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("group must be MODEL=RESULT_DIRECTORY")
    name, raw_path = value.split("=", 1)
    if not name or not raw_path:
        raise argparse.ArgumentTypeError("group must be MODEL=RESULT_DIRECTORY")
    return name, Path(raw_path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--group", action="append", required=True, type=parse_group)
    parser.add_argument("--minimum-runs", type=int, default=12)
    parser.add_argument("--target-min", type=float, default=0.10)
    parser.add_argument("--target-max", type=float, default=0.30)
    args = parser.parse_args()
    if not 0.0 <= args.target_min < args.target_max <= 1.0:
        parser.error("target band must satisfy 0 <= min < max <= 1")

    groups: dict[str, dict[str, Any]] = {}
    pooled: list[dict[str, Any]] = []
    for name, directory in args.group:
        values = load_results(directory)
        pooled.extend(values)
        groups[name] = summarize(values)

    pooled_summary = summarize(pooled)
    rate = pooled_summary["pass_rate"]
    if len(pooled) < args.minimum_runs * len(groups):
        status = "insufficient_samples"
    elif rate is not None and args.target_min <= rate <= args.target_max:
        status = "in_target_band"
    elif rate is not None and rate > args.target_max:
        status = "too_easy"
    else:
        status = "too_hard"

    print(json.dumps({
        "schema": "longbench.pilot-summary.v1",
        "target_pass_rate": [args.target_min, args.target_max],
        "status": status,
        "groups": groups,
        "pooled": pooled_summary,
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
