"""
Tests for the `edx-enterprise` admin forms module.
"""

import json
from math import ceil
from unittest import mock
from unittest.mock import ANY
from urllib.parse import urlencode

import ddt
from edx_rest_api_client.exceptions import HttpClientError
from pytest import mark

from django.conf import settings
from django.contrib import auth
from django.contrib.messages import constants as messages
from django.core import mail
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from consent.models import DataSharingConsent
from enterprise import admin as enterprise_admin
from enterprise.admin import (
    EnterpriseCustomerManageLearnerDataSharingConsentView,
    EnterpriseCustomerManageLearnersView,
    EnterpriseCustomerTransmitCoursesView,
    TemplatePreviewView,
)
from enterprise.admin.forms import (
    ManageLearnersDataSharingConsentForm,
    ManageLearnersForm,
    TransmitEnterpriseCoursesForm,
)
from enterprise.admin.utils import ValidationMessages
from enterprise.constants import PAGE_SIZE
from enterprise.models import (
    EnrollmentNotificationEmailTemplate,
    EnterpriseCatalogQuery,
    EnterpriseCourseEnrollment,
    EnterpriseCustomer,
    EnterpriseCustomerUser,
    EnterpriseEnrollmentSource,
    PendingEnrollment,
    PendingEnterpriseCustomerUser,
)
from test_utils import fake_catalog_api, fake_enrollment_api
from test_utils.factories import (
    FAKER,
    DataSharingConsentFactory,
    EnterpriseCustomerFactory,
    EnterpriseCustomerUserFactory,
    PendingEnterpriseCustomerUserFactory,
    UserFactory,
)
from test_utils.file_helpers import MakeCsvStreamContextManager

User = auth.get_user_model()


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
        super().setUp()

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


@mark.django_db
@override_settings(ROOT_URLCONF="test_utils.admin_urls")
class TestCatalogQueryPreviewView(TestCase):
    """
    Test the Catalog Query Preview view
    """
    def setUp(self):
        """
        Set up testing variables
        """
        self.user = UserFactory.create(is_staff=True, is_active=True)
        self.user.set_password("QWERTY")
        self.user.save()
        self.non_staff_user = UserFactory.create(is_staff=False, is_active=True)
        self.non_staff_user.set_password("QWERTY")
        self.non_staff_user.save()
        self.client = Client()
        self.catalog_query = EnterpriseCatalogQuery.objects.create(
            title='Test Catalog Query',
            content_filter={'partner': 'MuiX'}
        )
        super().setUp()

    @mock.patch('enterprise.api_client.discovery.CourseCatalogApiServiceClient')
    def test_preview_query(self, mock_catalog_api_client):
        """
        Test that we render the query preview correctly.
        """
        mock_catalog_api_client.return_value = mock.Mock(
            get_catalog_results=mock.Mock(
                return_value=fake_catalog_api.FAKE_SEARCH_ALL_RESULTS
            ),
        )
        assert self.client.login(username=self.user.username, password="QWERTY")
        url = reverse(
            'admin:' + enterprise_admin.utils.UrlNames.PREVIEW_QUERY_RESULT,
            args=(self.catalog_query.pk,)
        )
        result = self.client.get(url)
        content_count = json.loads(result.content)['count']
        self.assertEqual(content_count, 3)

    def test_missing_object(self):
        """
        Test that a missing object causes a 404.
        """
        assert self.client.login(username=self.user.username, password="QWERTY")
        url = reverse(
            'admin:' + enterprise_admin.utils.UrlNames.PREVIEW_QUERY_RESULT,
            args=(self.catalog_query.pk + 1,)
        )
        result = self.client.get(url)
        assert result.status_code == 404

    @mock.patch('enterprise.api_client.discovery.CourseCatalogApiServiceClient')
    def test_no_data_for_non_staff(self, mock_catalog_api_client):
        """
        Test that a non staff user is not returned any data.
        """
        mock_catalog_api_client.return_value = mock.Mock(
            get_catalog_results=mock.Mock(
                return_value=fake_catalog_api.FAKE_SEARCH_ALL_RESULTS
            ),
        )
        assert self.client.login(username=self.non_staff_user.username, password="QWERTY")
        url = reverse(
            'admin:' + enterprise_admin.utils.UrlNames.PREVIEW_QUERY_RESULT,
            args=(self.catalog_query.pk,)
        )
        result = self.client.get(url)
        self.assertEqual(result.content, b'')


class BaseEnterpriseCustomerView(TestCase):
    """
    Common functionality for EnterpriseCustomerViews.
    """
    def setUp(self):
        """
        Test set up
        """
        super().setUp()
        self.user = UserFactory.create(is_staff=True, is_active=True)
        self.user.set_password('QWERTY')
        self.user.save()
        self.enterprise_channel_worker = UserFactory.create(is_staff=True, is_active=True)
        self.enterprise_customer = EnterpriseCustomerFactory()
        self.default_context = {
            'has_permission': True,
            'opts': self.enterprise_customer._meta,
            'user': self.user
        }
        self.client = Client()

    def _test_common_context(self, actual_context, context_overrides=None):
        """
        Test common context parts.
        """
        expected_context = {}
        expected_context.update(self.default_context)
        expected_context.update(context_overrides or {})

        for context_key, expected_value in expected_context.items():
            assert actual_context[context_key] == expected_value

    def _login(self):
        """
        Log user in.
        """
        assert self.client.login(username=self.user.username, password='QWERTY')


class BaseTestEnterpriseCustomerManageLearnersDSCView(BaseEnterpriseCustomerView):
    """
    Common functionality for EnterpriseCustomerManageLearnersDataSharingConsentView tests.
    """

    def setUp(self):
        """
        Test set up
        """
        super().setUp()
        self.manage_learners_dsc_form = ManageLearnersDataSharingConsentForm()
        self.view_url = reverse(
            'admin:' + enterprise_admin.utils.UrlNames.MANAGE_LEARNERS_DSC,
            args=(self.enterprise_customer.uuid,)
        )
        self.context_parameters = EnterpriseCustomerManageLearnerDataSharingConsentView.ContextParameters


@mark.django_db
@override_settings(ROOT_URLCONF='test_utils.admin_urls')
class TestEnterpriseCustomerManageLearnersDSCViewGet(BaseTestEnterpriseCustomerManageLearnersDSCView):
    """
    Tests for EnterpriseCustomerManageLearnersDataSharingConsentView GET endpoint.
    """

    def _test_get_response(self, response):
        """
        Test view GET response for common parts.
        """
        assert response.status_code == 200
        self._test_common_context(response.context)
        assert response.context[self.context_parameters.ENTERPRISE_CUSTOMER] == self.enterprise_customer
        assert not response.context[self.context_parameters.MANAGE_LEARNERS_DSC_FORM].is_bound

    def test_get_not_logged_in(self):
        response = self.client.get(self.view_url)
        assert response.status_code == 302

    def test_get_links(self):
        self._login()

        response = self.client.get(self.view_url)
        self._test_get_response(response)


