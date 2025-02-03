"""
Tests for the edx-enterprise ``api.v1.views.default_enterprise_enrollments module``.
"""
import uuid
from unittest import mock

import ddt
from faker import Faker
from oauth2_provider.models import get_application_model
from pytest import mark
from rest_framework import status
from rest_framework.reverse import reverse

from django.conf import settings

from enterprise.constants import ENTERPRISE_LEARNER_ROLE
from enterprise.models import EnterpriseCourseEnrollment
from test_utils import FAKE_UUIDS, TEST_PASSWORD, factories, fake_catalog_api

from .constants import AUDIT_COURSE_MODE, VERIFIED_COURSE_MODE
from .test_views import BaseTestEnterpriseAPIViews, create_mock_default_enterprise_enrollment_intention

Application = get_application_model()
fake = Faker()

DEFAULT_ENTERPRISE_ENROLLMENT_INTENTION_LIST_ENDPOINT = reverse('default-enterprise-enrollment-intentions-list')
DEFAULT_ENTERPRISE_ENROLLMENT_INTENTION_LEARNER_STATUS_ENDPOINT = reverse(
    'default-enterprise-enrollment-intentions-learner-status'
)


def get_default_enterprise_enrollment_intention_detail_endpoint(enrollment_intention_uuid=None):
    return reverse(
        'default-enterprise-enrollment-intentions-detail',
        kwargs={'pk': enrollment_intention_uuid if enrollment_intention_uuid else FAKE_UUIDS[0]}
    )


