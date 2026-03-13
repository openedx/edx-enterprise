"""
Tests for enterprise.filters.support pipeline steps.
"""
import sys
from types import ModuleType
from unittest.mock import MagicMock, patch

from django.test import RequestFactory, TestCase

from enterprise.filters.support import (
    SupportContactEnterpriseTagInjector,
    SupportEnterpriseEnrollmentDataInjector,
)


CONTACT_FILTER_TYPE = "org.openedx.learning.support.contact.context.requested.v1"
ENROLLMENT_FILTER_TYPE = "org.openedx.learning.support.enrollment.data.requested.v1"


def _make_openedx_modules():
    """
    Build a minimal set of sys.modules entries for the openedx namespace.
    """
    entries = {}
    for name in (
        "openedx",
        "openedx.features",
        "openedx.features.enterprise_support",
    ):
        entries[name] = ModuleType(name)
    return entries


def _make_mock_api_module(enterprise_customer=None):
    """
    Return a fake ``openedx.features.enterprise_support.api`` module.
    """
    mock_module = ModuleType("openedx.features.enterprise_support.api")
    mock_module.enterprise_customer_for_request = MagicMock(return_value=enterprise_customer)
    mock_module.get_enterprise_course_enrollments = MagicMock(return_value=[])
    mock_module.get_data_sharing_consents = MagicMock(return_value=[])
    return mock_module


def _make_mock_serializers_module():
    """
    Return a fake ``openedx.features.enterprise_support.serializers`` module.
    """
    mock_module = ModuleType("openedx.features.enterprise_support.serializers")
    mock_serializer_instance = MagicMock()
    mock_serializer_instance.data = {}
    mock_module.EnterpriseCourseEnrollmentSerializer = MagicMock(
        return_value=mock_serializer_instance
    )
    return mock_module


class TestSupportContactEnterpriseTagInjector(TestCase):
    """
    Tests for SupportContactEnterpriseTagInjector pipeline step.
    """

    def _make_step(self):
        return SupportContactEnterpriseTagInjector(CONTACT_FILTER_TYPE, [])

    def _make_request(self):
        factory = RequestFactory()
        return factory.get('/')

    def _make_user(self):
        user = MagicMock()
        user.id = 42
        return user

    def test_appends_enterprise_learner_tag_for_enterprise_user(self):
        """
        When the request is associated with an enterprise customer, 'enterprise_learner'
        is appended to the tags list.
        """
        request = self._make_request()
        user = self._make_user()
        tags = ['some_tag']
        enterprise_customer = {'uuid': 'some-uuid', 'name': 'Test Enterprise'}

        mock_api_module = _make_mock_api_module(enterprise_customer=enterprise_customer)
        extra_modules = _make_openedx_modules()
        extra_modules["openedx.features.enterprise_support.api"] = mock_api_module

        step = self._make_step()
        with patch.dict(sys.modules, extra_modules):
            result = step.run_filter(tags=tags, request=request, user=user)

        assert 'enterprise_learner' in result['tags']
        assert 'some_tag' in result['tags']
        assert result['request'] is request
        assert result['user'] is user

    def test_does_not_append_duplicate_enterprise_learner_tag(self):
        """
        When 'enterprise_learner' is already in the tags list, it should not be duplicated.
        """
        request = self._make_request()
        user = self._make_user()
        tags = ['enterprise_learner']
        enterprise_customer = {'uuid': 'some-uuid', 'name': 'Test Enterprise'}

        mock_api_module = _make_mock_api_module(enterprise_customer=enterprise_customer)
        extra_modules = _make_openedx_modules()
        extra_modules["openedx.features.enterprise_support.api"] = mock_api_module

        step = self._make_step()
        with patch.dict(sys.modules, extra_modules):
            result = step.run_filter(tags=tags, request=request, user=user)

        assert result['tags'].count('enterprise_learner') == 1

    def test_does_not_append_tag_for_non_enterprise_user(self):
        """
        When the request is not associated with an enterprise customer,
        'enterprise_learner' is NOT added to the tags.
        """
        request = self._make_request()
        user = self._make_user()
        tags = ['some_tag']

        mock_api_module = _make_mock_api_module(enterprise_customer=None)
        extra_modules = _make_openedx_modules()
        extra_modules["openedx.features.enterprise_support.api"] = mock_api_module

        step = self._make_step()
        with patch.dict(sys.modules, extra_modules):
            result = step.run_filter(tags=tags, request=request, user=user)

        assert 'enterprise_learner' not in result['tags']
        assert result['tags'] == ['some_tag']

    def test_returns_tags_unchanged_on_exception(self):
        """
        When enterprise_customer_for_request raises an exception, the tags list
        is returned unchanged without propagating the exception.
        """
        request = self._make_request()
        user = self._make_user()
        tags = ['existing_tag']

        mock_api_module = _make_mock_api_module()
        mock_api_module.enterprise_customer_for_request = MagicMock(
            side_effect=Exception('API error')
        )
        extra_modules = _make_openedx_modules()
        extra_modules["openedx.features.enterprise_support.api"] = mock_api_module

        step = self._make_step()
        with patch.dict(sys.modules, extra_modules):
            result = step.run_filter(tags=tags, request=request, user=user)

        assert result['tags'] == ['existing_tag']
        assert 'enterprise_learner' not in result['tags']