@mark.django_db
@override_settings(ROOT_URLCONF='test_utils.admin_urls')
class TestEnterpriseCustomerManageLearnersDSCViewPost(BaseTestEnterpriseCustomerManageLearnersDSCView):
    """
    Tests for EnterpriseCustomerManageLearnersDataSharingConsentView POST endpoint.
    """

    def post_request(self, email_or_username, course_id):
        """
        Post the request ad return the response.
        """
        data = {
            ManageLearnersDataSharingConsentForm.Fields.EMAIL_OR_USERNAME: email_or_username,
            ManageLearnersDataSharingConsentForm.Fields.COURSE: course_id
        }
        with mock.patch("enterprise.api_client.lms.EnrollmentApiClient") as mock_enrollment_client:
            enrollment_instance = mock_enrollment_client.return_value
            enrollment_instance.get_course_details.side_effect = fake_enrollment_api.get_course_details
            return self.client.post(self.view_url, data=data)

    def assert_error(self, response, field, expected_error_message):
        """
        Assert the form with error for given field.
        """
        assert response.status_code == 200
        self._test_common_context(response.context)
        manage_learners_dsc_form = response.context[self.context_parameters.MANAGE_LEARNERS_DSC_FORM]
        assert manage_learners_dsc_form.is_bound
        assert manage_learners_dsc_form.errors == {field: [expected_error_message]}

    def test_post_not_logged_in(self):
        response = self.client.post(self.view_url, data={})
        assert response.status_code == 302

    def test_post_error_user_not_linked(self):
        """
        Test the post request with user not linked with enterprise customer
        """
        self._login()
        course_id = 'course-v1:edX+DemoX+Demo_Course'
        user_not_linked = UserFactory(
            username='user_not_linked',
            email='user_not_linked@example.com',
        )
        with mock.patch.object(EnterpriseCustomer, 'catalog_contains_course') as mock_catalog_contains_course:
            mock_catalog_contains_course.return_value = True
            response = self.post_request(user_not_linked.email, course_id)
            self.assert_error(response, ManageLearnersForm.Fields.EMAIL_OR_USERNAME, ValidationMessages.USER_NOT_LINKED)

    def test_post_error_user_not_exist(self):
        """
        Test the post request with user not exist.
        """
        self._login()
        course_id = 'course-v1:edX+DemoX+Demo_Course'
        email = "user_not_exist@example.com"

        with mock.patch.object(EnterpriseCustomer, 'catalog_contains_course') as mock_catalog_contains_course:
            mock_catalog_contains_course.return_value = True
            response = self.post_request(email, course_id)
            self.assert_error(
                response,
                ManageLearnersForm.Fields.EMAIL_OR_USERNAME,
                ValidationMessages.USER_NOT_EXIST.format(email=email)
            )

    def test_post_error_course_not_exist(self):
        """
        Test the post request with course not exist.
        """
        self._login()
        course_id = 'dummy-course'
        user = UserFactory(username='user_linked', email='user_linked@example.com', )
        EnterpriseCustomerUserFactory(enterprise_customer=self.enterprise_customer, user_id=user.id)

        with mock.patch.object(EnterpriseCustomer, 'catalog_contains_course') as mock_catalog_contains_course:
            mock_catalog_contains_course.return_value = True
            response = self.post_request(user.email, course_id)
            self.assert_error(
                response,
                ManageLearnersForm.Fields.COURSE,
                ValidationMessages.INVALID_COURSE_ID.format(course_id=course_id)
            )

    def test_post_error_course_not_in_catalog(self):
        """
        Test the post request with course doesn't exist in customer's catalog.
        """
        self._login()
        course_id = 'course-v1:edX+DemoX+Demo_Course'
        user = UserFactory(username='user_linked', email='user_linked@example.com',)
        EnterpriseCustomerUserFactory(enterprise_customer=self.enterprise_customer, user_id=user.id)

        with mock.patch.object(EnterpriseCustomer, 'catalog_contains_course') as mock_catalog_contains_course:
            mock_catalog_contains_course.return_value = False
            response = self.post_request(user.email, course_id)
            self.assert_error(
                response,
                ManageLearnersForm.Fields.COURSE,
                ValidationMessages.COURSE_NOT_EXIST_IN_CATALOG.format(course_id=course_id)
            )

    def test_post_valid_request(self):
        """
        Test the valid post request.
        """
        self._login()
        course_id = 'course-v1:edX+DemoX+Demo_Course'
        user = UserFactory(username='user_linked', email='user_linked@example.com')
        EnterpriseCustomerUserFactory(enterprise_customer=self.enterprise_customer, user_id=user.id)

        DataSharingConsentFactory(
            enterprise_customer=self.enterprise_customer,
            username=user.username,
            course_id=course_id
        )

        # Learner has a DSC
        assert DataSharingConsent.objects.filter(
            enterprise_customer=self.enterprise_customer,
            course_id=course_id,
            username=user.username
        ).count() == 1

        with mock.patch.object(EnterpriseCustomer, 'catalog_contains_course') as mock_catalog_contains_course:
            mock_catalog_contains_course.return_value = True
            response = self.post_request(user.email, course_id)
            # Learner DSC has been removed
            assert DataSharingConsent.objects.filter(
                enterprise_customer=self.enterprise_customer,
                course_id=course_id,
                username=user.username
            ).count() == 0
            self.assertRedirects(response, self.view_url)


class BaseTestEnterpriseCustomerManageLearnersView(BaseEnterpriseCustomerView):
    """
    Common functionality for EnterpriseCustomerManageLearnersView tests.
    """

    def setUp(self):
        """
        Test set up - installs common dependencies.
        """
        super().setUp()
        self.view_url = reverse(
            "admin:" + enterprise_admin.utils.UrlNames.MANAGE_LEARNERS,
            args=(self.enterprise_customer.uuid,)
        )
        self.context_parameters = EnterpriseCustomerManageLearnersView.ContextParameters
        self.required_fields_with_default = {
            ManageLearnersForm.Fields.REASON: "tests",
            ManageLearnersForm.Fields.DISCOUNT: 0.0,
        }

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

    def _assert_django_messages(self, post_response, expected_messages):
        """
        Verify that the expected_messages are included in the context of the next response.
        """
        self.assertRedirects(post_response, self.view_url, fetch_redirect_response=False)
        get_response = self.client.get(self.view_url)
        response_messages = {
            (m.level, m.message) for m in get_response.context['messages']
        }
        assert response_messages == expected_messages

    def add_required_data(self, data):
        """
        Adds required fields to post data
        """
        return dict(list(self.required_fields_with_default.items()) + list(data.items()))


