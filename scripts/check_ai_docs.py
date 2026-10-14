#!/usr/bin/env python3
"""Проверка AI-документации и покрытия отслеживаемых файлов."""

from __future__ import annotations

import argparse
from fnmatch import fnmatchcase
from pathlib import Path
import re
import subprocess
import sys


REQUIRED_FILES = ("AGENTS.md", "HANDOFF.md", "docs/FILEMAP.md")
REQUIRED_SECTIONS = {
    "AGENTS.md": (
        "Что это за проект",
        "Порядок чтения",
        "Правила работы",
        "Где искать информацию",
        "Особенности",
        "Как поддерживать документацию актуальной",
    ),
    "HANDOFF.md": (
        "Состояние сейчас",
        "Последние изменения",
        "В работе",
        "Ждёт ответа",
        "Планы и очередь",
        "Особенности",
    ),
}
MAP_ENTRY = re.compile(r"^\s*-\s+`([^`]+)`\s+—\s+\S", re.MULTILINE)
HANDOFF_ENTRY = re.compile(r"^\s*-\s+\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}\s+\(Минск\)\s+·", re.MULTILINE)


def git(*args: str) -> bytes:
    result = subprocess.run(("git", *args), capture_output=True, check=False)
    if result.returncode:
        raise RuntimeError(result.stderr.decode("utf-8", "replace").strip())
    return result.stdout


def git_paths(*args: str) -> set[str]:
    return {path.decode("utf-8", "surrogateescape") for path in git(*args).split(b"\0") if path}


def read_doc(path: str, staged: bool) -> str | None:
    if staged:
        result = subprocess.run(("git", "show", f":{path}"), capture_output=True, check=False)
        if result.returncode:
            return None
        return result.stdout.decode("utf-8", "replace")
    try:
        return Path(path).read_text(encoding="utf-8")
    except FileNotFoundError:
        return None


def current_version(staged: bool) -> str | None:
    """Return an explicit project version, if one is declared."""
    for file_name in ("pyproject.toml", "package.json"):
        content = read_doc(file_name, staged)
        if content is None:
            continue
        match = re.search(r'^\s*["\']?version["\']?\s*[:=]\s*["\']([^"\']+)', content, re.MULTILINE)
        if match:
            return match.group(1)
    return None


def matches_path(path: str, entry: str) -> bool:
    if not any(character in entry for character in "*?"):
        return path == entry
    pattern = Path(entry)
    return pattern.parent != Path(".") and Path(path).parent == pattern.parent and fnmatchcase(Path(path).name, pattern.name)


def check(staged: bool) -> list[str]:
    errors: list[str] = []
    tracked = git_paths("ls-files", "--cached", "-z")
    expected = tracked if staged else tracked | set(REQUIRED_FILES) | {"scripts/check_ai_docs.py", "scripts/install-hooks.sh", "tests/test_ai_docs.py"}
    docs: dict[str, str] = {}

    for path in REQUIRED_FILES:
        content = read_doc(path, staged)
        if not content or not content.strip():
            errors.append(f"Добавьте непустой {path}{' в индекс' if staged else ''}.")
        else:
            docs[path] = content

    for path, sections in REQUIRED_SECTIONS.items():
        if path not in docs:
            continue
        headings = set(re.findall(r"^## (.+?)\s*$", docs[path], re.MULTILINE))
        for section in sections:
            if section not in headings:
                errors.append(f"Добавьте раздел '## {section}' в {path}.")

    handoff = docs.get("HANDOFF.md", "")
    entries = HANDOFF_ENTRY.findall(handoff)
    if handoff and not entries:
        errors.append("Добавьте датированную запись в '## Последние изменения' файла HANDOFF.md.")
    version = current_version(staged)
    if version and entries:
        newest = next((line for line in handoff.splitlines() if HANDOFF_ENTRY.match(line)), "")
        if version not in newest:
            errors.append(f"Укажите текущую версию {version} в первой записи HANDOFF.md.")

    filemap = docs.get("docs/FILEMAP.md", "")
    entries_map = MAP_ENTRY.findall(filemap)
    if filemap and not entries_map:
        errors.append("Добавьте строки `путь` — описание в docs/FILEMAP.md.")
    for path in sorted(expected):
        if not any(matches_path(path, entry) for entry in entries_map):
            errors.append(f"Добавьте {path} в docs/FILEMAP.md.")
    for entry in entries_map:
        if not any(matches_path(path, entry) for path in expected):
            errors.append(f"Удалите устаревшую строку {entry} из docs/FILEMAP.md.")

    if staged:
        changed = git_paths("diff", "--cached", "--name-only", "-z")
        if changed - {"HANDOFF.md"} and "HANDOFF.md" not in changed:
            errors.append("Добавьте HANDOFF.md в коммит с остальными изменениями.")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staged", action="store_true", help="проверить подготовленный коммит")
    args = parser.parse_args()
    try:
        errors = check(args.staged)
    except (OSError, RuntimeError) as exc:
        print(f"Не удалось проверить AI-документацию: {exc}", file=sys.stderr)
        return 1
    if errors:
        for error in errors:
            print(f"Ошибка: {error}", file=sys.stderr)
        return 1
    print("AI-документация в порядке.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
