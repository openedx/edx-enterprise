"""
Tests for enterprise.filters.support pipeline steps.
"""
from unittest.mock import patch

from django.test import RequestFactory, TestCase

from enterprise.filters.support import SupportContactEnterpriseTagStep, SupportEnterpriseEnrollmentDataInjector
from test_utils.factories import (
    DataSharingConsentFactory,
    EnterpriseCourseEnrollmentFactory,
    EnterpriseCustomerFactory,
    EnterpriseCustomerUserFactory,
    UserFactory,
)

CONTACT_FILTER_TYPE = "org.openedx.learning.support.contact.context.requested.v1"
ENROLLMENT_FILTER_TYPE = "org.openedx.learning.support.enrollment.data.requested.v1"


class TestSupportContactEnterpriseTagStep(TestCase):
    """
    Tests for SupportContactEnterpriseTagStep pipeline step.
    """

    def _make_step(self):
        return SupportContactEnterpriseTagStep(CONTACT_FILTER_TYPE, [])

    def _make_request(self):
        return RequestFactory().get('/')

    @patch('enterprise.filters.support.enterprise_customer_for_request')
    @patch('enterprise.filters.support.get_current_request')
    def test_appends_tag_for_linked_customer_request(self, mock_get_current_request, mock_customer_for_request):
        """
        When the request is associated with a linked customer account, 'enterprise_learner'
        is appended to context['tags'].
        """
        mock_customer_for_request.return_value = {'uuid': 'some-uuid', 'name': 'Test Customer'}
        request = self._make_request()
        mock_get_current_request.return_value = request
        context = {'tags': ['some_tag']}

        step = self._make_step()
        result = step.run_filter(context=context)

        assert result['context']['tags'] == ['some_tag', 'enterprise_learner']
        mock_customer_for_request.assert_called_once_with(request)

    @patch('enterprise.filters.support.enterprise_customer_for_request')
    @patch('enterprise.filters.support.get_current_request')
    def test_does_not_duplicate_tag(self, mock_get_current_request, mock_customer_for_request):
        """
        When 'enterprise_learner' is already in context['tags'], it is not duplicated.
        """
        mock_customer_for_request.return_value = {'uuid': 'some-uuid', 'name': 'Test Customer'}
        mock_get_current_request.return_value = self._make_request()
        context = {'tags': ['enterprise_learner']}

        step = self._make_step()
        result = step.run_filter(context=context)

        assert result['context']['tags'].count('enterprise_learner') == 1

    @patch('enterprise.filters.support.enterprise_customer_for_request')
    @patch('enterprise.filters.support.get_current_request')
    def test_does_not_append_tag_for_unlinked_request(self, mock_get_current_request, mock_customer_for_request):
        """
        When the request is not associated with a linked customer account, context['tags'] is unchanged.
        """
        mock_customer_for_request.return_value = None
        mock_get_current_request.return_value = self._make_request()
        context = {'tags': ['some_tag']}

        step = self._make_step()
        result = step.run_filter(context=context)

        assert result['context']['tags'] == ['some_tag']


class TestSupportEnterpriseEnrollmentDataInjector(TestCase):
    """
    Tests for SupportEnterpriseEnrollmentDataInjector pipeline step.
    """

    def _make_step(self):
        return SupportEnterpriseEnrollmentDataInjector(ENROLLMENT_FILTER_TYPE, [])

    @patch('enterprise.filters.support.get_data_sharing_consents')
    @patch('enterprise.filters.support.get_enterprise_course_enrollments')
    def test_returns_enrollment_data_unchanged_when_no_enrollments(self, mock_get_enrollments, mock_get_consents):
        """
        When the user has no enterprise course enrollments, enrollment_data is unchanged.
        """
        mock_get_enrollments.return_value = []
        mock_get_consents.return_value = []
        user = UserFactory()
        step = self._make_step()

        result = step.run_filter(enrollment_data={}, user=user)

        assert result == {'enrollment_data': {}, 'user': user}

    @patch('enterprise.filters.support.EnterpriseCourseEnrollmentSerializer')
    @patch('enterprise.filters.support.get_data_sharing_consents')
    @patch('enterprise.filters.support.get_enterprise_course_enrollments')
    def test_enriches_enrollment_data_with_enterprise_enrollments(
        self, mock_get_enrollments, mock_get_consents, mock_serializer_class,
    ):
        """
        Enterprise course enrollments are serialized and keyed by course_id, with a matching
        data-sharing-consent record attached.
        """
        user = UserFactory()
        enterprise_customer = EnterpriseCustomerFactory()
        ecu = EnterpriseCustomerUserFactory(enterprise_customer=enterprise_customer, user_id=user.id)
        course_id = 'course-v1:edX+DemoX+Demo_Course'
        ecr = EnterpriseCourseEnrollmentFactory(enterprise_customer_user=ecu, course_id=course_id)
        consent = DataSharingConsentFactory(
            enterprise_customer=enterprise_customer,
            username=user.username,
            course_id=course_id,
            granted=True,
        )
        mock_get_enrollments.return_value = [ecr]
        mock_get_consents.return_value = [consent]
        mock_serializer_class.return_value.data = {'course_id': course_id, 'saved_for_later': False}

        step = self._make_step()
        result = step.run_filter(enrollment_data={}, user=user)

        entries = result['enrollment_data'][course_id]
        assert len(entries) == 1
        entry = entries[0]
        assert entry['course_id'] == course_id
        assert entry['data_sharing_consent']['consent_provided'] is True
        assert entry['data_sharing_consent']['enterprise_customer_uuid'] == enterprise_customer.uuid
        mock_serializer_class.assert_called_once_with(ecr)
        mock_get_enrollments.assert_called_once_with(user)
        mock_get_consents.assert_called_once_with(user)

    @patch('enterprise.filters.support.EnterpriseCourseEnrollmentSerializer')
    @patch('enterprise.filters.support.get_data_sharing_consents')
    @patch('enterprise.filters.support.get_enterprise_course_enrollments')
    def test_enrollment_without_matching_consent_has_none_consent(
        self, mock_get_enrollments, mock_get_consents, mock_serializer_class,
    ):
        """
        When no data-sharing consent record exists for the enrollment, 'data_sharing_consent' is None.
        """
        user = UserFactory()
        enterprise_customer = EnterpriseCustomerFactory()
        ecu = EnterpriseCustomerUserFactory(enterprise_customer=enterprise_customer, user_id=user.id)
        course_id = 'course-v1:edX+DemoX+Demo_Course'
        ecr = EnterpriseCourseEnrollmentFactory(enterprise_customer_user=ecu, course_id=course_id)
        mock_get_enrollments.return_value = [ecr]
        mock_get_consents.return_value = []
        mock_serializer_class.return_value.data = {'course_id': course_id}

        step = self._make_step()
        result = step.run_filter(enrollment_data={}, user=user)

        assert result['enrollment_data'][course_id][0]['data_sharing_consent'] is None

    @patch('enterprise.filters.support.get_data_sharing_consents')
    @patch('enterprise.filters.support.get_enterprise_course_enrollments')
    def test_preserves_existing_enrollment_data_keys(self, mock_get_enrollments, mock_get_consents):
        """
        Pre-existing keys in enrollment_data (for courses with no enterprise enrollment) survive.
        """
        mock_get_enrollments.return_value = []
        mock_get_consents.return_value = []
        user = UserFactory()
        step = self._make_step()

        result = step.run_filter(enrollment_data={'some-other-course': []}, user=user)

        assert result['enrollment_data'] == {'some-other-course': []}
