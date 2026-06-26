from __future__ import annotations

import unittest

from scripts.miley_club import (
    ZERO_GUID,
    apply_contract_summary,
    build_start_day_candidates,
    classify_course,
    compute_seats_left,
    create_member_session,
    infer_course_contract_requirement,
    normalize_course,
    parse_contract_summary,
    parse_course_window,
)


class MileyClubTests(unittest.TestCase):
    def test_parse_contract_summary(self) -> None:
        html = """
        <div id="contractitem" class="content">
          <div class='contract'><div class='contractNo'>合同编号：TEST-1</div><div class='hour'>
            <div class='row'><div class='row-left'><div class='text'>Pre-Intermediate-课程系列(课时):</div></div><div class='row-right'><div class='text'>0.00，剩余0.00</div></div></div>
            <div class='row'><div class='row-left'><div class='text'>通选班课(课时):</div></div><div class='row-right'><div class='text'>0.00，剩余0.00</div></div></div>
            <div class='row'><div class='row-left'><div class='text'>Pre-Intermediate&Intermediate-系列课程(课时):</div></div><div class='row-right'><div class='text'>0.00，剩余0.00</div></div></div>
          </div><div class='time'><div class='time-l'>有效日期:</div><div class='time-r'>2026.03.18-2026.08.10</div></div><img class='ico' src='../Images/weixin/DoStatus68.png' /></div>
        </div>
        """
        summary = parse_contract_summary(html, today=__import__("datetime").date(2026, 6, 26))
        self.assertEqual(
            summary["allowed_keys"],
            ["general", "pre_intermediate", "pre_intermediate_intermediate"],
        )
        self.assertIn("Pre-Intermediate-课程系列", summary["active_series_names"])
        self.assertEqual(summary["active_contracts"][0]["contract_no"], "TEST-1")

    def test_create_member_session_from_wechat_url(self) -> None:
        session = create_member_session(
            "https://vip4.zj.etmcn.com/WeiXin/selfLesson.aspx?openID=openid123&lic=lic456&memberGuid=member789&MPUserGuid=mp999",
            label="Miley",
        )

        self.assertEqual(session.member_id, "miley")
        self.assertEqual(session.open_id, "openid123")
        self.assertEqual(session.lic, "lic456")
        self.assertEqual(session.member_guid, "member789")
        self.assertEqual(session.mp_user_guid, "mp999")
        self.assertEqual(session.upstream_origin, "https://vip4.etmcn.com")

    def test_build_start_day_candidates(self) -> None:
        candidates = build_start_day_candidates(__import__("datetime").date(2026, 6, 26))
        self.assertEqual(candidates, ["2026-06-26", "2026/06/26", "2026/6/26"])

    def test_parse_course_window(self) -> None:
        start_at, end_at = parse_course_window("2026-06-09T00:00:00", "13:15-14:15")
        self.assertEqual(start_at, "2026-06-09T13:15:00")
        self.assertEqual(end_at, "2026-06-09T14:15:00")

    def test_normalize_available_course(self) -> None:
        record = {
            "CourseGuid": "course-1",
            "CourseDate": "2099-06-09T00:00:00",
            "ClassSectionName": "13:15-14:15",
            "ClassSectionGuid": "section-1",
            "CourseInfoGuid": ZERO_GUID,
            "MemberCourseGuid": ZERO_GUID,
            "ApplyCourseGuid": ZERO_GUID,
            "courseName": "面授课程-口语 E3-012A Hiking Trip",
            "lessonName": "Elementary-口语课程",
            "TeacherNames": "中教Bridget",
            "ClassRoomName": "麒麟社Classroom1",
            "ReduceHours": 1,
            "MemberLimitCount": 10,
            "FreeLimitCount": -1,
            "SelMemberCount": 0,
            "SelFreeCount": 0,
            "CancelMemberLineUp": False,
        }

        course = normalize_course(record)
        self.assertEqual(course.status, "available")
        self.assertTrue(course.can_book)
        self.assertEqual(course.seats_left, 10)

    def test_normalize_booked_course(self) -> None:
        record = {
            "CourseGuid": "course-2",
            "CourseDate": "2099-06-09T00:00:00",
            "ClassSectionName": "12:00-13:00",
            "ClassSectionGuid": "section-2",
            "CourseInfoGuid": "info-2",
            "MemberCourseGuid": "member-course-2",
            "ApplyCourseGuid": "apply-2",
            "courseName": "面授课程-口语 PI3-Street Life",
            "lessonName": "Pre-Intermediate-口语课程",
            "TeacherNames": "中教Bridget",
            "ClassRoomName": "麒麟社Classroom1",
            "ReduceHours": 1,
            "MemberLimitCount": 10,
            "FreeLimitCount": -1,
            "SelMemberCount": 3,
            "SelFreeCount": 0,
            "CancelMemberCourse": True,
        }

        course = normalize_course(record)
        self.assertEqual(course.status, "booked")
        self.assertTrue(course.can_cancel)
        self.assertEqual(course.status_label, "已预约")

    def test_infer_course_contract_requirement(self) -> None:
        course = normalize_course(
            {
                "CourseGuid": "course-3",
                "CourseDate": "2099-06-09T00:00:00",
                "ClassSectionName": "15:45-16:45",
                "courseName": "面授课程-口语 PI & I-Eating In…And Out",
                "lessonName": "Pre-Intermediate & Intermediate-口语课程",
            }
        )
        self.assertEqual(
            infer_course_contract_requirement(course),
            ("pre_intermediate_intermediate", "Pre-Intermediate&Intermediate"),
        )

    def test_apply_contract_summary_blocks_mismatched_course(self) -> None:
        course = normalize_course(
            {
                "CourseGuid": "course-4",
                "CourseDate": "2099-06-09T00:00:00",
                "ClassSectionName": "15:45-16:45",
                "courseName": "面授课程-口语 E2-Negotiation (Part 1)",
                "lessonName": "Elementary-口语课程",
                "ClassSectionGuid": "section-4",
                "MemberLimitCount": 10,
                "FreeLimitCount": -1,
                "SelMemberCount": 0,
                "SelFreeCount": 0,
            }
        )
        course = apply_contract_summary(
            course,
            {
                "active_series_names": ["Pre-Intermediate-课程系列"],
                "allowed_keys": ["pre_intermediate"],
            },
        )
        self.assertFalse(course.can_book)
        self.assertEqual(course.status, "package_mismatch")
        self.assertEqual(course.status_label, "套餐不匹配")

    def test_classify_waitlist_open(self) -> None:
        record = {
            "CancelMemberLineUp": True,
            "IsWait": False,
            "ApplyCourseGuid": ZERO_GUID,
            "MemberCourseGuid": ZERO_GUID,
        }
        status, label, bucket = classify_course(record, "2099-06-09T10:00:00", 0)
        self.assertEqual((status, label, bucket), ("waitlist_open", "可排队", "waitlist"))

    def test_compute_seats_left(self) -> None:
        record = {
            "MemberLimitCount": 10,
            "FreeLimitCount": -1,
            "SelMemberCount": 3,
            "SelFreeCount": 1,
        }
        self.assertEqual(compute_seats_left(record), 6)


if __name__ == "__main__":
    unittest.main()
