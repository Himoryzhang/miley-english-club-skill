#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

PRIMARY_UPSTREAM_HOST = "vip4.etmcn.com"
SUPPORTED_UPSTREAM_HOSTS = {PRIMARY_UPSTREAM_HOST, "vip4.zj.etmcn.com"}
UPSTREAM_API_PATH = "/Ashx/WeiXin.ashx"
MEMBER_ROLE_CHECK_PATH = "/Ashx/GetMemberCourse.ashx"
MY_CONTRACT_PATH = "/WeiXin/MyContract.aspx"
ZERO_GUID = "00000000-0000-0000-0000-000000000000"
ARRAY_KEYS = [
    "data",
    "rows",
    "list",
    "result",
    "results",
    "courses",
    "courseList",
    "Table",
    "Data",
    "Rdata",
    "rdata",
]
TITLE_KEYS = [
    "CourseName",
    "LessonName",
    "ClassName",
    "Name",
    "Title",
    "courseName",
    "lessonName",
    "className",
]
DATE_KEYS = ["CourseDate", "LessonDate", "ClassDate", "Date", "Day", "date"]
COACH_KEYS = ["TeacherNames", "TeacherName", "CoachName", "TrainerName", "teacherName"]
LOCATION_KEYS = ["ClassRoomName", "StoreName", "RoomName", "Location", "storeName", "location"]
DEFAULT_TIMEOUT_SECONDS = 20


class MileyClubError(RuntimeError):
    pass


@dataclass
class MemberSession:
    member_id: str
    label: str
    open_id: str
    lic: str
    member_guid: str
    mp_user_guid: str
    page_type: str
    source_url: str
    upstream_origin: str
    created_at: str
    updated_at: str

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "MemberSession":
        return cls(
            member_id=str(value["member_id"]),
            label=str(value["label"]),
            open_id=str(value["open_id"]),
            lic=str(value["lic"]),
            member_guid=str(value["member_guid"]),
            mp_user_guid=str(value.get("mp_user_guid") or ZERO_GUID),
            page_type=str(value.get("page_type") or ""),
            source_url=str(value["source_url"]),
            upstream_origin=str(value["upstream_origin"]),
            created_at=str(value["created_at"]),
            updated_at=str(value["updated_at"]),
        )

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "member_id": self.member_id,
            "label": self.label,
            "open_id_suffix": self.open_id[-6:],
            "lic_suffix": self.lic[-6:],
            "member_guid": self.member_guid,
            "page_type": self.page_type,
            "upstream_origin": self.upstream_origin,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class CourseRecord:
    course_guid: str
    course_info_guid: str
    member_course_guid: str
    class_section_guid: str
    title: str
    course_name: str
    lesson_name: str
    teacher_names: str
    classroom_name: str
    course_date: str
    class_section_name: str
    start_at: str | None
    end_at: str | None
    reduce_hours: float | None
    seats_left: int | None
    member_limit_count: int | None
    selected_member_count: int | None
    status: str
    status_label: str
    bucket: str
    can_book: bool
    can_cancel: bool
    can_join_waitlist: bool
    can_cancel_waitlist: bool
    can_request_leave: bool
    is_waiting: bool
    required_contract_key: str | None
    required_contract_label: str | None
    package_eligible: bool | None
    active_contract_series: list[str]
    raw: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["raw"] = self.raw
        return result


