#!/usr/bin/env python3
"""Create target-specific DSBench bundles for the nav/rollback long task."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import zipfile


ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = ROOT.parents[1]
sys.path.insert(0, str(REPOSITORY))
from scripts import bootstrap_perfetto  # noqa: E402


DIST = ROOT / "dist"
TEST_FILES = DIST / "test_files"
WORKSPACE_ARCHIVE = DIST / "workspace.zip"
BASELINE_ARCHIVE = TEST_FILES / "baseline_source.zip"
MAX_ATTACHMENT_BYTES = 1_000_000
LOGIC_NAMES = ("CMakeLists.txt", "include", "src")
ROOT_CAUSES = [
    "repeated_search", "redundant_work", "allocation", "poor_locality",
    "copy_amplification", "cache_invalidation", "serialization", "branching",
    "dirty_propagation", "pair_generation", "event_churn", "temporal_state",
    "component_query", "structural_churn", "interest_management", "spatial_index",
]


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


def reset_dist() -> None:
    resolved = DIST.resolve()
    if resolved.parent != ROOT.resolve() or resolved.name != "dist":
        raise RuntimeError("unexpected dist directory")
    if DIST.exists():
        shutil.rmtree(DIST)
    TEST_FILES.mkdir(parents=True)


def archive_baseline() -> None:
    with zipfile.ZipFile(BASELINE_ARCHIVE, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as bundle:
        for path in stable_files(ROOT):
            bundle.write(path, path.relative_to(ROOT).as_posix())


def public_workspace_files() -> list[Path]:
    excluded = {"artifacts", "authoring", "build-profile", "build-release", "dist", "grader", "third_party", "tools", "__pycache__"}
    result = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(ROOT)
        if relative.parts[0] in excluded or relative.parts[0].startswith("build-"):
            continue
        if "__pycache__" in relative.parts or path.suffix == ".pyc":
            continue
        result.append(path)
    return result


def target_processor(target: str) -> tuple[str, bytes, str]:
    asset = bootstrap_perfetto.platform_asset(target)
    cache = REPOSITORY / ".tools" / "downloads" / bootstrap_perfetto.VERSION
    archive = cache / asset
    bootstrap_perfetto.download(asset, archive)
    wanted = ("trace_processor_shell.exe", "trace_processor.exe") if target == "windows-amd64" else ("trace_processor_shell", "trace_processor")
    with zipfile.ZipFile(archive) as bundle:
        member = next((name for name in bundle.namelist() if Path(name).name in wanted), None)
        if member is None:
            raise RuntimeError("target trace processor missing")
        data = bundle.read(member)
    relative = f"tools/perfetto/bin/{Path(member).name}"
    return relative, data, hashlib.sha256(data).hexdigest()


def add_bytes(bundle: zipfile.ZipFile, name: str, data: bytes, mode: int) -> None:
    info = zipfile.ZipInfo(name)
    info.create_system = 3
    info.external_attr = mode << 16
    info.compress_type = zipfile.ZIP_DEFLATED
    bundle.writestr(info, data, compresslevel=9)


def archive_workspace(processor_path: str, processor_data: bytes) -> None:
    sdk_root = REPOSITORY / "third_party" / "perfetto"
    required_sdk = (sdk_root / "perfetto.h", sdk_root / "perfetto.cc", sdk_root / "SDK_VERSION.txt")
    if not all(path.is_file() for path in required_sdk):
        raise RuntimeError("pinned Perfetto SDK is missing from authoring repository")
    with zipfile.ZipFile(WORKSPACE_ARCHIVE, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as bundle:
        for path in sorted(public_workspace_files(), key=lambda item: item.relative_to(ROOT).as_posix()):
            bundle.write(path, path.relative_to(ROOT).as_posix())
        for path in required_sdk:
            bundle.write(path, f"third_party/perfetto/{path.name}")
        add_bytes(bundle, processor_path, processor_data, 0o755)
        add_bytes(bundle, "tools/perfetto/VERSION", (bootstrap_perfetto.VERSION + "\n").encode(), 0o644)


def case(
    identifier: str,
    family: str,
    seed: int,
    units: int,
    navigators: int,
    width: int,
    height: int,
    goals: int,
    warmup: int,
    frames: int,
    history: int,
    rollback_period: int,
    rollback_depth: int,
    edit_period: int,
    edits: int,
    mutations: int,
    transforms: int,
    colliders: int,
    events: int,
    transform_mutations: int,
    reparent_period: int,
    component_queries: int = 0,
    structural_changes: int = 0,
    interest_observers: int = 0,
    interest_radius: int = 0,
    interest_movements: int = 0,
) -> dict[str, object]:
    return {
        "id": identifier, "family": family, "scenario": "mixed", "seed": seed,
        "units": units, "navigators": navigators,
        "grid_width": width, "grid_height": height, "goals": goals,
        "warmup": warmup, "frames": frames, "history_capacity": history,
        "rollback_period": rollback_period, "rollback_depth": rollback_depth,
        "edit_period": edit_period, "edits": edits, "mutations": mutations,
        "transforms": transforms, "colliders": colliders, "events": events,
        "transform_mutations": transform_mutations,
        "reparent_period": reparent_period,
        "component_queries": component_queries,
        "structural_changes": structural_changes,
        "interest_observers": interest_observers,
        "interest_radius": interest_radius,
        "interest_movements": interest_movements,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--target",
        choices=("linux-amd64", "windows-amd64", "mac-amd64", "mac-arm64"),
        default="linux-amd64",
    )
    args = parser.parse_args()
    processor_path, processor_data, processor_sha = target_processor(args.target)
    reset_dist()
    archive_baseline()
    original_hash = logic_hash(ROOT)

    semantic_cases = [
        case("s_equal", "semantic", 1927, 311, 27, 13, 17, 4, 1, 13, 8, 5, 3, 4, 2, 31, 313, 80, 131, 17, 5),
        case("s_wrap", "semantic", 8819, 607, 11, 19, 11, 3, 2, 24, 7, 5, 4, 3, 2, 47, 509, 101, 257, 23, 3),
        case("s_churn", "semantic", 5501, 503, 43, 17, 14, 7, 1, 16, 9, 6, 5, 1, 5, 39, 777, 211, 333, 51, 2),
        case("s_reparent", "semantic", 31337, 887, 5, 23, 9, 5, 2, 29, 12, 6, 4, 2, 3, 53, 2048, 600, 300, 97, 1),
        case("s_collision_order", "semantic", 8441, 503, 0, 12, 13, 3, 1, 13, 0, 0, 0, 0, 0, 17, 701, 650, 0, 43, 3),
        case("s_event_order", "semantic", 7207, 997, 0, 16, 15, 4, 1, 11, 0, 0, 0, 0, 0, 89, 129, 0, 1700, 7, 0),
        case("s_cross_rollback", "semantic", 8675309, 1201, 31, 21, 17, 6, 2, 25, 11, 5, 4, 3, 2, 101, 1500, 800, 1200, 83, 2),
        case("s_no_nav", "semantic", 9029, 733, 0, 18, 15, 4, 1, 18, 10, 7, 4, 5, 2, 71, 901, 277, 411, 29, 4),
        case("s_no_rollback", "semantic", 441, 433, 23, 12, 21, 2, 2, 15, 6, 0, 3, 3, 4, 37, 601, 190, 211, 31, 6),
        case("s_disabled", "semantic", 77, 97, 0, 7, 9, 1, 1, 7, 0, 0, 0, 0, 0, 5, 1, 0, 0, 0, 0),
        case("s_query_overlap", "semantic", 6211, 701, 0, 17, 13, 2, 1, 15, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0,
             component_queries=29, structural_changes=113),
        case("s_interest_delta", "semantic", 17713, 809, 11, 19, 17, 4, 2, 18, 0, 0, 0, 5, 1, 17, 13, 0, 37, 0, 0,
             component_queries=3, structural_changes=47, interest_observers=37,
             interest_radius=9, interest_movements=151),
        case("s_structural_rollback", "semantic", 44021, 1201, 23, 23, 19, 6, 2, 27, 12, 6, 5, 3, 2, 61, 501, 120, 211, 31, 2,
             component_queries=17, structural_changes=307, interest_observers=41,
             interest_radius=8, interest_movements=277),
    ]
    performance_cases = [
        case("p_route", "route", 7727, 18000, 520, 47, 43, 7, 3, 30, 0, 0, 0, 11, 2, 180, 100, 20, 0, 0, 0),
        case("p_history", "history", 99173, 120000, 12, 31, 37, 5, 3, 68, 26, 7, 5, 13, 1, 280, 35000, 80, 300, 80, 11),
        case("p_transform", "transform", 334455, 1000, 0, 11, 13, 2, 3, 70, 0, 0, 0, 0, 0, 20, 250000, 0, 0, 16, 17),
        case("p_transform_churn", "transform", 535897, 1200, 0, 13, 11, 2, 3, 46, 0, 0, 0, 0, 0, 20, 180000, 0, 0, 1300, 2),
        case("p_collision", "collision", 271828, 1000, 0, 13, 11, 2, 2, 20, 0, 0, 0, 0, 0, 20, 10000, 6500, 0, 50, 9),
        case("p_events", "events", 161803, 40000, 0, 13, 13, 2, 3, 35, 0, 0, 0, 0, 0, 80, 100, 0, 55000, 0, 0),
        case("p_invalidation", "invalidation", 6161, 25000, 220, 41, 39, 13, 3, 34, 0, 0, 0, 1, 5, 350, 100000, 2500, 3000, 100, 1),
        case("p_mixed", "mixed", 481516, 70000, 260, 43, 45, 8, 4, 36, 28, 9, 6, 8, 3, 500, 45000, 3500, 15000, 120, 5),
        case("p_query_sparse", "query", 424243, 180000, 0, 53, 47, 3, 3, 26, 0, 0, 0, 0, 0, 40, 1, 0, 0, 0, 0,
             component_queries=52, structural_changes=160),
        case("p_query_churn", "query", 909091, 120000, 0, 43, 41, 3, 3, 32, 0, 0, 0, 0, 0, 60, 100, 0, 0, 0, 0,
             component_queries=32, structural_changes=6000),
        case("p_interest_sparse", "interest", 112358, 100000, 0, 79, 73, 3, 3, 20, 0, 0, 0, 0, 0, 40, 1, 0, 0, 0, 0,
             structural_changes=80, interest_observers=90,
             interest_radius=4, interest_movements=120),
        case("p_interest_churn", "interest", 314159, 65000, 37, 61, 59, 5, 3, 24, 18, 8, 5, 0, 0, 80, 100, 0, 200, 0, 0,
             component_queries=2, structural_changes=2400, interest_observers=110,
             interest_radius=11, interest_movements=5000),
        case("p_mixed_scale", "mixed", 2718281, 50000, 180, 47, 43, 9, 3, 28, 22, 8, 6, 5, 4, 420, 32000, 2600, 9000, 180, 3,
             component_queries=16, structural_changes=1200, interest_observers=36,
             interest_radius=7, interest_movements=1800),
    ]
    config = {
        "schema": "longbench.hidden-grade.v3",
        "target_platform": args.target,
        "baseline_archive": BASELINE_ARCHIVE.name,
        "baseline_archive_sha256": sha256(BASELINE_ARCHIVE),
        "original_logic_hash": original_hash,
        "trace_processor_path": processor_path,
        "trace_processor_sha256": processor_sha,
        "minimum_trace_bytes": 2048,
        "case_timeout_seconds": 45,
        "timing_rounds": 3,
        "workflow_stage_gain": 1.04,
        "allowed_root_causes": ROOT_CAUSES,
        "semantic_cases": semantic_cases,
        "performance_cases": performance_cases,
        "resolved_thresholds": {
            "family_speedups": {
                "route": 3.0, "history": 1.25, "transform": 2.0,
                "collision": 2.5, "events": 1.5,
                "invalidation": 2.0, "mixed": 2.5,
                "query": 1.8, "interest": 2.0,
            },
            "case_floor_fraction": 0.9,
            "geomean_speedup": 2.3,
            "workflow_points": 23,
            "unresolved_score_cap": 0.79,
        },
    }
    config_path = TEST_FILES / "grader_config.json"
    config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    shutil.copy2(ROOT / "grader" / "test_by_code.py", DIST / "test_by_code.py")
    shutil.copy2(ROOT / "task" / "TASK_PROMPT.md", DIST / "TASK_PROMPT.md")
    archive_workspace(processor_path, processor_data)

    attachments = (BASELINE_ARCHIVE, config_path)
    if any(path.stat().st_size >= MAX_ATTACHMENT_BYTES for path in attachments):
        raise RuntimeError("hidden attachment exceeds 1 MB")
    manifest = {
        "schema": "longbench.upload-manifest.v1",
        "task_id": "extreme_frame_pipeline_longbench_v3",
        "target_platform": args.target,
        "original_logic_hash": original_hash,
        "workspace": {"file": WORKSPACE_ARCHIVE.name, "bytes": WORKSPACE_ARCHIVE.stat().st_size, "sha256": sha256(WORKSPACE_ARCHIVE)},
        "grader": {"file": "test_by_code.py", "sha256": sha256(DIST / "test_by_code.py")},
        "test_files": [
            {"file": path.name, "bytes": path.stat().st_size, "sha256": sha256(path)}
            for path in attachments
        ],
    }
    (DIST / "upload_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
