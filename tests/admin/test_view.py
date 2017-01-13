# -*- coding: utf-8 -*-
"""
Tests for the `edx-enterprise` admin forms module.
"""
from __future__ import absolute_import, unicode_literals

import json

import ddt
import mock
import six
from edx_rest_api_client.exceptions import HttpClientError
from pytest import mark

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.messages import constants as messages
from django.test import Client, TestCase, override_settings

from enterprise import admin as enterprise_admin
from enterprise.admin import EnterpriseCustomerManageLearnersView
from enterprise.admin.forms import ManageLearnersForm
from enterprise.admin.utils import ValidationMessages, get_course_runs_from_program
from enterprise.django_compatibility import reverse
from enterprise.models import EnterpriseCustomerUser, PendingEnterpriseCustomerUser
from test_utils import fake_catalog_api, fake_enrollment_api
from test_utils.factories import (FAKER, EnterpriseCustomerFactory, EnterpriseCustomerUserFactory,
                                  PendingEnterpriseCustomerUserFactory, UserFactory)
from test_utils.fake_catalog_api import FAKE_PROGRAM_RESPONSE2
from test_utils.file_helpers import MakeCsvStreamContextManager


class BaseTestEnterpriseCustomerManageLearnersView(TestCase):
    """
    Common functionality for EnterpriseCustomerManageLearnersView tests.
    """

    def setUp(self):
        """
        Test set up - installs common dependencies.
        """
        super(BaseTestEnterpriseCustomerManageLearnersView, self).setUp()
        self.user = UserFactory.create(is_staff=True, is_active=True)
        self.user.set_password("QWERTY")
        self.user.save()
        self.enterprise_customer = EnterpriseCustomerFactory()
        self.default_context = {
            "has_permission": True,
            "opts": self.enterprise_customer._meta,
            "user": self.user
        }
        self.view_url = reverse(
            "admin:" + enterprise_admin.utils.UrlNames.MANAGE_LEARNERS,
            args=(self.enterprise_customer.uuid,)
        )
        self.client = Client()
        self.context_parameters = EnterpriseCustomerManageLearnersView.ContextParameters

    def _test_common_context(self, actual_context, context_overrides=None):
        """
        Test common context parts.
        """
        expected_context = {}
        expected_context.update(self.default_context)
        expected_context.update(context_overrides or {})

        for context_key, expected_value in six.iteritems(expected_context):
            assert actual_context[context_key] == expected_value

    @staticmethod
    def _assert_no_record(email):
        """
        Assert that linked user record with specified email does not exist.
        """
        assert len(PendingEnterpriseCustomerUser.objects.filter(user_email=email)) == 0
        try:
            user = User.objects.get(email=email)
            assert len(EnterpriseCustomerUser.objects.filter(user_id=user.id)) == 0
        except User.DoesNotExist:
            pass

    def _login(self):
        """
        Log user in.
        """
        assert self.client.login(username=self.user.username, password="QWERTY")  # make sure we've logged in

    def _assert_django_messages(self, post_response, expected_messages):
        """
        Verify that the expected_messages are included in the context of the next response.
        """
        self.assertRedirects(post_response, self.view_url, fetch_redirect_response=False)
        get_response = self.client.get(self.view_url)
        response_messages = set(
            (m.level, m.message) for m in get_response.context['messages']  # pylint: disable=no-member
        )
        assert response_messages == expected_messages


