from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from prc.diff import parse_ref


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


@pytest.fixture()
def tiny_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "r"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    (repo / "a.txt").write_text("one\n")
    _git(repo, "add", "a.txt")
    _git(repo, "commit", "-q", "-m", "initial")
    (repo / "a.txt").write_text("one\ntwo\n")
    _git(repo, "add", "a.txt")
    _git(repo, "commit", "-q", "-m", "add line two")
    return repo


def test_parse_ref_extracts_subject_and_files(tiny_repo: Path) -> None:
    diff = parse_ref("HEAD", repo=tiny_repo)
    assert diff.subject == "add line two"
    assert [f.path for f in diff.files] == ["a.txt"]
    assert "+two" in diff.files[0].patch
    assert diff.total_changed_lines() >= 1


def test_parse_ref_rejects_urls() -> None:
    with pytest.raises(NotImplementedError):
        parse_ref("https://github.com/x/y/pull/1")
