#!/usr/bin/env python3
"""Independent Code Grade evaluator for the long-horizon optimization case."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import os
from pathlib import Path
import shutil
import statistics
import subprocess
import tempfile
import time
from typing import Any, Iterable
import zipfile


WORKSPACE = Path(os.environ.get("LONGBENCH_GRADE_WORKSPACE", "/workspace"))
TEST_FILES = Path(os.environ.get("LONGBENCH_GRADE_TEST_FILES", "/test_files"))
EVAL_DIR = Path(os.environ.get("LONGBENCH_GRADE_EVAL", "/eval"))
RESULT_PATH = EVAL_DIR / "code_result.json"
LOGIC_NAMES = ("CMakeLists.txt", "include", "src")
COARSE_ZONES = {"Frame", "Input", "Update", "Checkpoint", "RunMetadata"}


class GradeError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_files(root: Path) -> list[Path]:
    result: list[Path] = []
    for name in LOGIC_NAMES:
        path = root / name
        if path.is_file():
            result.append(path)
        elif path.is_dir():
            result.extend(item for item in path.rglob("*") if item.is_file())
    return sorted(result, key=lambda item: item.relative_to(root).as_posix())


def logic_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in stable_files(root):
        relative = path.relative_to(root).as_posix().encode("utf-8")
        payload = path.read_bytes()
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(payload)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def safe_extract(archive: Path, destination: Path) -> None:
    root = destination.resolve()
    with zipfile.ZipFile(archive) as bundle:
        for member in bundle.infolist():
            target = (destination / member.filename).resolve()
            if target != root and root not in target.parents:
                raise GradeError("unsafe path in baseline archive")
        bundle.extractall(destination)


def run(command: list[str], *, cwd: Path, timeout: float, check: bool = True) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        env={**os.environ, "LC_ALL": "C", "LANG": "C"},
    )
    if check and completed.returncode != 0:
        raise GradeError(
            f"command failed ({completed.returncode}): {' '.join(command)}\n"
            + (completed.stderr or completed.stdout)[-2500:]
        )
    return completed


def build_project(root: Path, output: Path) -> Path:
    cmake = shutil.which("cmake")
    if cmake is None:
        raise GradeError("cmake is unavailable")
    command = [
        cmake, "-S", str(root), "-B", str(output),
        "-DCMAKE_BUILD_TYPE=Release",
        "-DLONGBENCH_ENABLE_PERFETTO=OFF",
        "-DLONGBENCH_WARNINGS_AS_ERRORS=OFF",
    ]
    if shutil.which("ninja"):
        command += ["-G", "Ninja"]
    for cmake_name, environment_name in (
        ("CMAKE_AR", "LONGBENCH_CMAKE_AR"),
        ("CMAKE_RANLIB", "LONGBENCH_CMAKE_RANLIB"),
    ):
        if os.environ.get(environment_name):
            command.append(f"-D{cmake_name}={os.environ[environment_name]}")
    run(command, cwd=root, timeout=120)
    run([cmake, "--build", str(output), "--config", "Release", "--target", "longbench", "--parallel"], cwd=root, timeout=240)
    suffix = ".exe" if os.name == "nt" else ""
    candidates = (output / f"longbench{suffix}", output / "Release" / f"longbench{suffix}")
    binary = next((path for path in candidates if path.is_file()), None)
    if binary is None:
        raise GradeError("longbench executable is missing")
    return binary


def case_arguments(case: dict[str, Any]) -> list[str]:
    mapping = (
        ("scenario", "--scenario"), ("seed", "--seed"),
        ("units", "--units"), ("navigators", "--navigators"),
        ("grid_width", "--grid-width"), ("grid_height", "--grid-height"),
        ("goals", "--goals"), ("warmup", "--warmup"),
        ("frames", "--frames"), ("history_capacity", "--history-capacity"),
        ("rollback_period", "--rollback-period"), ("rollback_depth", "--rollback-depth"),
        ("edit_period", "--edit-period"), ("edits", "--edits"),
        ("mutations", "--mutations"),
        ("transforms", "--transforms"), ("colliders", "--colliders"),
        ("events", "--events"),
        ("transform_mutations", "--transform-mutations"),
        ("reparent_period", "--reparent-period"),
        ("component_queries", "--component-queries"),
        ("structural_changes", "--structural-changes"),
        ("interest_observers", "--interest-observers"),
        ("interest_radius", "--interest-radius"),
        ("interest_movements", "--interest-movements"),
    )
    result: list[str] = []
    for key, flag in mapping:
        result += [flag, str(case[key])]
    return [*result, "--quiet"]


def execute_case(binary: Path, case: dict[str, Any], timeout: float) -> tuple[dict[str, Any], float]:
    start = time.perf_counter_ns()
    completed = run([str(binary), *case_arguments(case)], cwd=binary.parent, timeout=timeout)
    elapsed = (time.perf_counter_ns() - start) / 1_000_000_000.0
    if len(completed.stdout) > 64 * 1024:
        raise GradeError("excessive stdout")
    try:
        value = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise GradeError("longbench stdout is not JSON") from error
    if value.get("schema") != "longbench.run.v3":
        raise GradeError("result schema changed")
    return value, elapsed


def outputs_match(reference: dict[str, Any], candidate: dict[str, Any]) -> bool:
    fields = (
        "checksum", "route_digest", "rollback_digest", "transform_digest",
        "collision_digest", "event_digest", "query_digest", "interest_digest",
        "collision_pair_count", "query_match_count", "interest_visible_count",
        "units", "navigators", "frames", "transforms", "colliders",
        "events_per_frame", "component_queries", "interest_observers",
    )
    return all(reference.get(field) == candidate.get(field) for field in fields)


def measure_pair(
    baseline: Path,
    candidate: Path,
    case: dict[str, Any],
    rounds: int,
    timeout: float,
) -> tuple[bool, float, float, float]:
    reference, _ = execute_case(baseline, case, timeout)
    observed, _ = execute_case(candidate, case, timeout)
    correct = outputs_match(reference, observed)
    baseline_times: list[float] = []
    candidate_times: list[float] = []
    for round_index in range(rounds):
        order = ((baseline, baseline_times), (candidate, candidate_times))
        if round_index % 2:
            order = tuple(reversed(order))
        for binary, samples in order:
            _, elapsed = execute_case(binary, case, timeout)
            samples.append(elapsed)
    baseline_median = statistics.median(baseline_times)
    candidate_median = statistics.median(candidate_times)
    ratio = baseline_median / candidate_median if candidate_median > 0 else 0.0
    return correct, baseline_median, candidate_median, ratio


def query_trace(processor: Path, trace: Path) -> tuple[set[str], str | None, float, dict[str, dict[str, float]]]:
    zone_sql = (
        "SELECT name, COUNT(*) AS calls, SUM(dur) / 1000000.0 AS total_ms, "
        "AVG(dur) / 1000000.0 AS avg_ms, MAX(dur) / 1000000.0 AS max_ms "
        "FROM slice WHERE category GLOB 'longbench.*' AND dur >= 0 GROUP BY name ORDER BY name;"
    )
    metadata_sql = (
        "SELECT a.string_value AS source_hash FROM slice s JOIN args a USING(arg_set_id) "
        "WHERE s.name='RunMetadata' AND a.key IN ('source_hash','debug.source_hash') LIMIT 1;"
    )
    frame_sql = "SELECT SUM(dur) / 1000000.0 AS total_ms FROM slice WHERE name='Frame' AND dur >= 0;"

    def query(sql: str) -> list[dict[str, str]]:
        for command in ([str(processor), str(trace), "-Q", sql], [str(processor), "-Q", sql, str(trace)]):
            completed = run(command, cwd=WORKSPACE, timeout=30, check=False)
            if completed.returncode == 0 and completed.stdout.strip():
                return list(csv.DictReader(io.StringIO(completed.stdout)))
        return []

    zone_rows = query(zone_sql)
    metrics: dict[str, dict[str, float]] = {}
    for row in zone_rows:
        name = row.get("name", "")
        if not name:
            continue
        try:
            metrics[name] = {
                key: float(row.get(key, "0"))
                for key in ("calls", "total_ms", "avg_ms", "max_ms")
            }
        except (TypeError, ValueError):
            continue
    zones = set(metrics)
    metadata = query(metadata_sql)
    frames = query(frame_sql)
    try:
        frame_total_ms = float(frames[0].get("total_ms", "0")) if frames else 0.0
    except (TypeError, ValueError):
        frame_total_ms = 0.0
    return zones, metadata[0].get("source_hash") if metadata else None, frame_total_ms, metrics


def artifact(
    tag: str,
    expected_hash: str | None,
    processor: Path | None,
    minimum_trace_bytes: int,
) -> tuple[bool, dict[str, Any], set[str], Path, float, dict[str, dict[str, float]]]:
    directory = WORKSPACE / "artifacts" / tag
    manifest = load_json(directory / "manifest.json") or {}
    trace = directory / "profile.pftrace"
    run_file = directory / "run.json"
    good = bool(
        manifest.get("schema") == "longbench.artifact.v1"
        and manifest.get("tag") == tag
        and manifest.get("kind") == "profile_run"
        and trace.is_file()
        and trace.stat().st_size >= minimum_trace_bytes
        and manifest.get("trace_sha256") == sha256(trace)
        and run_file.is_file()
        and manifest.get("result_sha256") == sha256(run_file)
        and (load_json(run_file) or {}).get("schema") == "longbench.run.v3"
    )
    if expected_hash is not None:
        good = good and manifest.get("source_hash") == expected_hash
    zones: set[str] = set()
    metadata_hash = None
    frame_total_ms = 0.0
    metrics: dict[str, dict[str, float]] = {}
    if good and processor is not None:
        zones, metadata_hash, frame_total_ms, metrics = query_trace(processor, trace)
        good = metadata_hash == manifest.get("source_hash")
    else:
        good = False
    return good, manifest, zones, trace, frame_total_ms, metrics


def safe_workspace_file(value: Any) -> bool:
    try:
        relative = Path(str(value))
        if relative.is_absolute() or ".." in relative.parts:
            return False
        resolved = (WORKSPACE / relative).resolve()
        return resolved.is_relative_to(WORKSPACE.resolve()) and resolved.is_file()
    except (OSError, ValueError):
        return False


def source_contains(file_value: Any, symbol_value: Any) -> bool:
    if not safe_workspace_file(file_value) or not isinstance(symbol_value, str) or not symbol_value.strip():
        return False
    try:
        return symbol_value in (WORKSPACE / Path(str(file_value))).read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False


def score_workflow(config: dict[str, Any], final_hash: str) -> tuple[float, list[str]]:
    notes: list[str] = []
    points = 0.0
    processor = WORKSPACE / str(config["trace_processor_path"])
    if not processor.is_file() or sha256(processor) != config["trace_processor_sha256"]:
        processor = None
        notes.append("pinned trace processor missing or modified")
    original_hash = str(config["original_logic_hash"])
    minimum_bytes = int(config.get("minimum_trace_bytes", 2048))
    tags = (
        "baseline", "diagnostic_primary", "checkpoint_primary",
        "diagnostic_state", "checkpoint_state", "diagnostic_scale",
        "checkpoint_scale", "diagnostic_tail", "optimized",
    )
    expected = (original_hash, None, None, None, None, None, None, None, final_hash)
    values = {
        tag: artifact(tag, expected_hash, processor, minimum_bytes)
        for tag, expected_hash in zip(tags, expected)
    }
    runs = {
        tag: load_json(WORKSPACE / "artifacts" / tag / "run.json") or {}
        for tag in tags
    }
    baseline_checksum = runs["baseline"].get("checksum")
    same_public_result = bool(
        baseline_checksum
        and all(run.get("checksum") == baseline_checksum for run in runs.values())
    )

    def markers(tag: str) -> set[str]:
        return values[tag][2] - COARSE_ZONES

    minimum_gain = float(config.get("workflow_stage_gain", 1.04))

    def stage_gain(before: str, after: str) -> bool:
        before_ms = values[before][4]
        after_ms = values[after][4]
        return (
            before_ms > 0.0 and after_ms > 0.0
            and before_ms / after_ms >= minimum_gain
        )

    baseline_ok, _, baseline_zones, _, _, _ = values["baseline"]
    if baseline_ok and COARSE_ZONES.issubset(baseline_zones):
        points += 2
    else:
        notes.append("baseline trace/provenance incomplete")

    diagnostic_tags = (
        "diagnostic_primary", "diagnostic_state",
        "diagnostic_scale", "diagnostic_tail",
    )
    previous_markers: set[str] = set()
    prior_hashes = {original_hash}
    diagnostic_manifests: dict[str, dict[str, Any]] = {}
    for index, tag in enumerate(diagnostic_tags, 1):
        good, manifest_value, _, _, _, _ = values[tag]
        live = markers(tag)
        source_hash = manifest_value.get("source_hash")
        diagnostic_manifests[tag] = manifest_value
        if (
            good and source_hash not in prior_hashes
            and len(live) >= index * 2
            and len(live - previous_markers) >= 2
        ):
            points += 2
        else:
            notes.append(
                f"diagnostic {index} lacks a distinct hash or {index * 2} cumulative live markers"
            )
        if source_hash:
            prior_hashes.add(source_hash)
        previous_markers = live

    checkpoint_pairs = (
        ("checkpoint_primary", "baseline", "diagnostic_primary", 2),
        ("checkpoint_state", "checkpoint_primary", "diagnostic_state", 4),
        ("checkpoint_scale", "checkpoint_state", "diagnostic_scale", 6),
    )
    checkpoint_hashes: set[str] = set()
    for index, (tag, before, diagnostic_tag, marker_count) in enumerate(checkpoint_pairs, 1):
        good, manifest_value, _, _, _, _ = values[tag]
        source_hash = manifest_value.get("source_hash")
        diagnostic_hash = diagnostic_manifests[diagnostic_tag].get("source_hash")
        if (
            good and source_hash
            and source_hash not in prior_hashes
            and source_hash != diagnostic_hash
            and source_hash not in checkpoint_hashes
            and same_public_result
            and len(markers(tag)) >= marker_count
            and stage_gain(before, tag)
        ):
            points += 2
        else:
            notes.append(
                f"checkpoint {index} lacks exact output, distinct source or {minimum_gain:.2f}x raw-frame gain"
            )
        if source_hash:
            checkpoint_hashes.add(source_hash)
            prior_hashes.add(source_hash)

    findings = load_json(WORKSPACE / "artifacts" / "analysis" / "findings.json") or {}
    items = findings.get("findings")
    findings_ok = bool(
        findings.get("schema") == "longbench.findings.v3"
        and isinstance(items, list) and 4 <= len(items) <= 8
    )
    phases = set()
    phase_tags = {
        "primary": "diagnostic_primary",
        "state": "diagnostic_state",
        "scale": "diagnostic_scale",
        "tail": "diagnostic_tail",
    }

    def evidence_matches(tag: str, item: Any) -> bool:
        if not isinstance(item, dict):
            return False
        zone = item.get("zone")
        metric = item.get("metric")
        claimed = item.get("value")
        if (
            zone not in markers(tag)
            or metric not in {"calls", "total_ms", "avg_ms", "max_ms"}
            or not isinstance(claimed, (int, float))
            or isinstance(claimed, bool)
        ):
            return False
        actual = values[tag][5].get(str(zone), {}).get(str(metric))
        if actual is None:
            return False
        tolerance = 0.1 if metric == "calls" else max(0.25, abs(actual) * 0.15)
        return abs(float(claimed) - actual) <= tolerance

    if findings_ok:
        for index, finding in enumerate(items, 1):
            phase = finding.get("phase") if isinstance(finding, dict) else None
            source = finding.get("source", {}) if isinstance(finding, dict) else {}
            expected_tag = phase_tags.get(phase)
            evidence = finding.get("evidence") if isinstance(finding, dict) else None
            evidence_ok = bool(
                isinstance(evidence, list) and evidence and expected_tag in values
                and all(evidence_matches(expected_tag, item) for item in evidence)
            )
            findings_ok = bool(
                findings_ok and finding.get("rank") == index
                and phase in phase_tags
                and finding.get("trace_tag") == expected_tag
                and finding.get("root_cause") in config["allowed_root_causes"]
                and source_contains(source.get("file"), source.get("symbol"))
                and evidence_ok and finding.get("proposed_change")
            )
            phases.add(phase)
    if findings_ok and phases == set(phase_tags):
        points += 3
    else:
        notes.append("ranked findings do not cover all four measured diagnoses")

    optimized_ok, _, _, _, _, _ = values["optimized"]
    if (
        optimized_ok and same_public_result
        and len(markers("optimized")) >= 8
        and stage_gain("checkpoint_scale", "optimized")
    ):
        points += 2
    else:
        notes.append("final revision lacks exact output, eight markers or fourth raw-frame gain")

    comparison = load_json(WORKSPACE / "artifacts" / "comparison" / "comparison.json") or {}
    manifests = [values[tag][1] for tag in tags]
    try:
        source_hashes = [item["source_hash"] for item in manifests]
        trace_hashes = [sha256(values[tag][3]) for tag in tags]
        timestamps = [str(item["created_at"]) for item in manifests]
        provenance_ok = (
            len(set(source_hashes)) == 9
            and len(set(trace_hashes)) == 9
            and timestamps == sorted(timestamps)
            and comparison.get("schema") == "longbench.comparison.v3"
            and comparison.get("source_hashes") == [
                source_hashes[0], source_hashes[2], source_hashes[4],
                source_hashes[6], source_hashes[8],
            ]
            and comparison.get("checksum") == baseline_checksum
            and comparison.get("first_stage_speedup", 0) > 1.0
            and comparison.get("second_stage_speedup", 0) > 1.0
            and comparison.get("third_stage_speedup", 0) > 1.0
            and comparison.get("fourth_stage_speedup", 0) > 1.0
            and comparison.get("end_to_end_speedup", 0) > 1.0
        )
    except (KeyError, OSError, TypeError):
        provenance_ok = False
    if provenance_ok:
        points += 4
    else:
        notes.append("nine-trace ordering/comparison provenance incomplete")
    return points, notes


def speed_points(geomean: float, ratios: dict[str, float], thresholds: dict[str, float]) -> float:
    family_points = 0.0
    family_budget = 21.0
    per_family = family_budget / max(1, len(thresholds["family_speedups"]))
    for family, floor in thresholds["family_speedups"].items():
        ratio = ratios.get(family, 0.0)
        family_points += per_family * min(
            1.0, max(0.0, (ratio - 1.0) / (float(floor) - 1.0))
        )
    knots = ((1.0, 0.0), (1.5, 6.0), (2.1, 13.0), (4.0, 20.0), (8.0, 24.0))
    geo_points = 0.0
    if geomean > 1.0:
        for (x0, y0), (x1, y1) in zip(knots, knots[1:]):
            if geomean <= x1:
                fraction = (math.log(geomean) - math.log(x0)) / (math.log(x1) - math.log(x0))
                geo_points = y0 + fraction * (y1 - y0)
                break
        else:
            geo_points = 24.0
    return min(45.0, family_points + geo_points)


def apply_score_policy(
    raw_total: float,
    resolved: bool,
    gate_coverage: float,
    unresolved_score_cap: float,
) -> tuple[float, float, bool]:
    """Return reported points, weakest-gate multiplier and whether the cap applied."""
    score_multiplier = 1.0 if resolved else 0.65 + 0.35 * gate_coverage
    uncapped_total = raw_total * score_multiplier
    if resolved:
        return uncapped_total, score_multiplier, False
    cap_points = 100.0 * max(0.0, min(1.0, unresolved_score_cap))
    return min(uncapped_total, cap_points), score_multiplier, uncapped_total > cap_points


def write_result(resolved: bool, score: float, reason: str) -> None:
    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(
        json.dumps({"resolved": bool(resolved), "score": max(0.0, min(1.0, float(score))), "reason": str(reason)}, ensure_ascii=False),
        encoding="utf-8",
    )


def grade() -> tuple[bool, float, str]:
    config = load_json(TEST_FILES / "grader_config.json")
    if config is None:
        raise GradeError("grader config is missing")
    baseline_archive = TEST_FILES / str(config["baseline_archive"])
    if sha256(baseline_archive) != config["baseline_archive_sha256"]:
        raise GradeError("baseline archive hash mismatch")

    final_hash = logic_hash(WORKSPACE)
    with tempfile.TemporaryDirectory(prefix="longbench-grade-") as temporary:
        temp = Path(temporary)
        baseline_root = temp / "baseline"
        safe_extract(baseline_archive, baseline_root)
        if logic_hash(baseline_root) != config["original_logic_hash"]:
            raise GradeError("baseline logic hash mismatch")
        baseline_binary = build_project(baseline_root, temp / "build-baseline")
        candidate_binary = build_project(WORKSPACE, temp / "build-candidate")

        semantic_passes = 0
        semantic_total = len(config["semantic_cases"])
        for case in config["semantic_cases"]:
            reference, _ = execute_case(baseline_binary, case, config["case_timeout_seconds"])
            observed, _ = execute_case(candidate_binary, case, config["case_timeout_seconds"])
            semantic_passes += int(outputs_match(reference, observed))

        case_ratios: dict[str, list[tuple[str, float]]] = {}
        performance_correct = True
        timing_rows: list[tuple[str, str, bool, float, float, float]] = []
        for case in config["performance_cases"]:
            correct, baseline_time, candidate_time, ratio = measure_pair(
                baseline_binary,
                candidate_binary,
                case,
                int(config.get("timing_rounds", 3)),
                float(config["case_timeout_seconds"]),
            )
            performance_correct = performance_correct and correct
            effective_ratio = ratio if correct else 0.0
            case_ratios.setdefault(str(case["family"]), []).append(
                (str(case["id"]), effective_ratio)
            )
            timing_rows.append((
                str(case["id"]), str(case["family"]), correct, ratio,
                baseline_time, candidate_time,
            ))

    all_correct = semantic_passes == semantic_total and performance_correct
    correctness_score = 25.0 * semantic_passes / semantic_total
    ratios = {
        family: math.exp(sum(math.log(max(0.01, ratio)) for _, ratio in values) / len(values))
        for family, values in case_ratios.items()
    }
    worst_ratios = {
        family: min(ratio for _, ratio in values)
        for family, values in case_ratios.items()
    }
    positive_ratios = [max(0.01, ratio) for ratio in ratios.values()]
    geomean = math.exp(sum(math.log(value) for value in positive_ratios) / len(positive_ratios)) if positive_ratios else 0.0
    thresholds = config["resolved_thresholds"]
    performance_score = speed_points(geomean, ratios, thresholds) if all_correct else 0.0
    workflow_score, workflow_notes = score_workflow(config, final_hash)
    hygiene_score = 5.0 if final_hash != config["original_logic_hash"] and all_correct else 0.0
    raw_total = correctness_score + performance_score + workflow_score + hygiene_score
    case_floor_fraction = float(thresholds.get("case_floor_fraction", 0.9))
    family_ok = all(
        ratios.get(family, 0.0) >= float(floor)
        for family, floor in thresholds["family_speedups"].items()
    )
    case_floor_ok = all(
        worst_ratios.get(family, 0.0) >= float(floor) * case_floor_fraction
        for family, floor in thresholds["family_speedups"].items()
    )
    resolved = bool(
        all_correct
        and family_ok
        and case_floor_ok
        and geomean >= float(thresholds["geomean_speedup"])
        and workflow_score >= float(thresholds["workflow_points"])
    )
    gate_coverages = [
        ratios.get(family, 0.0) / float(floor)
        for family, floor in thresholds["family_speedups"].items()
    ] + [
        worst_ratios.get(family, 0.0) / (float(floor) * case_floor_fraction)
        for family, floor in thresholds["family_speedups"].items()
    ] + [
        geomean / float(thresholds["geomean_speedup"]),
        workflow_score / float(thresholds["workflow_points"]),
        semantic_passes / semantic_total,
        1.0 if performance_correct else 0.0,
    ]
    gate_coverage = min(1.0, max(0.0, min(gate_coverages))) if gate_coverages else 0.0
    unresolved_score_cap = float(thresholds.get("unresolved_score_cap", 0.79))
    total, score_multiplier, score_was_capped = apply_score_policy(
        raw_total, resolved, gate_coverage, unresolved_score_cap
    )
    failed_gates: list[str] = []
    if semantic_passes != semantic_total:
        failed_gates.append(f"semantics {semantic_passes}/{semantic_total}")
    if not performance_correct:
        failed_gates.append("performance_correctness")
    for family, floor in thresholds["family_speedups"].items():
        if ratios.get(family, 0.0) < float(floor):
            failed_gates.append(
                f"{family}_aggregate {ratios.get(family, 0.0):.2f}<{float(floor):.2f}x"
            )
        if worst_ratios.get(family, 0.0) < float(floor) * case_floor_fraction:
            failed_gates.append(
                f"{family}_worst {worst_ratios.get(family, 0.0):.2f}<"
                f"{float(floor) * case_floor_fraction:.2f}x"
            )
    if geomean < float(thresholds["geomean_speedup"]):
        failed_gates.append(
            f"geomean {geomean:.2f}<{float(thresholds['geomean_speedup']):.2f}x"
        )
    if workflow_score < float(thresholds["workflow_points"]):
        failed_gates.append(
            f"workflow {workflow_score:.0f}<{float(thresholds['workflow_points']):.0f}"
        )
    timing_notes = []
    for identifier, family, correct, ratio, baseline_time, candidate_time in timing_rows:
        floor = float(thresholds["family_speedups"][family]) * case_floor_fraction
        guard_state = "pass" if correct and ratio >= floor else "FAIL"
        guard_operator = ">=" if guard_state == "pass" else "<"
        timing_notes.append(
            f"{identifier}=correct:{'yes' if correct else 'no'},case_guard:{guard_state},"
            f"{ratio:.2f}x{guard_operator}{floor:.3f}x({baseline_time:.2f}/{candidate_time:.2f}s)"
        )
    family_notes = []
    for family, floor_value in thresholds["family_speedups"].items():
        floor = float(floor_value)
        ratio = ratios.get(family, 0.0)
        family_state = "pass" if ratio >= floor else "FAIL"
        family_operator = ">=" if family_state == "pass" else "<"
        family_notes.append(
            f"{family}=family_gate:{family_state},{ratio:.2f}x{family_operator}{floor:.2f}x"
        )
    reason = (
        f"semantics {semantic_passes}/{semantic_total}, performance correctness={'ok' if performance_correct else 'wrong'}; "
        f"speed geo {geomean:.2f}x; case guards [{', '.join(timing_notes)}]; "
        f"family gates [{', '.join(family_notes)}]; "
        f"workflow {workflow_score:.0f}/25; raw {raw_total:.1f}/100, "
        f"gate coverage {gate_coverage:.2f}, multiplier {score_multiplier:.3f}, "
        f"reported {total:.1f}/100"
    )
    if score_was_capped:
        reason += (
            f" (pre-cap {raw_total * score_multiplier:.1f}, "
            f"unresolved cap {100.0 * unresolved_score_cap:.1f})"
        )
    if failed_gates:
        reason += "; failed gates: " + ", ".join(failed_gates[:6])
    if workflow_notes:
        reason += "; missing: " + ", ".join(workflow_notes[:3])
    return resolved, total / 100.0, reason


def main() -> int:
    try:
        resolved, score, reason = grade()
    except Exception as error:
        resolved, score, reason = False, 0.0, f"grader failed safely: {type(error).__name__}: {error}"
    write_result(resolved, score, reason)
    print(RESULT_PATH.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