@ddt.ddt
@mark.django_db
@override_settings(ROOT_URLCONF="test_utils.admin_urls")
class TestEnterpriseCustomerManageLearnersViewGet(BaseTestEnterpriseCustomerManageLearnersView):
    """
    Tests for EnterpriseCustomerManageLearnersView GET endpoint.
    """

    def _verify_pagination(
            self,
            page_object,
            total_result,
            page_number=1,
            page_start=0,
            page_end=PAGE_SIZE,
            page_size=PAGE_SIZE
    ):
        """
        Verifies pagination.
        """
        # Verify current page details
        assert page_object.number == page_number
        assert list(page_object.object_list) == total_result[page_start:page_end]

        # Verify pagination details
        assert page_object.paginator.count == len(total_result)
        assert page_object.paginator.per_page == page_size

        # if no record is set, pagination will have 1 empty page i.e showing Page 1 of 1.
        result_pages = int(ceil(len(total_result) / float(page_size))) if total_result else 1
        assert page_object.paginator.num_pages == result_pages
        assert list(page_object.paginator.object_list) == total_result

    def _test_get_response(self, response, linked_learners, pending_linked_learners):
        """
        Test view GET response for common parts.
        """
        if linked_learners:
            learner_ids = [learner.user_id for learner in linked_learners]
            # get sorted list of learners to match it with API results
            sorted_linked_learners = list(EnterpriseCustomerUser.objects.filter(
                user_id__in=learner_ids
            ))
        else:
            sorted_linked_learners = linked_learners
        assert response.status_code == 200
        self._test_common_context(response.context)
        assert list(response.context[self.context_parameters.LEARNERS]) == sorted_linked_learners
        assert list(response.context[self.context_parameters.PENDING_LEARNERS]) == pending_linked_learners
        assert response.context[self.context_parameters.ENTERPRISE_CUSTOMER] == self.enterprise_customer
        assert not response.context[self.context_parameters.MANAGE_LEARNERS_FORM].is_bound
        self._verify_pagination(response.context[self.context_parameters.LEARNERS], sorted_linked_learners)

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

        linked_learners = [
            EnterpriseCustomerUserFactory(
                enterprise_customer=self.enterprise_customer,
                user_id=UserFactory().id,
            ),
            EnterpriseCustomerUserFactory(
                enterprise_customer=self.enterprise_customer,
                user_id=UserFactory().id,
            ),
            EnterpriseCustomerUserFactory(
                enterprise_customer=self.enterprise_customer,
                user_id=UserFactory().id,
            ),
        ]
        response = self.client.get(self.view_url)
        self._test_get_response(response, linked_learners, [])

    def test_get_existing_and_pending_links(self):
        self._login()

        linked_learners = [
            EnterpriseCustomerUserFactory(
                enterprise_customer=self.enterprise_customer,
                user_id=UserFactory().id,
            ),
            EnterpriseCustomerUserFactory(
                enterprise_customer=self.enterprise_customer,
                user_id=UserFactory().id,
            ),
            EnterpriseCustomerUserFactory(
                enterprise_customer=self.enterprise_customer,
                user_id=UserFactory().id,
            ),
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

    @ddt.data(
        (1, 1, 0, 25, 50),
        (6, 6, 125, 150, 300),
        (7, 7, 150, 175, 300),
        #  Invalid page values
        ('invalid-page-value', 1, 0, 25, 50),
        (100, 2, 25, 50, 50),
        (-1, 2, 25, 50, 50)
    )
    @ddt.unpack
    def test_get_pagination(self, current_page_number, expected_page_number, page_start, page_end, total_records):
        """
        Test pagination for linked learners list works expectedly.
        """
        self._login()
        linked_learners = []
        for i in range(total_records):
            learner = EnterpriseCustomerUserFactory(
                enterprise_customer=self.enterprise_customer,
                user_id=UserFactory(
                    username='user{user_index}'.format(user_index=i),
                    id=i + 100,  # Just to make sure we don't get IntegrityError.
                ).id
            )
            linked_learners.append(learner.user_id)

        # get sorted list of learners to match it with API results
        sorted_linked_learners = list(EnterpriseCustomerUser.objects.filter(
            user_id__in=linked_learners
        ))
        # Verify we get the paginated result for correct page.
        response = self.client.get('{view_url}?page={page_number}'.format(
            view_url=self.view_url, page_number=current_page_number
        ))
        self._verify_pagination(
            response.context[self.context_parameters.LEARNERS],
            sorted_linked_learners,
            page_number=expected_page_number,
            page_start=page_start,
            page_end=page_end
        )


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

        response = self.client.post(
            self.view_url,
            data=self.add_required_data({ManageLearnersForm.Fields.EMAIL_OR_USERNAME: email})
        )

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

        user = UserFactory(username=username, email=email)

        response = self.client.post(
            self.view_url,
            data=self.add_required_data({ManageLearnersForm.Fields.EMAIL_OR_USERNAME: username})
        )

        self.assertRedirects(response, self.view_url)
        assert EnterpriseCustomerUser.objects.filter(user_id=user.id).count() == 1

    def test_post_invalid_email(self):
        # precondition checks:
        self._login()
        assert EnterpriseCustomerUser.objects.count() == 0  # there're no link records
        assert PendingEnterpriseCustomerUser.objects.count() == 0  # there're no pending link records

        response = self.client.post(
            self.view_url,
            data=self.add_required_data({ManageLearnersForm.Fields.EMAIL_OR_USERNAME: "invalid_email"})
        )

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
                self.view_url, data=self.add_required_data({
                    ManageLearnersForm.Fields.EMAIL_OR_USERNAME: invalid_email

                })
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

        user = UserFactory(email=email)
        EnterpriseCustomerUserFactory(enterprise_customer=self.enterprise_customer, user_id=user.id)
        assert EnterpriseCustomerUser.objects.filter(user_id=user.id).count() == 1
        response = self.client.post(
            self.view_url,
            data=self.add_required_data({ManageLearnersForm.Fields.EMAIL_OR_USERNAME: email})
        )
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

        user = UserFactory(email=email)
        EnterpriseCustomerUserFactory(user_id=user.id, enterprise_customer=self.enterprise_customer)
        assert EnterpriseCustomerUser.objects.count() == 1
        assert PendingEnterpriseCustomerUser.objects.count() == 0
        self.client.post(
            self.view_url,
            data=self.add_required_data({
                ManageLearnersForm.Fields.EMAIL_OR_USERNAME: email + ', john@smith.com'
            })
        )
        assert EnterpriseCustomerUser.objects.count() == 1
        assert PendingEnterpriseCustomerUser.objects.count() == 1

    def test_post_redirected_successfully(self):
        """
        Test post call to enroll user redirected successfully.
        """
        self._login()

        email = FAKER.email()  # pylint: disable=no-member

        user = UserFactory(email=email)
        EnterpriseCustomerUserFactory(user_id=user.id)
        response = self.client.post(
            self.view_url + "?q=bob",
            data=self.add_required_data({
                ManageLearnersForm.Fields.EMAIL_OR_USERNAME: email + ', john@smith.com'
            })
        )
        self.assertRedirects(response, self.view_url + "?q=bob")
        self.assertEqual(response.status_code, 302)

    def test_post_existing_pending_record(self):
        # precondition checks:
        self._login()

        email = FAKER.email()  # pylint: disable=no-member
        PendingEnterpriseCustomerUserFactory(enterprise_customer=self.enterprise_customer, user_email=email)
        assert PendingEnterpriseCustomerUser.objects.filter(user_email=email).count() == 1

        response = self.client.post(
            self.view_url,
            data=self.add_required_data({ManageLearnersForm.Fields.EMAIL_OR_USERNAME: email})
        )
        self._test_post_existing_record_response(response)
        assert PendingEnterpriseCustomerUser.objects.filter(user_email=email).count() == 1

    def test_post_existing_pending_record_with_another_enterprise_customer(self):
        """
        Tests that a PendingEnterpriseCustomerUser already linked with an Enterprise can be linked with another
        Enterprise
        """
        # precondition checks:
        self._login()
        email = FAKER.email()  # pylint: disable=no-member
        another_ent = EnterpriseCustomerFactory()
        PendingEnterpriseCustomerUserFactory(enterprise_customer=another_ent, user_email=email)
        # Confirm that only one instance exists before post request
        assert PendingEnterpriseCustomerUser.objects.filter(user_email=email).count() == 1

        response = self.client.post(
            self.view_url,
            data=self.add_required_data({ManageLearnersForm.Fields.EMAIL_OR_USERNAME: email})
        )
        self._test_post_existing_record_response(response)
        assert PendingEnterpriseCustomerUser.objects.filter(user_email=email).count() == 2

    def _enroll_user_request(
        self,
        user,
        mode,
        course_id="",
        notify=True,
        reason="tests",
        discount=0.0,
        force_enrollment=False
    ):
        """
        Perform post request to log in and submit the form to enroll a user.
        """
        notify = (
            ManageLearnersForm.NotificationTypes.BY_EMAIL if notify
            else ManageLearnersForm.NotificationTypes.NO_NOTIFICATION
        )
        self._login()

        if isinstance(user, str):
            email_or_username = user
        else:
            # Allow us to send forms involving pending users
            email_or_username = getattr(user, 'username', getattr(user, 'user_email', None))

        with mock.patch("enterprise.api_client.ecommerce.get_ecommerce_api_client"):
            with mock.patch('enterprise.api_client.ecommerce.configuration_helpers'):
                response = self.client.post(self.view_url, data={
                    ManageLearnersForm.Fields.EMAIL_OR_USERNAME: email_or_username,
                    ManageLearnersForm.Fields.COURSE_MODE: mode,
                    ManageLearnersForm.Fields.COURSE: course_id,
                    ManageLearnersForm.Fields.NOTIFY: notify,
                    ManageLearnersForm.Fields.REASON: reason,
                    ManageLearnersForm.Fields.DISCOUNT: discount,
                    ManageLearnersForm.Fields.FORCE_ENROLLMENT: force_enrollment,
                })
        return response

    @mock.patch("enterprise.admin.views.EcommerceApiClient")
    @mock.patch("enterprise.utils.track_enrollment")
    @mock.patch("enterprise.models.CourseCatalogApiClient")
    @mock.patch("enterprise.api_client.lms.EnrollmentApiClient")
    @mock.patch("enterprise.models.EnterpriseCatalogApiClient")
    @ddt.data(
        (True, True),
        (False, True),
        (True, False),
        (False, False)
    )
    @ddt.unpack
    def test_post_enroll_user(
            self,
            enrollment_exists,
            audit_mode,
            enterprise_catalog_client,
            enrollment_client,
            course_catalog_client,
            track_enrollment,
            ecommerce_api_client_mock
    ):
        catalog_instance = course_catalog_client.return_value
        catalog_instance.get_course_run.return_value = {
            "title": "Cool Science",
            "start": "2017-01-01T12:00:00Z",
            "marketing_url": "http://lms.example.com/courses/course-v1:HarvardX+CoolScience+2016"
        }
        enrollment_instance = enrollment_client.return_value
        enrollment_instance.enroll_user_in_course.side_effect = fake_enrollment_api.enroll_user_in_course
        enrollment_instance.get_course_details.side_effect = fake_enrollment_api.get_course_details
        enterprise_catalog_instance = enterprise_catalog_client.return_value
        enterprise_catalog_instance.enterprise_contains_content_items.return_value = True

        user = UserFactory()
        course_id = "course-v1:HarvardX+CoolScience+2016"
        mode = "audit" if audit_mode else "verified"
        if enrollment_exists:
            enterprise_customer_user = EnterpriseCustomerUser.objects.create(
                enterprise_customer=self.enterprise_customer,
                user_id=user.id,
            )
            EnterpriseCourseEnrollment.objects.create(
                enterprise_customer_user=enterprise_customer_user,
                course_id=course_id,
            )
        response = self._enroll_user_request(user, mode, course_id=course_id)
        if audit_mode:
            ecommerce_api_client_mock.assert_not_called()
        else:
            ecommerce_api_client_mock.assert_called_once()
        enrollment_instance.enroll_user_in_course.assert_called_once_with(
            user.username,
            course_id,
            mode,
            enterprise_uuid=str(self.enterprise_customer.uuid),
            force_enrollment=False
        )
        if enrollment_exists:
            track_enrollment.assert_not_called()
        else:
            track_enrollment.assert_called_once_with('admin-enrollment', user.id, course_id)
        self._assert_django_messages(response, {
            (messages.SUCCESS, "1 learner was enrolled in {}.".format(course_id)),
        })
        all_enterprise_enrollments = EnterpriseCourseEnrollment.objects.all()
        num_enterprise_enrollments = len(all_enterprise_enrollments)
        assert num_enterprise_enrollments == 1
        enrollment = all_enterprise_enrollments[0]
        assert enrollment.enterprise_customer_user.user == user
        assert enrollment.course_id == course_id
        if not enrollment_exists:
            assert enrollment.source is not None
            assert enrollment.source.slug == EnterpriseEnrollmentSource.MANUAL
        num_messages = len(mail.outbox)
        assert num_messages == 1

    def _post_multi_enroll(
            self,
            enterprise_catalog_client,
            enrollment_client,
            course_catalog_client,
            track_enrollment,
            create_user,
    ):
        """
        Enroll an enterprise learner or pending learner in multiple courses.
        """
        courses = {
            "course-v1:HarvardX+CoolScience+2016": {
                "title": "Cool Science",
                "start": "2017-01-01T12:00:00Z",
                "marketing_url": "http://lms.example.com/courses/course-v1:HarvardX+CoolScience+2016",
                "mode": "verified"
            },
            "course-v1:edX+DemoX+Demo_Course": {
                "title": "edX Demo Course",
                "start": "2013-02-05T05:00:00Z",
                "marketing_url": "http://lms.example.com/courses/course-v1:edX+DemoX+Demo_Course",
                "mode": "audit"
            }
        }
        catalog_instance = course_catalog_client.return_value
        enrollment_instance = enrollment_client.return_value
        enrollment_instance.enroll_user_in_course.side_effect = fake_enrollment_api.enroll_user_in_course
        enrollment_instance.get_course_details.side_effect = fake_enrollment_api.get_course_details
        enterprise_catalog_instance = enterprise_catalog_client.return_value
        enterprise_catalog_instance.enterprise_contains_content_items.return_value = True

        enrollment_count = 0
        user = None
        user_email = FAKER.email()  # pylint: disable=no-member
        if create_user:
            user = UserFactory(email=user_email)

        for course_id, course_metadata in courses.items():
            catalog_instance.get_course_run.return_value = course_metadata
            mode = course_metadata['mode']
            enrollment_count += 1

            if user:
                response = self._enroll_user_request(user, mode, course_id=course_id)
                if enrollment_count == 1:
                    enrollment_instance.enroll_user_in_course.assert_called_once()
                    track_enrollment.assert_called_once()
                enrollment_instance.enroll_user_in_course.assert_called_with(
                    user.username,
                    course_id,
                    mode,
                    enterprise_uuid=str(self.enterprise_customer.uuid),
                    force_enrollment=False,
                )
                track_enrollment.assert_called_with('admin-enrollment', user.id, course_id)
                self._assert_django_messages(response, {
                    (messages.SUCCESS, "1 learner was enrolled in {}.".format(course_id)),
                })
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
            assert enrollment.source is not None
            assert enrollment.source.slug == EnterpriseEnrollmentSource.MANUAL
            num_messages = len(mail.outbox)
            assert num_messages == enrollment_count

    @mock.patch("enterprise.utils.track_enrollment")
    @mock.patch("enterprise.models.CourseCatalogApiClient")
    @mock.patch("enterprise.api_client.lms.EnrollmentApiClient")
    @mock.patch("enterprise.models.EnterpriseCatalogApiClient")
    def test_post_multi_enroll_user(
            self,
            enterprise_catalog_client,
            enrollment_client,
            course_catalog_client,
            track_enrollment,
    ):
        """
        Test that an existing learner can be enrolled in multiple courses.
        """
        self._post_multi_enroll(
            enterprise_catalog_client,
            enrollment_client,
            course_catalog_client,
            track_enrollment,
            True,
        )

    @mock.patch("enterprise.utils.track_enrollment")
    @mock.patch("enterprise.models.CourseCatalogApiClient")
    @mock.patch("enterprise.api_client.lms.EnrollmentApiClient")
    @mock.patch("enterprise.models.EnterpriseCatalogApiClient")
    def test_post_multi_enroll_pending_user(
            self,
            enterprise_catalog_client,
            enrollment_client,
            course_catalog_client,
            track_enrollment,
    ):
        """
        Test that a pending learner can be enrolled in multiple courses.
        """
        with mock.patch(
            'enterprise.models.EnrollmentApiClient.get_course_details',
            wraps=fake_enrollment_api.get_course_details,
        ):
            self._post_multi_enroll(
                enterprise_catalog_client,
                enrollment_client,
                course_catalog_client,
                track_enrollment,
                False,
            )

    @mock.patch("enterprise.utils.track_enrollment")
    @mock.patch("enterprise.models.CourseCatalogApiClient")
    @mock.patch("enterprise.api_client.lms.EnrollmentApiClient")
    @mock.patch("enterprise.models.EnterpriseCatalogApiClient")
    def test_post_enroll_no_course_detail(
            self,
            enterprise_catalog_client,
            enrollment_client,
            course_catalog_client,
            track_enrollment,
    ):
        catalog_instance = course_catalog_client.return_value
        catalog_instance.get_course_run.return_value = {}
        enrollment_instance = enrollment_client.return_value
        enrollment_instance.enroll_user_in_course.side_effect = fake_enrollment_api.enroll_user_in_course
        enrollment_instance.get_course_details.side_effect = fake_enrollment_api.get_course_details
        enterprise_catalog_instance = enterprise_catalog_client.return_value
        enterprise_catalog_instance.enterprise_contains_content_items.return_value = True

        user = UserFactory()
        course_id = "course-v1:HarvardX+CoolScience+2016"
        mode = "verified"
        response = self._enroll_user_request(user, mode, course_id=course_id)
        enrollment_instance.enroll_user_in_course.assert_called_once_with(
            user.username,
            course_id,
            mode,
            enterprise_uuid=str(self.enterprise_customer.uuid),
            force_enrollment=False
        )
        track_enrollment.assert_called_once_with('admin-enrollment', user.id, course_id)
        self._assert_django_messages(response, {
            (messages.SUCCESS, "1 learner was enrolled in {}.".format(course_id)),
        })
        all_enterprise_enrollments = EnterpriseCourseEnrollment.objects.all()
        num_enterprise_enrollments = len(all_enterprise_enrollments)
        assert num_enterprise_enrollments == 1
        enrollment = all_enterprise_enrollments[0]
        assert enrollment.enterprise_customer_user.user == user
        assert enrollment.course_id == course_id
        assert enrollment.source is not None
        assert enrollment.source.slug == EnterpriseEnrollmentSource.MANUAL
        num_messages = len(mail.outbox)
        assert num_messages == 0

    @mock.patch("enterprise.utils.track_enrollment")
    @mock.patch("enterprise.models.CourseCatalogApiClient")
    @mock.patch("enterprise.api_client.lms.EnrollmentApiClient")
    @mock.patch("enterprise.models.EnterpriseCatalogApiClient")
    @ddt.data(True, False)
    def test_post_enroll_force_enrollment(
            self,
            force_enrollment,
            enterprise_catalog_client,
            enrollment_client,
            course_catalog_client,
            track_enrollment,
    ):
        catalog_instance = course_catalog_client.return_value
        catalog_instance.get_course_run.return_value = {}
        enrollment_instance = enrollment_client.return_value
        enrollment_instance.enroll_user_in_course.side_effect = fake_enrollment_api.enroll_user_in_course
        enrollment_instance.get_course_details.side_effect = fake_enrollment_api.get_course_details
        enterprise_catalog_instance = enterprise_catalog_client.return_value
        enterprise_catalog_instance.enterprise_contains_content_items.return_value = True

        user = UserFactory()
        course_id = "course-v1:HarvardX+CoolScience+2016"
        mode = "verified"
        response = self._enroll_user_request(user, mode, course_id=course_id, force_enrollment=force_enrollment)
        enrollment_instance.enroll_user_in_course.assert_called_once_with(
            user.username,
            course_id,
            mode,
            enterprise_uuid=str(self.enterprise_customer.uuid),
            force_enrollment=force_enrollment
        )
        track_enrollment.assert_called_once_with('admin-enrollment', user.id, course_id)
        self._assert_django_messages(response, {
            (messages.SUCCESS, "1 learner was enrolled in {}.".format(course_id)),
        })
        all_enterprise_enrollments = EnterpriseCourseEnrollment.objects.all()
        num_enterprise_enrollments = len(all_enterprise_enrollments)
        assert num_enterprise_enrollments == 1
        enrollment = all_enterprise_enrollments[0]
        assert enrollment.enterprise_customer_user.user == user
        assert enrollment.course_id == course_id
        assert enrollment.source is not None
        assert enrollment.source.slug == EnterpriseEnrollmentSource.MANUAL

    @mock.patch("enterprise.utils.track_enrollment")
    @mock.patch("enterprise.models.CourseCatalogApiClient")
    @mock.patch("enterprise.api_client.lms.EnrollmentApiClient")
    @mock.patch("enterprise.models.EnterpriseCatalogApiClient")
    def test_post_enroll_course_when_enrollment_closed(
            self,
            enterprise_catalog_client,
            enrollment_client,
            course_catalog_client,
            track_enrollment,
    ):
        """
        Tests scenario when user being enrolled has already SCE(student CourseEnrollment) record
        and course enrollment window is closed
        """
        catalog_instance = course_catalog_client.return_value
        catalog_instance.get_course_run.return_value = {}
        enrollment_instance = enrollment_client.return_value
        enrollment_instance.enroll_user_in_course.side_effect = HttpClientError(
            "Client Error", content=json.dumps({"message": "Enrollment closed"}).encode()
        )
        enrollment_instance.get_course_enrollment.side_effect = fake_enrollment_api.get_course_enrollment
        enrollment_instance.get_course_details.side_effect = fake_enrollment_api.get_course_details
        enterprise_catalog_instance = enterprise_catalog_client.return_value
        enterprise_catalog_instance.enterprise_contains_content_items.return_value = True

        user = UserFactory()
        course_id = "course-v1:HarvardX+CoolScience+2016"
        mode = "verified"
        response = self._enroll_user_request(user, mode, course_id=course_id)
        track_enrollment.assert_called_once_with('admin-enrollment', user.id, course_id)
        self._assert_django_messages(response, {
            (messages.SUCCESS, "1 learner was enrolled in {}.".format(course_id)),
        })
        all_enterprise_enrollments = EnterpriseCourseEnrollment.objects.all()
        num_enterprise_enrollments = len(all_enterprise_enrollments)
        assert num_enterprise_enrollments == 1
        enrollment = all_enterprise_enrollments[0]
        assert enrollment.enterprise_customer_user.user == user
        assert enrollment.course_id == course_id
        assert enrollment.source is not None
        assert enrollment.source.slug == EnterpriseEnrollmentSource.MANUAL
        num_messages = len(mail.outbox)
        assert num_messages == 0
        enrollment_instance.enroll_user_in_course.assert_called_once_with(
            user.username,
            course_id,
            mode,
            enterprise_uuid=str(self.enterprise_customer.uuid),
            force_enrollment=False
        )

    @mock.patch("enterprise.utils.track_enrollment")
    @mock.patch("enterprise.models.CourseCatalogApiClient")
    @mock.patch("enterprise.api_client.lms.EnrollmentApiClient")
    @mock.patch("enterprise.models.EnterpriseCatalogApiClient")
    def test_post_enroll_course_when_enrollment_closed_mode_changed(
            self, enterprise_catalog_client, enrollment_client, course_catalog_client, track_enrollment
    ):
        """
        Tests scenario when user being enrolled has already SCE(student CourseEnrollment) record
        with different mode
        and course enrollment window is closed
        """
        catalog_instance = course_catalog_client.return_value
        catalog_instance.get_course_run.return_value = {}
        enrollment_instance = enrollment_client.return_value
        enrollment_instance.enroll_user_in_course.side_effect = HttpClientError(
            "Client Error", content=json.dumps({"message": "Enrollment closed"}).encode()
        )
        enrollment_instance.get_course_enrollment.side_effect = fake_enrollment_api.get_course_enrollment
        enrollment_instance.get_course_details.side_effect = fake_enrollment_api.get_course_details
        enterprise_catalog_instance = enterprise_catalog_client.return_value
        enterprise_catalog_instance.enterprise_contains_content_items.return_value = True

        user = UserFactory()
        course_id = "course-v1:HarvardX+CoolScience+2016"
        mode = "audit"
        response = self._enroll_user_request(user, mode, course_id=course_id)
        enrollment_instance.enroll_user_in_course.assert_called_once_with(
            user.username,
            course_id,
            mode,
            enterprise_uuid=str(self.enterprise_customer.uuid),
            force_enrollment=False
        )
        track_enrollment.assert_not_called()
        self._assert_django_messages(response, {
            (messages.ERROR, "The following learners could not be enrolled in {}: {}".format(course_id, user.email))
        })

    @mock.patch("enterprise.utils.track_enrollment")
    @mock.patch("enterprise.models.CourseCatalogApiClient")
    @mock.patch("enterprise.api_client.lms.EnrollmentApiClient")
    @mock.patch("enterprise.models.EnterpriseCatalogApiClient")
    def test_post_enroll_course_when_enrollment_closed_no_sce_exists(
            self,
            enterprise_catalog_client,
            enrollment_client,
            course_catalog_client,
            track_enrollment,
    ):
        """
        Tests scenario when user being enrolled has no SCE(student CourseEnrollment) record
        and course enrollment window is closed
        """
        catalog_instance = course_catalog_client.return_value
        catalog_instance.get_course_run.return_value = {}
        enrollment_instance = enrollment_client.return_value
        enrollment_instance.enroll_user_in_course.side_effect = HttpClientError(
            "Client Error", content=json.dumps({"message": "Enrollment closed"}).encode()
        )
        enrollment_instance.get_course_enrollment.return_value = None
        enrollment_instance.get_course_details.side_effect = fake_enrollment_api.get_course_details
        enterprise_catalog_instance = enterprise_catalog_client.return_value
        enterprise_catalog_instance.enterprise_contains_content_items.return_value = True

        user = UserFactory()
        course_id = "course-v1:HarvardX+CoolScience+2016"
        mode = "verified"
        response = self._enroll_user_request(user, mode, course_id=course_id)
        enrollment_instance.enroll_user_in_course.assert_called_once_with(
            user.username,
            course_id,
            mode,
            enterprise_uuid=str(self.enterprise_customer.uuid),
            force_enrollment=False
        )
        track_enrollment.assert_not_called()
        self._assert_django_messages(response, {
            (messages.ERROR, "The following learners could not be enrolled in {}: {}".format(course_id, user.email))
        })

    @mock.patch("enterprise.utils.track_enrollment")
    @mock.patch("enterprise.models.CourseCatalogApiClient")
    @mock.patch("enterprise.api_client.lms.EnrollmentApiClient")
    @mock.patch("enterprise.models.EnterpriseCatalogApiClient")
    def test_post_enroll_with_missing_course_start_date(
            self,
            enterprise_catalog_client,
            enrollment_client,
            course_catalog_client,
            track_enrollment,
    ):
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
            "marketing_url": "http://lms.example.com/courses/course-v1:HarvardX+CoolScience+2016"
        }
        enrollment_instance = enrollment_client.return_value
        enrollment_instance.enroll_user_in_course.side_effect = fake_enrollment_api.enroll_user_in_course
        enrollment_instance.get_course_details.side_effect = fake_enrollment_api.get_course_details
        enterprise_catalog_instance = enterprise_catalog_client.return_value
        enterprise_catalog_instance.enterprise_contains_content_items.return_value = True

        user = UserFactory()
        course_id = "course-v1:HarvardX+CoolScience+2016"
        mode = "verified"
        response = self._enroll_user_request(user, mode, course_id=course_id)
        enrollment_instance.enroll_user_in_course.assert_called_once_with(
            user.username,
            course_id,
            mode,
            enterprise_uuid=str(self.enterprise_customer.uuid),
            force_enrollment=False
        )
        track_enrollment.assert_called_once_with('admin-enrollment', user.id, course_id)
        self._assert_django_messages(response, {
            (messages.SUCCESS, "1 learner was enrolled in {}.".format(course_id)),
        })
        all_enterprise_enrollments = EnterpriseCourseEnrollment.objects.all()
        num_enterprise_enrollments = len(all_enterprise_enrollments)
        assert num_enterprise_enrollments == 1
        enrollment = all_enterprise_enrollments[0]
        assert enrollment.enterprise_customer_user.user == user
        assert enrollment.course_id == course_id
        assert enrollment.source is not None
        assert enrollment.source.slug == EnterpriseEnrollmentSource.MANUAL
        num_messages = len(mail.outbox)
        assert num_messages == 1

    @mock.patch("enterprise.utils.reverse")
    @mock.patch("enterprise.models.CourseCatalogApiClient")
    @mock.patch("enterprise.api_client.lms.EnrollmentApiClient")
    @mock.patch("enterprise.models.EnterpriseCatalogApiClient")
    def test_post_enrollment_error(
            self,
            enterprise_catalog_client,
            enrollment_client,
            course_catalog_client,
            reverse_mock,
    ):
        reverse_mock.return_value = '/courses/course-v1:HarvardX+CoolScience+2016'
        catalog_instance = course_catalog_client.return_value
        catalog_instance.get_course_run.return_value = {
            "name": "Cool Science",
            "start": "2017-01-01T12:00:00Z",
        }
        enrollment_instance = enrollment_client.return_value
        enrollment_instance.enroll_user_in_course.side_effect = HttpClientError(
            "Client Error", content=json.dumps({"message": "test"}).encode()
        )
        enrollment_instance.get_course_details.side_effect = fake_enrollment_api.get_course_details
        enterprise_catalog_instance = enterprise_catalog_client.return_value
        enterprise_catalog_instance.enterprise_contains_content_items.return_value = True

        user = UserFactory()
        course_id = "course-v1:HarvardX+CoolScience+2016"
        mode = "verified"
        response = self._enroll_user_request(user, mode, course_id=course_id)
        self._assert_django_messages(response, {
            (messages.ERROR, "The following learners could not be enrolled in {}: {}".format(course_id, user.email)),
        })

    @mock.patch("enterprise.utils.reverse")
    @mock.patch("enterprise.models.CourseCatalogApiClient")
    @mock.patch("enterprise.api_client.lms.EnrollmentApiClient")
    @mock.patch("enterprise.models.EnterpriseCatalogApiClient")
    def test_post_enrollment_error_bad_error_string(
            self,
            enterprise_catalog_client,
            enrollment_client,
            course_catalog_client,
            reverse_mock,
    ):
        reverse_mock.return_value = '/courses/course-v1:HarvardX+CoolScience+2016'
        catalog_instance = course_catalog_client.return_value
        catalog_instance.get_course_run.return_value = {
            "name": "Cool Science",
            "start": "2017-01-01T12:00:00Z",
        }
        enrollment_instance = enrollment_client.return_value
        enrollment_instance.enroll_user_in_course.side_effect = HttpClientError(
            "Client Error", content=b'This is not JSON'
        )
        enrollment_instance.get_course_details.side_effect = fake_enrollment_api.get_course_details
        enterprise_catalog_instance = enterprise_catalog_client.return_value
        enterprise_catalog_instance.enterprise_contains_content_items.return_value = True

        user = UserFactory()
        course_id = "course-v1:HarvardX+CoolScience+2016"
        mode = "verified"
        response = self._enroll_user_request(user, mode, course_id=course_id)
        self._assert_django_messages(response, {
            (messages.ERROR, "The following learners could not be enrolled in {}: {}".format(course_id, user.email)),
        })