class StateStore:
    def __init__(self, state_dir: Path) -> None:
        self.state_dir = state_dir
        self.state_file = self.state_dir / "members.json"

    def load(self) -> dict[str, Any]:
        if not self.state_file.exists():
            return {"default_member_id": None, "members": {}}
        try:
            return json.loads(self.state_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise MileyClubError(f"本地会员数据已损坏：{exc}") from exc

    def save(self, data: Mapping[str, Any]) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        if os.name != "nt":
            self.state_dir.chmod(0o700)
        self.state_file.write_text(
            json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        if os.name != "nt":
            self.state_file.chmod(0o600)

    def upsert_member(self, session: MemberSession, make_default: bool) -> tuple[dict[str, Any], MemberSession]:
        data = self.load()
        members = dict(data.get("members") or {})
        preserved_created_at = session.created_at
        stored_member_id = session.member_id

        for member_id, value in members.items():
            if str(value.get("member_guid") or "") == session.member_guid:
                stored_member_id = member_id
                preserved_created_at = str(value.get("created_at") or session.created_at)
                break

        if stored_member_id in members:
            preserved_created_at = str(members[stored_member_id].get("created_at") or preserved_created_at)

        session = MemberSession(
            member_id=stored_member_id,
            label=session.label,
            open_id=session.open_id,
            lic=session.lic,
            member_guid=session.member_guid,
            mp_user_guid=session.mp_user_guid,
            page_type=session.page_type,
            source_url=session.source_url,
            upstream_origin=session.upstream_origin,
            created_at=preserved_created_at,
            updated_at=session.updated_at,
        )
        members[session.member_id] = asdict(session)
        default_member_id = data.get("default_member_id")
        if make_default or not default_member_id:
            default_member_id = session.member_id
        new_state = {"default_member_id": default_member_id, "members": members}
        self.save(new_state)
        return new_state, session

    def get_member(self, member_hint: str | None = None) -> MemberSession:
        data = self.load()
        members = {
            key: MemberSession.from_dict(value)
            for key, value in dict(data.get("members") or {}).items()
        }
        if not members:
            raise MileyClubError("还没有保存会员信息。请先让用户发送微信约课页面完整链接。")

        if member_hint:
            lowered = member_hint.strip().lower()
            for session in members.values():
                if lowered in {
                    session.member_id.lower(),
                    session.label.lower(),
                    session.member_guid.lower(),
                }:
                    return session
            raise MileyClubError(f"没有找到会员 `{member_hint}`。")

        default_member_id = data.get("default_member_id")
        if default_member_id and default_member_id in members:
            return members[default_member_id]

        return next(iter(members.values()))

    def list_members(self) -> dict[str, Any]:
        data = self.load()
        members = [
            MemberSession.from_dict(value).to_public_dict()
            for value in dict(data.get("members") or {}).values()
        ]
        return {
            "default_member_id": data.get("default_member_id"),
            "members": sorted(members, key=lambda item: item["label"]),
        }


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds")


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower())
    slug = slug.strip("-")
    return slug or "member"


def resolve_state_dir(value: str | None) -> Path:
    if value:
        return Path(value).expanduser()
    env_value = os.environ.get("MILEY_CLUB_STATE_DIR")
    if env_value:
        return Path(env_value).expanduser()
    return Path.home() / ".codex" / "data" / "miley-english-club"


def normalize_source_url(source_url: str) -> urllib.parse.ParseResult:
    if not source_url or not source_url.strip():
        raise MileyClubError("约课链接不能为空。")
    parsed = urllib.parse.urlparse(source_url.strip())
    if not parsed.netloc:
        raise MileyClubError("约课链接不完整，请重新复制浏览器里的完整地址。")
    if parsed.scheme not in {"http", "https"}:
        raise MileyClubError("约课链接格式不正确，请重新复制浏览器地址。")
    hostname = parsed.hostname or ""
    if hostname in SUPPORTED_UPSTREAM_HOSTS:
        parsed = parsed._replace(scheme="https", netloc=PRIMARY_UPSTREAM_HOST)
    return parsed


def pick_query_value(parsed: urllib.parse.ParseResult, keys: Iterable[str]) -> str:
    query = urllib.parse.parse_qs(parsed.query, keep_blank_values=False)
    for key in keys:
        values = query.get(key)
        if not values:
            continue
        value = values[0].strip()
        if value:
            return value
    return ""


def create_member_session(source_url: str, label: str | None) -> MemberSession:
    parsed = normalize_source_url(source_url)
    open_id = pick_query_value(parsed, ["openID", "openid", "oid"])
    lic = pick_query_value(parsed, ["lic", "licence", "StoreGuid", "storeGuid"])
    member_guid = pick_query_value(parsed, ["memberGuid", "MemberGuid"])
    mp_user_guid = pick_query_value(parsed, ["MPUserGuid", "mpUserGuid", "mpuserguid"]) or ZERO_GUID
    page_type = pick_query_value(parsed, ["pagetype", "pageType"])
    if not open_id or not lic or not member_guid:
        raise MileyClubError("链接里缺少会员信息，请重新从微信课程预约页复制完整链接。")

    chosen_label = (label or "").strip()
    if not chosen_label:
        chosen_label = f"member-{member_guid[:8]}"
    member_id = slugify(chosen_label)
    timestamp = now_iso()
    normalized_url = urllib.parse.urlunparse(parsed)
    return MemberSession(
        member_id=member_id,
        label=chosen_label,
        open_id=open_id,
        lic=lic,
        member_guid=member_guid,
        mp_user_guid=mp_user_guid,
        page_type=page_type,
        source_url=normalized_url,
        upstream_origin=f"https://{PRIMARY_UPSTREAM_HOST}",
        created_at=timestamp,
        updated_at=timestamp,
    )


def parse_possible_json(value: Any) -> Any:
    current = value
    for _ in range(3):
        if not isinstance(current, str):
            return current
        stripped = current.strip()
        if not stripped:
            return current
        try:
            current = json.loads(stripped)
        except json.JSONDecodeError:
            return current
    return current


def decode_response_body(response: urllib.response.addinfourl) -> str:
    charset = response.headers.get_content_charset() or "utf-8"
    return response.read().decode(charset, errors="replace")


def fetch_text(url: str, referer: str | None = None, origin: str | None = None) -> str:
    headers = {
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "accept-language": "zh-CN,zh;q=0.9",
        "user-agent": "Mozilla/5.0",
    }
    if referer:
        headers["referer"] = referer
    if origin:
        headers["origin"] = origin
    request = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=DEFAULT_TIMEOUT_SECONDS) as response:
            return decode_response_body(response)
    except urllib.error.HTTPError as exc:
        response_text = exc.read().decode("utf-8", errors="replace")
        raise MileyClubError(f"请求失败（HTTP {exc.code}）：{response_text[:200]}") from exc
    except urllib.error.URLError as exc:
        raise MileyClubError(f"请求失败：{exc.reason}") from exc


