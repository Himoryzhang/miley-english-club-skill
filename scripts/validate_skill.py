#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SKILL_PATH = ROOT / "SKILL.md"
README_PATH = ROOT / "README.md"
OPENAI_YAML_PATH = ROOT / "agents" / "openai.yaml"
SCHEMA_PATH = ROOT / "agents" / "codex-skill-metadata.schema.json"


class ValidationError(RuntimeError):
    pass


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def extract_frontmatter(markdown: str) -> tuple[dict[str, object], str]:
    match = re.match(r"\A---\n(.*?)\n---\n(.*)\Z", markdown, re.DOTALL)
    if not match:
        raise ValidationError("SKILL.md 缺少合法的 frontmatter。")
    return parse_simple_yaml(match.group(1)), match.group(2)


def parse_simple_yaml(source: str) -> dict[str, object]:
    result: dict[str, object] = {}
    current_section: str | None = None

    for raw_line in source.splitlines():
        if not raw_line.strip():
            continue
        stripped = raw_line.lstrip()
        if stripped.startswith("#"):
            continue

        indent = len(raw_line) - len(stripped)
        if indent == 0:
            key, value = parse_yaml_pair(stripped)
            if value == "":
                result[key] = {}
                current_section = key
            else:
                result[key] = parse_yaml_scalar(value)
                current_section = None
            continue

        if indent >= 2 and current_section:
            section = result.get(current_section)
            if not isinstance(section, dict):
                raise ValidationError(f"YAML 段落 `{current_section}` 结构非法。")
            key, value = parse_yaml_pair(stripped)
            section[key] = parse_yaml_scalar(value)
            continue

        raise ValidationError(f"无法解析 YAML 行：{raw_line}")

    return result


def parse_yaml_pair(line: str) -> tuple[str, str]:
    if ":" not in line:
        raise ValidationError(f"YAML 行缺少冒号：{line}")
    key, value = line.split(":", 1)
    return key.strip(), value.strip()


def parse_yaml_scalar(value: str) -> object:
    if value.startswith('"') and value.endswith('"'):
        return value[1:-1]
    if value.startswith("'") and value.endswith("'"):
        return value[1:-1]
    if value == "true":
        return True
    if value == "false":
        return False
    return value


def validate_skill_frontmatter(frontmatter: dict[str, object], body: str) -> str:
    name = frontmatter.get("name")
    description = frontmatter.get("description")
    metadata = frontmatter.get("metadata")

    if not isinstance(name, str) or not re.fullmatch(r"[a-z0-9-]{1,64}", name):
        raise ValidationError("SKILL.md 的 `name` 不合法。")
    if not isinstance(description, str) or len(description.strip()) < 20:
        raise ValidationError("SKILL.md 的 `description` 过短或缺失。")
    if not body.strip():
        raise ValidationError("SKILL.md 正文为空。")

    if not isinstance(metadata, dict):
        raise ValidationError("SKILL.md 缺少 `metadata`。")

    version = metadata.get("version")
    version_date = metadata.get("version_date")
    if not isinstance(version, str) or not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ValidationError("SKILL.md 的 `metadata.version` 必须是 semver。")
    if not isinstance(version_date, str):
        raise ValidationError("SKILL.md 的 `metadata.version_date` 缺失。")
    try:
        dt.date.fromisoformat(version_date)
    except ValueError as exc:
        raise ValidationError("SKILL.md 的 `metadata.version_date` 必须是 YYYY-MM-DD。") from exc

    return version


def validate_openai_yaml() -> None:
    data = parse_simple_yaml(read_text(OPENAI_YAML_PATH))
    interface = data.get("interface")
    policy = data.get("policy")

    if not isinstance(interface, dict):
        raise ValidationError("agents/openai.yaml 缺少 `interface`。")
    if not isinstance(policy, dict):
        raise ValidationError("agents/openai.yaml 缺少 `policy`。")

    for key in ("display_name", "short_description", "default_prompt"):
        value = interface.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValidationError(f"agents/openai.yaml 缺少 `interface.{key}`。")

    allow_implicit_invocation = policy.get("allow_implicit_invocation")
    if not isinstance(allow_implicit_invocation, bool):
        raise ValidationError("agents/openai.yaml 的 `policy.allow_implicit_invocation` 必须是布尔值。")


def validate_schema_json() -> None:
    try:
        json.loads(read_text(SCHEMA_PATH))
    except json.JSONDecodeError as exc:
        raise ValidationError(f"agents/codex-skill-metadata.schema.json 不是合法 JSON：{exc}") from exc


def validate_readme_version(version: str) -> None:
    readme = read_text(README_PATH)
    match = re.search(r"img\.shields\.io/badge/version-([0-9.]+)-blue", readme)
    if not match:
        raise ValidationError("README.md 缺少 Version badge。")
    badge_version = match.group(1)
    if badge_version != version:
        raise ValidationError(
            f"README.md 的 Version badge 为 `{badge_version}`，与 SKILL.md 的 `{version}` 不一致。"
        )


def main() -> int:
    try:
        frontmatter, body = extract_frontmatter(read_text(SKILL_PATH))
        version = validate_skill_frontmatter(frontmatter, body)
        validate_openai_yaml()
        validate_schema_json()
        validate_readme_version(version)
    except ValidationError as exc:
        print(f"[validate_skill] {exc}", file=sys.stderr)
        return 1

    print("[validate_skill] OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