@ddt.ddt
@mark.django_db
@override_settings(ROOT_URLCONF="test_utils.admin_urls")
class TestEnterpriseCustomerManageLearnersViewGet(BaseTestEnterpriseCustomerManageLearnersView):
    """
    Tests for EnterpriseCustomerManageLearnersView GET endpoint.
    """

    def _test_get_response(self, response, linked_learners, pending_linked_learners):
        """
        Test view GET response for common parts.
        """
        assert response.status_code == 200
        self._test_common_context(response.context)
        assert list(response.context[self.context_parameters.LEARNERS]) == linked_learners
        assert list(response.context[self.context_parameters.PENDING_LEARNERS]) == pending_linked_learners
        assert response.context[self.context_parameters.ENTERPRISE_CUSTOMER] == self.enterprise_customer
        assert not response.context[self.context_parameters.MANAGE_LEARNERS_FORM].is_bound

    def test_get_not_logged_in(self):
        assert settings.SESSION_COOKIE_NAME not in self.client.cookies  # precondition check - no session cookie

        response = self.client.get(self.view_url)

        assert response.status_code == 302

    def test_get_empty_links(self):
        self._login()

        response = self.client.get(self.view_url)
        self._test_get_response(response, [], [])

    def test_get_existing_links_only(self):
        self._login()

        users = [
            EnterpriseCustomerUserFactory(enterprise_customer=self.enterprise_customer),
            EnterpriseCustomerUserFactory(enterprise_customer=self.enterprise_customer),
            EnterpriseCustomerUserFactory(enterprise_customer=self.enterprise_customer),
        ]

        response = self.client.get(self.view_url)
        self._test_get_response(response, users, [])

    def test_get_existing_and_pending_links(self):
        self._login()

        linked_learners = [
            EnterpriseCustomerUserFactory(enterprise_customer=self.enterprise_customer),
            EnterpriseCustomerUserFactory(enterprise_customer=self.enterprise_customer),
            EnterpriseCustomerUserFactory(enterprise_customer=self.enterprise_customer),
        ]
        pending_linked_learners = [
            PendingEnterpriseCustomerUserFactory(enterprise_customer=self.enterprise_customer),
            PendingEnterpriseCustomerUserFactory(enterprise_customer=self.enterprise_customer),
        ]

        response = self.client.get(self.view_url)
        self._test_get_response(response, linked_learners, pending_linked_learners)

    def test_get_with_search_param(self):
        self._login()

        linked_learners = [
            EnterpriseCustomerUserFactory(
                enterprise_customer=self.enterprise_customer,
                user_id=UserFactory(
                    username='bob',
                    email='bob@thing.com',
                ).id,
            ),
            EnterpriseCustomerUserFactory(
                enterprise_customer=self.enterprise_customer,
                user_id=UserFactory(
                    username='frank',
                    email='iloveschool@example.com',
                ).id,
            ),
            EnterpriseCustomerUserFactory(
                enterprise_customer=self.enterprise_customer,
                user_id=UserFactory(
                    username='angela',
                    email='cats@cats.org',
                ).id,
            ),
        ]
        pending_linked_learners = [
            PendingEnterpriseCustomerUserFactory(
                enterprise_customer=self.enterprise_customer,
                user_email='schoolisfun@example.com',
            ),
            PendingEnterpriseCustomerUserFactory(
                enterprise_customer=self.enterprise_customer,
                user_email='joebob@wherever.com',
            ),
        ]

        response = self.client.get(self.view_url + '?q=bob')
        self._test_get_response(response, [linked_learners[0]], [pending_linked_learners[1]])

        response = self.client.get(self.view_url + '?q=SCHOOL')
        self._test_get_response(response, [linked_learners[1]], [pending_linked_learners[0]])

        response = self.client.get(self.view_url + '?q=longstringthatdoesnthappen')
        self._test_get_response(response, [], [])