def post_form(url: str, data: Mapping[str, Any], referer: str, origin: str) -> str:
    encoded = urllib.parse.urlencode({key: "" if value is None else value for key, value in data.items()})
    request = urllib.request.Request(
        url,
        data=encoded.encode("utf-8"),
        headers={
            "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
            "accept": "*/*",
            "accept-language": "zh-CN,zh;q=0.9",
            "origin": origin,
            "referer": referer,
            "x-requested-with": "XMLHttpRequest",
            "user-agent": "Mozilla/5.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=DEFAULT_TIMEOUT_SECONDS) as response:
            return decode_response_body(response)
    except urllib.error.HTTPError as exc:
        response_text = exc.read().decode("utf-8", errors="replace")
        raise MileyClubError(f"请求失败（HTTP {exc.code}）：{response_text[:200]}") from exc
    except urllib.error.URLError as exc:
        raise MileyClubError(f"请求失败：{exc.reason}") from exc


def build_action_url(session: MemberSession, action: str, path: str = UPSTREAM_API_PATH) -> str:
    base = urllib.parse.urljoin(session.upstream_origin, path)
    parsed = urllib.parse.urlparse(base)
    query = urllib.parse.urlencode({"action": action})
    return urllib.parse.urlunparse(parsed._replace(query=query))


def call_weixin_action(session: MemberSession, action: str, data: Mapping[str, Any]) -> dict[str, Any]:
    url = build_action_url(session, action)
    response_text = post_form(
        url,
        data=data,
        referer=session.source_url or urllib.parse.urljoin(session.upstream_origin, "/WeiXin/selfLesson.aspx"),
        origin=session.upstream_origin,
    )
    parsed = parse_possible_json(response_text)
    if isinstance(parsed, Mapping) and "IsOk" in parsed:
        is_ok = bool(parsed.get("IsOk"))
        message = str(parsed.get("Msg") or "")
        payload = parse_possible_json(parsed.get("Rdata"))
        if not is_ok:
            raise MileyClubError(message or f"{action} 失败。")
        return {
            "action": action,
            "message": message,
            "payload": payload,
            "raw": parsed,
        }
    if isinstance(parsed, str) and "<html" in parsed.lower():
        raise MileyClubError("上游返回了页面内容，当前会员链接可能已失效，请重新从微信课程预约页复制完整链接。")
    return {
        "action": action,
        "message": "",
        "payload": parsed,
        "raw": parsed,
    }


def call_member_role_check(session: MemberSession, course_date: str, class_section_guid: str) -> dict[str, Any]:
    url = urllib.parse.urljoin(session.upstream_origin, MEMBER_ROLE_CHECK_PATH)
    response_text = post_form(
        url,
        data={
            "action": "getcourserolebycardtype",
            "memberGuid": session.member_guid,
            "coursedate": course_date,
            "classSectionGuid": class_section_guid,
        },
        referer=session.source_url or urllib.parse.urljoin(session.upstream_origin, "/WeiXin/selfLesson.aspx"),
        origin=session.upstream_origin,
    )
    parsed = parse_possible_json(response_text)
    if not isinstance(parsed, Mapping):
        return {
            "skipped": True,
            "reason": "member_role_check_non_json",
            "raw": response_text[:200],
        }
    code = str(parsed.get("code") or "")
    if code not in {"", "0", "1"}:
        raise MileyClubError(str(parsed.get("tips") or "当前会员不满足本课程的约课条件。"))
    return dict(parsed)


def build_weixin_page_url(session: MemberSession, path: str) -> str:
    if session.source_url:
        parsed = urllib.parse.urlparse(session.source_url)
        query_items = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
        query_map = dict(query_items)
        if "openid" not in query_map and session.open_id:
            query_map["openid"] = session.open_id
        if "oid" not in query_map and session.open_id:
            query_map["oid"] = session.open_id
        if "lic" not in query_map and session.lic:
            query_map["lic"] = session.lic
        if "licence" not in query_map and session.lic:
            query_map["licence"] = session.lic
        if "MemberGuid" not in query_map and session.member_guid:
            query_map["MemberGuid"] = session.member_guid
        if "MPUserGuid" not in query_map and session.mp_user_guid and session.mp_user_guid != ZERO_GUID:
            query_map["MPUserGuid"] = session.mp_user_guid
        if "mobile" not in query_map:
            query_map["mobile"] = ""
        rebuilt_query = urllib.parse.urlencode(query_map)
        return urllib.parse.urlunparse(
            parsed._replace(path=path, params="", query=rebuilt_query, fragment="")
        )

    fallback_query = urllib.parse.urlencode(
        {
            "openid": session.open_id,
            "oid": session.open_id,
            "lic": session.lic,
            "licence": session.lic,
            "MemberGuid": session.member_guid,
            "MPUserGuid": session.mp_user_guid,
            "mobile": "",
        }
    )
    return f"{session.upstream_origin}{path}?{fallback_query}"


def coerce_int(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(float(str(value)))
    except (TypeError, ValueError):
        return None


def coerce_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(str(value))
    except (TypeError, ValueError):
        return None


def real_guid(value: Any) -> bool:
    return isinstance(value, str) and value and value != ZERO_GUID


def clean_html_text(value: str) -> str:
    normalized = html.unescape(value)
    normalized = normalized.replace("\xa0", " ")
    normalized = re.sub(r"<[^>]+>", "", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def extract_course_records(payload: Any) -> list[dict[str, Any]]:
    parsed = parse_possible_json(payload)
    if isinstance(parsed, list):
        return [item for item in parsed if isinstance(item, dict)]
    if not isinstance(parsed, Mapping):
        return []
    for key in ARRAY_KEYS:
        if key in parsed:
            records = extract_course_records(parsed[key])
            if records:
                return records
    for value in parsed.values():
        records = extract_course_records(value)
        if records:
            return records
    return []


def parse_date_only(value: Any) -> dt.date | None:
    if not isinstance(value, str):
        return None
    match = re.match(r"^(\d{4})-(\d{2})-(\d{2})", value.strip())
    if not match:
        return None
    return dt.date(int(match.group(1)), int(match.group(2)), int(match.group(3)))


def parse_contract_range(value: str) -> tuple[dt.date, dt.date] | None:
    match = re.match(r"^\s*(\d{4})\.(\d{2})\.(\d{2})-(\d{4})\.(\d{2})\.(\d{2})\s*$", value)
    if not match:
        return None
    return (
        dt.date(int(match.group(1)), int(match.group(2)), int(match.group(3))),
        dt.date(int(match.group(4)), int(match.group(5)), int(match.group(6))),
    )


def normalize_contract_series_name(name: str) -> tuple[str | None, str | None]:
    cleaned = simplify_contract_series_name(name)

    if "Pre-Intermediate&Intermediate" in cleaned or "Pre-Intermediate & Intermediate" in cleaned:
        return "pre_intermediate_intermediate", "Pre-Intermediate&Intermediate"
    if "Pre-Intermediate" in cleaned:
        return "pre_intermediate", "Pre-Intermediate"
    if "Elementary" in cleaned:
        return "elementary", "Elementary"
    if (
        "通选班课" in cleaned
        or "通选课程" in cleaned
        or "Club Class" in cleaned
        or "Culture Class" in cleaned
        or "Skill Class" in cleaned
    ):
        return "general", "通选班课"
    if re.search(r"(?<!Pre-)Intermediate", cleaned):
        return "intermediate", "Intermediate"
    return None, None


def simplify_contract_series_name(name: str) -> str:
    cleaned = clean_html_text(name)
    cleaned = cleaned.rstrip(":：")
    cleaned = re.sub(r"[（(]课时[）)]\s*$", "", cleaned)
    return cleaned


def infer_course_contract_requirement(course: CourseRecord) -> tuple[str | None, str | None]:
    text = " ".join(
        part for part in [course.lesson_name, course.course_name, course.title] if part
    )
    if (
        "通选课程" in text
        or "通选班课" in text
        or "Club Class" in text
        or "Culture Class" in text
        or "Skill Class" in text
        or "俱乐部课" in text
    ):
        return "general", "通选班课"
    if "Pre-Intermediate & Intermediate" in text or re.search(r"\bPI\s*&\s*I\b", text):
        return "pre_intermediate_intermediate", "Pre-Intermediate&Intermediate"
    if "Elementary" in text or re.search(r"\bE\d", text):
        return "elementary", "Elementary"
    if "Pre-Intermediate" in text or re.search(r"\bPI(?=\d|\s*-)", text):
        return "pre_intermediate", "Pre-Intermediate"
    if re.search(r"(?<!Pre-)Intermediate", text) or re.search(r"\bI(?=\d|\s*-)", text):
        return "intermediate", "Intermediate"
    return None, None


def contract_allows_requirement(allowed_keys: set[str], required_key: str) -> bool:
    if required_key == "intermediate":
        return "intermediate" in allowed_keys or "pre_intermediate_intermediate" in allowed_keys
    return required_key in allowed_keys


def parse_contract_summary(html_text: str, today: dt.date | None = None) -> dict[str, Any]:
    effective_today = today or dt.date.today()
    contract_pattern = re.compile(
        r"<div class='contract'>(?P<body>.*?)<div class='time'>\s*"
        r"<div class='time-l'>有效日期:</div>\s*<div class='time-r'>(?P<date>[^<]+)</div>\s*</div>"
        r"<img class='ico'[^>]* /></div>",
        re.S,
    )
    row_name_pattern = re.compile(
        r"<div class='row-left'><div class='text'>(?P<name>[^<]+)</div></div>",
        re.S,
    )
    contract_no_pattern = re.compile(r"<div class='contractNo'>(?P<no>[^<]+)</div>", re.S)

    active_contracts: list[dict[str, Any]] = []
    all_series_names: list[str] = []
    active_series_names: list[str] = []
    allowed_keys: set[str] = set()

    for match in contract_pattern.finditer(html_text):
        body = match.group("body")
        date_text = clean_html_text(match.group("date"))
        contract_no = clean_html_text(contract_no_pattern.search(body).group("no")) if contract_no_pattern.search(body) else ""
        series_names = [simplify_contract_series_name(item.group("name")) for item in row_name_pattern.finditer(body)]
        normalized_series = []
        for name in series_names:
            all_series_names.append(name)
            key, label = normalize_contract_series_name(name)
            if key and label:
                normalized_series.append({"key": key, "label": label, "name": name})

        date_range = parse_contract_range(date_text)
        is_active = False
        if date_range:
            start_date, end_date = date_range
            is_active = start_date <= effective_today <= end_date

        if is_active:
            for item in normalized_series:
                active_series_names.append(item["name"])
                allowed_keys.add(item["key"])

        active_contracts.append(
            {
                "contract_no": contract_no.replace("合同编号：", ""),
                "date_range": date_text,
                "is_active": is_active,
                "series_names": series_names,
                "normalized_series": normalized_series,
            }
        )

    unique_active_series = list(dict.fromkeys(active_series_names))
    unique_all_series = list(dict.fromkeys(all_series_names))
    # Rebuild labels from active rows to preserve display names.
    label_by_key = {}
    for contract in active_contracts:
        if not contract["is_active"]:
            continue
        for item in contract["normalized_series"]:
            label_by_key[item["key"]] = item["label"]

    return {
        "active_contracts": active_contracts,
        "all_series_names": unique_all_series,
        "active_series_names": unique_active_series,
        "allowed_keys": sorted(allowed_keys),
        "allowed_labels": [label_by_key[key] for key in sorted(label_by_key.keys())],
    }


def fetch_contract_summary(session: MemberSession) -> dict[str, Any]:
    contract_url = build_weixin_page_url(session, MY_CONTRACT_PATH)
    html_text = fetch_text(
        contract_url,
        referer=session.source_url or contract_url,
        origin=session.upstream_origin,
    )
    summary = parse_contract_summary(html_text)
    summary["contract_url"] = contract_url
    return summary


def build_start_day_candidates(day: dt.date) -> list[str]:
    return [
        day.isoformat(),
        day.strftime("%Y/%m/%d"),
        f"{day.year}/{day.month}/{day.day}",
    ]


def contains_requested_day(records: Iterable[dict[str, Any]], day: dt.date) -> bool:
    for record in records:
        course_day = parse_date_only(record.get("CourseDate") or record.get("courseDate"))
        if course_day == day:
            return True
    return False


def fetch_course_setting(session: MemberSession) -> dict[str, Any]:
    result = call_weixin_action(
        session,
        "GetCourseSetting",
        {
            "openID": session.open_id,
            "lic": session.lic,
        },
    )
    payload = result["payload"]
    data = payload if isinstance(payload, Mapping) else {}
    return {
        "show_course_days": coerce_int(data.get("showCourseDays")) or 0,
        "advance_course_date": coerce_int(data.get("advanceCourseDate")) or 0,
        "raw": payload,
    }


def fetch_appointment_state(session: MemberSession) -> bool | None:
    try:
        result = call_weixin_action(session, "GetAppointmentCourseState", {"lic": session.lic})
    except MileyClubError:
        return None
    payload = result["payload"]
    if isinstance(payload, bool):
        return payload
    if isinstance(payload, str):
        lowered = payload.strip().lower()
        if lowered == "true":
            return True
        if lowered == "false":
            return False
    return None


def fetch_course_day(session: MemberSession, day: dt.date) -> list[dict[str, Any]]:
    last_records: list[dict[str, Any]] = []
    for candidate in build_start_day_candidates(day):
        payload = call_weixin_action(
            session,
            "GetCourse",
            {
                "openID": session.open_id,
                "startDay": candidate,
                "lic": session.lic,
                "memberGuid": session.member_guid,
                "pagetype": session.page_type,
            },
        )["payload"]
        records = extract_course_records(payload)
        last_records = records
        if not records or contains_requested_day(records, day):
            return records
    return last_records


def parse_course_window(course_date: str, class_section_name: str) -> tuple[str | None, str | None]:
    course_day = parse_date_only(course_date)
    if not course_day or not isinstance(class_section_name, str):
        return None, None
    match = re.search(r"(\d{1,2}:\d{2})\s*[-~]\s*(\d{1,2}:\d{2})", class_section_name)
    if not match:
        return None, None
    start = dt.datetime.combine(course_day, dt.time.fromisoformat(f"{match.group(1)}:00"))
    end = dt.datetime.combine(course_day, dt.time.fromisoformat(f"{match.group(2)}:00"))
    return start.isoformat(), end.isoformat()


def compute_seats_left(record: Mapping[str, Any]) -> int | None:
    member_limit_count = coerce_int(record.get("MemberLimitCount"))
    selected_member_count = coerce_int(record.get("SelMemberCount")) or 0
    selected_free_count = coerce_int(record.get("SelFreeCount")) or 0
    free_limit_count = coerce_int(record.get("FreeLimitCount"))
    if member_limit_count is None:
        return None
    if free_limit_count is not None and free_limit_count >= 0:
        return member_limit_count - selected_member_count
    return member_limit_count - selected_member_count - selected_free_count


def pick_first_string(record: Mapping[str, Any], keys: Iterable[str]) -> str:
    for key in keys:
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def classify_course(record: Mapping[str, Any], start_at: str | None, seats_left: int | None) -> tuple[str, str, str]:
    leave_status = coerce_int(record.get("LeaveStatus"))
    leave_count = coerce_int(record.get("LeaveCount")) or 0
    apply_status = coerce_int(record.get("ApplyCourseDoStatus"))
    derived_apply_status = coerce_int(record.get("D_ApplyCourseDoStatus"))
    attendance_status = coerce_int(record.get("CDoStatus"))
    cancel_member_course = bool(record.get("CancelMemberCourse"))
    can_leave = bool(record.get("CanLeave"))
    is_wait = bool(record.get("IsWait"))
    cancel_member_line_up = bool(record.get("CancelMemberLineUp"))
    now = dt.datetime.now()

    if attendance_status and attendance_status != 0:
        labels = {39: "已上课", 40: "迟到", 41: "旷课", 42: "已请假"}
        return "completed", labels.get(attendance_status, "已完成"), "registered"

    booked = real_guid(record.get("ApplyCourseGuid")) or real_guid(record.get("MemberCourseGuid"))
    if booked:
        if leave_count > 0 or leave_status == 1:
            return "leave_approved", "已请假", "registered"
        if leave_status == 0:
            return "leave_pending", "请假审核中", "registered"
        if leave_status == 2:
            return "leave_rejected", "请假未通过", "registered"
        if apply_status == 0 or derived_apply_status == 0:
            return "review_pending", "审核中", "registered"
        if apply_status == 3 or derived_apply_status == 2:
            return "booking_rejected", "未通过", "registered"
        if cancel_member_course:
            return "booked", "已预约", "registered"
        if can_leave:
            return "booked", "已预约", "registered"
        return "booked", "已预约", "registered"

    if is_wait:
        return "waitlisted", "已候补", "waitlist"

    if seats_left == 0 and cancel_member_line_up:
        return "waitlist_open", "可候补", "waitlist"

    if start_at:
        try:
            start_dt = dt.datetime.fromisoformat(start_at)
            if start_dt < now:
                return "expired", "已超时", "other"
        except ValueError:
            pass

    if seats_left is not None and seats_left <= 0:
        return "full", "已约满", "other"

    return "available", "可预约", "available"


def normalize_course(record: dict[str, Any]) -> CourseRecord:
    course_date = pick_first_string(record, DATE_KEYS)
    class_section_name = pick_first_string(record, ["ClassSectionName"])
    start_at, end_at = parse_course_window(course_date, class_section_name)
    seats_left = compute_seats_left(record)
    status, status_label, bucket = classify_course(record, start_at, seats_left)
    return CourseRecord(
        course_guid=pick_first_string(record, ["CourseGuid"]),
        course_info_guid=pick_first_string(record, ["CourseInfoGuid"]),
        member_course_guid=pick_first_string(record, ["MemberCourseGuid"]),
        class_section_guid=pick_first_string(record, ["ClassSectionGuid"]),
        title=pick_first_string(record, TITLE_KEYS) or "未命名课程",
        course_name=pick_first_string(record, ["CourseName", "courseName"]),
        lesson_name=pick_first_string(record, ["LessonName", "lessonName"]),
        teacher_names=pick_first_string(record, COACH_KEYS),
        classroom_name=pick_first_string(record, LOCATION_KEYS),
        course_date=course_date,
        class_section_name=class_section_name,
        start_at=start_at,
        end_at=end_at,
        reduce_hours=coerce_float(record.get("ReduceHours")),
        seats_left=seats_left,
        member_limit_count=coerce_int(record.get("MemberLimitCount")),
        selected_member_count=coerce_int(record.get("SelMemberCount")),
        status=status,
        status_label=status_label,
        bucket=bucket,
        can_book=status == "available",
        can_cancel=status == "booked" and bool(record.get("CancelMemberCourse")),
        can_join_waitlist=status == "waitlist_open",
        can_cancel_waitlist=status == "waitlisted",
        can_request_leave=status == "booked" and bool(record.get("CanLeave")),
        is_waiting=status == "waitlisted",
        required_contract_key=None,
        required_contract_label=None,
        package_eligible=None,
        active_contract_series=[],
        raw=record,
    )


def apply_contract_summary(course: CourseRecord, contract_summary: Mapping[str, Any] | None) -> CourseRecord:
    required_key, required_label = infer_course_contract_requirement(course)
    course.required_contract_key = required_key
    course.required_contract_label = required_label

    if not contract_summary:
        course.package_eligible = None
        course.active_contract_series = []
        return course

    active_series_names = list(contract_summary.get("active_series_names") or [])
    allowed_keys = set(contract_summary.get("allowed_keys") or [])
    course.active_contract_series = active_series_names

    if not required_key:
        course.package_eligible = None
        return course

    course.package_eligible = contract_allows_requirement(allowed_keys, required_key)
    if course.package_eligible is False and course.status in {"available", "waitlist_open"}:
        course.status = "package_mismatch"
        course.status_label = "套餐不匹配"
        course.bucket = "other"
        course.can_book = False
        course.can_join_waitlist = False

    return course


def summarize_counts(courses: Iterable[CourseRecord]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for course in courses:
        counts[course.status] = counts.get(course.status, 0) + 1
    return counts


def list_courses(
    session: MemberSession,
    start_day: dt.date | None,
    days: int | None,
    bucket_filter: str,
) -> dict[str, Any]:
    settings = fetch_course_setting(session)
    appointment_enabled = fetch_appointment_state(session)
    try:
        contract_summary = fetch_contract_summary(session)
    except MileyClubError:
        contract_summary = None
    base_day = dt.date.today() + dt.timedelta(days=settings["advance_course_date"])
    effective_start_day = start_day or base_day
    total_days = days if days is not None else settings["show_course_days"]
    total_days = max(total_days, 1)

    records: list[CourseRecord] = []
    for offset in range(total_days):
        day = effective_start_day + dt.timedelta(days=offset)
        for record in fetch_course_day(session, day):
            normalized = apply_contract_summary(normalize_course(record), contract_summary)
            records.append(normalized)

    records.sort(key=lambda item: (item.start_at or "", item.course_guid))

    if bucket_filter != "all":
        records = [item for item in records if item.bucket == bucket_filter]

    return {
        "member": session.to_public_dict(),
        "settings": {
            "show_course_days": settings["show_course_days"],
            "advance_course_date": settings["advance_course_date"],
            "appointment_enabled": appointment_enabled,
        },
        "contracts": contract_summary,
        "window": {
            "start_day": effective_start_day.isoformat(),
            "days": total_days,
        },
        "counts": summarize_counts(records),
        "courses": [item.to_dict() for item in records],
    }


def find_course_by_guid(courses: Iterable[CourseRecord], course_guid: str) -> CourseRecord:
    for course in courses:
        if course.course_guid == course_guid:
            return course
    raise MileyClubError(f"没有找到课程 `{course_guid}`。请先重新读取课程列表。")


def fetch_window_courses(session: MemberSession, start_day: dt.date | None = None, days: int | None = None) -> list[CourseRecord]:
    data = list_courses(session, start_day=start_day, days=days, bucket_filter="all")
    contract_summary = data.get("contracts")
    return [apply_contract_summary(normalize_course(course["raw"]), contract_summary) for course in data["courses"]]


def ensure_appointment_enabled(session: MemberSession) -> None:
    state = fetch_appointment_state(session)
    if state is False:
        raise MileyClubError("当前俱乐部暂未开放自助约课。")


def format_course_date_for_check(course: CourseRecord) -> str:
    course_day = parse_date_only(course.course_date)
    if not course_day:
        raise MileyClubError("课程日期格式异常，无法继续约课。")
    return f"{course_day.year}/{course_day.month}/{course_day.day}"


def book_course(session: MemberSession, course_guid: str) -> dict[str, Any]:
    ensure_appointment_enabled(session)
    courses = fetch_window_courses(session)
    course = find_course_by_guid(courses, course_guid)
    if course.package_eligible is False:
        package_name = course.required_contract_label or "当前课程类型"
        active_series = "、".join(course.active_contract_series) or "当前套餐"
        raise MileyClubError(f"你的合同不包含 {package_name}，当前只能预约：{active_series}。")
    if not course.can_book:
        raise MileyClubError(f"课程当前状态为“{course.status_label}”，不能直接预约。")
    if not course.class_section_guid:
        raise MileyClubError("课程缺少时段信息，无法继续约课。")

    call_member_role_check(session, format_course_date_for_check(course), course.class_section_guid)
    result = call_weixin_action(
        session,
        "SelectCourse",
        {
            "openID": session.open_id,
            "CourseGuid": course.course_guid,
            "MPUserGuid": session.mp_user_guid,
            "lic": session.lic,
            "memberGuid": session.member_guid,
        },
    )
    return {
        "ok": True,
        "action": "book_course",
        "message": result["message"] or "预约成功。",
        "course": course.to_dict(),
    }


def show_contracts(session: MemberSession) -> dict[str, Any]:
    summary = fetch_contract_summary(session)
    return {
        "member": session.to_public_dict(),
        "contracts": summary,
    }


def cancel_course(session: MemberSession, course_guid: str) -> dict[str, Any]:
    courses = fetch_window_courses(session)
    course = find_course_by_guid(courses, course_guid)
    if not course.can_cancel:
        raise MileyClubError(f"课程当前状态为“{course.status_label}”，不能取消预约。")
    if not course.course_info_guid:
        raise MileyClubError("课程缺少课程信息编号，无法取消预约。")

    result = call_weixin_action(
        session,
        "CancelSelectCourse",
        {
            "openID": session.open_id,
            "CourseGuid": course.course_guid,
            "MPUserGuid": session.mp_user_guid,
            "CourseInfoGuid": course.course_info_guid,
            "lic": session.lic,
            "memberGuid": session.member_guid,
        },
    )
    return {
        "ok": True,
        "action": "cancel_course",
        "message": result["message"] or "已取消预约。",
        "course": course.to_dict(),
    }


def join_waitlist(session: MemberSession, course_guid: str) -> dict[str, Any]:
    courses = fetch_window_courses(session)
    course = find_course_by_guid(courses, course_guid)
    if not course.can_join_waitlist:
        raise MileyClubError(f"课程当前状态为“{course.status_label}”，不能加入候补。")
    result = call_weixin_action(
        session,
        "createWaitCourse",
        {
            "openID": session.open_id,
            "CourseGuid": course.course_guid,
            "MPUserGuid": session.mp_user_guid,
            "lic": session.lic,
            "memberGuid": session.member_guid,
        },
    )
    return {
        "ok": True,
        "action": "join_waitlist",
        "message": result["message"] or "已加入候补。",
        "course": course.to_dict(),
    }


def cancel_waitlist(session: MemberSession, course_guid: str) -> dict[str, Any]:
    courses = fetch_window_courses(session)
    course = find_course_by_guid(courses, course_guid)
    if not course.can_cancel_waitlist:
        raise MileyClubError(f"课程当前状态为“{course.status_label}”，不能取消候补。")
    result = call_weixin_action(
        session,
        "CancelWaitCourse",
        {
            "openID": session.open_id,
            "CourseGuid": course.course_guid,
            "MPUserGuid": session.mp_user_guid,
            "lic": session.lic,
            "memberGuid": session.member_guid,
        },
    )
    return {
        "ok": True,
        "action": "cancel_waitlist",
        "message": result["message"] or "已取消候补。",
        "course": course.to_dict(),
    }


def parse_date_arg(value: str | None) -> dt.date | None:
    if not value:
        return None
    try:
        return dt.date.fromisoformat(value)
    except ValueError as exc:
        raise MileyClubError("日期格式应为 YYYY-MM-DD。") from exc


def bucket_filter_from_status(value: str) -> str:
    mapping = {
        "all": "all",
        "available": "available",
        "registered": "registered",
        "waitlist": "waitlist",
    }
    if value not in mapping:
        raise MileyClubError("status 只支持 all / available / registered / waitlist。")
    return mapping[value]


def print_json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Miley English Club member helper")
    parser.add_argument(
        "--state-dir",
        help="Override the local state directory. Defaults to ~/.codex/data/miley-english-club",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    bind_parser = subparsers.add_parser("bind-member", help="Save a member session from the WeChat booking URL")
    bind_parser.add_argument("source_url", help="Full booking page URL copied from the browser")
    bind_parser.add_argument("--label", help="Optional friendly label")
    bind_parser.add_argument(
        "--make-default",
        action="store_true",
        help="Mark this member as the default member",
    )

    subparsers.add_parser("list-members", help="List saved members")

    show_parser = subparsers.add_parser("show-member", help="Show a saved member")
    show_parser.add_argument("--member", help="Member id, label, or memberGuid")

    courses_parser = subparsers.add_parser("list-courses", help="Fetch courses for a saved member")
    courses_parser.add_argument("--member", help="Member id, label, or memberGuid")
    courses_parser.add_argument("--start-day", help="Start day in YYYY-MM-DD")
    courses_parser.add_argument("--days", type=int, help="How many days to fetch")
    courses_parser.add_argument(
        "--status",
        default="all",
        choices=["all", "available", "registered", "waitlist"],
        help="Filter by status bucket",
    )

    contracts_parser = subparsers.add_parser("show-contracts", help="Show active contract/package information")
    contracts_parser.add_argument("--member", help="Member id, label, or memberGuid")

    book_parser = subparsers.add_parser("book-course", help="Book a course by CourseGuid")
    book_parser.add_argument("course_guid", help="CourseGuid from list-courses")
    book_parser.add_argument("--member", help="Member id, label, or memberGuid")

    cancel_parser = subparsers.add_parser("cancel-course", help="Cancel a booked course by CourseGuid")
    cancel_parser.add_argument("course_guid", help="CourseGuid from list-courses")
    cancel_parser.add_argument("--member", help="Member id, label, or memberGuid")

    wait_parser = subparsers.add_parser("join-waitlist", help="Join a waitlist by CourseGuid")
    wait_parser.add_argument("course_guid", help="CourseGuid from list-courses")
    wait_parser.add_argument("--member", help="Member id, label, or memberGuid")

    cancel_wait_parser = subparsers.add_parser("cancel-waitlist", help="Cancel waitlist by CourseGuid")
    cancel_wait_parser.add_argument("course_guid", help="CourseGuid from list-courses")
    cancel_wait_parser.add_argument("--member", help="Member id, label, or memberGuid")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    state_store = StateStore(resolve_state_dir(args.state_dir))

    try:
        if args.command == "bind-member":
            session = create_member_session(args.source_url, args.label)
            state, stored_session = state_store.upsert_member(session, make_default=args.make_default)
            print_json(
                {
                    "ok": True,
                    "default_member_id": state["default_member_id"],
                    "member": stored_session.to_public_dict(),
                }
            )
            return 0

        if args.command == "list-members":
            print_json(state_store.list_members())
            return 0

        if args.command == "show-member":
            session = state_store.get_member(args.member)
            print_json(session.to_public_dict())
            return 0

        if args.command == "list-courses":
            session = state_store.get_member(args.member)
            result = list_courses(
                session,
                start_day=parse_date_arg(args.start_day),
                days=args.days,
                bucket_filter=bucket_filter_from_status(args.status),
            )
            print_json(result)
            return 0

        if args.command == "show-contracts":
            session = state_store.get_member(args.member)
            print_json(show_contracts(session))
            return 0

        if args.command == "book-course":
            session = state_store.get_member(args.member)
            print_json(book_course(session, args.course_guid))
            return 0

        if args.command == "cancel-course":
            session = state_store.get_member(args.member)
            print_json(cancel_course(session, args.course_guid))
            return 0

        if args.command == "join-waitlist":
            session = state_store.get_member(args.member)
            print_json(join_waitlist(session, args.course_guid))
            return 0

        if args.command == "cancel-waitlist":
            session = state_store.get_member(args.member)
            print_json(cancel_waitlist(session, args.course_guid))
            return 0

        raise MileyClubError(f"不支持的命令：{args.command}")
    except MileyClubError as exc:
        print_json({"ok": False, "error": str(exc)})
        return 1


if __name__ == "__main__":
    sys.exit(main())
