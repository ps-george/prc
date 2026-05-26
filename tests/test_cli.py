from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


@pytest.fixture()
def tiny_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "r"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    (repo / "a.py").write_text("def f():\n    return 1\n")
    _git(repo, "add", "a.py")
    _git(repo, "commit", "-q", "-m", "initial")
    (repo / "a.py").write_text("def f():\n    return 2\n")
    _git(repo, "add", "a.py")
    _git(repo, "commit", "-q", "-m", "tweak return value")
    return repo


def test_cli_smoke_md(tiny_repo: Path) -> None:
    env = {**os.environ, "PRC_MOCK": "1"}
    result = subprocess.run(
        ["prc", "HEAD", "--repo", str(tiny_repo)],
        env=env, capture_output=True, text=True, check=True,
    )
    assert "PR Review" in result.stdout
    assert "Summary" in result.stdout
    assert "Author response" in result.stdout


def test_cli_smoke_json(tiny_repo: Path) -> None:
    env = {**os.environ, "PRC_MOCK": "1"}
    result = subprocess.run(
        ["prc", "HEAD", "--repo", str(tiny_repo), "--format", "json"],
        env=env, capture_output=True, text=True, check=True,
    )
    assert '"decision"' in result.stdout


def test_cli_help() -> None:
    result = subprocess.run(
        ["prc", "--help"], capture_output=True, text=True, check=True
    )
    assert "PR critic" in result.stdout
    assert "--mode" in result.stdout
