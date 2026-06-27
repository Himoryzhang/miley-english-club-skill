#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
import urllib.parse
from pathlib import Path, PurePosixPath
import re


ROOT = Path(__file__).resolve().parent.parent
GITIGNORE_PATH = ROOT / ".gitignore"
SENSITIVE_WECHAT_URL_RE = re.compile(
    r"https?://[^\s'\"`]+/WeiXin/(?:selfLesson|MyContract)\.aspx\?[^\s'\"`]+",
    re.IGNORECASE,
)
ALLOWED_TEST_FILE_PATHS = {"tests/test_miley_club.py"}


def tracked_files() -> list[str]:
    output = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT)
    return [item for item in output.decode("utf-8").split("\0") if item]


def read_text_if_possible(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return None


def find_sensitive_urls(relative_path: str, content: str) -> list[str]:
    issues: list[str] = []
    if relative_path in ALLOWED_TEST_FILE_PATHS:
        return issues

    for match in SENSITIVE_WECHAT_URL_RE.finditer(content):
        url = match.group(0)

        parsed = urllib.parse.urlparse(url)
        query = urllib.parse.parse_qs(parsed.query)
        sensitive_keys = {"openid", "openID", "lic", "licence", "MemberGuid", "memberGuid", "MPUserGuid"}
        if sensitive_keys.intersection(query):
            issues.append(f"{relative_path}: 检测到带敏感查询参数的 ETMCN 链接。")
    return issues


def main() -> int:
    issues: list[str] = []
    tracked = tracked_files()

    gitignore = GITIGNORE_PATH.read_text(encoding="utf-8")
    if ".local-state/" not in gitignore:
        issues.append(".gitignore: 缺少 `.local-state/` 忽略规则。")

    for relative_path in tracked:
        posix_path = PurePosixPath(relative_path)
        if ".local-state" in posix_path.parts:
            issues.append(f"{relative_path}: 本地会员状态目录不应进入版本控制。")

        text = read_text_if_possible(ROOT / relative_path)
        if text is None:
            continue
        issues.extend(find_sensitive_urls(relative_path, text))

    if issues:
        for issue in issues:
            print(f"[check_repo_safety] {issue}", file=sys.stderr)
        return 1

    print("[check_repo_safety] OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
