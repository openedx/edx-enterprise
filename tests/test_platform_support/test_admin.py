"""
Enterprise support admin tests.
"""

import csv
import os
import tempfile
from unittest import mock

from django.contrib.messages import get_messages
from django.test import TestCase
from django.test.utils import override_settings
from django.urls import reverse

from enterprise.platform_support.admin.forms import CSVImportForm
from test_utils.factories import UserFactory

from .platform_stubs import CourseEnrollmentDoesNotExist

TEST_PASSWORD = 'test-password'
COURSE_ID = 'course-v1:edX+DemoX+Demo_Course'


@override_settings(ROOT_URLCONF='test_utils.admin_urls')
class EnrollmentAttributeOverrideViewTest(TestCase):
    """
    Tests for the enrollment attribute override admin view.

    ``CourseEnrollment`` and ``CourseEnrollmentAttribute`` are openedx-platform models
    with no tables in this repo's database, so the view's two ORM entry points are
    stubbed and the assertions are made against the calls it issues. Everything the view
    itself owns -- CSV parsing and validation, the per-row lookup, the upsert payload and
    the success/error messaging -- is still exercised end to end through the real URL.
    """

    def setUp(self):
        """ Test case setup """
        super().setUp()

        admin_user = UserFactory.create(is_staff=True, is_superuser=True, is_active=True)
        admin_user.set_password(TEST_PASSWORD)
        admin_user.save()
        self.view_url = reverse('admin:enterprise_override_attributes')
        self.client.login(username=admin_user.username, password=TEST_PASSWORD)

        self.users = [UserFactory.create() for _ in range(3)]
        self.csv_data = [
            [self.users[0].id, COURSE_ID, 'OP_4321'],
            [self.users[1].id, COURSE_ID, 'OP_8765'],
            [self.users[2].id, COURSE_ID, 'OP_2109'],
        ]
        self.csv_data_for_existing_attributes = [
            [self.users[0].id, COURSE_ID, 'OP_1234'],
            [self.users[1].id, COURSE_ID, 'OP_5678'],
            [self.users[2].id, COURSE_ID, 'OP_9012'],
        ]

        enrollment_patcher = mock.patch('enterprise.platform_support.admin.views.CourseEnrollment')
        self.mock_course_enrollment = enrollment_patcher.start()
        # ``form_valid`` names this in an ``except`` clause, so it has to be a real class.
        self.mock_course_enrollment.DoesNotExist = CourseEnrollmentDoesNotExist
        self.enrollments = {(str(user.id), COURSE_ID) for user in self.users}
        self.mock_course_enrollment.objects.get.side_effect = self._get_enrollment
        self.addCleanup(enrollment_patcher.stop)

        attribute_patcher = mock.patch('enterprise.platform_support.admin.views.CourseEnrollmentAttribute')
        self.mock_enrollment_attribute = attribute_patcher.start()
        self.addCleanup(attribute_patcher.stop)

    def _get_enrollment(self, user_id, course_id):
        """Stand in for ``CourseEnrollment.objects.get``, keyed on the enrollments set up above."""
        if (str(user_id), str(course_id)) not in self.enrollments:
            raise CourseEnrollmentDoesNotExist(user_id, course_id)
        return mock.MagicMock(name=f'enrollment-{user_id}', user_id=user_id, course_id=course_id)

    def create_csv(self, header=None, data=None):
        """Create csv"""
        header = header or ['lms_user_id', 'course_id', 'opportunity_id']
        data = data or self.csv_data
        tmp_csv_path = os.path.join(tempfile.gettempdir(), 'data.csv')
        with open(tmp_csv_path, 'w') as csv_file:
            csv_writer = csv.writer(csv_file)
            csv_writer.writerow(header)
            csv_writer.writerows(data)

        return tmp_csv_path

    def verify_enrollment_attributes(self, data=None):
        """
        Verify that every row in the csv produced the matching attribute upsert.
        """
        data = data or self.csv_data
        actual = [
            (
                call.kwargs['enrollment'].user_id,
                call.kwargs['enrollment'].course_id,
                call.kwargs['defaults']['value'],
            )
            for call in self.mock_enrollment_attribute.objects.update_or_create.call_args_list
        ]
        expected = [(str(user_id), course_id, opportunity_id) for user_id, course_id, opportunity_id in data]
        assert actual == expected

        for call in self.mock_enrollment_attribute.objects.update_or_create.call_args_list:
            assert call.kwargs['namespace'] == 'salesforce'
            assert call.kwargs['name'] == 'opportunity_id'

    def test_get(self):
        """
        Tests that HTTP GET is working as expected.
        """
        response = self.client.get(self.view_url)
        assert response.status_code == 200
        assert isinstance(response.context['form'], CSVImportForm)

    def test_post(self):
        """
        Tests that HTTP POST is working as expected when creating new attributes and updating.
        """
        csv_path = self.create_csv()
        with open(csv_path) as csv_file:
            post_data = {'csv_file': csv_file}
            response = self.client.post(self.view_url, data=post_data)
            assert response.status_code == 302
        self.verify_enrollment_attributes()

        # override existing
        self.mock_enrollment_attribute.objects.update_or_create.reset_mock()
        csv_path = self.create_csv(data=self.csv_data_for_existing_attributes)
        with open(csv_path) as csv_file:
            post_data = {'csv_file': csv_file}
            response = self.client.post(self.view_url, data=post_data)
            assert response.status_code == 302
        self.verify_enrollment_attributes(data=self.csv_data_for_existing_attributes)

    def test_post_with_no_csv(self):
        """
        Tests that HTTP POST without out csv file is working as expected.
        """
        response = self.client.post(self.view_url)
        assert response.context['form'].errors == {'csv_file': ['This field is required.']}

    def test_post_with_incorrect_csv_header(self):
        """
        Tests that HTTP POST with incorrect csv header is working as expected.
        """
        csv_path = self.create_csv(header=['a', 'b'])
        with open(csv_path) as csv_file:
            response = self.client.post(self.view_url, data={'csv_file': csv_file})
        assert response.context['form'].errors == {
            'csv_file': [
                'Expected a CSV file with [lms_user_id, course_id, opportunity_id] '
                'columns, but found [a, b] columns instead.'
            ]
        }

    def test_post_with_no_enrollment_error(self):
        """
        Tests that HTTP POST is working as expected when for some records there is no enrollment.
        """
        csv_data = self.csv_data + [[999, COURSE_ID, 'NOPE'], [1000, COURSE_ID, 'NONE']]
        csv_path = self.create_csv(data=csv_data)
        with open(csv_path) as csv_file:
            response = self.client.post(self.view_url, data={'csv_file': csv_file})
        assert response.status_code == 302
        messages = []
        for msg in get_messages(response.wsgi_request):
            messages.append(str(msg))
        assert messages == [
            'Successfully updated learner enrollment opportunity ids.',
            'Enrollment attributes were not updated for records at following line numbers '
            'in csv because no enrollment found for these records: 4, 5'
        ]
