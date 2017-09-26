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
from django.core import mail
from django.test import Client, TestCase, override_settings

from enterprise import admin as enterprise_admin
from enterprise.admin import EnterpriseCustomerManageLearnersView, TemplatePreviewView
from enterprise.admin.forms import ManageLearnersForm
from enterprise.admin.utils import ValidationMessages, get_course_runs_from_program
from enterprise.django_compatibility import reverse
from enterprise.models import (
    EnrollmentNotificationEmailTemplate,
    EnterpriseCourseEnrollment,
    EnterpriseCustomerUser,
    PendingEnrollment,
    PendingEnterpriseCustomerUser,
)
from test_utils import fake_enrollment_api  # pylint: disable=ungrouped-imports
from test_utils import fake_catalog_api
from test_utils.factories import (
    FAKER,
    EnterpriseCustomerFactory,
    EnterpriseCustomerUserFactory,
    PendingEnterpriseCustomerUserFactory,
    UserFactory,
)
from test_utils.fake_catalog_api import FAKE_PROGRAM_RESPONSE2
from test_utils.file_helpers import MakeCsvStreamContextManager


@ddt.ddt
@mark.django_db
@override_settings(ROOT_URLCONF="test_utils.admin_urls")
class TestPreviewTemplateView(TestCase):
    """
    Test the Preview Template view
    """
    def setUp(self):
        """
        Set up testing variables
        """
        self.user = UserFactory.create(is_staff=True, is_active=True)
        self.user.set_password("QWERTY")
        self.user.save()
        self.client = Client()
        self.template = EnrollmentNotificationEmailTemplate.objects.create(
            plaintext_template='',
            html_template=(
                '<html><body>You\'ve been enrolled in {{ enrolled_in.name }}!{% if enrolled_in.type == "program" %}'
                ' Program Variant{% endif %}</body></html>'
            ),
            subject_line='Enrollment Notification',
            enterprise_customer=EnterpriseCustomerFactory(),
        )
        super(TestPreviewTemplateView, self).setUp()

    @ddt.unpack
    @ddt.data(
        ('', 'jsmith', 'jsmith'),
        ('John', 'jsmith', 'John'),
    )
    def test_get_user_name(self, first_name, username, expected_name):
        """
        Test that the get_user_name method returns the name we expect.
        """
        request = mock.MagicMock(
            user=mock.MagicMock(
                first_name=first_name,
                username=username
            )
        )
        assert TemplatePreviewView.get_user_name(request) == expected_name

    def test_preview_course(self):
        """
        Test that we render the template for a course correctly.
        """
        assert self.client.login(username=self.user.username, password="QWERTY")
        url = reverse(
            'admin:' + enterprise_admin.utils.UrlNames.PREVIEW_EMAIL_TEMPLATE,
            args=((self.template.pk, 'course'))
        )
        result = self.client.get(url)
        assert result.content.decode('utf-8') == (
            '<html><body>You\'ve been enrolled in OpenEdX Demo Course!</body></html>'
        )

    def test_preview_program(self):
        """
        Test that we render the template for a program correctly.
        """
        assert self.client.login(username=self.user.username, password="QWERTY")
        url = reverse(
            'admin:' + enterprise_admin.utils.UrlNames.PREVIEW_EMAIL_TEMPLATE,
            args=((self.template.pk, 'program'))
        )
        result = self.client.get(url)
        assert result.content.decode('utf-8') == (
            '<html><body>You\'ve been enrolled in OpenEdX Demo Program! Program Variant</body></html>'
        )

    def test_bad_preview_mode(self):
        """
        Test that a non-standard preview mode causes a 404.
        """
        assert self.client.login(username=self.user.username, password="QWERTY")
        url = reverse(
            'admin:' + enterprise_admin.utils.UrlNames.PREVIEW_EMAIL_TEMPLATE,
            args=((self.template.pk, 'faketype'))
        )
        result = self.client.get(url)
        assert result.status_code == 404

    def test_missing_object(self):
        """
        Test that a missing template object causes a 404.
        """
        assert self.client.login(username=self.user.username, password="QWERTY")
        url = reverse(
            'admin:' + enterprise_admin.utils.UrlNames.PREVIEW_EMAIL_TEMPLATE,
            args=((self.template.pk + 1, 'course'))
        )
        result = self.client.get(url)
        assert result.status_code == 404