@ddt.ddt
@mark.django_db
@override_settings(ROOT_URLCONF="test_utils.admin_urls")
class TestEnterpriseCustomerManageLearnersViewPostBulkUpload(BaseTestEnterpriseCustomerManageLearnersView):
    """
    Tests for EnterpriseCustomerManageLearnersView POST endpoint - bulk user linking.
    """

    def _get_form(self, response, expected_status_code=200):
        """
        Utility function to capture common parts of assertions on form errors.

        Arguments:
            response (HttpResponse): View response.
            expected_status_code: The expected status code, e.g. 200.

        Returns:
            ManageLearnersForm: bound instance of ManageLearnersForm used to render the response,
                or None if the response is a 302 redirect.

        Raises:
            AssertionError: if response status code mismatches the expected status code or form is unbound.
        """
        assert response.status_code == expected_status_code

        # response.context is ``None`` when the POST request is successful, without any errors in form validation.
        if not response.context:
            return None

        self._test_common_context(response.context)
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

    @mock.patch("enterprise.api_client.ecommerce.configuration_helpers", mock.Mock())
    def _perform_request(self, columns, data, course=None, course_mode=None, notify=True):
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
            if course is not None:
                post_data[ManageLearnersForm.Fields.COURSE] = course
            if course_mode is not None:
                post_data[ManageLearnersForm.Fields.COURSE_MODE] = course_mode
            post_data[ManageLearnersForm.Fields.NOTIFY] = 'by_email' if notify else 'do_not_notify'
            post_data['enterprise_customer'] = self.enterprise_customer
            with mock.patch("enterprise.api_client.ecommerce.get_ecommerce_api_client"):
                response = self.client.post(self.view_url, data=self.add_required_data(post_data))
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
        user = UserFactory()
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

    def test_post_unlinkable_user_error_skips_all(self):
        self._login()
        user_email = "abc@example.com"
        user = UserFactory(email=user_email)
        EnterpriseCustomerUserFactory(
            enterprise_customer=self.enterprise_customer,
            user_id=user.id,
            active=False,
            linked=False,
            is_relinkable=False
        )

        assert EnterpriseCustomerUser.objects.count() == 0, "Precondition check: no linked users"
        assert PendingEnterpriseCustomerUser.objects.count() == 0, "Precondition check: no pending linked users"

        columns = [ManageLearnersForm.CsvColumns.EMAIL]
        data = [
            (FAKER.email(),),  # valid not previously seen email;  pylint: disable=no-member
            (user.email,),  # invalid user email
        ]
        response = self._perform_request(columns, data)

        assert not EnterpriseCustomerUser.objects.all().exists(), "No linked users should be created"
        assert not PendingEnterpriseCustomerUser.objects.all().exists(), "No pending linked users should be created"

        manage_learners_form = self._get_form(response)
        bulk_upload_errors = manage_learners_form.errors[ManageLearnersForm.Fields.BULK_UPLOAD]

        expected_error_message = "User {} cannot be relinked to {}.".format(user, self.enterprise_customer)
        assert bulk_upload_errors[0] == expected_error_message

    @ddt.data(
        {'valid_course_id': False, 'course_in_catalog': False, 'expected_status_code': 200},
        {'valid_course_id': False, 'course_in_catalog': True, 'expected_status_code': 200},
        {'valid_course_id': True, 'course_in_catalog': False, 'expected_status_code': 200},
        {'valid_course_id': True, 'course_in_catalog': True, 'expected_status_code': 302},
    )
    @ddt.unpack
    @mock.patch("enterprise.admin.views.create_manual_enrollment_audit")
    @mock.patch("enterprise.models.CourseCatalogApiClient")
    @mock.patch("enterprise.api_client.lms.EnrollmentApiClient")
    @mock.patch("enterprise.models.EnterpriseCatalogApiClient")
    @mock.patch("enterprise.admin.views.enroll_users_in_course")
    def test_post_create_course_enrollments(
            self,
            enroll_users_in_course_mock,
            enterprise_catalog_client,
            enrollment_client,
            course_catalog_client,
            create_enrollment_audit_mock,
            valid_course_id,
            course_in_catalog,
            expected_status_code,
    ):
        self._login()
        user = UserFactory()
        second_email = FAKER.email()  # pylint: disable=no-member
        third_email = FAKER.email()  # pylint: disable=no-member
        course_id = "course-v1:edX+DemoX+Demo_Course"
        second_course_id = "course-v1:HarvardX+CoolScience+2016"
        should_create_enrollments = False

        enrollment_instance = enrollment_client.return_value
        course_catalog_instance = course_catalog_client.return_value
        enterprise_catalog_instance = enterprise_catalog_client.return_value
        enterprise_catalog_instance.enterprise_contains_content_items.return_value = course_in_catalog
        create_enrollment_audit_mock.return_value = True
        enroll_users_in_course_mock.return_value = [user], [], []

        csv_columns = [ManageLearnersForm.CsvColumns.EMAIL, ManageLearnersForm.CsvColumns.COURSE_ID]
        csv_data = [
            (user.email, course_id),
            (second_email, course_id),
            (third_email, second_course_id),
        ]

        if valid_course_id:
            enrollment_instance.get_course_details.side_effect = [
                fake_enrollment_api.get_course_details(course_id),
                fake_enrollment_api.get_course_details(course_id),
                fake_enrollment_api.get_course_details(second_course_id),
            ]
            course_catalog_instance.get_course_run.side_effect = [
                {
                    'key': course_id,
                    'title': 'Fake Course',
                    'start': '2020-11-01T00:00:00Z',
                },
                {
                    'key': course_id,
                    'title': 'Fake Course',
                    'start': '2020-11-01T00:00:00Z',
                },
                {
                    'key': second_course_id,
                    'title': 'Fake Course 2',
                    'start': '2019-10-01T00:00:00Z',
                },
            ]
        else:
            enrollment_instance.get_course_details.return_value = {}

        response = self._perform_request(csv_columns, csv_data, notify=False)

        manage_learners_form = self._get_form(response, expected_status_code=expected_status_code)
        bulk_upload_errors = []
        if manage_learners_form:
            bulk_upload_errors = manage_learners_form.errors[ManageLearnersForm.Fields.BULK_UPLOAD]
            print('bulk_upload_errors', bulk_upload_errors)

        if valid_course_id and course_in_catalog:
            # valid input, no errors
            assert not bulk_upload_errors
            should_create_enrollments = True

        if not valid_course_id:
            line_error_message = ValidationMessages.INVALID_COURSE_ID.format(course_id=course_id)
            self._assert_line_message(bulk_upload_errors[0], 1, line_error_message)
        elif not course_in_catalog:
            line_error_message = ValidationMessages.COURSE_NOT_EXIST_IN_CATALOG.format(course_id=course_id)
            self._assert_line_message(bulk_upload_errors[0], 1, line_error_message)

        if should_create_enrollments:
            # assert correct users are enrolled in the proper courses based on the csv data
            enroll_users_in_course_mock.assert_any_call(
                course_id=course_id,
                emails=sorted([user.email, second_email]),
                course_mode=ANY,
                discount=ANY,
                enrollment_reason=ANY,
                enrollment_requester=ANY,
                enterprise_customer=ANY,
                sales_force_id=ANY,
                force_enrollment=ANY,
            )
            enroll_users_in_course_mock.assert_any_call(
                course_id=second_course_id,
                emails=[third_email],
                course_mode=ANY,
                discount=ANY,
                enrollment_reason=ANY,
                enrollment_requester=ANY,
                enterprise_customer=ANY,
                sales_force_id=ANY,
                force_enrollment=ANY,
            )
        else:
            enroll_users_in_course_mock.assert_not_called()

    def test_post_existing_and_duplicates(self):
        """
        Test that duplicates and existing links are handled correctly.

        1. Users already linked to an EnterpriseCustomer should cause a warning message, and an
            additional link won't be created, but otherwise will behave normally.
        2. Users that appear in a CSV twice will be ignored and a message will be created.
        3. Users that are attached to a different EnterpriseCustomer will be added to the enterprise being managed
        """
        self._login()
        user = UserFactory()
        linked_user = UserFactory()
        user_linked_to_other_ec = UserFactory()
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

        assert EnterpriseCustomerUser.objects.count() == 4, \
            "Two linked users remain, and one new link is created"
        assert EnterpriseCustomerUser.objects.filter(user_id=linked_user.id).exists()
        assert EnterpriseCustomerUser.objects.filter(user_id=user.id).exists()
        assert PendingEnterpriseCustomerUser.objects.count() == 1, "One pending linked users should be created"
        assert PendingEnterpriseCustomerUser.objects.filter(user_email=new_email).exists()
        self._assert_django_messages(response, {
            (messages.SUCCESS, "3 new learners were added to {}.".format(self.enterprise_customer.name)),
            (
                messages.WARNING,
                "The following learners were already associated with this "
                "Enterprise Customer: {}".format(linked_user.email)
            ),
            (messages.WARNING, "The following duplicate email addresses were not added: {}".format(user.email)),
        })

    def test_post_successful_test(self):
        """
        Test bulk upload in complex.
        """
        self._login()

        assert EnterpriseCustomerUser.objects.count() == 0, "Precondition check: no linked users"
        assert PendingEnterpriseCustomerUser.objects.count() == 0, "Precondition check: no pending linked users"

        user_by_email = UserFactory()
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
        self._assert_django_messages(response, {
            (messages.SUCCESS, "2 new learners were added to {}.".format(self.enterprise_customer.name)),
        })

    @mock.patch("enterprise.utils.track_enrollment")
    @mock.patch("enterprise.models.CourseCatalogApiClient")
    @mock.patch("enterprise.api_client.lms.EnrollmentApiClient")
    @mock.patch("enterprise.models.EnterpriseCatalogApiClient")
    @mock.patch("enterprise.models.CourseEnrollmentAllowed")
    def test_post_link_and_enroll(
            self,
            mock_cea,
            enterprise_catalog_client,
            enrollment_client,
            course_catalog_client,
            track_enrollment,
    ):
        """
        Test bulk upload with linking and enrolling
        """
        discount_percentage = 20.0
        sales_force_id = 'dummy-sales_force_id'
        self.required_fields_with_default[ManageLearnersForm.Fields.DISCOUNT] = discount_percentage
        self.required_fields_with_default[ManageLearnersForm.Fields.SALES_FORCE_ID] = sales_force_id
        course_catalog_instance = course_catalog_client.return_value
        course_catalog_instance.get_course_run.return_value = {
            "name": "Enterprise Training",
            "start": "2017-01-01T12:00:00Z",
            "marketing_url": "http://localhost/course-v1:EnterpriseX+Training+2017"
        }
        enrollment_instance = enrollment_client.return_value
        enrollment_instance.enroll_user_in_course.side_effect = fake_enrollment_api.enroll_user_in_course
        enrollment_instance.get_course_details.side_effect = fake_enrollment_api.get_course_details
        enterprise_catalog_instance = enterprise_catalog_client.return_value
        enterprise_catalog_instance.enterprise_contains_content_items.return_value = True

        self._login()
        user = UserFactory.create()
        unknown_email = FAKER.email()  # pylint: disable=no-member
        columns = [ManageLearnersForm.CsvColumns.EMAIL]
        data = [(user.email,), (unknown_email,)]
        course_id = "course-v1:EnterpriseX+Training+2017"
        course_mode = "professional"

        with mock.patch(
            'enterprise.models.EnrollmentApiClient.get_course_details',
            wraps=fake_enrollment_api.get_course_details,
        ):
            response = self._perform_request(columns, data, course=course_id, course_mode=course_mode)

        enrollment_instance.enroll_user_in_course.assert_called_once_with(
            user.username,
            course_id,
            course_mode,
            enterprise_uuid=str(self.enterprise_customer.uuid),
            force_enrollment=False
        )
        track_enrollment.assert_called_once_with('admin-enrollment', user.id, course_id)
        pending_user_message = (
            "The following learners do not have an account on Test platform. "
            "They have not been enrolled in {}. When these learners create an "
            "account, they will be enrolled automatically: {}"
        )
        self._assert_django_messages(response, {
            (messages.SUCCESS, "2 new learners were added to {}.".format(self.enterprise_customer.name)),
            (messages.SUCCESS, "1 learner was enrolled in {}.".format(course_id)),
            (messages.WARNING, pending_user_message.format(course_id, unknown_email)),
        })
        pending_enrollment = PendingEnterpriseCustomerUser.objects.all()[0].pendingenrollment_set.all()[0]
        assert pending_enrollment.course_id == course_id
        assert pending_enrollment.discount_percentage == discount_percentage
        assert pending_enrollment.sales_force_id == sales_force_id
        num_messages = len(mail.outbox)
        assert num_messages == 2
        mock_cea.objects.update_or_create.assert_called_once()

    @mock.patch("enterprise.utils.track_enrollment")
    @mock.patch("enterprise.models.CourseCatalogApiClient")
    @mock.patch("enterprise.api_client.lms.EnrollmentApiClient")
    @mock.patch("enterprise.models.EnterpriseCatalogApiClient")
    @mock.patch("enterprise.models.CourseEnrollmentAllowed")
    def test_post_link_and_enroll_no_course_details(
            self,
            mock_cea,
            enterprise_catalog_client,
            enrollment_client,
            course_catalog_client,
            track_enrollment,
    ):
        """
        Test bulk upload with linking and enrolling
        """
        course_catalog_instance = course_catalog_client.return_value
        course_catalog_instance.get_course_run.return_value = {}
        enrollment_instance = enrollment_client.return_value
        enrollment_instance.enroll_user_in_course.side_effect = fake_enrollment_api.enroll_user_in_course
        enrollment_instance.get_course_details.side_effect = fake_enrollment_api.get_course_details
        enterprise_catalog_instance = enterprise_catalog_client.return_value
        enterprise_catalog_instance.enterprise_contains_content_items.return_value = True

        self._login()
        user = UserFactory.create()
        unknown_email = FAKER.email()  # pylint: disable=no-member
        columns = [ManageLearnersForm.CsvColumns.EMAIL]
        data = [(user.email,), (unknown_email,)]
        course_id = "course-v1:EnterpriseX+Training+2017"
        course_mode = "professional"

        with mock.patch(
            'enterprise.models.EnrollmentApiClient.get_course_details',
            wraps=fake_enrollment_api.get_course_details,
        ):
            response = self._perform_request(columns, data, course=course_id, course_mode=course_mode)

        enrollment_instance.enroll_user_in_course.assert_called_once_with(
            user.username,
            course_id,
            course_mode,
            enterprise_uuid=str(self.enterprise_customer.uuid),
            force_enrollment=False
        )
        track_enrollment.assert_called_once_with('admin-enrollment', user.id, course_id)
        pending_user_message = (
            "The following learners do not have an account on Test platform. "
            "They have not been enrolled in {}. When these learners create an "
            "account, they will be enrolled automatically: {}"
        )
        self._assert_django_messages(response, {
            (messages.SUCCESS, "2 new learners were added to {}.".format(self.enterprise_customer.name)),
            (messages.SUCCESS, "1 learner was enrolled in {}.".format(course_id)),
            (messages.WARNING, pending_user_message.format(course_id, unknown_email)),
        })
        assert PendingEnterpriseCustomerUser.objects.all()[0].pendingenrollment_set.all()[0].course_id == course_id
        num_messages = len(mail.outbox)
        assert num_messages == 0
        mock_cea.objects.update_or_create.assert_called_once()

    @mock.patch("enterprise.utils.track_enrollment")
    @mock.patch("enterprise.api_client.lms.EnrollmentApiClient")
    @mock.patch("enterprise.models.EnterpriseCatalogApiClient")
    @mock.patch("enterprise.models.CourseEnrollmentAllowed")
    def test_post_link_and_enroll_no_notification(
            self,
            mock_cea,
            enterprise_catalog_client,
            enrollment_client,
            track_enrollment,
    ):
        """
        Test bulk upload with linking and enrolling
        """
        enrollment_instance = enrollment_client.return_value
        enrollment_instance.enroll_user_in_course.side_effect = fake_enrollment_api.enroll_user_in_course
        enrollment_instance.get_course_details.side_effect = fake_enrollment_api.get_course_details
        enterprise_catalog_instance = enterprise_catalog_client.return_value
        enterprise_catalog_instance.enterprise_contains_content_items.return_value = True

        self._login()
        user = UserFactory.create()
        unknown_email = FAKER.email()  # pylint: disable=no-member
        columns = [ManageLearnersForm.CsvColumns.EMAIL]
        data = [(user.email,), (unknown_email,)]
        course_id = "course-v1:EnterpriseX+Training+2017"
        course_mode = "professional"

        with mock.patch(
            'enterprise.models.EnrollmentApiClient.get_course_details',
            wraps=fake_enrollment_api.get_course_details,
        ):
            response = self._perform_request(columns, data, course=course_id, course_mode=course_mode, notify=False)

        enrollment_instance.enroll_user_in_course.assert_called_once_with(
            user.username,
            course_id,
            course_mode,
            enterprise_uuid=str(self.enterprise_customer.uuid),
            force_enrollment=False
        )
        track_enrollment.assert_called_once_with('admin-enrollment', user.id, course_id)
        pending_user_message = (
            "The following learners do not have an account on Test platform. They have not been enrolled in {}. "
            "When these learners create an account, they will be enrolled automatically: {}"
        )
        self._assert_django_messages(response, {
            (messages.SUCCESS, "2 new learners were added to {}.".format(self.enterprise_customer.name)),
            (messages.SUCCESS, "1 learner was enrolled in {}.".format(course_id)),
            (messages.WARNING, pending_user_message.format(course_id, unknown_email)),
        })
        assert PendingEnterpriseCustomerUser.objects.all()[0].pendingenrollment_set.all()[0].course_id == course_id
        num_messages = len(mail.outbox)
        assert num_messages == 0
        mock_cea.objects.update_or_create.assert_called_once()


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
        query_string = urlencode({"unlink_email": email})

        response = self.client.delete(self.view_url + "?" + query_string)

        assert response.status_code == 404
        expected_message = "Email {email} is not associated with Enterprise Customer {ec_name}".format(
            email=email, ec_name=self.enterprise_customer.name
        )
        assert response.content.decode("utf-8") == expected_message

    def test_delete_linked(self):
        self._login()

        email = FAKER.email()  # pylint: disable=no-member
        user = UserFactory(email=email)
        EnterpriseCustomerUserFactory(enterprise_customer=self.enterprise_customer, user_id=user.id)
        query_string = urlencode({"unlink_email": email})

        assert EnterpriseCustomerUser.objects.filter(user_id=user.id).count() == 1

        response = self.client.delete(self.view_url + "?" + query_string)

        assert response.status_code == 200
        assert json.loads(response.content.decode("utf-8")) == {}
        assert EnterpriseCustomerUser.objects.filter(user_id=user.id).count() == 0

    def test_delete_linked_pending(self):
        self._login()

        email = FAKER.email()  # pylint: disable=no-member
        query_string = urlencode({"unlink_email": email})

        PendingEnterpriseCustomerUserFactory(enterprise_customer=self.enterprise_customer, user_email=email)

        assert PendingEnterpriseCustomerUser.objects.filter(user_email=email).count() == 1

        response = self.client.delete(self.view_url + "?" + query_string)

        assert response.status_code == 200
        assert json.loads(response.content.decode("utf-8")) == {}
        assert PendingEnterpriseCustomerUser.objects.filter(user_email=email).count() == 0


