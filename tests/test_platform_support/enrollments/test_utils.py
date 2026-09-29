"""
Test the enterprise support utils.
"""
from unittest import mock
from unittest.case import TestCase

import pytest
from opaque_keys.edx.keys import CourseKey

from django.core.exceptions import ObjectDoesNotExist

from enterprise.platform_support.enrollments.exceptions import CourseIdMissingException, UserDoesNotExistException
from enterprise.platform_support.enrollments.utils import lms_update_or_create_enrollment

COURSE_STRING = 'course-v1:OpenEdX+OutlineCourse+Run3'
ENTERPRISE_UUID = 'enterprise_uuid'
COURSE_ID = CourseKey.from_string(COURSE_STRING)
USERNAME = 'test'
USER_ID = 1223
COURSE_MODE = 'verified'


class CourseEnrollmentError(Exception):
    """Stand-in for the platform's ``CourseEnrollmentError``."""

    def __init__(self, msg, data=None):
        super().__init__(msg)
        self.data = data


class CourseEnrollmentExistsError(CourseEnrollmentError):
    """Stand-in for the platform's ``CourseEnrollmentExistsError``."""

    def __init__(self, message, enrollment):
        super().__init__(message)
        self.enrollment = enrollment


class CourseEnrollmentNotUpdatableError(CourseEnrollmentError):
    """Stand-in for the platform's ``CourseEnrollmentNotUpdatableError``."""


