"""
Tests for the xAPI models.
"""

import base64
import unittest

from pytest import mark

from test_utils import factories


@mark.django_db
class TestXAPILRSConfiguration(unittest.TestCase):
    """
    Tests for the ``XAPILRSConfiguration`` model.
    """

    def setUp(self):
        super().setUp()
        self.x_api_lrs_config = factories.XAPILRSConfigurationFactory()

    def test_string_representation(self):
        """
        Test the string representation of the model.
        """
        expected_string = '<XAPILRSConfiguration for Enterprise {enterprise_name}>'.format(
            enterprise_name=self.x_api_lrs_config.enterprise_customer.name,
        )
        assert expected_string == repr(self.x_api_lrs_config)

    def test_authorization_header(self):
        """
        Test the authorization header for the configuration.
        """
        expected_header = 'Basic {}'.format(
            base64.b64encode('{key}:{secret}'.format(
                key=self.x_api_lrs_config.key,
                secret=self.x_api_lrs_config.secret
            ).encode()).decode()
        )
        assert expected_header == self.x_api_lrs_config.authorization_header


@mark.django_db
class TestXAPILearnerDataTransmissionAudit(unittest.TestCase):
    """
    Tests for the ``XAPILearnerDataTransmissionAudit`` model.
    """

    def setUp(self):
        super().setUp()
        self.xapi_learner_transmission = factories.XAPILearnerDataTransmissionAuditFactory(
            user_id=factories.UserFactory().id,
            course_id='dummy'
        )

    def test_string_representation(self):
        """
        Test the string representation of the model.
        """
        expected_string = '<XAPILearnerDataTransmissionAudit {id} for enterprise enrollment {ece_id}, XAPI user ' \
                          '{user_id}, and course {course_id}>'.format(
                              id=self.xapi_learner_transmission.id,
                              ece_id=self.xapi_learner_transmission.enterprise_course_enrollment_id,
                              user_id=self.xapi_learner_transmission.user_id,
                              course_id=self.xapi_learner_transmission.course_id
                          )
        assert expected_string == str(self.xapi_learner_transmission)