class BaseTestEnterpriseCustomerTransmitCoursesView(BaseEnterpriseCustomerView):
    """
    Common functionality for EnterpriseCustomerTransmitCoursesView tests.
    """

    def setUp(self):
        """
        Test set up
        """
        super().setUp()
        self.transmit_courses_metadata_form = TransmitEnterpriseCoursesForm()
        self.view_url = reverse(
            'admin:' + enterprise_admin.utils.UrlNames.TRANSMIT_COURSES_METADATA,
            args=(self.enterprise_customer.uuid,)
        )
        self.context_parameters = EnterpriseCustomerTransmitCoursesView.ContextParameters


@ddt.ddt
@mark.django_db
@override_settings(ROOT_URLCONF='test_utils.admin_urls')
class TestEnterpriseCustomerTransmitCoursesViewGet(BaseTestEnterpriseCustomerTransmitCoursesView):
    """
    Tests for EnterpriseCustomerTransmitCoursesView GET endpoint.
    """

    def _test_get_response(self, response):
        """
        Test view GET response for common parts.
        """
        assert response.status_code == 200
        self._test_common_context(response.context)
        assert response.context[self.context_parameters.ENTERPRISE_CUSTOMER] == self.enterprise_customer
        assert not response.context[self.context_parameters.TRANSMIT_COURSES_METADATA_FORM].is_bound

    def test_get_not_logged_in(self):
        response = self.client.get(self.view_url)
        assert response.status_code == 302

    def test_get_links(self):
        self._login()

        response = self.client.get(self.view_url)
        self._test_get_response(response)


