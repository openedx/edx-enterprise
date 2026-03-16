"""
Tests for enterprise.filters.grades pipeline step.
"""
import uuid
from unittest.mock import patch

from django.test import TestCase

from enterprise.filters.grades import GradeEventContextEnricher


class TestGradeEventContextEnricher(TestCase):
    """
    Tests for GradeEventContextEnricher pipeline step.
    """

    def _make_step(self):
        return GradeEventContextEnricher(
            "org.openedx.learning.grade.context.requested.v1",
            [],
        )

    @patch(
        "enterprise.filters.grades.EnterpriseCourseEnrollment"
        ".get_enterprise_uuids_with_user_and_course"
    )
    def test_enriches_context_when_enterprise_enrollment_found(self, mock_get_uuids):
        """
        When an enterprise course enrollment exists, enterprise_uuid is added to context.
        """
        enterprise_uuid = uuid.uuid4()
        mock_get_uuids.return_value = [enterprise_uuid]

        step = self._make_step()
        context = {"org": "TestOrg", "course_id": "course-v1:org+course+run"}
        result = step.run_filter(context=context, user_id=7, course_id="course-v1:org+course+run")

        assert result == {"context": {**context, "enterprise_uuid": str(enterprise_uuid)}}
        mock_get_uuids.assert_called_once_with("7", "course-v1:org+course+run")

    @patch(
        "enterprise.filters.grades.EnterpriseCourseEnrollment"
        ".get_enterprise_uuids_with_user_and_course"
    )
    def test_returns_unchanged_context_when_no_enterprise_enrollment(self, mock_get_uuids):
        """
        When no enterprise course enrollment exists, context is returned unchanged.
        """
        mock_get_uuids.return_value = []

        step = self._make_step()
        context = {"org": "TestOrg"}
        result = step.run_filter(context=context, user_id=99, course_id="course-v1:org+course+run")

        assert result == {"context": context}
        assert "enterprise_uuid" not in result["context"]

    @patch(
        "enterprise.filters.grades.EnterpriseCourseEnrollment"
        ".get_enterprise_uuids_with_user_and_course"
    )
    def test_uses_first_uuid_when_multiple_enrollments(self, mock_get_uuids):
        """
        When multiple enterprise enrollments exist, only the first UUID is used.
        """
        first_uuid = uuid.uuid4()
        second_uuid = uuid.uuid4()
        mock_get_uuids.return_value = [first_uuid, second_uuid]

        step = self._make_step()
        context = {}
        result = step.run_filter(context=context, user_id=1, course_id="course-v1:x+y+z")

        assert result["context"]["enterprise_uuid"] == str(first_uuid)
