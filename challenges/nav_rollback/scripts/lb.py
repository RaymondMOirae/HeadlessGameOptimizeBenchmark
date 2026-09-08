#!/usr/bin/env python3
"""Build, capture, analyze and compare the long-horizon headless benchmark."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
AUTHOR_ROOT = ROOT.parents[1]
ARTIFACTS = ROOT / "artifacts"
LOGIC_PATHS = (ROOT / "CMakeLists.txt", ROOT / "include", ROOT / "src")
ROOT_CAUSES = {
    "repeated_search",
    "redundant_work",
    "allocation",
    "poor_locality",
    "copy_amplification",
    "cache_invalidation",
    "serialization",
    "branching",
    "dirty_propagation",
    "pair_generation",
    "event_churn",
    "temporal_state",
    "component_query",
    "structural_churn",
    "interest_management",
    "spatial_index",
}


def stable_files(paths: Iterable[Path]) -> list[Path]:
    result: list[Path] = []
    for path in paths:
        if path.is_file():
            result.append(path)
        elif path.is_dir():
            result.extend(item for item in path.rglob("*") if item.is_file())
    return sorted(result, key=lambda item: item.relative_to(ROOT).as_posix())


def logic_hash() -> str:
    digest = hashlib.sha256()
    for path in stable_files(LOGIC_PATHS):
        relative = path.relative_to(ROOT).as_posix().encode("utf-8")
        payload = path.read_bytes()
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(payload)
    return digest.hexdigest()


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def find_program(name: str) -> str | None:
    return shutil.which(name)


def run_checked(command: list[str], *, capture: bool = False) -> subprocess.CompletedProcess[str]:
    print("+ " + " ".join(command), file=sys.stderr)
    return subprocess.run(
        command,
        cwd=ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
    )


def build_dir(profile: bool) -> Path:
    suffix = os.environ.get("LONGBENCH_BUILD_SUFFIX", "")
    return ROOT / (("build-profile" if profile else "build-release") + suffix)


def executable(profile: bool) -> Path:
    suffix = ".exe" if os.name == "nt" else ""
    candidates = (
        build_dir(profile) / f"longbench{suffix}",
        build_dir(profile) / "Release" / f"longbench{suffix}",
    )
    return next((path for path in candidates if path.is_file()), candidates[0])


def configure_and_build(profile: bool) -> Path:
    cmake = find_program("cmake")
    if cmake is None:
        raise RuntimeError("cmake is not on PATH")
    output = build_dir(profile)
    output.mkdir(parents=True, exist_ok=True)
    command = [
        cmake,
        "-S", str(ROOT),
        "-B", str(output),
        f"-DLONGBENCH_ENABLE_PERFETTO={'ON' if profile else 'OFF'}",
        f"-DLONGBENCH_SOURCE_HASH={logic_hash()}",
        f"-DCMAKE_BUILD_TYPE={'RelWithDebInfo' if profile else 'Release'}",
    ]
    for cmake_name, environment_name in (
        ("CMAKE_AR", "LONGBENCH_CMAKE_AR"),
        ("CMAKE_RANLIB", "LONGBENCH_CMAKE_RANLIB"),
    ):
        if os.environ.get(environment_name):
            command.append(f"-D{cmake_name}={os.environ[environment_name]}")
    if not (output / "CMakeCache.txt").exists() and find_program("ninja"):
        command += ["-G", "Ninja"]
    run_checked(command)
    run_checked([cmake, "--build", str(output), "--config", "Release", "--parallel"])
    binary = executable(profile)
    if not binary.is_file():
        raise RuntimeError(f"build did not produce {binary}")
    return binary


def trace_processor() -> Path | None:
    candidates = [
        ROOT / "tools" / "perfetto" / "bin" / "trace_processor_shell.exe",
        ROOT / "tools" / "perfetto" / "bin" / "trace_processor_shell",
        AUTHOR_ROOT / "tools" / "perfetto" / "bin" / "trace_processor_shell.exe",
        AUTHOR_ROOT / "tools" / "perfetto" / "bin" / "trace_processor_shell",
    ]
    from_path = find_program("trace_processor_shell")
    if from_path:
        candidates.append(Path(from_path))
    return next((path for path in candidates if path.is_file()), None)


def perfetto_sdk() -> Path | None:
    candidates = (
        ROOT / "third_party" / "perfetto" / "perfetto.cc",
        AUTHOR_ROOT / "third_party" / "perfetto" / "perfetto.cc",
    )
    return next((path.parent for path in candidates if path.is_file()), None)


def execute_query(trace: Path, sql: str) -> list[dict[str, str]]:
    processor = trace_processor()
    if processor is None:
        raise RuntimeError("trace processor is missing")
    failures: list[str] = []
    for command in (
        [str(processor), str(trace), "-Q", sql],
        [str(processor), "-Q", sql, str(trace)],
    ):
        completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
        if completed.returncode == 0 and completed.stdout.strip():
            return list(csv.DictReader(io.StringIO(completed.stdout)))
        failures.append(completed.stderr[-1200:])
    raise RuntimeError("unable to query trace: " + " | ".join(failures))


def create_report(trace: Path) -> dict[str, Any]:
    zones = execute_query(trace, (ROOT / "queries" / "zone_summary.sql").read_text())
    frames = execute_query(trace, (ROOT / "queries" / "frame_summary.sql").read_text())
    return {
        "schema": "longbench.profile-report.v1",
        "trace": str(trace.relative_to(ROOT)) if trace.is_relative_to(ROOT) else str(trace),
        "trace_sha256": file_hash(trace),
        "zones": zones,
        "frame_summary": frames[0] if frames else {},
    }


def workload_arguments(args: argparse.Namespace) -> list[str]:
    command = ["--scenario", args.scenario, "--seed", str(args.seed)]
    mappings = (
        ("--units", "units"),
        ("--navigators", "navigators"),
        ("--grid-width", "grid_width"),
        ("--grid-height", "grid_height"),
        ("--goals", "goals"),
        ("--warmup", "warmup"),
        ("--frames", "frames"),
        ("--history-capacity", "history_capacity"),
        ("--rollback-period", "rollback_period"),
        ("--rollback-depth", "rollback_depth"),
        ("--edit-period", "edit_period"),
        ("--edits", "edits"),
        ("--mutations", "mutations"),
        ("--transforms", "transforms"),
        ("--colliders", "colliders"),
        ("--events", "events"),
        ("--transform-mutations", "transform_mutations"),
        ("--reparent-period", "reparent_period"),
        ("--component-queries", "component_queries"),
        ("--structural-changes", "structural_changes"),
        ("--interest-observers", "interest_observers"),
        ("--interest-radius", "interest_radius"),
        ("--interest-movements", "interest_movements"),
    )
    for flag, attribute in mappings:
        value = getattr(args, attribute, None)
        if value is not None:
            command += [flag, str(value)]
    return command


def parse_run(completed: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError("longbench did not emit one JSON object") from error
    if result.get("schema") != "longbench.run.v3":
        raise RuntimeError("longbench result schema changed")
    return result


def manifest(tag: str, binary: Path, command: list[str]) -> dict[str, Any]:
    return {
        "schema": "longbench.artifact.v1",
        "tag": tag,
        "kind": "profile_run",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_hash": logic_hash(),
        "binary_sha256": file_hash(binary),
        "command": command,
    }


def command_doctor(_: argparse.Namespace) -> int:
    checks = {
        "python": sys.executable,
        "cmake": find_program("cmake"),
        "ninja": find_program("ninja"),
        "cxx": find_program("c++") or find_program("clang++") or find_program("g++") or find_program("cl"),
        "perfetto_sdk": str(perfetto_sdk()) if perfetto_sdk() else None,
        "trace_processor": str(trace_processor()) if trace_processor() else None,
    }
    print(json.dumps(checks, indent=2))
    return 0 if all(checks[key] for key in ("cmake", "cxx", "perfetto_sdk", "trace_processor")) else 1


def command_build(args: argparse.Namespace) -> int:
    print(configure_and_build(bool(args.profile)))
    return 0


def command_profile(args: argparse.Namespace) -> int:
    binary = configure_and_build(True)
    directory = ARTIFACTS / args.tag
    directory.mkdir(parents=True, exist_ok=True)
    trace = directory / "profile.pftrace"
    result_path = directory / "run.json"
    command = [
        str(binary), *workload_arguments(args),
        "--trace", str(trace), "--output", str(result_path), "--quiet",
    ]
    result = parse_run(run_checked(command, capture=True))
    if not trace.is_file() or trace.stat().st_size < 512:
        raise RuntimeError("profile did not produce a usable trace")
    report = create_report(trace)
    write_json(directory / "report.json", report)
    artifact = manifest(args.tag, binary, command)
    artifact.update({
        "trace_sha256": file_hash(trace),
        "trace_bytes": trace.stat().st_size,
        "result_sha256": file_hash(result_path),
        "scenario": args.scenario,
    })
    write_json(directory / "manifest.json", artifact)
    print(json.dumps({"result": result, "report": report}, indent=2))
    return 0


def command_report(args: argparse.Namespace) -> int:
    trace = Path(args.trace)
    if not trace.is_absolute():
        trace = ROOT / trace
    report = create_report(trace)
    if args.output:
        output = Path(args.output)
        write_json(output if output.is_absolute() else ROOT / output, report)
    print(json.dumps(report, indent=2))
    return 0


def command_submit_analysis(args: argparse.Namespace) -> int:
    source = Path(args.input)
    if not source.is_absolute():
        source = ROOT / source
    value = json.loads(source.read_text(encoding="utf-8"))
    findings = value.get("findings")
    if value.get("schema") != "longbench.findings.v3" or not isinstance(findings, list):
        raise RuntimeError("invalid longbench findings schema")
    if not 4 <= len(findings) <= 8:
        raise RuntimeError("findings must contain 4-8 ranked entries")
    phases = set()
    phase_tags = {
        "primary": "diagnostic_primary",
        "state": "diagnostic_state",
        "scale": "diagnostic_scale",
        "tail": "diagnostic_tail",
    }
    for index, finding in enumerate(findings, 1):
        phase = finding.get("phase")
        expected_tag = phase_tags.get(phase)
        source_ref = finding.get("source", {})
        if (
            finding.get("rank") != index
            or phase not in phase_tags
            or finding.get("trace_tag") != expected_tag
            or finding.get("root_cause") not in ROOT_CAUSES
            or not source_ref.get("file")
            or not source_ref.get("symbol")
            or not finding.get("evidence")
            or not finding.get("proposed_change")
        ):
            raise RuntimeError(f"finding {index} is incomplete")
        phases.add(phase)
    if phases != set(phase_tags):
        raise RuntimeError("findings must cover all three diagnostic phases")
    destination = ARTIFACTS / "analysis" / "findings.json"
    write_json(destination, value)
    write_json(destination.parent / "manifest.json", {
        "schema": "longbench.analysis-artifact.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_hash": logic_hash(),
        "findings_sha256": file_hash(destination),
    })
    print(destination)
    return 0


def command_compare(args: argparse.Namespace) -> int:
    tags = (args.baseline, args.checkpoint_primary, args.checkpoint_state,
            args.checkpoint_scale, args.optimized)
    runs = [json.loads((ARTIFACTS / tag / "run.json").read_text()) for tag in tags]
    manifests = [json.loads((ARTIFACTS / tag / "manifest.json").read_text()) for tag in tags]
    if len({run["checksum"] for run in runs}) != 1:
        raise RuntimeError("phase checksums differ")
    baseline_ns, primary_ns, state_ns, scale_ns, optimized_ns = (
        float(run["measured_ns"]) for run in runs
    )
    value = {
        "schema": "longbench.comparison.v3",
        "baseline_tag": tags[0],
        "checkpoint_primary_tag": tags[1],
        "checkpoint_state_tag": tags[2],
        "checkpoint_scale_tag": tags[3],
        "optimized_tag": tags[4],
        "checksum": runs[0]["checksum"],
        "first_stage_speedup": baseline_ns / primary_ns,
        "second_stage_speedup": primary_ns / state_ns,
        "third_stage_speedup": state_ns / scale_ns,
        "fourth_stage_speedup": scale_ns / optimized_ns,
        "end_to_end_speedup": baseline_ns / optimized_ns,
        "source_hashes": [item["source_hash"] for item in manifests],
    }
    output = ARTIFACTS / "comparison" / "comparison.json"
    write_json(output, value)
    print(json.dumps(value, indent=2))
    return 0


VERIFY_CASES = (
    ("micro", ["--scenario", "mixed", "--seed", "17", "--units", "211", "--navigators", "19", "--grid-width", "17", "--grid-height", "13", "--goals", "4", "--warmup", "2", "--frames", "8", "--history-capacity", "9", "--rollback-period", "5", "--rollback-depth", "3", "--edit-period", "3", "--edits", "2", "--mutations", "11", "--transforms", "97", "--colliders", "31", "--events", "83", "--transform-mutations", "7", "--reparent-period", "4", "--component-queries", "7", "--structural-changes", "13", "--interest-observers", "9", "--interest-radius", "4", "--interest-movements", "17"]),
    ("wrap", ["--scenario", "mixed", "--seed", "991", "--units", "401", "--navigators", "7", "--grid-width", "15", "--grid-height", "16", "--goals", "3", "--warmup", "1", "--frames", "17", "--history-capacity", "8", "--rollback-period", "4", "--rollback-depth", "3", "--edit-period", "2", "--edits", "1", "--mutations", "23", "--transforms", "129", "--colliders", "44", "--events", "127", "--transform-mutations", "13", "--reparent-period", "3", "--component-queries", "11", "--structural-changes", "31", "--interest-observers", "13", "--interest-radius", "6", "--interest-movements", "29"]),
    ("churn", ["--scenario", "mixed", "--seed", "8081", "--units", "333", "--navigators", "31", "--grid-width", "11", "--grid-height", "19", "--goals", "5", "--warmup", "2", "--frames", "12", "--history-capacity", "7", "--rollback-period", "6", "--rollback-depth", "4", "--edit-period", "1", "--edits", "3", "--mutations", "29", "--transforms", "111", "--colliders", "58", "--events", "99", "--transform-mutations", "17", "--reparent-period", "2", "--component-queries", "17", "--structural-changes", "97", "--interest-observers", "21", "--interest-radius", "8", "--interest-movements", "83"]),
    ("no_rollback", ["--scenario", "mixed", "--seed", "73", "--units", "257", "--navigators", "13", "--grid-width", "13", "--grid-height", "13", "--goals", "2", "--warmup", "2", "--frames", "9", "--history-capacity", "6", "--rollback-period", "0", "--rollback-depth", "3", "--edit-period", "4", "--edits", "2", "--mutations", "17", "--transforms", "73", "--colliders", "29", "--events", "71", "--transform-mutations", "5", "--reparent-period", "0", "--component-queries", "5", "--structural-changes", "19", "--interest-observers", "7", "--interest-radius", "5", "--interest-movements", "23"]),
    ("population", ["--scenario", "mixed", "--seed", "4409", "--units", "509", "--navigators", "0", "--grid-width", "12", "--grid-height", "14", "--goals", "3", "--warmup", "1", "--frames", "11", "--history-capacity", "8", "--rollback-period", "5", "--rollback-depth", "2", "--edit-period", "3", "--edits", "2", "--mutations", "41", "--transforms", "151", "--colliders", "0", "--events", "0", "--transform-mutations", "23", "--reparent-period", "5", "--component-queries", "9", "--structural-changes", "47", "--interest-observers", "15", "--interest-radius", "7", "--interest-movements", "53"]),
    ("query_order", ["--scenario", "mixed", "--seed", "6203", "--units", "601", "--navigators", "0", "--grid-width", "17", "--grid-height", "13", "--goals", "2", "--warmup", "1", "--frames", "13", "--history-capacity", "0", "--rollback-period", "0", "--rollback-depth", "0", "--edit-period", "0", "--edits", "0", "--mutations", "0", "--transforms", "1", "--colliders", "0", "--events", "0", "--transform-mutations", "0", "--reparent-period", "0", "--component-queries", "23", "--structural-changes", "89", "--interest-observers", "0", "--interest-radius", "0", "--interest-movements", "0"]),
    ("interest_rollback", ["--scenario", "mixed", "--seed", "17713", "--units", "701", "--navigators", "17", "--grid-width", "19", "--grid-height", "17", "--goals", "4", "--warmup", "2", "--frames", "19", "--history-capacity", "10", "--rollback-period", "6", "--rollback-depth", "4", "--edit-period", "5", "--edits", "1", "--mutations", "17", "--transforms", "11", "--colliders", "0", "--events", "31", "--transform-mutations", "0", "--reparent-period", "0", "--component-queries", "3", "--structural-changes", "41", "--interest-observers", "31", "--interest-radius", "9", "--interest-movements", "131"]),
)

VERIFY_EXPECTED: dict[str, tuple[str, ...]] = {
    "micro": ("5160195086676532809", "2483208225172915148", "3637809342824308589", "65732527750846085", "983461426983142847", "5460604845209339591", "5221321146441708396", "13968216303193806161", "1", "117", "135"),
    "wrap": ("8030903919227204526", "15400307127261886685", "4767302621170273198", "13135676915025375921", "2297128035875487459", "11306704578388399545", "8623312079317575395", "7113205660606014827", "0", "294", "623"),
    "churn": ("8083716177803621023", "8884492658589913917", "14607269064670219881", "15686425443004064162", "11651131685524587037", "12740170579671535689", "16933130970357190356", "119968792352620591", "0", "428", "1327"),
    "no_rollback": ("4164149371997277360", "12123402341281249810", "0", "2278440846177738381", "2781093377060572601", "11018544207411067999", "16101671774746730946", "4088573417883878851", "0", "138", "133"),
    "population": ("15656868460945300725", "9248179162272533867", "717431067011329406", "10817088812798460472", "3477402096434102467", "6576140662502462449", "15872647304077221720", "10450722464221309091", "0", "315", "1255"),
    "query_order": ("10987683295453388339", "9248179162272646825", "0", "9430594917780220773", "6341997761790499863", "3803766078125147182", "10996080452216466403", "9248179162272646825", "0", "777", "0"),
    "interest_rollback": ("8680551590982113775", "4392786615244338484", "15822565339666841867", "11432806366503023651", "4500613956485017458", "157197008999463733", "14806730109184684273", "7664835133280997498", "0", "235", "3909"),
}


def command_verify(_: argparse.Namespace) -> int:
    binary = configure_and_build(False)
    rows = []
    for name, case in VERIFY_CASES:
        first = parse_run(run_checked([str(binary), *case, "--quiet"], capture=True))
        second = parse_run(run_checked([str(binary), *case, "--quiet"], capture=True))
        fields = ("checksum", "route_digest", "rollback_digest",
                  "transform_digest", "collision_digest", "event_digest",
                  "query_digest", "interest_digest", "collision_pair_count",
                  "query_match_count", "interest_visible_count")
        if any(first[field] != second[field] for field in fields):
            raise RuntimeError(f"non-deterministic output in {name}")
        if tuple(str(first[field]) for field in fields) != VERIFY_EXPECTED.get(name):
            raise RuntimeError(f"semantic regression in public oracle {name}")
        rows.append({"name": name, **{field: first[field] for field in fields}})
    print(json.dumps({"verified": True, "cases": rows}, indent=2))
    return 0


def add_workload_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--scenario", choices=("mixed", "raid", "history", "churn", "scene", "events", "ecs", "interest"), default="mixed")
    parser.add_argument("--seed", type=int, default=2027)
    for option in ("units", "navigators", "goals", "warmup", "frames", "edits", "mutations",
                   "transforms", "colliders", "events", "transform_mutations", "reparent_period"):
        parser.add_argument("--" + option.replace("_", "-"), type=int)
    for option in ("grid_width", "grid_height", "history_capacity", "rollback_period", "rollback_depth", "edit_period"):
        parser.add_argument("--" + option.replace("_", "-"), type=int)
    for option in ("component_queries", "structural_changes", "interest_observers",
                   "interest_radius", "interest_movements"):
        parser.add_argument("--" + option.replace("_", "-"), type=int)


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    doctor = commands.add_parser("doctor")
    doctor.set_defaults(function=command_doctor)
    build = commands.add_parser("build")
    modes = build.add_mutually_exclusive_group(required=True)
    modes.add_argument("--profile", action="store_true")
    modes.add_argument("--release", action="store_true")
    build.set_defaults(function=command_build)
    profile = commands.add_parser("profile")
    profile.add_argument("--tag", required=True)
    add_workload_options(profile)
    profile.set_defaults(function=command_profile)
    report = commands.add_parser("report")
    report.add_argument("trace")
    report.add_argument("--output")
    report.set_defaults(function=command_report)
    submit = commands.add_parser("submit-analysis")
    submit.add_argument("input")
    submit.set_defaults(function=command_submit_analysis)
    compare = commands.add_parser("compare")
    compare.add_argument("baseline")
    compare.add_argument("checkpoint_primary")
    compare.add_argument("checkpoint_state")
    compare.add_argument("checkpoint_scale")
    compare.add_argument("optimized")
    compare.set_defaults(function=command_compare)
    verify = commands.add_parser("verify")
    verify.set_defaults(function=command_verify)
    return parser


def main() -> int:
    try:
        args = make_parser().parse_args()
        return int(args.function(args))
    except (RuntimeError, OSError, subprocess.CalledProcessError, json.JSONDecodeError) as error:
        print(f"lb: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