@ddt.ddt
@mark.django_db
@override_settings(ROOT_URLCONF='test_utils.admin_urls')
class TestEnterpriseCustomerTransmitCoursesViewPost(BaseTestEnterpriseCustomerTransmitCoursesView):
    """
    Tests for EnterpriseCustomerTransmitCoursesView POST endpoint.
    """

    def test_post_not_logged_in(self):
        response = self.client.post(self.view_url, data={})
        assert response.status_code == 302

    @mock.patch('enterprise.admin.views.call_command')
    def test_post_with_valid_enterprise_channel_worker(self, mock_call_command):
        self._login()
        response = self.client.post(
            self.view_url,
            data={'channel_worker_username': self.enterprise_channel_worker.username}
        )
        mock_call_command.assert_called_once_with(
            'transmit_content_metadata',
            '--catalog_user',
            self.enterprise_channel_worker.username,
            enterprise_customer=str(self.enterprise_customer.uuid),
        )
        self.assertRedirects(response, self.view_url)

    def test_post_validation_errors(self):
        self._login()
        invalid_channel_worker = 'invalid_channel_worker'
        response = self.client.post(
            self.view_url,
            data={'channel_worker_username': invalid_channel_worker}
        )
        assert response.status_code == 200
        self._test_common_context(response.context)
        transmit_courses_metadata_form = response.context[self.context_parameters.TRANSMIT_COURSES_METADATA_FORM]
        assert transmit_courses_metadata_form.is_bound
        assert transmit_courses_metadata_form.errors == {
            'channel_worker_username': [
                ValidationMessages.INVALID_CHANNEL_WORKER.format(
                    channel_worker_username=invalid_channel_worker
                )
            ]
        }