class EnrollmentUtilsTest(TestCase):
    """
    Test enterprise support utils.
    """

    def setUp(self):
        super().setUp()
        self.a_user = mock.MagicMock()
        self.a_user.id = USER_ID
        self.a_user.username = USERNAME

        # Patch various imports from platform.
        for target, new in (
            ('enterprise.platform_support.enrollments.utils.enrollment_api', mock.DEFAULT),
            ('enterprise.platform_support.enrollments.utils.audit_log', mock.DEFAULT),
            ('enterprise.platform_support.enrollments.utils.CourseEnrollmentError', CourseEnrollmentError),
            ('enterprise.platform_support.enrollments.utils.CourseEnrollmentExistsError', CourseEnrollmentExistsError),
            (
                'enterprise.platform_support.enrollments.utils.CourseEnrollmentNotUpdatableError',
                CourseEnrollmentNotUpdatableError,
            ),
        ):
            patcher = mock.patch(target, new)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_validation_of_inputs_course_id(self):
        with pytest.raises(CourseIdMissingException):
            lms_update_or_create_enrollment(
                USERNAME, None, COURSE_MODE, is_active=True, enterprise_uuid=ENTERPRISE_UUID
            )

    def test_validation_of_inputs_user_not_provided(self):
        with pytest.raises(UserDoesNotExistException):
            lms_update_or_create_enrollment(
                None, COURSE_ID, COURSE_MODE, is_active=True, enterprise_uuid=ENTERPRISE_UUID
            )

    @mock.patch('enterprise.platform_support.enrollments.utils.User.objects.get')
    @mock.patch('enterprise.platform_support.enrollments.utils.transaction')
    def test_validation_of_inputs_user_not_found(
        self,
        mock_tx,
        mock_user_model,
    ):
        mock_tx.return_value.atomic.side_effect = None
        mock_user_model.side_effect = ObjectDoesNotExist()
        with pytest.raises(UserDoesNotExistException):
            lms_update_or_create_enrollment(
                USERNAME, COURSE_ID, COURSE_MODE, is_active=True, enterprise_uuid=ENTERPRISE_UUID
            )

    @mock.patch('enterprise.platform_support.enrollments.utils.enrollment_api.add_enrollment')
    @mock.patch('enterprise.platform_support.enrollments.utils.enrollment_api.get_enrollment')
    @mock.patch('enterprise.platform_support.enrollments.utils.User.objects.get')
    @mock.patch('enterprise.platform_support.enrollments.utils.transaction')
    def test_course_enrollment_error_raises(
        self,
        mock_tx,
        mock_user_model,
        mock_get_enrollment_api,
        mock_add_enrollment_api,
    ):
        mock_add_enrollment_api.side_effect = CourseEnrollmentError("test")
        mock_tx.return_value.atomic.side_effect = None

        mock_user_model.return_value = self.a_user
        mock_get_enrollment_api.return_value = None
        with pytest.raises(CourseEnrollmentError):
            lms_update_or_create_enrollment(
                USERNAME, COURSE_ID, COURSE_MODE, is_active=True, enterprise_uuid=ENTERPRISE_UUID
            )
            mock_get_enrollment_api.assert_called_once_with(USERNAME, str(COURSE_ID))

    @mock.patch('enterprise.platform_support.enrollments.utils.enrollment_api.add_enrollment')
    @mock.patch('enterprise.platform_support.enrollments.utils.enrollment_api.get_enrollment')
    @mock.patch('enterprise.platform_support.enrollments.utils.User.objects.get')
    @mock.patch('enterprise.platform_support.enrollments.utils.transaction')
    def test_course_group_error_raises(
        self,
        mock_tx,
        mock_user_model,
        mock_get_enrollment_api,
        mock_add_enrollment_api,
    ):
        # Stands in for a missing cohort (``CourseUserGroup.DoesNotExist``), which is not one of
        # the enrollment errors the function handles, so it must propagate.
        mock_add_enrollment_api.side_effect = ObjectDoesNotExist()
        mock_tx.return_value.atomic.side_effect = None

        mock_user_model.return_value = self.a_user
        mock_get_enrollment_api.return_value = None
        with pytest.raises(ObjectDoesNotExist):
            lms_update_or_create_enrollment(
                USERNAME, COURSE_ID, COURSE_MODE, is_active=True, enterprise_uuid=ENTERPRISE_UUID
            )
        mock_get_enrollment_api.assert_called_once_with(USERNAME, str(COURSE_ID))

    @mock.patch('enterprise.platform_support.enrollments.utils.enrollment_api.add_enrollment')
    @mock.patch('enterprise.platform_support.enrollments.utils.enrollment_api.get_enrollment')
    @mock.patch('enterprise.platform_support.enrollments.utils.User.objects.get')
    @mock.patch('enterprise.platform_support.enrollments.utils.transaction')
    def test_calls_enrollment_and_cohort_apis(
        self,
        mock_tx,
        mock_user_model,
        mock_get_enrollment_api,
        mock_add_enrollment_api,
    ):
        expected_response = {'mode': COURSE_MODE, 'is_active': True}

        mock_add_enrollment_api.return_value = expected_response
        mock_tx.return_value.atomic.side_effect = None

        mock_user_model.return_value = self.a_user
        mock_get_enrollment_api.return_value = None

        response = lms_update_or_create_enrollment(
            USERNAME, COURSE_ID, COURSE_MODE, is_active=True, enterprise_uuid=ENTERPRISE_UUID
        )
        assert response == expected_response
        mock_add_enrollment_api.assert_called_once_with(
            USERNAME,
            str(COURSE_ID),
            mode=COURSE_MODE,
            is_active=True,
            enrollment_attributes=None,
            enterprise_uuid=ENTERPRISE_UUID,
            force_enrollment=False,
        )
        mock_get_enrollment_api.assert_called_once_with(USERNAME, str(COURSE_ID))

    @mock.patch('enterprise.platform_support.enrollments.utils.enrollment_api.add_enrollment')
    @mock.patch('enterprise.platform_support.enrollments.utils.enrollment_api.get_enrollment')
    @mock.patch('enterprise.platform_support.enrollments.utils.User.objects.get')
    @mock.patch('enterprise.platform_support.enrollments.utils.transaction')
    def test_passes_force_enrollment_flag(
        self,
        mock_tx,
        mock_user_model,
        mock_get_enrollment_api,
        mock_add_enrollment_api,
    ):
        """
        Everything about this test is the same as the standard happy case, except we're just making sure the
        force_enrollment flag gets passed to add_enrollment().
        """
        expected_response = {'mode': COURSE_MODE, 'is_active': True}

        mock_add_enrollment_api.return_value = expected_response
        mock_tx.return_value.atomic.side_effect = None

        mock_user_model.return_value = self.a_user
        mock_get_enrollment_api.return_value = None

        response = lms_update_or_create_enrollment(
            USERNAME, COURSE_ID, COURSE_MODE, is_active=True, enterprise_uuid=ENTERPRISE_UUID, force_enrollment=True
        )
        assert response == expected_response
        mock_add_enrollment_api.assert_called_once_with(
            USERNAME,
            str(COURSE_ID),
            mode=COURSE_MODE,
            is_active=True,
            enrollment_attributes=None,
            enterprise_uuid=ENTERPRISE_UUID,
            force_enrollment=True,  # Literally the only purpose of this test.
        )
        mock_get_enrollment_api.assert_called_once_with(USERNAME, str(COURSE_ID))

    @mock.patch('enterprise.platform_support.enrollments.utils.enrollment_api.add_enrollment')
    @mock.patch('enterprise.platform_support.enrollments.utils.enrollment_api.get_enrollment')
    @mock.patch('enterprise.platform_support.enrollments.utils.User.objects.get')
    @mock.patch('enterprise.platform_support.enrollments.utils.transaction')
    def test_existing_enrollment_does_not_fail(
        self,
        mock_tx,
        mock_user_model,
        mock_get_enrollment_api,
        mock_add_enrollment_api,
    ):
        expected_response = {'mode': COURSE_MODE, 'is_active': True}
        enrollment_response = {'mode': COURSE_MODE, 'is_active': True}

        mock_add_enrollment_api.side_effect = CourseEnrollmentExistsError("test", {})
        mock_tx.return_value.atomic.side_effect = None

        mock_get_enrollment_api.return_value = enrollment_response
        mock_user_model.return_value = self.a_user

        response = lms_update_or_create_enrollment(
            USERNAME, COURSE_ID, COURSE_MODE, is_active=True, enterprise_uuid=ENTERPRISE_UUID
        )
        mock_add_enrollment_api.assert_not_called()
        assert response == expected_response
        mock_get_enrollment_api.assert_called_once()

    @mock.patch('enterprise.platform_support.enrollments.utils.enrollment_api.update_enrollment')
    @mock.patch('enterprise.platform_support.enrollments.utils.enrollment_api.get_enrollment')
    @mock.patch('enterprise.platform_support.enrollments.utils.enrollment_api.add_enrollment')
    @mock.patch('enterprise.platform_support.enrollments.utils.User.objects.get')
    @mock.patch('enterprise.platform_support.enrollments.utils.transaction')
    def test_upgrade_user_enrollment_mode(
        self,
        mock_tx,
        mock_user_model,
        mock_add_enrollment_api,
        mock_get_enrollment_api,
        mock_update_enrollment_api,
    ):
        enrollment_response = {'mode': COURSE_MODE, 'is_active': True}
        mock_get_enrollment_api.return_value = {
            'mode': 'audit',
            'is_active': True,
        }

        mock_update_enrollment_api.return_value = {
            'mode': 'verified',
            'is_active': True,
        }
        mock_tx.return_value.atomic.side_effect = None
        mock_user_model.return_value = self.a_user

        upgraded_enrollment = lms_update_or_create_enrollment(
            USERNAME, COURSE_ID, desired_mode=COURSE_MODE, is_active=True
        )

        assert upgraded_enrollment == enrollment_response
        mock_update_enrollment_api.assert_called_once_with(
            USERNAME,
            str(COURSE_ID),
            mode='verified',
            is_active=True,
            enrollment_attributes=None,
        )

        mock_get_enrollment_api.assert_called_once_with(USERNAME, str(COURSE_ID))
        mock_add_enrollment_api.assert_not_called()

    @mock.patch('enterprise.platform_support.enrollments.utils.enrollment_api.update_enrollment')
    @mock.patch('enterprise.platform_support.enrollments.utils.enrollment_api.get_enrollment')
    @mock.patch('enterprise.platform_support.enrollments.utils.enrollment_api.add_enrollment')
    @mock.patch('enterprise.platform_support.enrollments.utils.User.objects.get')
    @mock.patch('enterprise.platform_support.enrollments.utils.transaction')
    def test_upgrade_user_enrollment_mode_already_verified(
        self,
        mock_tx,
        mock_user_model,
        mock_add_enrollment_api,
        mock_get_enrollment_api,
        mock_update_enrollment_api,
    ):
        existing_enrollment = {
            'mode': 'verified',
            'is_active': True,
        }
        mock_get_enrollment_api.return_value = existing_enrollment

        mock_tx.return_value.atomic.side_effect = None
        mock_user_model.return_value = self.a_user

        upgraded_enrollment = lms_update_or_create_enrollment(
            USERNAME, COURSE_ID, desired_mode='verified', is_active=True
        )

        assert upgraded_enrollment == existing_enrollment
        mock_update_enrollment_api.assert_not_called()
        mock_get_enrollment_api.assert_called_once()
        mock_add_enrollment_api.assert_not_called()