class BaseTestEnterpriseCustomerManageLearnersView(TestCase):
    """
    Common functionality for EnterpriseCustomerManageLearnersView tests.
    """

    def setUp(self):
        """
        Test set up - installs common dependencies.
        """
        super(BaseTestEnterpriseCustomerManageLearnersView, self).setUp()
        self.user = UserFactory.create(is_staff=True, is_active=True, id=1)
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
        assert PendingEnterpriseCustomerUser.objects.filter(user_email=email).count() == 0
        try:
            user = User.objects.get(email=email)
            assert EnterpriseCustomerUser.objects.filter(user_id=user.id).count() == 0
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
                    id=2,
                ).id,
            ),
            EnterpriseCustomerUserFactory(
                enterprise_customer=self.enterprise_customer,
                user_id=UserFactory(
                    username='frank',
                    email='iloveschool@example.com',
                    id=3,
                ).id,
            ),
            EnterpriseCustomerUserFactory(
                enterprise_customer=self.enterprise_customer,
                user_id=UserFactory(
                    username='angela',
                    email='cats@cats.org',
                    id=4,
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
        assert PendingEnterpriseCustomerUser.objects.filter(user_email=email).count() == 1

    @ddt.unpack
    @ddt.data(
        ("TestGuy", "test@example.com"),
        ("AdamJensen", "adam.jensen@sarif.com"),
    )
    def test_post_new_user_by_username(self, username, email):
        # precondition checks:
        self._login()
        self._assert_no_record(email)  # there're no record with current email

        user = UserFactory(username=username, email=email, id=2)

        response = self.client.post(self.view_url, data={ManageLearnersForm.Fields.EMAIL_OR_USERNAME: username})

        self.assertRedirects(response, self.view_url)
        assert EnterpriseCustomerUser.objects.filter(user_id=user.id).count() == 1

    def test_post_invalid_email(self):
        # precondition checks:
        self._login()
        assert EnterpriseCustomerUser.objects.count() == 0  # there're no link records
        assert PendingEnterpriseCustomerUser.objects.count() == 0  # there're no pending link records

        response = self.client.post(self.view_url, data={ManageLearnersForm.Fields.EMAIL_OR_USERNAME: "invalid_email"})

        assert response.status_code == 200
        self._test_common_context(response.context)
        assert EnterpriseCustomerUser.objects.count() == 0
        assert response.context[self.context_parameters.MANAGE_LEARNERS_FORM].is_bound

    def test_post_invalid_email_form_validation_suppressed(self):
        # precondition checks:
        self._login()
        assert EnterpriseCustomerUser.objects.count() == 0  # there're no link records
        assert PendingEnterpriseCustomerUser.objects.count() == 0  # there're no pending link records

        invalid_email = "invalid_email"

        with mock.patch("enterprise.admin.views.ManageLearnersForm.clean_email_or_username") as patched_clean:
            patched_clean.return_value = invalid_email
            response = self.client.post(
                self.view_url, data={ManageLearnersForm.Fields.EMAIL_OR_USERNAME: invalid_email}
            )

        assert response.status_code == 200
        self._test_common_context(response.context)
        assert EnterpriseCustomerUser.objects.count() == 0
        manage_learners_form = response.context[self.context_parameters.MANAGE_LEARNERS_FORM]
        assert manage_learners_form.is_bound
        assert manage_learners_form.errors == {
            ManageLearnersForm.Fields.EMAIL_OR_USERNAME: [
                ValidationMessages.INVALID_EMAIL_OR_USERNAME.format(argument=invalid_email)
            ]
        }

    def _test_post_existing_record_response(self, response):
        """
        Test view POST response for common parts.
        """
        assert response.status_code == 302

    def test_post_existing_record(self):
        # precondition checks:
        self._login()

        email = FAKER.email()  # pylint: disable=no-member

        user = UserFactory(email=email, id=2)
        EnterpriseCustomerUserFactory(enterprise_customer=self.enterprise_customer, user_id=user.id)
        assert EnterpriseCustomerUser.objects.filter(user_id=user.id).count() == 1
        response = self.client.post(self.view_url, data={ManageLearnersForm.Fields.EMAIL_OR_USERNAME: email})
        self._test_post_existing_record_response(response)
        assert EnterpriseCustomerUser.objects.filter(user_id=user.id).count() == 1

    def test_post_one_existing_one_new_record(self):
        """
        Test that we can submit a comma-separated string value directly in the form.

        Once we make a submission with one existing user and one new user, verify
        that a new EnterpriseCustomerUser doesn't get created for the existing record,
        but that a PendingEnterpriseCustomerUser is created for the email address
        that wasn't previously linked.
        """
        # precondition checks:
        self._login()

        email = FAKER.email()  # pylint: disable=no-member

        user = UserFactory(email=email, id=2)
        EnterpriseCustomerUserFactory(user_id=user.id)
        assert EnterpriseCustomerUser.objects.count() == 1
        assert PendingEnterpriseCustomerUser.objects.count() == 0
        self.client.post(
            self.view_url,
            data={
                ManageLearnersForm.Fields.EMAIL_OR_USERNAME: email + ', john@smith.com'
            }
        )
        assert EnterpriseCustomerUser.objects.count() == 1
        assert PendingEnterpriseCustomerUser.objects.count() == 1

    def test_post_existing_pending_record(self):
        # precondition checks:
        self._login()

        email = FAKER.email()  # pylint: disable=no-member
        PendingEnterpriseCustomerUserFactory(enterprise_customer=self.enterprise_customer, user_email=email)
        assert PendingEnterpriseCustomerUser.objects.filter(user_email=email).count() == 1

        response = self.client.post(self.view_url, data={ManageLearnersForm.Fields.EMAIL_OR_USERNAME: email})
        self._test_post_existing_record_response(response)
        assert PendingEnterpriseCustomerUser.objects.filter(user_email=email).count() == 1

    def _enroll_user_request(self, user, mode, course_id="", program_id="", notify=True):
        """
        Perform post request to log in and submit the form to enroll a user.
        """
        notify = (
            ManageLearnersForm.NotificationTypes.BY_EMAIL if notify
            else ManageLearnersForm.NotificationTypes.NO_NOTIFICATION
        )
        self._login()

        if isinstance(user, six.string_types):
            email_or_username = user
        else:
            # Allow us to send forms involving pending users
            email_or_username = getattr(user, 'username', getattr(user, 'user_email', None))

        response = self.client.post(self.view_url, data={
            ManageLearnersForm.Fields.EMAIL_OR_USERNAME: email_or_username,
            ManageLearnersForm.Fields.COURSE_MODE: mode,
            ManageLearnersForm.Fields.COURSE: course_id,
            ManageLearnersForm.Fields.PROGRAM: program_id,
            ManageLearnersForm.Fields.NOTIFY: notify
        })
        return response

    @mock.patch("enterprise.admin.views.CourseCatalogApiClient")
    @mock.patch("enterprise.admin.views.EnrollmentApiClient")
    @mock.patch("enterprise.admin.forms.EnrollmentApiClient")
    def test_post_enroll_user(self, forms_client, views_client, course_catalog_client):
        catalog_instance = course_catalog_client.return_value
        catalog_instance.get_course_run.return_value = {
            "title": "Cool Science",
            "start": "2017-01-01T12:00:00Z",
            "marketing_url": "http://localhost:8000/courses/course-v1:HarvardX+CoolScience+2016"
        }
        views_instance = views_client.return_value
        views_instance.enroll_user_in_course.side_effect = fake_enrollment_api.enroll_user_in_course
        forms_instance = forms_client.return_value
        forms_instance.get_course_details.side_effect = fake_enrollment_api.get_course_details
        user = UserFactory(id=2)
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
            (messages.SUCCESS, "1 learner was enrolled in {}.".format(course_id)),
        ]))
        all_enterprise_enrollments = EnterpriseCourseEnrollment.objects.all()
        num_enterprise_enrollments = len(all_enterprise_enrollments)
        assert num_enterprise_enrollments == 1
        enrollment = all_enterprise_enrollments[0]
        assert enrollment.enterprise_customer_user.user == user
        assert enrollment.course_id == course_id
        num_messages = len(mail.outbox)
        assert num_messages == 1

    def _post_multi_enroll(self, forms_client, views_client, course_catalog_client, create_user):
        """
        Enroll an enterprise learner or pending learner in multiple courses.
        """
        courses = {
            "course-v1:HarvardX+CoolScience+2016": {
                "title": "Cool Science",
                "start": "2017-01-01T12:00:00Z",
                "marketing_url": "http://localhost:8000/courses/course-v1:HarvardX+CoolScience+2016",
                "mode": "verified"
            },
            "course-v1:edX+DemoX+Demo_Course": {
                "title": "edX Demo Course",
                "start": "2013-02-05T05:00:00Z",
                "marketing_url": "http://localhost:8000/courses/course-v1:edX+DemoX+Demo_Course",
                "mode": "audit"
            }
        }
        catalog_instance = course_catalog_client.return_value
        views_instance = views_client.return_value
        views_instance.enroll_user_in_course.side_effect = fake_enrollment_api.enroll_user_in_course
        forms_instance = forms_client.return_value
        forms_instance.get_course_details.side_effect = fake_enrollment_api.get_course_details
        enrollment_count = 0
        user = None
        user_email = FAKER.email()  # pylint: disable=no-member
        if create_user:
            user = UserFactory(email=user_email)

        for course_id in courses:
            catalog_instance.get_course_run.return_value = courses[course_id]
            mode = courses[course_id]['mode']
            enrollment_count += 1

            if user:
                response = self._enroll_user_request(user, mode, course_id=course_id)
                if enrollment_count == 1:
                    views_instance.enroll_user_in_course.assert_called_once()
                views_instance.enroll_user_in_course.assert_called_with(
                    user.username,
                    course_id,
                    mode,
                )
                self._assert_django_messages(response, set([
                    (messages.SUCCESS, "1 learner was enrolled in {}.".format(course_id)),
                ]))
            else:
                response = self._enroll_user_request(user_email, mode, course_id=course_id, notify=True)

            if user:
                all_enrollments = EnterpriseCourseEnrollment.objects.all()
            else:
                all_enrollments = PendingEnrollment.objects.all()

            num_enrollments = len(all_enrollments)
            assert num_enrollments == enrollment_count
            enrollment = all_enrollments[enrollment_count - 1]
            if user:
                assert enrollment.enterprise_customer_user.user == user
            assert enrollment.course_id == course_id
            num_messages = len(mail.outbox)
            assert num_messages == enrollment_count

    @mock.patch("enterprise.admin.views.CourseCatalogApiClient")
    @mock.patch("enterprise.admin.views.EnrollmentApiClient")
    @mock.patch("enterprise.admin.forms.EnrollmentApiClient")
    def test_post_multi_enroll_user(self, forms_client, views_client, course_catalog_client):
        """
        Test that an existing learner can be enrolled in multiple courses.
        """
        self._post_multi_enroll(forms_client, views_client, course_catalog_client, True)

    @mock.patch("enterprise.admin.views.CourseCatalogApiClient")
    @mock.patch("enterprise.admin.views.EnrollmentApiClient")
    @mock.patch("enterprise.admin.forms.EnrollmentApiClient")
    def test_post_multi_enroll_pending_user(self, forms_client, views_client, course_catalog_client):
        """
        Test that a pending learner can be enrolled in multiple courses.
        """
        self._post_multi_enroll(forms_client, views_client, course_catalog_client, False)

    @mock.patch("enterprise.admin.views.CourseCatalogApiClient")
    @mock.patch("enterprise.admin.views.EnrollmentApiClient")
    @mock.patch("enterprise.admin.forms.EnrollmentApiClient")
    def test_post_enroll_no_course_detail(self, forms_client, views_client, course_catalog_client):
        catalog_instance = course_catalog_client.return_value
        catalog_instance.get_course_run.return_value = {}
        views_instance = views_client.return_value
        views_instance.enroll_user_in_course.side_effect = fake_enrollment_api.enroll_user_in_course
        forms_instance = forms_client.return_value
        forms_instance.get_course_details.side_effect = fake_enrollment_api.get_course_details

        user = UserFactory(id=2)
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
            (messages.SUCCESS, "1 learner was enrolled in {}.".format(course_id)),
        ]))
        all_enterprise_enrollments = EnterpriseCourseEnrollment.objects.all()
        num_enterprise_enrollments = len(all_enterprise_enrollments)
        assert num_enterprise_enrollments == 1
        enrollment = all_enterprise_enrollments[0]
        assert enrollment.enterprise_customer_user.user == user
        assert enrollment.course_id == course_id
        num_messages = len(mail.outbox)
        assert num_messages == 0

    @mock.patch("enterprise.admin.views.CourseCatalogApiClient")
    @mock.patch("enterprise.admin.views.EnrollmentApiClient")
    @mock.patch("enterprise.admin.forms.EnrollmentApiClient")
    def test_post_enroll_with_missing_course_start_date(self, forms_client, views_client, course_catalog_client):
        """
        Test that learner is added successfully if course does not have a start date.

        If admin tries to add a learner to a course that does not have a start date then
        learner should be enrolled successfully without any errors and learner should receive an email
        about the enrollment.
        """
        catalog_instance = course_catalog_client.return_value
        catalog_instance.get_course_run.return_value = {
            "title": "Cool Science",
            "start": None,
            "marketing_url": "http://localhost:8000/courses/course-v1:HarvardX+CoolScience+2016"
        }
        views_instance = views_client.return_value
        views_instance.enroll_user_in_course.side_effect = fake_enrollment_api.enroll_user_in_course
        forms_instance = forms_client.return_value
        forms_instance.get_course_details.side_effect = fake_enrollment_api.get_course_details
        user = UserFactory(id=2)
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
            (messages.SUCCESS, "1 learner was enrolled in {}.".format(course_id)),
        ]))
        all_enterprise_enrollments = EnterpriseCourseEnrollment.objects.all()
        num_enterprise_enrollments = len(all_enterprise_enrollments)
        assert num_enterprise_enrollments == 1
        enrollment = all_enterprise_enrollments[0]
        assert enrollment.enterprise_customer_user.user == user
        assert enrollment.course_id == course_id
        num_messages = len(mail.outbox)
        assert num_messages == 1

    @mock.patch("enterprise.utils.reverse")
    @mock.patch("enterprise.admin.views.CourseCatalogApiClient")
    @mock.patch("enterprise.admin.views.EnrollmentApiClient")
    @mock.patch("enterprise.admin.forms.EnrollmentApiClient")
    def test_post_enrollment_error(self, forms_client, views_client, course_catalog_client, reverse_mock):
        reverse_mock.return_value = '/courses/course-v1:HarvardX+CoolScience+2016'
        catalog_instance = course_catalog_client.return_value
        catalog_instance.get_course_run.return_value = {
            "name": "Cool Science",
            "start": "2017-01-01T12:00:00Z",
        }
        views_instance = views_client.return_value
        views_instance.enroll_user_in_course.side_effect = HttpClientError(
            "Client Error", content=json.dumps({"message": "test"}).encode()
        )
        forms_instance = forms_client.return_value
        forms_instance.get_course_details.side_effect = fake_enrollment_api.get_course_details
        user = UserFactory(id=2)
        course_id = "course-v1:HarvardX+CoolScience+2016"
        mode = "verified"
        response = self._enroll_user_request(user, mode, course_id=course_id)
        self._assert_django_messages(response, set([
            (messages.ERROR, "The following learners could not be enrolled in {}: {}".format(course_id, user.email)),
        ]))

    @mock.patch('enterprise.admin.views.logging.error')
    @mock.patch("enterprise.utils.reverse")
    @mock.patch("enterprise.admin.views.CourseCatalogApiClient")
    @mock.patch("enterprise.admin.views.EnrollmentApiClient")
    @mock.patch("enterprise.admin.forms.EnrollmentApiClient")
    def test_post_enrollment_error_bad_error_string(
            self,
            forms_client,
            views_client,
            course_catalog_client,
            reverse_mock,
            logging_mock
    ):
        reverse_mock.return_value = '/courses/course-v1:HarvardX+CoolScience+2016'
        catalog_instance = course_catalog_client.return_value
        catalog_instance.get_course_run.return_value = {
            "name": "Cool Science",
            "start": "2017-01-01T12:00:00Z",
        }
        views_instance = views_client.return_value
        views_instance.enroll_user_in_course.side_effect = HttpClientError(
            "Client Error", content='This is not JSON'.encode()
        )
        forms_instance = forms_client.return_value
        forms_instance.get_course_details.side_effect = fake_enrollment_api.get_course_details
        user = UserFactory(id=2)
        course_id = "course-v1:HarvardX+CoolScience+2016"
        mode = "verified"
        response = self._enroll_user_request(user, mode, course_id=course_id)
        logging_mock.assert_called_with(
            'Error while enrolling user %(user)s: %(message)s',
            {'user': user.username, 'message': 'No error message provided'}
        )
        self._assert_django_messages(response, set([
            (messages.ERROR, "The following learners could not be enrolled in {}: {}".format(course_id, user.email)),
        ]))

    @mock.patch("enterprise.admin.views.CourseCatalogApiClient")
    @mock.patch("enterprise.admin.views.EnrollmentApiClient")
    @mock.patch("enterprise.admin.forms.CourseCatalogApiClient")
    def test_post_enroll_user_into_program(
            self,
            catalog_client,
            views_client,
            views_catalog_client
    ):
        views_catalog_instance = views_catalog_client.return_value
        views_catalog_instance.get_program_by_uuid.side_effect = fake_catalog_api.get_program_by_uuid
        views_instance = views_client.return_value
        views_instance.enroll_user_in_course.side_effect = fake_enrollment_api.enroll_user_in_course
        catalog_api_instance = catalog_client.return_value
        catalog_api_instance.get_program_by_uuid.side_effect = fake_catalog_api.get_program_by_uuid
        catalog_api_instance.get_common_course_modes.side_effect = {"professional"}
        user = UserFactory(id=2)
        program = FAKE_PROGRAM_RESPONSE2
        expected_courses = get_course_runs_from_program(program)
        mode = "professional"
        response = self._enroll_user_request(user, mode, program_id=program["uuid"], notify=True)
        assert views_instance.enroll_user_in_course.call_count == len(expected_courses)
        self._assert_django_messages(response, set(
            [
                (messages.SUCCESS, "1 learner was enrolled in {}.".format('Program2'))
            ]
        ))
        num_messages = len(mail.outbox)
        assert num_messages == 1

    @mock.patch("enterprise.admin.views.CourseCatalogApiClient")
    @mock.patch("enterprise.admin.forms.CourseCatalogApiClient")
    def test_post_enroll_pending_user_into_program(self, catalog_client, views_catalog_client):
        views_catalog_instance = views_catalog_client.return_value
        views_catalog_instance.get_program_by_uuid.side_effect = fake_catalog_api.get_program_by_uuid
        catalog_api_instance = catalog_client.return_value
        catalog_api_instance.get_program_by_uuid.side_effect = fake_catalog_api.get_program_by_uuid
        catalog_api_instance.get_common_course_modes.side_effect = {"professional"}
        user_email = FAKER.email()  # pylint: disable=no-member
        program = FAKE_PROGRAM_RESPONSE2
        expected_courses = get_course_runs_from_program(program)
        mode = "professional"
        self._enroll_user_request(user_email, mode, program_id=program["uuid"], notify=True)
        num_messages = len(mail.outbox)
        assert num_messages == 1
        assert PendingEnrollment.objects.count() == len(expected_courses)
        assert PendingEnterpriseCustomerUser.objects.count() == 1

    @mock.patch("enterprise.admin.views.CourseCatalogApiClient")
    @mock.patch("enterprise.admin.views.EnrollmentApiClient")
    @mock.patch("enterprise.admin.forms.CourseCatalogApiClient")
    def test_post_enroll_user_into_program_error(
            self,
            catalog_client,
            views_client,
            views_catalog_client
    ):
        views_catalog_instance = views_catalog_client.return_value
        views_catalog_instance.get_program_by_uuid.side_effect = fake_catalog_api.get_program_by_uuid
        views_instance = views_client.return_value
        views_instance.enroll_user_in_course.side_effect = HttpClientError(
            "Client Error", content=json.dumps({"message": "test"}).encode()
        )
        catalog_api_instance = catalog_client.return_value
        catalog_api_instance.get_program_by_uuid.side_effect = fake_catalog_api.get_program_by_uuid
        catalog_api_instance.get_common_course_modes.side_effect = {"professional"}
        user = UserFactory(id=2)
        program = FAKE_PROGRAM_RESPONSE2
        expected_courses = get_course_runs_from_program(program)
        mode = "professional"
        response = self._enroll_user_request(user, mode, program_id=program["uuid"])
        assert views_instance.enroll_user_in_course.call_count == len(expected_courses)
        self._assert_django_messages(response, set([
            (messages.ERROR, "The following learners could not be enrolled in Program2: {}".format(user.email)),
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

    def _perform_request(self, columns, data, course=None, program=None, course_mode=None, notify=True):
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
            post_data[ManageLearnersForm.Fields.NOTIFY] = 'by_email' if notify else 'do_not_notify'
            post_data['enterprise_customer'] = self.enterprise_customer
            response = self.client.post(self.view_url, data=post_data)
        return response

    def test_post_not_logged_in(self):
        assert settings.SESSION_COOKIE_NAME not in self.client.cookies  # precondition check - no session cookie

        response = self.client.post(self.view_url, data={})

        assert response.status_code == 302

    def test_post_invalid_headers(self):
        self._login()

        assert EnterpriseCustomerUser.objects.count() == 0, "Precondition check: no linked users"
        assert PendingEnterpriseCustomerUser.objects.count() == 0, "Precondition check: no pending linked users"

        invalid_columns = ["invalid", "header"]
        response = self._perform_request(invalid_columns, [("QWE",), ("ASD", )])

        assert EnterpriseCustomerUser.objects.count() == 0, "No users should be linked"
        assert PendingEnterpriseCustomerUser.objects.count() == 0, "No pending linked user records should be created"

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
        user = UserFactory(id=2)
        invalid_email = "invalid"

        assert EnterpriseCustomerUser.objects.count() == 0, "Precondition check: no linked users"
        assert PendingEnterpriseCustomerUser.objects.count() == 0, "Precondition check: no pending linked users"

        columns = [ManageLearnersForm.CsvColumns.EMAIL]
        data = [
            (FAKER.email(),),  # valid not previously seen email;  pylint: disable=no-member
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
        """
        Test that duplicates and existing links are handled correctly.

        1. Users already linked to an EnterpriseCustomer should cause a warning message, and an
            additional link won't be created, but otherwise will behave normally.
        2. Users that appear in a CSV twice will be ignored and a message will be created.
        3. Users that are attached to a different EnterpriseCustomer will be ignored, and
            a message will be created.
        """
        self._login()
        user = UserFactory(id=2)
        linked_user = UserFactory(id=3)
        user_linked_to_other_ec = UserFactory(id=4)
        EnterpriseCustomerUserFactory(user_id=user_linked_to_other_ec.id)
        EnterpriseCustomerUserFactory(user_id=linked_user.id, enterprise_customer=self.enterprise_customer)
        new_email = FAKER.email()  # pylint: disable=no-member

        assert EnterpriseCustomerUser.objects.count() == 2, "Precondition check: Two linked users"
        assert EnterpriseCustomerUser.objects.filter(user_id=linked_user.id).exists()
        assert EnterpriseCustomerUser.objects.filter(user_id=user_linked_to_other_ec.id).exists()
        assert not PendingEnterpriseCustomerUser.objects.exists(), "Precondition check: no pending user links"

        columns = [ManageLearnersForm.CsvColumns.EMAIL]
        data = [
            (linked_user.email,),  # a user that is already linked to this EC
            (new_email,),  # valid not previously seen email
            (user.email,),  # valid user email
            (user.email,),  # valid user email repeated
            (user_linked_to_other_ec.email,),  # valid user email linked to a different EC
        ]
        response = self._perform_request(columns, data)

        assert EnterpriseCustomerUser.objects.count() == 3, \
            "Two linked users remain, and one new link is created"
        assert EnterpriseCustomerUser.objects.filter(user_id=linked_user.id).exists()
        assert EnterpriseCustomerUser.objects.filter(user_id=user.id).exists()
        assert PendingEnterpriseCustomerUser.objects.count() == 1, "One pending linked users should be created"
        assert PendingEnterpriseCustomerUser.objects.filter(user_email=new_email).exists()
        self._assert_django_messages(response, set([
            (messages.SUCCESS, "2 new learners were added to {}.".format(self.enterprise_customer.name)),
            (
                messages.WARNING,
                "The following learners were already associated with this "
                "Enterprise Customer: {}".format(linked_user.email)
            ),
            (messages.WARNING, "The following duplicate email addresses were not added: {}".format(user.email)),
            (
                messages.WARNING,
                "The following learners are already associated with another Enterprise Customer. "
                "These learners were not added to {}: {}".format(
                    self.enterprise_customer.name,
                    user_linked_to_other_ec.email
                )
            )
        ]))

    def test_post_successful_test(self):
        """
        Test bulk upload in complex.
        """
        self._login()

        assert EnterpriseCustomerUser.objects.count() == 0, "Precondition check: no linked users"
        assert PendingEnterpriseCustomerUser.objects.count() == 0, "Precondition check: no pending linked users"

        user_by_email = UserFactory(id=2)
        previously_not_seen_email = FAKER.email()  # pylint: disable=no-member

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
            (messages.SUCCESS, "2 new learners were added to {}.".format(self.enterprise_customer.name)),
        ]))

    @mock.patch("enterprise.admin.views.CourseCatalogApiClient")
    @mock.patch("enterprise.admin.views.EnrollmentApiClient")
    @mock.patch("enterprise.admin.forms.EnrollmentApiClient")
    def test_post_link_and_enroll(self, forms_client, views_client, course_catalog_client):
        """
        Test bulk upload with linking and enrolling
        """
        course_catalog_instance = course_catalog_client.return_value
        course_catalog_instance.get_course_run.return_value = {
            "name": "Enterprise Training",
            "start": "2017-01-01T12:00:00Z",
            "marketing_url": "http://localhost/course-v1:EnterpriseX+Training+2017"
        }
        views_instance = views_client.return_value
        views_instance.enroll_user_in_course.side_effect = fake_enrollment_api.enroll_user_in_course
        forms_instance = forms_client.return_value
        forms_instance.get_course_details.side_effect = fake_enrollment_api.get_course_details
        self._login()
        user = UserFactory.create()
        unknown_email = FAKER.email()  # pylint: disable=no-member
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
            "The following learners do not have an account on Test platform. "
            "They have not been enrolled in {}. When these learners create an "
            "account, they will be enrolled automatically: {}"
        )
        self._assert_django_messages(response, set([
            (messages.SUCCESS, "2 new learners were added to {}.".format(self.enterprise_customer.name)),
            (messages.SUCCESS, "1 learner was enrolled in {}.".format(course_id)),
            (messages.WARNING, pending_user_message.format(course_id, unknown_email)),
        ]))
        assert PendingEnterpriseCustomerUser.objects.all()[0].pendingenrollment_set.all()[0].course_id == course_id
        num_messages = len(mail.outbox)
        assert num_messages == 2

    @mock.patch("enterprise.admin.views.CourseCatalogApiClient")
    @mock.patch("enterprise.admin.views.EnrollmentApiClient")
    @mock.patch("enterprise.admin.forms.EnrollmentApiClient")
    def test_post_link_and_enroll_no_course_details(self, forms_client, views_client, course_catalog_client):
        """
        Test bulk upload with linking and enrolling
        """
        course_catalog_instance = course_catalog_client.return_value
        course_catalog_instance.get_course_run.return_value = {}
        views_instance = views_client.return_value
        views_instance.enroll_user_in_course.side_effect = fake_enrollment_api.enroll_user_in_course
        forms_instance = forms_client.return_value
        forms_instance.get_course_details.side_effect = fake_enrollment_api.get_course_details

        self._login()
        user = UserFactory.create()
        unknown_email = FAKER.email()  # pylint: disable=no-member
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
            "The following learners do not have an account on Test platform. "
            "They have not been enrolled in {}. When these learners create an "
            "account, they will be enrolled automatically: {}"
        )
        self._assert_django_messages(response, set([
            (messages.SUCCESS, "2 new learners were added to {}.".format(self.enterprise_customer.name)),
            (messages.SUCCESS, "1 learner was enrolled in {}.".format(course_id)),
            (messages.WARNING, pending_user_message.format(course_id, unknown_email)),
        ]))
        assert PendingEnterpriseCustomerUser.objects.all()[0].pendingenrollment_set.all()[0].course_id == course_id
        num_messages = len(mail.outbox)
        assert num_messages == 0

    @mock.patch("enterprise.admin.views.CourseCatalogApiClient")
    @mock.patch("enterprise.admin.views.EnrollmentApiClient")
    @mock.patch("enterprise.admin.forms.EnrollmentApiClient")
    @mock.patch("enterprise.admin.forms.CourseCatalogApiClient")
    def test_post_link_and_enroll_no_notification(
            self,
            catalog_client,
            forms_client,
            views_client,
            views_catalog_client,
    ):
        """
        Test bulk upload with linking and enrolling
        """
        views_catalog_instance = views_catalog_client.return_value
        views_catalog_instance.get_program_by_uuid.return_value = fake_catalog_api.get_program_by_uuid
        catalog_api_instance = catalog_client.return_value
        catalog_api_instance.get_program_by_uuid.side_effect = fake_catalog_api.get_program_by_uuid
        catalog_api_instance.get_common_course_modes.side_effect = {"professional"}
        views_instance = views_client.return_value
        views_instance.enroll_user_in_course.side_effect = fake_enrollment_api.enroll_user_in_course
        forms_instance = forms_client.return_value
        forms_instance.get_course_details.side_effect = fake_enrollment_api.get_course_details
        self._login()
        user = UserFactory.create()
        unknown_email = FAKER.email()  # pylint: disable=no-member
        columns = [ManageLearnersForm.CsvColumns.EMAIL]
        data = [(user.email,), (unknown_email,)]
        course_id = "course-v1:EnterpriseX+Training+2017"
        course_mode = "professional"

        response = self._perform_request(columns, data, course=course_id, course_mode=course_mode, notify=False)

        views_instance.enroll_user_in_course.assert_called_once()
        views_instance.enroll_user_in_course.assert_called_with(
            user.username,
            course_id,
            course_mode
        )
        pending_user_message = (
            "The following learners do not have an account on Test platform. They have not been enrolled in {}. "
            "When these learners create an account, they will be enrolled automatically: {}"
        )
        self._assert_django_messages(response, set([
            (messages.SUCCESS, "2 new learners were added to {}.".format(self.enterprise_customer.name)),
            (messages.SUCCESS, "1 learner was enrolled in {}.".format(course_id)),
            (messages.WARNING, pending_user_message.format(course_id, unknown_email)),
        ]))
        assert PendingEnterpriseCustomerUser.objects.all()[0].pendingenrollment_set.all()[0].course_id == course_id
        num_messages = len(mail.outbox)
        assert num_messages == 0

    @mock.patch("enterprise.admin.views.CourseCatalogApiClient")
    @mock.patch("enterprise.admin.views.EnrollmentApiClient")
    @mock.patch("enterprise.admin.forms.CourseCatalogApiClient")
    def test_post_link_and_enroll_into_program(self, catalog_client, views_client, views_catalog_client):
        """
        Test bulk upload with linking and enrolling
        """
        views_catalog_instance = views_catalog_client.return_value
        views_catalog_instance.get_program_by_uuid.side_effect = fake_catalog_api.get_program_by_uuid
        views_instance = views_client.return_value
        views_instance.enroll_user_in_course.side_effect = fake_enrollment_api.enroll_user_in_course
        catalog_api_instance = catalog_client.return_value
        catalog_api_instance.get_program_by_uuid.side_effect = fake_catalog_api.get_program_by_uuid
        catalog_api_instance.get_common_course_modes.side_effect = {"professional"}
        self._login()
        user = UserFactory.create()
        unknown_email = FAKER.email()  # pylint: disable=no-member
        columns = [ManageLearnersForm.CsvColumns.EMAIL]
        data = [(user.email,), (unknown_email,)]
        program = FAKE_PROGRAM_RESPONSE2
        course_mode = "professional"
        expected_courses = get_course_runs_from_program(program)
        response = self._perform_request(columns, data, program=program["uuid"], course_mode=course_mode, notify=False)

        assert views_instance.enroll_user_in_course.call_count == len(expected_courses)
        for course_id in expected_courses:
            views_instance.enroll_user_in_course.assert_any_call(
                user.username,
                course_id,
                course_mode
            )
        pending_user_message = (
            "The following learners do not have an account on Test platform. They have not been enrolled in Program2. "
            "When these learners create an account, they will be enrolled automatically: {}"
        )
        expected_messages = {
            (messages.SUCCESS, "2 new learners were added to {}.".format(self.enterprise_customer.name)),
            (messages.WARNING, pending_user_message.format(unknown_email))
        } | set([
            (messages.SUCCESS, "1 learner was enrolled in Program2.")
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
        email = FAKER.email()  # pylint: disable=no-member
        query_string = six.moves.urllib.parse.urlencode({"unlink_email": email})

        response = self.client.delete(self.view_url + "?" + query_string)

        assert response.status_code == 404
        expected_message = "Email {email} is not associated with Enterprise Customer {ec_name}".format(
            email=email, ec_name=self.enterprise_customer.name
        )
        assert response.content.decode("utf-8") == expected_message

    def test_delete_linked(self):
        self._login()

        email = FAKER.email()  # pylint: disable=no-member
        user = UserFactory(email=email, id=2)
        EnterpriseCustomerUserFactory(enterprise_customer=self.enterprise_customer, user_id=user.id)
        query_string = six.moves.urllib.parse.urlencode({"unlink_email": email})

        assert EnterpriseCustomerUser.objects.filter(user_id=user.id).count() == 1

        response = self.client.delete(self.view_url + "?" + query_string)

        assert response.status_code == 200
        assert json.loads(response.content.decode("utf-8")) == {}
        assert EnterpriseCustomerUser.objects.filter(user_id=user.id).count() == 0

    def test_delete_linked_pending(self):
        self._login()

        email = FAKER.email()  # pylint: disable=no-member
        query_string = six.moves.urllib.parse.urlencode({"unlink_email": email})

        PendingEnterpriseCustomerUserFactory(enterprise_customer=self.enterprise_customer, user_email=email)

        assert PendingEnterpriseCustomerUser.objects.filter(user_email=email).count() == 1

        response = self.client.delete(self.view_url + "?" + query_string)

        assert response.status_code == 200
        assert json.loads(response.content.decode("utf-8")) == {}
        assert PendingEnterpriseCustomerUser.objects.filter(user_email=email).count() == 0