class TestSupportEnterpriseEnrollmentDataInjector(TestCase):
    """
    Tests for SupportEnterpriseEnrollmentDataInjector pipeline step.
    """

    def _make_step(self):
        return SupportEnterpriseEnrollmentDataInjector(ENROLLMENT_FILTER_TYPE, [])

    def _make_user(self):
        user = MagicMock()
        user.id = 42
        return user

    def test_returns_empty_enrollment_data_when_no_enrollments(self):
        """
        When there are no enterprise course enrollments, the enrollment_data is
        returned unchanged.
        """
        user = self._make_user()
        enrollment_data = {}

        mock_api_module = _make_mock_api_module()
        mock_api_module.get_enterprise_course_enrollments = MagicMock(return_value=[])
        mock_api_module.get_data_sharing_consents = MagicMock(return_value=[])
        mock_serializers_module = _make_mock_serializers_module()
        extra_modules = _make_openedx_modules()
        extra_modules["openedx.features.enterprise_support.api"] = mock_api_module
        extra_modules["openedx.features.enterprise_support.serializers"] = mock_serializers_module

        step = self._make_step()
        with patch.dict(sys.modules, extra_modules):
            result = step.run_filter(enrollment_data=enrollment_data, user=user)

        assert result['enrollment_data'] == {}
        assert result['user'] is user

    def test_enriches_enrollment_data_with_enterprise_enrollments(self):
        """
        When enterprise course enrollments exist, the enrollment_data dict is enriched
        with serialized enrollment records keyed by course_id.
        """
        user = self._make_user()
        enrollment_data = {}

        course_id = 'course-v1:org+course+run'
        enterprise_customer_id = 'ec-uuid-1'

        mock_ecr = MagicMock()
        mock_ecr.course_id = course_id
        mock_ecr.enterprise_customer_user.enterprise_customer_id = enterprise_customer_id

        mock_api_module = _make_mock_api_module()
        mock_api_module.get_enterprise_course_enrollments = MagicMock(return_value=[mock_ecr])
        mock_api_module.get_data_sharing_consents = MagicMock(return_value=[])

        mock_serializers_module = _make_mock_serializers_module()
        mock_serialized_data = {'course_id': course_id, 'user_id': 42}
        mock_serializer_instance = MagicMock()
        mock_serializer_instance.data = dict(mock_serialized_data)
        mock_serializers_module.EnterpriseCourseEnrollmentSerializer = MagicMock(
            return_value=mock_serializer_instance
        )

        extra_modules = _make_openedx_modules()
        extra_modules["openedx.features.enterprise_support.api"] = mock_api_module
        extra_modules["openedx.features.enterprise_support.serializers"] = mock_serializers_module

        step = self._make_step()
        with patch.dict(sys.modules, extra_modules):
            result = step.run_filter(enrollment_data=enrollment_data, user=user)

        assert course_id in result['enrollment_data']
        assert len(result['enrollment_data'][course_id]) == 1
        entry = result['enrollment_data'][course_id][0]
        assert entry['course_id'] == course_id
        assert entry['data_sharing_consent'] is None  # No matching consent

    def test_attaches_data_sharing_consent_to_enrollment(self):
        """
        When a matching data-sharing consent record exists, it is attached to the
        enrollment entry under 'data_sharing_consent'.
        """
        user = self._make_user()
        enrollment_data = {}

        course_id = 'course-v1:org+course+run'
        enterprise_customer_id = 'ec-uuid-1'

        mock_ecr = MagicMock()
        mock_ecr.course_id = course_id
        mock_ecr.enterprise_customer_user.enterprise_customer_id = enterprise_customer_id

        mock_consent = MagicMock()
        mock_consent.course_id = course_id
        mock_consent.enterprise_customer_id = enterprise_customer_id
        mock_consent.serialize.return_value = {'granted': True}

        mock_api_module = _make_mock_api_module()
        mock_api_module.get_enterprise_course_enrollments = MagicMock(return_value=[mock_ecr])
        mock_api_module.get_data_sharing_consents = MagicMock(return_value=[mock_consent])

        mock_serializers_module = _make_mock_serializers_module()
        mock_serializer_instance = MagicMock()
        mock_serializer_instance.data = {'course_id': course_id}
        mock_serializers_module.EnterpriseCourseEnrollmentSerializer = MagicMock(
            return_value=mock_serializer_instance
        )

        extra_modules = _make_openedx_modules()
        extra_modules["openedx.features.enterprise_support.api"] = mock_api_module
        extra_modules["openedx.features.enterprise_support.serializers"] = mock_serializers_module

        step = self._make_step()
        with patch.dict(sys.modules, extra_modules):
            result = step.run_filter(enrollment_data=enrollment_data, user=user)

        entry = result['enrollment_data'][course_id][0]
        assert entry['data_sharing_consent'] == {'granted': True}

    def test_returns_unchanged_enrollment_data_on_exception(self):
        """
        When get_enterprise_course_enrollments raises an exception, enrollment_data
        is returned unchanged without propagating the exception.
        """
        user = self._make_user()
        enrollment_data = {'existing-course': [{'some': 'data'}]}

        mock_api_module = _make_mock_api_module()
        mock_api_module.get_enterprise_course_enrollments = MagicMock(
            side_effect=Exception('DB error')
        )
        mock_serializers_module = _make_mock_serializers_module()
        extra_modules = _make_openedx_modules()
        extra_modules["openedx.features.enterprise_support.api"] = mock_api_module
        extra_modules["openedx.features.enterprise_support.serializers"] = mock_serializers_module

        step = self._make_step()
        with patch.dict(sys.modules, extra_modules):
            result = step.run_filter(enrollment_data=enrollment_data, user=user)

        assert result['enrollment_data'] == {'existing-course': [{'some': 'data'}]}
        assert result['user'] is user