@ddt.ddt
@mark.django_db
@override_settings(ROOT_URLCONF="test_utils.admin_urls")
class TestEnterpriseCustomerManageLearnersViewPostSingleUser(BaseTestEnterpriseCustomerManageLearnersView):
    """
    Tests for EnterpriseCustomerManageLearnersView POST endpoint - single user linking.
    """

    def test_post_not_logged_in(self):
        assert settings.SESSION_COOKIE_NAME not in self.client.cookies  # precondition check - no session cookie

        response = self.client.post(self.view_url, data={})

        assert response.status_code == 302

    @ddt.data(
        "test@example.com", "adam.jensen@sarif.com",
    )
    def test_post_new_user_by_email(self, email):
        # precondition checks:
        self._login()
        self._assert_no_record(email)  # there're no record with current email

        response = self.client.post(self.view_url, data={ManageLearnersForm.Fields.EMAIL_OR_USERNAME: email})

        self.assertRedirects(response, self.view_url)
        assert len(PendingEnterpriseCustomerUser.objects.filter(user_email=email)) == 1

    @ddt.unpack
    @ddt.data(
        ("TestGuy", "test@example.com"),
        ("AdamJensen", "adam.jensen@sarif.com"),
    )
    def test_post_new_user_by_username(self, username, email):
        # precondition checks:
        self._login()
        self._assert_no_record(email)  # there're no record with current email

        user = UserFactory(username=username, email=email)

        response = self.client.post(self.view_url, data={ManageLearnersForm.Fields.EMAIL_OR_USERNAME: username})

        self.assertRedirects(response, self.view_url)
        assert len(EnterpriseCustomerUser.objects.filter(user_id=user.id)) == 1

    def test_post_invalid_email(self):
        # precondition checks:
        self._login()
        assert len(EnterpriseCustomerUser.objects.all()) == 0  # there're no link records
        assert len(PendingEnterpriseCustomerUser.objects.all()) == 0  # there're no pending link records

        response = self.client.post(self.view_url, data={ManageLearnersForm.Fields.EMAIL_OR_USERNAME: "invalid_email"})

        # TODO: remove suppressions when https://github.com/landscapeio/pylint-django/issues/78 is fixed
        assert response.status_code == 200
        self._test_common_context(response.context)  # pylint: disable=no-member
        assert len(EnterpriseCustomerUser.objects.all()) == 0
        assert response.context[self.context_parameters.MANAGE_LEARNERS_FORM].is_bound  # pylint: disable=no-member

    def test_post_invalid_email_form_validation_suppressed(self):
        # precondition checks:
        self._login()
        assert len(EnterpriseCustomerUser.objects.all()) == 0  # there're no link records
        assert len(PendingEnterpriseCustomerUser.objects.all()) == 0  # there're no pending link records

        invalid_email = "invalid_email"

        with mock.patch("enterprise.admin.views.ManageLearnersForm.clean_email_or_username") as patched_clean:
            patched_clean.return_value = invalid_email
            response = self.client.post(
                self.view_url, data={ManageLearnersForm.Fields.EMAIL_OR_USERNAME: invalid_email}
            )

        # TODO: remove suppressions when https://github.com/landscapeio/pylint-django/issues/78 is fixed
        assert response.status_code == 200
        self._test_common_context(response.context)  # pylint: disable=no-member
        assert len(EnterpriseCustomerUser.objects.all()) == 0
        # pylint: disable=no-member
        manage_learners_form = response.context[self.context_parameters.MANAGE_LEARNERS_FORM]
        assert manage_learners_form.is_bound  # pylint: disable=no-member
        assert manage_learners_form.errors == {
            ManageLearnersForm.Fields.EMAIL_OR_USERNAME: [
                ValidationMessages.INVALID_EMAIL_OR_USERNAME.format(argument=invalid_email)
            ]
        }

    def _test_post_existing_record_response(self, response):
        """
        Test view POST response for common parts.
        """
        assert response.status_code == 200
        self._test_common_context(response.context)
        manage_learners_form = response.context[self.context_parameters.MANAGE_LEARNERS_FORM]
        assert manage_learners_form.is_bound
        assert ManageLearnersForm.Fields.EMAIL_OR_USERNAME in manage_learners_form.errors
        assert len(manage_learners_form.errors[ManageLearnersForm.Fields.EMAIL_OR_USERNAME]) >= 1

    def test_post_existing_record(self):
        # precondition checks:
        self._login()

        email = FAKER.email()

        user = UserFactory(email=email)
        EnterpriseCustomerUserFactory(user_id=user.id)
        assert len(EnterpriseCustomerUser.objects.filter(user_id=user.id)) == 1
        response = self.client.post(self.view_url, data={ManageLearnersForm.Fields.EMAIL_OR_USERNAME: email})
        self._test_post_existing_record_response(response)
        assert len(EnterpriseCustomerUser.objects.filter(user_id=user.id)) == 1

    def test_post_existing_pending_record(self):
        # precondition checks:
        self._login()

        email = FAKER.email()

        PendingEnterpriseCustomerUserFactory(user_email=email)
        assert len(PendingEnterpriseCustomerUser.objects.filter(user_email=email)) == 1

        response = self.client.post(self.view_url, data={ManageLearnersForm.Fields.EMAIL_OR_USERNAME: email})
        self._test_post_existing_record_response(response)
        assert len(PendingEnterpriseCustomerUser.objects.filter(user_email=email)) == 1

    def _enroll_user_request(self, user, mode, course_id="", program_id=""):
        """
        Perform post request to log in and submit the form to enroll a user.
        """
        self._login()
        response = self.client.post(self.view_url, data={
            ManageLearnersForm.Fields.EMAIL_OR_USERNAME: user.username,
            ManageLearnersForm.Fields.COURSE_MODE: mode,
            ManageLearnersForm.Fields.COURSE: course_id,
            ManageLearnersForm.Fields.PROGRAM: program_id,
        })
        return response

    @mock.patch("enterprise.admin.views.EnrollmentApiClient")
    @mock.patch("enterprise.admin.forms.EnrollmentApiClient")
    def test_post_enroll_user(self, forms_client, views_client):
        views_instance = views_client.return_value
        views_instance.enroll_user_in_course.side_effect = fake_enrollment_api.enroll_user_in_course
        forms_instance = forms_client.return_value
        forms_instance.get_course_details.side_effect = fake_enrollment_api.get_course_details
        user = UserFactory()
        course_id = "course-v1:HarvardX+CoolScience+2016"
        mode = "verified"
        response = self._enroll_user_request(user, mode, course_id=course_id)
        views_instance.enroll_user_in_course.assert_called_once()
        views_instance.enroll_user_in_course.assert_called_with(
            user.username,
            course_id,
            mode,
        )
        self._assert_django_messages(response, set([
            (messages.SUCCESS, "1 user was enrolled to {}.".format(course_id)),
        ]))

    @mock.patch("enterprise.admin.views.EnrollmentApiClient")
    @mock.patch("enterprise.admin.forms.EnrollmentApiClient")
    def test_post_enrollment_error(self, forms_client, views_client):
        views_instance = views_client.return_value
        views_instance.enroll_user_in_course.side_effect = HttpClientError(
            "Client Error", content=json.dumps({"message": "test"}).encode()
        )
        forms_instance = forms_client.return_value
        forms_instance.get_course_details.side_effect = fake_enrollment_api.get_course_details
        user = UserFactory()
        course_id = "course-v1:HarvardX+CoolScience+2016"
        mode = "verified"
        response = self._enroll_user_request(user, mode, course_id=course_id)
        self._assert_django_messages(response, set([
            (messages.ERROR, "Enrollment of some users failed: {}".format(user.email)),
        ]))

    @mock.patch("enterprise.admin.views.EnrollmentApiClient")
    @mock.patch("enterprise.admin.forms.CourseCatalogApiClient")
    def test_post_enroll_user_into_program(self, catalog_client, views_client):
        views_instance = views_client.return_value
        views_instance.enroll_user_in_course.side_effect = fake_enrollment_api.enroll_user_in_course
        catalog_api_instance = catalog_client.return_value
        catalog_api_instance.get_program_by_uuid.side_effect = fake_catalog_api.get_program_by_uuid
        catalog_api_instance.get_common_course_modes.side_effect = {"professional"}
        user = UserFactory()
        program = FAKE_PROGRAM_RESPONSE2
        expected_courses = get_course_runs_from_program(program)
        mode = "professional"
        response = self._enroll_user_request(user, mode, program_id=program["uuid"])
        assert views_instance.enroll_user_in_course.call_count == len(expected_courses)
        self._assert_django_messages(response, set(
            [
                (messages.SUCCESS, "1 user was enrolled to {}.".format(course_id))
                for course_id in expected_courses
            ]
        ))

    @mock.patch("enterprise.admin.views.EnrollmentApiClient")
    @mock.patch("enterprise.admin.forms.CourseCatalogApiClient")
    def test_post_enroll_user_into_program_error(self, catalog_client, views_client):
        views_instance = views_client.return_value
        views_instance.enroll_user_in_course.side_effect = HttpClientError(
            "Client Error", content=json.dumps({"message": "test"}).encode()
        )
        catalog_api_instance = catalog_client.return_value
        catalog_api_instance.get_program_by_uuid.side_effect = fake_catalog_api.get_program_by_uuid
        catalog_api_instance.get_common_course_modes.side_effect = {"professional"}
        user = UserFactory()
        program = FAKE_PROGRAM_RESPONSE2
        expected_courses = get_course_runs_from_program(program)
        mode = "professional"
        response = self._enroll_user_request(user, mode, program_id=program["uuid"])
        assert views_instance.enroll_user_in_course.call_count == len(expected_courses)
        self._assert_django_messages(response, set([
            (messages.ERROR, "Enrollment of some users failed: {}".format(user.email)),
        ]))


