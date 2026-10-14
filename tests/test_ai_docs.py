"""Integration checks for the AI documentation guard."""

from __future__ import annotations

from pathlib import Path
import shutil
import subprocess

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
CHECKER = REPO_ROOT / "scripts/check_ai_docs.py"
INSTALLER = REPO_ROOT / "scripts/install-hooks.sh"
DOC_FILES = (
    "README.md",
    "AGENTS.md",
    "HANDOFF.md",
    "docs/FILEMAP.md",
    "scripts/check_ai_docs.py",
    "scripts/install-hooks.sh",
    "tests/test_ai_docs.py",
)


def run(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, text=True, capture_output=True, check=False)


@pytest.fixture
def sample_repo(tmp_path: Path) -> Path:
    for relative_path in DOC_FILES:
        target = tmp_path / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO_ROOT / relative_path, target)
    image = tmp_path / "data/image_bank/01-ageing.jpg"
    image.parent.mkdir(parents=True)
    image.write_bytes(b"sample")
    assert run("git", "init", "-q", cwd=tmp_path).returncode == 0
    assert run("git", "add", "--", *DOC_FILES, "data/image_bank/01-ageing.jpg", cwd=tmp_path).returncode == 0
    return tmp_path


def test_full_check_passes() -> None:
    result = run("python3", str(CHECKER), cwd=REPO_ROOT)
    assert result.returncode == 0, result.stderr


def test_uncovered_file_fails(sample_repo: Path) -> None:
    extra = sample_repo / "notes.txt"
    extra.write_text("new tracked file\n", encoding="utf-8")
    assert run("git", "add", "--", "notes.txt", cwd=sample_repo).returncode == 0

    result = run("python3", str(CHECKER), cwd=sample_repo)

    assert result.returncode == 1
    assert "Добавьте notes.txt в docs/FILEMAP.md" in result.stderr


def test_staged_check_passes_for_documented_files(sample_repo: Path) -> None:
    result = run("python3", str(CHECKER), "--staged", cwd=sample_repo)
    assert result.returncode == 0, result.stderr


def test_staged_change_requires_handoff(sample_repo: Path) -> None:
    committed = run(
        "git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
        "commit", "-qm", "test baseline", cwd=sample_repo,
    )
    assert committed.returncode == 0, committed.stderr
    (sample_repo / "README.md").write_text("Changed description\n", encoding="utf-8")
    assert run("git", "add", "--", "README.md", cwd=sample_repo).returncode == 0

    result = run("python3", str(CHECKER), "--staged", cwd=sample_repo)

    assert result.returncode == 1
    assert "Добавьте HANDOFF.md в коммит" in result.stderr


def test_stale_filemap_entry_fails(sample_repo: Path) -> None:
    filemap = sample_repo / "docs/FILEMAP.md"
    filemap.write_text(filemap.read_text(encoding="utf-8") + "- `gone.txt` — устарело.\n", encoding="utf-8")

    result = run("python3", str(CHECKER), cwd=sample_repo)

    assert result.returncode == 1
    assert "Удалите устаревшую строку gone.txt" in result.stderr


def test_hook_installer_preserves_existing_hook_and_is_idempotent(sample_repo: Path) -> None:
    hook = sample_repo / ".git/hooks/pre-commit"
    original = "#!/bin/sh\nprintf 'existing hook\\n'\n"
    hook.write_text(original, encoding="utf-8")

    first = run("bash", str(INSTALLER), cwd=sample_repo)
    assert first.returncode == 0, first.stderr
    content = hook.read_text(encoding="utf-8")
    assert original.splitlines()[1] in content
    assert content.count("python3 scripts/check_ai_docs.py --staged") == 1

    second = run("bash", str(INSTALLER), cwd=sample_repo)
    assert second.returncode == 0, second.stderr
    assert hook.read_text(encoding="utf-8") == content
    executed = run(str(hook), cwd=sample_repo)
    assert executed.returncode == 0, executed.stderr
    assert "existing hook" in executed.stdout