@ddt.ddt
@mark.django_db
class TestDefaultEnterpriseEnrollmentIntentionViewSet(BaseTestEnterpriseAPIViews):
    """
    Test DefaultEnterpriseEnrollmentIntentionViewSet
    """

    def setUp(self):
        super().setUp()
        self.enterprise_customer = factories.EnterpriseCustomerFactory()

        username = 'test_user_default_enterprise_enrollment_intentions'
        self.user = self.create_user(username=username, is_staff=False)
        self.client.login(username=self.user.username, password=TEST_PASSWORD)

    def get_default_enrollment_intention_with_learner_enrollment_state(self, enrollment_intention, **kwargs):
        """
        Returns the expected serialized default enrollment intention with learner enrollment state.

        Args:
            enrollment_intention: The enrollment intention to serialize.
            **kwargs: Additional parameters to customize the response.
                - applicable_enterprise_catalog_uuids: List of applicable enterprise catalog UUIDs.
                - is_course_run_enrollable: Boolean indicating if the course run is enrollable.
                - best_mode_for_course_run: The best mode for the course run (e.g., "verified", "audit").
                - has_existing_enrollment: Boolean indicating if there is an existing enrollment.
                - is_existing_enrollment_active: Boolean indicating if the existing enrollment is
                  active, or None if no existing enrollment.
                - is_existing_enrollment_audit: Boolean indicating if the existing enrollment is
                  audit, or None if no existing enrollment.
        """
        return {
            'uuid': str(enrollment_intention.uuid),
            'content_key': enrollment_intention.content_key,
            'enterprise_customer': str(self.enterprise_customer.uuid),
            'course_key': enrollment_intention.course_key,
            'course_run_key': enrollment_intention.course_run_key,
            'is_course_run_enrollable': kwargs.get('is_course_run_enrollable', True),
            'best_mode_for_course_run': kwargs.get('best_mode_for_course_run', VERIFIED_COURSE_MODE),
            'applicable_enterprise_catalog_uuids': kwargs.get(
                'applicable_enterprise_catalog_uuids',
                [fake_catalog_api.FAKE_CATALOG_RESULT.get('uuid')],
            ),
            'course_run_normalized_metadata': {
                'start_date': fake_catalog_api.FAKE_COURSE_RUN.get('start'),
                'end_date': fake_catalog_api.FAKE_COURSE_RUN.get('end'),
                'enroll_by_date': fake_catalog_api.FAKE_COURSE_RUN.get('seats')[1].get('upgrade_deadline'),
                'enroll_start_date': fake_catalog_api.FAKE_COURSE_RUN.get('enrollment_start'),
                'content_price': fake_catalog_api.FAKE_COURSE_RUN.get('first_enrollable_paid_seat_price'),
            },
            'created': enrollment_intention.created.strftime("%Y-%m-%dT%H:%M:%SZ"),
            'modified': enrollment_intention.modified.strftime("%Y-%m-%dT%H:%M:%SZ"),
            'has_existing_enrollment': kwargs.get('has_existing_enrollment', False),
            'is_existing_enrollment_active': kwargs.get('is_existing_enrollment_active', None),
            'is_existing_enrollment_audit': kwargs.get('is_existing_enrollment_audit', None),
        }

    def test_default_enterprise_enrollment_intentions_missing_enterprise_uuid(self):
        """
        Test expected response when successfully listing existing default enterprise enrollment intentions.
        """
        self.set_jwt_cookie(ENTERPRISE_LEARNER_ROLE, str(self.enterprise_customer.uuid))
        response = self.client.get(f"{settings.TEST_SERVER}{DEFAULT_ENTERPRISE_ENROLLMENT_INTENTION_LIST_ENDPOINT}")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {'detail': 'enterprise_customer_uuid is a required query parameter.'}

    def test_default_enterprise_enrollment_intentions_invalid_enterprise_uuid(self):
        """
        Test expected response when successfully listing existing default enterprise enrollment intentions.
        """
        self.set_jwt_cookie(ENTERPRISE_LEARNER_ROLE, str(self.enterprise_customer.uuid))
        query_params = 'enterprise_customer_uuid=invalid-uuid'
        response = self.client.get(
            f"{settings.TEST_SERVER}{DEFAULT_ENTERPRISE_ENROLLMENT_INTENTION_LIST_ENDPOINT}?{query_params}"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {'detail': 'enterprise_customer_uuid query parameter is not a valid UUID.'}

    @mock.patch('enterprise.content_metadata.api.EnterpriseCatalogApiClient')
    def test_default_enterprise_enrollment_intentions_list(self, mock_catalog_api_client):
        """
        Test expected response when successfully listing existing default enterprise enrollment intentions.
        """
        self.set_jwt_cookie(ENTERPRISE_LEARNER_ROLE, str(self.enterprise_customer.uuid))
        enrollment_intention = create_mock_default_enterprise_enrollment_intention(
            enterprise_customer=self.enterprise_customer,
            mock_catalog_api_client=mock_catalog_api_client,
        )
        query_params = f'enterprise_customer_uuid={str(self.enterprise_customer.uuid)}'
        response = self.client.get(
            f"{settings.TEST_SERVER}{DEFAULT_ENTERPRISE_ENROLLMENT_INTENTION_LIST_ENDPOINT}?{query_params}"
        )
        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        assert response_data['count'] == 1
        result = response_data['results'][0]
        assert result['content_key'] == enrollment_intention.content_key
        assert result['applicable_enterprise_catalog_uuids'] == [fake_catalog_api.FAKE_CATALOG_RESULT.get('uuid')]

    @mock.patch('enterprise.content_metadata.api.EnterpriseCatalogApiClient')
    def test_default_enterprise_enrollment_intentions_detail(self, mock_catalog_api_client):
        """
        Test expected response when unauthorized user attempts to list default
        enterprise enrollment intentions.
        """
        self.set_jwt_cookie(ENTERPRISE_LEARNER_ROLE, str(self.enterprise_customer.uuid))
        enrollment_intention = create_mock_default_enterprise_enrollment_intention(
            enterprise_customer=self.enterprise_customer,
            mock_catalog_api_client=mock_catalog_api_client,
        )
        query_params = f'enterprise_customer_uuid={str(self.enterprise_customer.uuid)}'
        base_url = get_default_enterprise_enrollment_intention_detail_endpoint(str(enrollment_intention.uuid))
        response = self.client.get(f"{settings.TEST_SERVER}{base_url}?{query_params}")
        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        assert response_data['content_key'] == enrollment_intention.content_key
        assert response_data['applicable_enterprise_catalog_uuids'] == \
            [fake_catalog_api.FAKE_CATALOG_RESULT.get('uuid')]

    @mock.patch('enterprise.content_metadata.api.EnterpriseCatalogApiClient')
    def test_default_enterprise_enrollment_intentions_list_unauthorized(self, mock_catalog_api_client):
        """
        Test expected response when unauthorized user attempts to list default
        enterprise enrollment intentions.
        """
        self.set_jwt_cookie(ENTERPRISE_LEARNER_ROLE, str(self.enterprise_customer.uuid))
        create_mock_default_enterprise_enrollment_intention(
            enterprise_customer=self.enterprise_customer,
            mock_catalog_api_client=mock_catalog_api_client,
        )
        query_params = f'enterprise_customer_uuid={str(uuid.uuid4())}'
        response = self.client.get(
            f"{settings.TEST_SERVER}{DEFAULT_ENTERPRISE_ENROLLMENT_INTENTION_LIST_ENDPOINT}?{query_params}"
        )
        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        assert response_data['count'] == 0
        assert response_data['results'] == []

    @mock.patch('enterprise.content_metadata.api.EnterpriseCatalogApiClient')
    def test_default_enterprise_enrollment_intentions_detail_403_forbidden(self, mock_catalog_api_client):
        """
        Test expected response when unauthorized user attempts to list default
        enterprise enrollment intentions.
        """
        self.set_jwt_cookie(ENTERPRISE_LEARNER_ROLE, str(self.enterprise_customer.uuid))
        enrollment_intention = create_mock_default_enterprise_enrollment_intention(
            enterprise_customer=self.enterprise_customer,
            mock_catalog_api_client=mock_catalog_api_client,
        )
        query_params = f'enterprise_customer_uuid={str(uuid.uuid4())}'
        base_url = get_default_enterprise_enrollment_intention_detail_endpoint(str(enrollment_intention.uuid))
        response = self.client.get(f"{settings.TEST_SERVER}{base_url}?{query_params}")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    @mock.patch('enterprise.content_metadata.api.EnterpriseCatalogApiClient')
    def test_default_enterprise_enrollment_intentions_not_in_catalog(self, mock_catalog_api_client):
        """
        Test expected response when default enterprise enrollment intention is not in catalog.
        """
        self.set_jwt_cookie(ENTERPRISE_LEARNER_ROLE, str(self.enterprise_customer.uuid))
        enrollment_intention = create_mock_default_enterprise_enrollment_intention(
            enterprise_customer=self.enterprise_customer,
            mock_catalog_api_client=mock_catalog_api_client,
            catalog_list=[],
        )
        query_params = f'enterprise_customer_uuid={str(self.enterprise_customer.uuid)}'
        base_url = get_default_enterprise_enrollment_intention_detail_endpoint(str(enrollment_intention.uuid))
        response = self.client.get(f"{settings.TEST_SERVER}{base_url}?{query_params}")
        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        assert response_data['content_key'] == enrollment_intention.content_key
        assert response_data['applicable_enterprise_catalog_uuids'] == []

    def test_default_enterprise_enrollment_intentions_learner_status_not_linked(self):
        """
        Test default enterprise enrollment intentions for specific learner not linked to enterprise customer.
        """
        self.set_jwt_cookie(ENTERPRISE_LEARNER_ROLE, str(self.enterprise_customer.uuid))
        query_params = f'enterprise_customer_uuid={str(self.enterprise_customer.uuid)}'
        response = self.client.get(
            f"{settings.TEST_SERVER}{DEFAULT_ENTERPRISE_ENROLLMENT_INTENTION_LEARNER_STATUS_ENDPOINT}?{query_params}"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        response_data = response.json()
        assert response_data['detail'] == (
            f'User with lms_user_id {self.user.id} is not associated with '
            f'the enterprise customer {str(self.enterprise_customer.uuid)}.'
        )

    @mock.patch('enterprise.content_metadata.api.EnterpriseCatalogApiClient')
    @mock.patch('enterprise.models.utils.get_best_mode_from_course_key')
    def test_default_enterprise_enrollment_intentions_learner_status_enrollable(
        self,
        mock_get_best_mode_from_course_key,
        mock_catalog_api_client,
    ):
        """
        Test default enterprise enrollment intentions for specific learner linked to enterprise customer, where
        the course run associated with the default enrollment intention is enrollable.
        """
        self.set_jwt_cookie(ENTERPRISE_LEARNER_ROLE, str(self.enterprise_customer.uuid))
        enrollment_intention = create_mock_default_enterprise_enrollment_intention(
            enterprise_customer=self.enterprise_customer,
            mock_catalog_api_client=mock_catalog_api_client,
        )
        mock_get_best_mode_from_course_key.return_value = VERIFIED_COURSE_MODE
        factories.EnterpriseCustomerUserFactory(
            user_id=self.user.id,
            enterprise_customer=self.enterprise_customer,
        )
        query_params = f'enterprise_customer_uuid={str(self.enterprise_customer.uuid)}'
        response = self.client.get(
            f"{settings.TEST_SERVER}{DEFAULT_ENTERPRISE_ENROLLMENT_INTENTION_LEARNER_STATUS_ENDPOINT}?{query_params}"
        )
        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        assert response_data['lms_user_id'] == self.user.id
        assert response_data['user_email'] == self.user.email
        assert response_data['enrollment_statuses'] == {
            'needs_enrollment': {
                'enrollable': [
                    self.get_default_enrollment_intention_with_learner_enrollment_state(enrollment_intention)
                ],
                'not_enrollable': [],
            },
            'already_enrolled': [],
        }
        assert response_data['metadata'] == {
            'total_default_enterprise_enrollment_intentions': 1,
            'total_needs_enrollment': {
                'enrollable': 1,
                'not_enrollable': 0,
            },
            'total_already_enrolled': 0,
        }

    @ddt.data(
        {'run_is_enrollable': False, 'unenrollment_exists': False},
        {'run_is_enrollable': True, 'unenrollment_exists': True},
    )
    @mock.patch('enterprise.content_metadata.api.EnterpriseCatalogApiClient')
    @mock.patch('enterprise.models.utils.get_best_mode_from_course_key')
    @mock.patch.object(EnterpriseCourseEnrollment, 'course_enrollment', new_callable=mock.PropertyMock)
    @ddt.unpack
    def test_default_enrollment_intentions_learner_status_content_not_enrollable(
        self,
        mock_course_enrollment,
        mock_get_best_mode_from_course_key,
        mock_catalog_api_client,
        run_is_enrollable,
        unenrollment_exists,
    ):
        """
        Test default enterprise enrollment intentions (not enrollable) for
        specific learner linked to enterprise customer.
        """
        self.set_jwt_cookie(ENTERPRISE_LEARNER_ROLE, str(self.enterprise_customer.uuid))

        mock_course_run = fake_catalog_api.FAKE_COURSE_RUN.copy()
        mock_course_run.update({'is_enrollable': run_is_enrollable})
        mock_course = fake_catalog_api.FAKE_COURSE.copy()
        mock_course.update({'course_runs': [mock_course_run]})
        enrollment_intention = create_mock_default_enterprise_enrollment_intention(
            enterprise_customer=self.enterprise_customer,
            mock_catalog_api_client=mock_catalog_api_client,
            content_metadata=mock_course,
        )

        mock_get_best_mode_from_course_key.return_value = VERIFIED_COURSE_MODE
        ecu = factories.EnterpriseCustomerUserFactory(
            user_id=self.user.id,
            enterprise_customer=self.enterprise_customer,
        )
        if unenrollment_exists:
            factories.EnterpriseCourseEnrollmentFactory(
                enterprise_customer_user=ecu,
                course_id=fake_catalog_api.FAKE_COURSE_RUN.get('key'),
                unenrolled=True,
            )
            mock_course_enrollment.return_value = mock.Mock(
                is_active=False,
                mode=VERIFIED_COURSE_MODE,
            )

        query_params = f'enterprise_customer_uuid={str(self.enterprise_customer.uuid)}'
        response = self.client.get(
            f"{settings.TEST_SERVER}{DEFAULT_ENTERPRISE_ENROLLMENT_INTENTION_LEARNER_STATUS_ENDPOINT}?{query_params}"
        )

        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        assert response_data['lms_user_id'] == self.user.id
        assert response_data['user_email'] == self.user.email
        assert response_data['enrollment_statuses'] == {
            'needs_enrollment': {
                'enrollable': [],
                'not_enrollable': [
                    self.get_default_enrollment_intention_with_learner_enrollment_state(
                        enrollment_intention,
                        is_course_run_enrollable=run_is_enrollable,
                        has_existing_enrollment=unenrollment_exists,
                        is_existing_enrollment_active=False if unenrollment_exists else None,
                        is_existing_enrollment_audit=False if unenrollment_exists else None,
                    )
                ],
            },
            'already_enrolled': [],
        }
        assert response_data['metadata'] == {
            'total_default_enterprise_enrollment_intentions': 1,
            'total_needs_enrollment': {
                'enrollable': 0,
                'not_enrollable': 1,
            },
            'total_already_enrolled': 0,
        }

    @mock.patch('enterprise.content_metadata.api.EnterpriseCatalogApiClient')
    @mock.patch('enterprise.models.utils.get_best_mode_from_course_key')
    def test_default_enrollment_intentions_learner_status_content_not_in_catalog(
        self,
        mock_get_best_mode_from_course_key,
        mock_catalog_api_client,
    ):
        """
        Test default enterprise enrollment intentions (not enrollable, no applicable
        catalog) for specific learner linked to enterprise customer.
        """
        self.set_jwt_cookie(ENTERPRISE_LEARNER_ROLE, str(self.enterprise_customer.uuid))
        enrollment_intention = create_mock_default_enterprise_enrollment_intention(
            enterprise_customer=self.enterprise_customer,
            mock_catalog_api_client=mock_catalog_api_client,
            catalog_list=[],
        )
        mock_get_best_mode_from_course_key.return_value = VERIFIED_COURSE_MODE
        factories.EnterpriseCustomerUserFactory(
            user_id=self.user.id,
            enterprise_customer=self.enterprise_customer,
        )
        query_params = f'enterprise_customer_uuid={str(self.enterprise_customer.uuid)}'
        response = self.client.get(
            f"{settings.TEST_SERVER}{DEFAULT_ENTERPRISE_ENROLLMENT_INTENTION_LEARNER_STATUS_ENDPOINT}?{query_params}"
        )
        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        assert response_data['lms_user_id'] == self.user.id
        assert response_data['user_email'] == self.user.email
        assert response_data['enrollment_statuses'] == {
            'needs_enrollment': {
                'enrollable': [],
                'not_enrollable': [
                    self.get_default_enrollment_intention_with_learner_enrollment_state(
                        enrollment_intention,
                        applicable_enterprise_catalog_uuids=[],
                        is_course_run_enrollable=True,
                        has_existing_enrollment=False,
                        is_existing_enrollment_active=None,
                        is_existing_enrollment_audit=None,
                    )
                ],
            },
            'already_enrolled': [],
        }
        assert response_data['metadata'] == {
            'total_default_enterprise_enrollment_intentions': 1,
            'total_needs_enrollment': {
                'enrollable': 0,
                'not_enrollable': 1,
            },
            'total_already_enrolled': 0,
        }

    @mock.patch('enterprise.content_metadata.api.EnterpriseCatalogApiClient')
    @mock.patch('enterprise.models.utils.get_best_mode_from_course_key')
    @mock.patch.object(EnterpriseCourseEnrollment, 'course_enrollment', new_callable=mock.PropertyMock)
    def test_default_enrollment_intentions_learner_status_already_enrolled_active(
        self,
        mock_course_enrollment,
        mock_get_best_mode_from_course_key,
        mock_catalog_api_client,
    ):
        """
        Test default enterprise enrollment intentions (already enrolled, active
        enrollment) for specific learner linked to enterprise customer.
        """
        self.set_jwt_cookie(ENTERPRISE_LEARNER_ROLE, str(self.enterprise_customer.uuid))
        enrollment_intention = create_mock_default_enterprise_enrollment_intention(
            enterprise_customer=self.enterprise_customer,
            mock_catalog_api_client=mock_catalog_api_client,
        )
        mock_get_best_mode_from_course_key.return_value = VERIFIED_COURSE_MODE
        enterprise_customer_user = factories.EnterpriseCustomerUserFactory(
            user_id=self.user.id,
            enterprise_customer=self.enterprise_customer,
        )
        factories.EnterpriseCourseEnrollmentFactory(
            enterprise_customer_user=enterprise_customer_user,
            course_id=fake_catalog_api.FAKE_COURSE_RUN.get('key'),
        )
        course_enrollment_kwargs = {
            'is_active': True,
            'mode': VERIFIED_COURSE_MODE,
        }
        mock_course_enrollment.return_value = mock.Mock(**course_enrollment_kwargs)
        query_params = f'enterprise_customer_uuid={str(self.enterprise_customer.uuid)}'
        response = self.client.get(
            f"{settings.TEST_SERVER}{DEFAULT_ENTERPRISE_ENROLLMENT_INTENTION_LEARNER_STATUS_ENDPOINT}?{query_params}"
        )
        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        assert response_data['lms_user_id'] == self.user.id
        assert response_data['user_email'] == self.user.email
        assert response_data['enrollment_statuses'] == {
            'needs_enrollment': {
                'enrollable': [],
                'not_enrollable': [],
            },
            'already_enrolled': [
                self.get_default_enrollment_intention_with_learner_enrollment_state(
                    enrollment_intention,
                    has_existing_enrollment=True,
                    is_existing_enrollment_active=True,
                    is_existing_enrollment_audit=False,
                )
            ],
        }
        assert response_data['metadata'] == {
            'total_default_enterprise_enrollment_intentions': 1,
            'total_needs_enrollment': {
                'enrollable': 0,
                'not_enrollable': 0,
            },
            'total_already_enrolled': 1,
        }

    @mock.patch('enterprise.content_metadata.api.EnterpriseCatalogApiClient')
    @mock.patch('enterprise.models.utils.get_best_mode_from_course_key')
    @mock.patch.object(EnterpriseCourseEnrollment, 'course_enrollment', new_callable=mock.PropertyMock)
    def test_default_enrollment_intentions_learner_status_already_enrolled_inactive(
        self,
        mock_course_enrollment,
        mock_get_best_mode_from_course_key,
        mock_catalog_api_client,
    ):
        """
        Test default enterprise enrollment intentions (already enrolled, inactive
        enrollment) for specific learner linked to enterprise customer.
        """
        self.set_jwt_cookie(ENTERPRISE_LEARNER_ROLE, str(self.enterprise_customer.uuid))
        enrollment_intention = create_mock_default_enterprise_enrollment_intention(
            enterprise_customer=self.enterprise_customer,
            mock_catalog_api_client=mock_catalog_api_client,
        )
        mock_get_best_mode_from_course_key.return_value = VERIFIED_COURSE_MODE
        enterprise_customer_user = factories.EnterpriseCustomerUserFactory(
            user_id=self.user.id,
            enterprise_customer=self.enterprise_customer,
        )
        factories.EnterpriseCourseEnrollmentFactory(
            enterprise_customer_user=enterprise_customer_user,
            course_id=fake_catalog_api.FAKE_COURSE_RUN.get('key'),
        )
        course_enrollment_kwargs = {
            'is_active': False,
            'mode': VERIFIED_COURSE_MODE,
        }
        mock_course_enrollment.return_value = mock.Mock(**course_enrollment_kwargs)
        query_params = f'enterprise_customer_uuid={str(self.enterprise_customer.uuid)}'
        response = self.client.get(
            f"{settings.TEST_SERVER}{DEFAULT_ENTERPRISE_ENROLLMENT_INTENTION_LEARNER_STATUS_ENDPOINT}?{query_params}"
        )
        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        assert response_data['lms_user_id'] == self.user.id
        assert response_data['user_email'] == self.user.email
        assert response_data['enrollment_statuses'] == {
            'needs_enrollment': {
                'enrollable': [
                    self.get_default_enrollment_intention_with_learner_enrollment_state(
                        enrollment_intention,
                        has_existing_enrollment=True,
                        is_existing_enrollment_active=False,
                        is_existing_enrollment_audit=False,
                    )
                ],
                'not_enrollable': [],
            },
            'already_enrolled': [],
        }
        assert response_data['metadata'] == {
            'total_default_enterprise_enrollment_intentions': 1,
            'total_needs_enrollment': {
                'enrollable': 1,
                'not_enrollable': 0,
            },
            'total_already_enrolled': 0,
        }

    @ddt.data(
        {'has_audit_mode_only': True},
        {'has_audit_mode_only': False},
    )
    @mock.patch('enterprise.content_metadata.api.EnterpriseCatalogApiClient')
    @mock.patch('enterprise.models.utils.get_best_mode_from_course_key')
    @mock.patch.object(EnterpriseCourseEnrollment, 'course_enrollment', new_callable=mock.PropertyMock)
    @ddt.unpack
    def test_default_enrollment_intentions_learner_status_already_enrolled_active_audit(
        self,
        mock_course_enrollment,
        mock_get_best_mode_from_course_key,
        mock_catalog_api_client,
        has_audit_mode_only,
    ):
        """
        Test default enterprise enrollment intentions (already enrolled, active
        audit enrollment) for specific learner linked to enterprise customer.
        """
        self.set_jwt_cookie(ENTERPRISE_LEARNER_ROLE, str(self.enterprise_customer.uuid))
        enrollment_intention = create_mock_default_enterprise_enrollment_intention(
            enterprise_customer=self.enterprise_customer,
            mock_catalog_api_client=mock_catalog_api_client,
        )

        best_mode_for_course_run = AUDIT_COURSE_MODE if has_audit_mode_only else VERIFIED_COURSE_MODE
        mock_get_best_mode_from_course_key.return_value = best_mode_for_course_run

        enterprise_customer_user = factories.EnterpriseCustomerUserFactory(
            user_id=self.user.id,
            enterprise_customer=self.enterprise_customer,
        )
        factories.EnterpriseCourseEnrollmentFactory(
            enterprise_customer_user=enterprise_customer_user,
            course_id=fake_catalog_api.FAKE_COURSE_RUN.get('key'),
        )
        course_enrollment_kwargs = {
            'is_active': True,
            'mode': AUDIT_COURSE_MODE,
        }
        mock_course_enrollment.return_value = mock.Mock(**course_enrollment_kwargs)
        query_params = f'enterprise_customer_uuid={str(self.enterprise_customer.uuid)}'
        response = self.client.get(
            f"{settings.TEST_SERVER}{DEFAULT_ENTERPRISE_ENROLLMENT_INTENTION_LEARNER_STATUS_ENDPOINT}?{query_params}"
        )
        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        assert response_data['lms_user_id'] == self.user.id
        assert response_data['user_email'] == self.user.email

        expected_enrollable = []
        expected_already_enrolled = []

        expected_serialized_intention = self.get_default_enrollment_intention_with_learner_enrollment_state(
            enrollment_intention,
            has_existing_enrollment=True,
            is_existing_enrollment_active=True,
            is_existing_enrollment_audit=True,
            best_mode_for_course_run=best_mode_for_course_run,
        )

        if has_audit_mode_only:
            expected_already_enrolled.append(expected_serialized_intention)
        else:
            expected_enrollable.append(expected_serialized_intention)

        assert response_data['enrollment_statuses'] == {
            'needs_enrollment': {
                'enrollable': expected_enrollable,
                'not_enrollable': [],
            },
            'already_enrolled': expected_already_enrolled,
        }
        assert response_data['metadata'] == {
            'total_default_enterprise_enrollment_intentions': 1,
            'total_needs_enrollment': {
                'enrollable': len(expected_enrollable),
                'not_enrollable': 0,
            },
            'total_already_enrolled': len(expected_already_enrolled),
        }

    @mock.patch('enterprise.content_metadata.api.EnterpriseCatalogApiClient')
    @mock.patch('enterprise.models.utils.get_best_mode_from_course_key')
    def test_default_enrollment_intentions_learner_status_staff_lms_user_id_override(
        self,
        mock_get_best_mode_from_course_key,
        mock_catalog_api_client,
    ):
        """
        Test default enterprise enrollment intentions for staff user, requesting a specific user
        linked to enterprise customer via lms_user_id query parameter.
        """
        self.set_jwt_cookie(ENTERPRISE_LEARNER_ROLE, str(self.enterprise_customer.uuid))

        # Create and login as a staff user
        staff_user = self.create_user(username='staff_username', password=TEST_PASSWORD, is_staff=True)
        self.client.login(username=staff_user.username, password=TEST_PASSWORD)

        enrollment_intention = create_mock_default_enterprise_enrollment_intention(
            enterprise_customer=self.enterprise_customer,
            mock_catalog_api_client=mock_catalog_api_client,
        )
        mock_get_best_mode_from_course_key.return_value = VERIFIED_COURSE_MODE
        factories.EnterpriseCustomerUserFactory(
            user_id=self.user.id,
            enterprise_customer=self.enterprise_customer,
        )
        query_params = (
            f'enterprise_customer_uuid={str(self.enterprise_customer.uuid)}'
            # Validates staff user can get back data for another user (i.e., request user is `staff_user`)
            f'&lms_user_id={self.user.id}'
        )
        response = self.client.get(
            f"{settings.TEST_SERVER}{DEFAULT_ENTERPRISE_ENROLLMENT_INTENTION_LEARNER_STATUS_ENDPOINT}?{query_params}"
        )
        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        assert response_data['lms_user_id'] == self.user.id
        assert response_data['user_email'] == self.user.email
        assert response_data['enrollment_statuses'] == {
            'needs_enrollment': {
                'enrollable': [
                    self.get_default_enrollment_intention_with_learner_enrollment_state(enrollment_intention)
                ],
                'not_enrollable': [],
            },
            'already_enrolled': [],
        }
        assert response_data['metadata'] == {
            'total_default_enterprise_enrollment_intentions': 1,
            'total_needs_enrollment': {
                'enrollable': 1,
                'not_enrollable': 0,
            },
            'total_already_enrolled': 0,
        }

    @mock.patch('enterprise.content_metadata.api.EnterpriseCatalogApiClient')
    @mock.patch('enterprise.models.utils.get_best_mode_from_course_key')
    def test_default_enrollment_intentions_learner_status_nonstaff_lms_user_id_override(
        self,
        mock_get_best_mode_from_course_key,
        mock_catalog_api_client
    ):
        """
        Test default enterprise enrollment intentions for non-staff user linked to enterprise customer.
        """
        self.set_jwt_cookie(ENTERPRISE_LEARNER_ROLE, str(self.enterprise_customer.uuid))
        enrollment_intention = create_mock_default_enterprise_enrollment_intention(
            enterprise_customer=self.enterprise_customer,
            mock_catalog_api_client=mock_catalog_api_client,
        )
        mock_get_best_mode_from_course_key.return_value = VERIFIED_COURSE_MODE
        factories.EnterpriseCustomerUserFactory(
            user_id=self.user.id,
            enterprise_customer=self.enterprise_customer,
        )
        query_params = (
            f'enterprise_customer_uuid={str(self.enterprise_customer.uuid)}'
            f'&lms_user_id={self.user.id + 1}'  # Validates non-staff user can't get back data for another user
        )
        response = self.client.get(
            f"{settings.TEST_SERVER}{DEFAULT_ENTERPRISE_ENROLLMENT_INTENTION_LEARNER_STATUS_ENDPOINT}?{query_params}"
        )

        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        assert response_data['lms_user_id'] == self.user.id
        assert response_data['user_email'] == self.user.email
        assert response_data['enrollment_statuses'] == {
            'needs_enrollment': {
                'enrollable': [
                    self.get_default_enrollment_intention_with_learner_enrollment_state(enrollment_intention)
                ],
                'not_enrollable': [],
            },
            'already_enrolled': [],
        }
        assert response_data['metadata'] == {
            'total_default_enterprise_enrollment_intentions': 1,
            'total_needs_enrollment': {
                'enrollable': 1,
                'not_enrollable': 0,
            },
            'total_already_enrolled': 0,
        }