@ddt.ddt
@mark.django_db
@override_settings(ROOT_URLCONF="test_utils.admin_urls")
class TestEnterpriseCustomerManageLearnersViewPostBulkUpload(BaseTestEnterpriseCustomerManageLearnersView):
    """
    Tests for EnterpriseCustomerManageLearnersView POST endpoint - bulk user linking.
    """

    def _get_form(self, response):
        """
        Utility function to capture common parts of assertions on form errors.

        Arguments:
            response (HttpResponse): View response.

        Returns:
            ManageLearnersForm: bound instance of ManageLearnersForm used to render the response.

        Raises:
            AssertionError: if response status code is not 200 or form is unbound.
        """
        assert response.status_code == 200
        self._test_common_context(response.context)  # pylint: disable=no-member
        # pylint: disable=no-member
        manage_learners_form = response.context[self.context_parameters.MANAGE_LEARNERS_FORM]
        assert manage_learners_form.is_bound
        return manage_learners_form

    @staticmethod
    def _assert_line_message(actual_message, lineno, expected_message):
        """
        Assert that `actual_message` contains line number and `expected_message`
        """
        assert "Error at line {}".format(lineno) in actual_message
        assert expected_message in actual_message

    def _perform_request(self, columns, data, course=None, program=None, course_mode=None):
        """
        Perform bulk upload request with specified columns and data.

        Arguments:
            columns (list): CSV column header
            data (list): CSV contents.
            course (str): The course ID entered in the form.
            course_mode (str): The enrollment mode entered in the form.

        Returns:
            HttpResponse: View response.
        """
        with MakeCsvStreamContextManager(columns, data) as stream:
            post_data = {ManageLearnersForm.Fields.BULK_UPLOAD: stream}
            if program is not None:
                post_data[ManageLearnersForm.Fields.PROGRAM] = program
            if course is not None:
                post_data[ManageLearnersForm.Fields.COURSE] = course
            if course_mode is not None:
                post_data[ManageLearnersForm.Fields.COURSE_MODE] = course_mode
            response = self.client.post(self.view_url, data=post_data)
        return response

    def test_post_not_logged_in(self):
        assert settings.SESSION_COOKIE_NAME not in self.client.cookies  # precondition check - no session cookie

        response = self.client.post(self.view_url, data={})

        assert response.status_code == 302

    def test_post_invalid_headers(self):
        self._login()

        assert len(EnterpriseCustomerUser.objects.all()) == 0, "Precondition check: no linked users"
        assert len(PendingEnterpriseCustomerUser.objects.all()) == 0, "Precondition check: no pending linked users"

        invalid_columns = ["invalid", "header"]
        response = self._perform_request(invalid_columns, [("QWE",), ("ASD", )])

        assert len(EnterpriseCustomerUser.objects.all()) == 0, "No users should be linked"
        assert len(PendingEnterpriseCustomerUser.objects.all()) == 0, "No pending linked user records should be created"

        expected_message = ValidationMessages.MISSING_EXPECTED_COLUMNS.format(
            expected_columns=", ".join({ManageLearnersForm.CsvColumns.EMAIL}),
            actual_columns=", ".join(invalid_columns)
        )

        manage_learners_form = self._get_form(response)
        assert manage_learners_form.errors == {
            ManageLearnersForm.Fields.GENERAL_ERRORS: [ValidationMessages.BULK_LINK_FAILED],
            ManageLearnersForm.Fields.BULK_UPLOAD: [expected_message]
        }

    def test_post_invalid_email_error_skips_all(self):
        self._login()
        user = UserFactory()
        invalid_email = "invalid"

        assert len(EnterpriseCustomerUser.objects.all()) == 0, "Precondition check: no linked users"
        assert len(PendingEnterpriseCustomerUser.objects.all()) == 0, "Precondition check: no pending linked users"

        columns = [ManageLearnersForm.CsvColumns.EMAIL]
        data = [
            (FAKER.email(),),  # valid not previously seen email
            (user.email,),  # valid user email
            (invalid_email,)  # invalid email
        ]
        response = self._perform_request(columns, data)

        assert not EnterpriseCustomerUser.objects.all().exists(), "No linked users should be created"
        assert not PendingEnterpriseCustomerUser.objects.all().exists(), "No pending linked users should be created"

        manage_learners_form = self._get_form(response)
        bulk_upload_errors = manage_learners_form.errors[ManageLearnersForm.Fields.BULK_UPLOAD]

        line_error_message = ValidationMessages.INVALID_EMAIL.format(argument=invalid_email)
        self._assert_line_message(bulk_upload_errors[0], 3, line_error_message)

    def test_post_existing_and_duplicates(self):
        self._login()
        user = UserFactory()
        linked_user = UserFactory()
        EnterpriseCustomerUserFactory(user_id=linked_user.id)
        new_email = FAKER.email()

        assert EnterpriseCustomerUser.objects.count() == 1, "Precondition check: Single linked user"
        assert EnterpriseCustomerUser.objects.filter(user_id=linked_user.id).exists()
        assert not PendingEnterpriseCustomerUser.objects.exists(), "Precondition check: no pending user links"

        columns = [ManageLearnersForm.CsvColumns.EMAIL]
        data = [
            (linked_user.email,),  # a user that is already linked to this EC
            (new_email,),  # valid not previously seen email
            (user.email,),  # valid user email
            (user.email,),  # valid user email repeated
        ]
        response = self._perform_request(columns, data)

        assert EnterpriseCustomerUser.objects.count() == 2, \
            "Single linked user remains, and one new link is created"
        assert EnterpriseCustomerUser.objects.filter(user_id=linked_user.id).exists()
        assert EnterpriseCustomerUser.objects.filter(user_id=user.id).exists()
        assert PendingEnterpriseCustomerUser.objects.count() == 1, "One pending linked users should be created"
        assert PendingEnterpriseCustomerUser.objects.filter(user_email=new_email).exists()
        self._assert_django_messages(response, set([
            (messages.SUCCESS, "2 new users were linked to {}.".format(self.enterprise_customer.name)),
            (
                messages.WARNING,
                "Some users were already linked to this Enterprise Customer: {}".format(linked_user.email)
            ),
            (messages.WARNING, "Some duplicate emails in the CSV were ignored: {}".format(user.email)),
        ]))

    def test_post_successful_test(self):
        """
        Test bulk upload in complex.
        """
        self._login()

        assert len(EnterpriseCustomerUser.objects.all()) == 0, "Precondition check: no linked users"
        assert len(PendingEnterpriseCustomerUser.objects.all()) == 0, "Precondition check: no pending linked users"

        user_by_email = UserFactory()
        previously_not_seen_email = FAKER.email()

        columns = [ManageLearnersForm.CsvColumns.EMAIL]
        data = [
            (previously_not_seen_email, ),  # should create PendingEnterpriseCustomerUser
            (user_by_email.email, ),  # should create EnterpriseCustomerUser by email
        ]

        response = self._perform_request(columns, data)

        assert EnterpriseCustomerUser.objects.filter(user_id=user_by_email.id).exists(), \
            "it should create EnterpriseCustomerRecord by email"
        assert PendingEnterpriseCustomerUser.objects.filter(user_email=previously_not_seen_email).exists(), \
            "it should create EnterpriseCustomerRecord by email"
        self._assert_django_messages(response, set([
            (messages.SUCCESS, "2 new users were linked to {}.".format(self.enterprise_customer.name)),
        ]))

    @mock.patch("enterprise.admin.views.EnrollmentApiClient")
    @mock.patch("enterprise.admin.forms.EnrollmentApiClient")
    def test_post_link_and_enroll(self, forms_client, views_client):
        """
        Test bulk upload with linking and enrolling
        """
        views_instance = views_client.return_value
        views_instance.enroll_user_in_course.side_effect = fake_enrollment_api.enroll_user_in_course
        forms_instance = forms_client.return_value
        forms_instance.get_course_details.side_effect = fake_enrollment_api.get_course_details
        self._login()
        user = UserFactory.create()
        unknown_email = FAKER.email()
        columns = [ManageLearnersForm.CsvColumns.EMAIL]
        data = [(user.email,), (unknown_email,)]
        course_id = "course-v1:EnterpriseX+Training+2017"
        course_mode = "professional"

        response = self._perform_request(columns, data, course=course_id, course_mode=course_mode)

        views_instance.enroll_user_in_course.assert_called_once()
        views_instance.enroll_user_in_course.assert_called_with(
            user.username,
            course_id,
            course_mode
        )
        pending_user_message = (
            "The following users do not have an account on Test platform. They have not been enrolled in the course. "
            "When these users create an account, they will be enrolled in the course automatically: {}"
        )
        self._assert_django_messages(response, set([
            (messages.SUCCESS, "2 new users were linked to {}.".format(self.enterprise_customer.name)),
            (messages.SUCCESS, "1 user was enrolled to {}.".format(course_id)),
            (messages.WARNING, pending_user_message.format(unknown_email)),
        ]))
        assert PendingEnterpriseCustomerUser.objects.all()[0].pendingenrollment_set.all()[0].course_id == course_id

    @mock.patch("enterprise.admin.views.EnrollmentApiClient")
    @mock.patch("enterprise.admin.forms.CourseCatalogApiClient")
    def test_post_link_and_enroll_into_program(self, catalog_client, views_client):
        """
        Test bulk upload with linking and enrolling
        """
        views_instance = views_client.return_value
        views_instance.enroll_user_in_course.side_effect = fake_enrollment_api.enroll_user_in_course
        catalog_api_instance = catalog_client.return_value
        catalog_api_instance.get_program_by_uuid.side_effect = fake_catalog_api.get_program_by_uuid
        catalog_api_instance.get_common_course_modes.side_effect = {"professional"}
        self._login()
        user = UserFactory.create()
        unknown_email = FAKER.email()
        columns = [ManageLearnersForm.CsvColumns.EMAIL]
        data = [(user.email,), (unknown_email,)]
        program = FAKE_PROGRAM_RESPONSE2
        course_mode = "professional"
        expected_courses = get_course_runs_from_program(program)
        response = self._perform_request(columns, data, program=program["uuid"], course_mode=course_mode)

        assert views_instance.enroll_user_in_course.call_count == len(expected_courses)
        for course_id in expected_courses:
            views_instance.enroll_user_in_course.assert_any_call(
                user.username,
                course_id,
                course_mode
            )
        pending_user_message = (
            "The following users do not have an account on Test platform. They have not been enrolled in the course. "
            "When these users create an account, they will be enrolled in the course automatically: {}"
        )
        expected_messages = {
            (messages.SUCCESS, "2 new users were linked to {}.".format(self.enterprise_customer.name)),
            (messages.WARNING, pending_user_message.format(unknown_email))
        } | set([
            (messages.SUCCESS, "1 user was enrolled to {}.".format(course_id))
            for course_id in expected_courses
        ])

        self._assert_django_messages(response, expected_messages)


