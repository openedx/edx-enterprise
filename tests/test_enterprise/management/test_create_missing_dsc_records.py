# -*- coding: utf-8 -*-
"""
Tests for the djagno management command `create_missing_dsc_records`.
"""
import csv
import os
import random
import tempfile

from pytest import mark

from django.core.management import call_command
from django.test import TestCase

from consent.models import DataSharingConsent
from test_utils.factories import (
    DataSharingConsentFactory,
    EnterpriseCourseEnrollmentFactory,
    EnterpriseCustomerFactory,
    EnterpriseCustomerUserFactory,
    UserFactory,
)

EXCEPTION = "DUMMY_TRACE_BACK"


@mark.django_db
class CreateEnterpriseCourseEnrollmentCommandTests(TestCase):
    """
    Test command `create_missing_dsc_records`.
    """
    command = 'create_missing_dsc_records'

    def setUp(self):
        super().setUp()

        self.course_ids = [
            'course-v1:edX+DemoX+Demo_Course',
            'course-v1:edX+Python+1T2019',
            'course-v1:edX+React+2T2019',
        ]
        self.enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
        )

        learners = []
        for __ in range(5):
            user = UserFactory.create(is_staff=False, is_active=True)
            learners.append(user)

        self.learners_data = []
        for learner in learners:
            course_id = random.choice(self.course_ids)
            self.learners_data.append(
                {
                    'ENTERPRISE_UUID': self.enterprise_customer.uuid,
                    'EMAIL': learner.email,
                    'USERNAME': learner.username,
                    'USER_ID': learner.id,
                    'COURSE_ID': course_id
                }
            )

            enterprise_customer_user = EnterpriseCustomerUserFactory(
                user_id=learner.id,
                enterprise_customer=self.enterprise_customer
            )

            EnterpriseCourseEnrollmentFactory(
                enterprise_customer_user=enterprise_customer_user,
                course_id=course_id,
            )

        self.existing_dsc_record_count = 2
        # create consent records for some learners with `granted` set to `False`
        # this is needed to verify that command is working for existing DSC records
        for learner in self.learners_data[:self.existing_dsc_record_count]:
            DataSharingConsentFactory(
                username=learner['USERNAME'],
                course_id=learner['COURSE_ID'],
                enterprise_customer=self.enterprise_customer,
                granted=False
            )

    def create_input_data_csv(self):
        """Create csv with required data"""
        tmp_csv_path = os.path.join(tempfile.gettempdir(), 'data.csv')

        with open(tmp_csv_path, 'w') as csv_file:
            csv_writer = csv.DictWriter(
                csv_file,
                fieldnames=['ENTERPRISE_UUID', 'EMAIL', 'USERNAME', 'USER_ID', 'COURSE_ID']
            )
            csv_writer.writeheader()
            for row in self.learners_data:
                csv_writer.writerow(row)

        return tmp_csv_path

    def test_create_missing_dsc_records(self):
        """
        Test that DSC records were created for desired learners.
        """
        csv_file_path = self.create_input_data_csv()

        assert DataSharingConsent.objects.count() == self.existing_dsc_record_count
        assert list(DataSharingConsent.objects.values_list('granted', flat=True)) == [False, False]

        call_command(
            self.command, '--data-csv={}'.format(csv_file_path)
        )

        for learner in self.learners_data:
            DataSharingConsent.objects.get(
                username=learner['USERNAME'],
                course_id=learner['COURSE_ID'],
                enterprise_customer__uuid=learner['ENTERPRISE_UUID'],
                granted=True
            )
