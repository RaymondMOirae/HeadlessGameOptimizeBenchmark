#!/usr/bin/env python3
"""Install pinned official Perfetto SDK/tools into this workspace.

This script is intended for the authoring/SnapCode setup phase. The resulting
files are captured in the pre-prompt snapshot, so rollout agents do not need
network access.
"""

from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import platform
import shutil
import stat
import sys
import tempfile
import urllib.request
import zipfile


ROOT = Path(__file__).resolve().parents[1]
VERSION = "v57.2"
BASE_URL = f"https://github.com/google/perfetto/releases/download/{VERSION}"
ASSETS = {
    "perfetto-cpp-sdk-src.zip": (
        "c6fa3d89aee30f7da39402c9cd178c9f2e344544fda5c2109fd8457e319c3a2f"
    ),
    "linux-amd64.zip": (
        "a5354a4a133cc629bb398da53c95515e5a49d4bd96edfebe1ebc3221c85d936f"
    ),
    "windows-amd64.zip": (
        "0d47a31f9058cae5442baeab1ffce3f3f75e176f4f7cd8fedb1a29a51955975e"
    ),
    "mac-amd64.zip": (
        "8d56edbd061a947ec4a63b2b1b396a9beeccac2bc7b0c33e10240cc1d6bce32f"
    ),
    "mac-arm64.zip": (
        "f0f282ef199a2942ee5286856cd57260b11e93f95fdd80e3ffafe2f56ed936de"
    ),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(asset: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and sha256(destination) == ASSETS[asset]:
        return
    request = urllib.request.Request(
        f"{BASE_URL}/{asset}", headers={"User-Agent": "gamebench-authoring"}
    )
    print(f"Downloading {asset} ...", file=sys.stderr)
    with urllib.request.urlopen(request, timeout=120) as response:
        with destination.open("wb") as output:
            shutil.copyfileobj(response, output)
    actual = sha256(destination)
    if actual != ASSETS[asset]:
        destination.unlink(missing_ok=True)
        raise RuntimeError(f"sha256 mismatch for {asset}: {actual}")


def install_sdk(cache: Path, install_root: Path = ROOT) -> None:
    asset = "perfetto-cpp-sdk-src.zip"
    archive = cache / asset
    download(asset, archive)
    target = install_root / "third_party" / "perfetto"
    target.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as bundle:
        names = bundle.namelist()
        for expected in ("perfetto.h", "perfetto.cc"):
            match = next((name for name in names if name.endswith("/" + expected) or name == expected), None)
            if match is None:
                raise RuntimeError(f"{expected} missing from {asset}")
            with bundle.open(match) as source, (target / expected).open("wb") as output:
                shutil.copyfileobj(source, output)
    # Do not name this file VERSION: on case-insensitive filesystems it shadows
    # the C++20 standard header <version> because this directory is on -I.
    (target / "VERSION").unlink(missing_ok=True)
    (target / "SDK_VERSION.txt").write_text(VERSION + "\n", encoding="utf-8")
    print(f"Installed Perfetto C++ SDK {VERSION} in {target}")


def platform_asset(target: str = "current") -> str:
    if target != "current":
        asset = target + ".zip"
        if asset not in ASSETS or asset == "perfetto-cpp-sdk-src.zip":
            raise RuntimeError(f"unsupported Perfetto tool target: {target}")
        return asset
    machine = platform.machine().lower()
    if sys.platform.startswith("win") and machine in {"amd64", "x86_64"}:
        return "windows-amd64.zip"
    if sys.platform.startswith("linux") and machine in {"amd64", "x86_64"}:
        return "linux-amd64.zip"
    if sys.platform == "darwin" and machine in {"arm64", "aarch64"}:
        return "mac-arm64.zip"
    if sys.platform == "darwin" and machine in {"amd64", "x86_64"}:
        return "mac-amd64.zip"
    raise RuntimeError(f"no pinned trace processor bundle for {sys.platform}/{machine}")


def install_tools(
    cache: Path, target_platform: str = "current", install_root: Path = ROOT
) -> None:
    asset = platform_asset(target_platform)
    archive = cache / asset
    download(asset, archive)
    target = install_root / "tools" / "perfetto" / "bin"
    target.mkdir(parents=True, exist_ok=True)
    wanted = {"trace_processor_shell", "trace_processor_shell.exe", "trace_processor", "trace_processor.exe"}
    installed = None
    with zipfile.ZipFile(archive) as bundle:
        for name in bundle.namelist():
            basename = Path(name).name
            if basename not in wanted:
                continue
            installed = target / basename
            with bundle.open(name) as source, installed.open("wb") as output:
                shutil.copyfileobj(source, output)
            if os.name != "nt":
                installed.chmod(installed.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP)
            break
    if installed is None:
        raise RuntimeError(f"trace processor missing from {asset}")
    (target.parent / "VERSION").write_text(VERSION + "\n", encoding="utf-8")
    print(f"Installed {installed}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sdk", action="store_true", help="install the C++ SDK")
    parser.add_argument("--tools", action="store_true", help="install trace processor")
    parser.add_argument(
        "--platform",
        choices=("current", "linux-amd64", "windows-amd64", "mac-amd64", "mac-arm64"),
        default="current",
        help="tool bundle to install (default: detect this machine)",
    )
    args = parser.parse_args()
    if not args.sdk and not args.tools:
        args.sdk = args.tools = True
    cache = ROOT / ".tools" / "downloads" / VERSION
    if args.sdk:
        install_sdk(cache)
    if args.tools:
        install_tools(cache, args.platform)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