@mark.django_db
@override_settings(ROOT_URLCONF="test_utils.admin_urls")
class TestManageUsersDeletion(BaseTestEnterpriseCustomerManageLearnersView):
    """
    Tests for EnterpriseCustomerManageLearnersView DELETE endpoint.
    """

    def test_delete_not_logged_in(self):
        assert settings.SESSION_COOKIE_NAME not in self.client.cookies  # precondition check - no session cookie

        response = self.client.delete(self.view_url, data={})

        assert response.status_code == 302

    def test_delete_not_linked(self):
        self._login()
        email = FAKER.email()
        query_string = six.moves.urllib.parse.urlencode({"unlink_email": email})

        response = self.client.delete(self.view_url + "?" + query_string)

        assert response.status_code == 404
        expected_message = "Email {email} is not linked to Enterprise Customer {ec_name}".format(
            email=email, ec_name=self.enterprise_customer.name
        )
        assert response.content.decode("utf-8") == expected_message

    def test_delete_linked(self):
        self._login()

        email = FAKER.email()
        user = UserFactory(email=email)
        EnterpriseCustomerUserFactory(enterprise_customer=self.enterprise_customer, user_id=user.id)
        query_string = six.moves.urllib.parse.urlencode({"unlink_email": email})

        assert len(EnterpriseCustomerUser.objects.filter(user_id=user.id)) == 1

        response = self.client.delete(self.view_url + "?" + query_string)

        assert response.status_code == 200
        assert json.loads(response.content.decode("utf-8")) == {}
        assert len(EnterpriseCustomerUser.objects.filter(user_id=user.id)) == 0

    def test_delete_linked_pending(self):
        self._login()

        email = FAKER.email()
        query_string = six.moves.urllib.parse.urlencode({"unlink_email": email})

        PendingEnterpriseCustomerUserFactory(enterprise_customer=self.enterprise_customer, user_email=email)

        assert len(PendingEnterpriseCustomerUser.objects.filter(user_email=email)) == 1

        response = self.client.delete(self.view_url + "?" + query_string)

        assert response.status_code == 200
        assert json.loads(response.content.decode("utf-8")) == {}
        assert len(PendingEnterpriseCustomerUser.objects.filter(user_email=email)) == 0
