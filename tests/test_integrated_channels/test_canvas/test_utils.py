"""
Tests for utils in integrated_channels.canvas.
"""
import copy
import datetime
import random
import unittest
from unittest import mock

import pytest
from requests.models import Response

from integrated_channels.canvas.utils import CanvasUtil
from integrated_channels.exceptions import ClientError
from integrated_channels.utils import refresh_session_if_expired
from test_utils import factories

NOW = datetime.datetime(2017, 1, 2, 3, 4, 5, tzinfo=datetime.timezone.utc)
NOW_TIMESTAMP_FORMATTED = NOW.strftime('%F')


@pytest.mark.django_db
class TestCanvasUtils(unittest.TestCase):
    '''Tests CanvasUtils'''

    def setUp(self):
        super().setUp()
        self.account_id = random.randint(9223372036854775800, 9223372036854775807)
        self.course_id = "edx+111"
        self.url_base = "http://betatest.instructure.com"
        self.decrypted_client_id = "client_id"
        self.decrypted_client_secret = "client_secret"
        self.access_token = "access_token"
        self.refresh_token = "refresh_token"
        self.enterprise_config = factories.CanvasEnterpriseCustomerConfigurationFactory(
            decrypted_client_id=self.decrypted_client_id,
            decrypted_client_secret=self.decrypted_client_secret,
            canvas_account_id=self.account_id,
            canvas_base_url=self.url_base,
            refresh_token=self.refresh_token,
        )
        self.get_oauth_access_token = unittest.mock.MagicMock(
            name='_get_oauth_access_token',
            return_value=('atoken', 10000)
        )

    def test_find_root_canvas_account_found(self):
        """
        Tests interacting with {{canvas_url}}/api/v1/accounts to get root account
        """
        success_response = unittest.mock.Mock(spec=Response)
        success_response.status_code = 200
        success_response.json.return_value = [{'id': 1, 'parent_account_id': None},
                                              {'id': 2, 'parent_account_id': 1}, ]

        mock_session, _ = refresh_session_if_expired(self.get_oauth_access_token)
        mock_session.get = unittest.mock.MagicMock(
            name="_get",
            return_value=success_response
        )
        root_account = CanvasUtil.find_root_canvas_account(self.enterprise_config, mock_session)
        assert root_account['id'] == 1

    def test_find_root_canvas_account_not_found(self):
        success_response = unittest.mock.Mock(spec=Response)
        success_response.status_code = 200
        success_response.json.return_value = [{'id': 1, 'parent_account_id': 2},
                                              {'id': 2, 'parent_account_id': 1}, ]

        mock_session, _ = refresh_session_if_expired(self.get_oauth_access_token)
        mock_session.get = unittest.mock.MagicMock(
            name="_get",
            return_value=success_response
        )
        root_account = CanvasUtil.find_root_canvas_account(self.enterprise_config, mock_session)
        assert root_account is None

    def test_find_course_in_account_found(self):
        success_response = unittest.mock.Mock(spec=Response)
        success_response.status_code = 200
        a_course_1 = {
            "id": 125,
            "name": "Vernacular Architecture of Asia: Tradition, Modernity and Cultural Sustainability",
            "account_id": 1,
            "course_code": "Vernacular",
            "root_account_id": 1,
            "integration_id": "HKUx+HKU02.2x",
            "workflow_state": "unpublished",
        }
        a_course_2 = copy.deepcopy(a_course_1)
        a_course_2['integration_id'] = 'edx:test1'

        success_response.json.return_value = [a_course_1, a_course_2]

        mock_session, _ = refresh_session_if_expired(self.get_oauth_access_token)
        mock_session.get = unittest.mock.MagicMock(
            name="_get",
            return_value=success_response
        )

        canvas_account_id = 109
        edx_course_id = 'edx:test1'

        course = CanvasUtil.find_course_in_account(
            self.enterprise_config, mock_session, canvas_account_id, edx_course_id)
        assert course == a_course_2

    @mock.patch('integrated_channels.canvas.utils.CanvasUtil.find_course_in_account')
    @mock.patch('integrated_channels.canvas.utils.CanvasUtil.find_root_canvas_account')
    def test_find_no_root_account(self, mock_find_root_canvas_account, mock_find_course_in_account):
        mock_find_course_in_account.return_value = None
        mock_find_root_canvas_account.return_value = None
        mock_session, _ = refresh_session_if_expired(self.get_oauth_access_token)
        course = CanvasUtil.find_course_by_course_id(
            self.enterprise_config, mock_session, 666
        )
        assert course is None

    def test_find_course_in_account_fail(self):
        success_response = unittest.mock.Mock(spec=Response)
        success_response.status_code = 400
        success_response.json.return_value = {
            'errors': [{'message': 'failure 1'}]
        }

        mock_session, _ = refresh_session_if_expired(self.get_oauth_access_token)
        mock_session.get = unittest.mock.MagicMock(
            name="_get",
            return_value=success_response
        )

        canvas_account_id = 109
        edx_course_id = 'edx:test1'

        with self.assertRaises(ClientError):
            CanvasUtil.find_course_in_account(
                self.enterprise_config, mock_session, canvas_account_id, edx_course_id)

    def test_get_course_id_from_edx_course_id(self):
        success_response = unittest.mock.Mock(spec=Response)
        success_response.status_code = 200
        a_course_1 = {
            "id": 125,
            "integration_id": "HKUx+HKU02.2x",
            "workflow_state": "completed",
            "parent_account_id": None,
        }
        a_course_2 = copy.deepcopy(a_course_1)
        a_course_2['id'] = 129
        a_course_2['integration_id'] = 'edx:test1'
        a_course_2['parent_account_id'] = 125

        success_response.json.return_value = [a_course_1, a_course_2]

        mock_session, _ = refresh_session_if_expired(self.get_oauth_access_token)
        mock_session.get = unittest.mock.MagicMock(
            name="_get",
            return_value=success_response
        )

        assert CanvasUtil.get_course_id_from_edx_course_id(
            self.enterprise_config,
            mock_session,
            'edx:test1',
        ) == 129

        assert CanvasUtil.get_course_id_from_edx_course_id(
            self.enterprise_config,
            mock_session,
            'HKUx+HKU02.2x',
        ) == 125

        with self.assertRaises(ClientError):
            CanvasUtil.get_course_id_from_edx_course_id(
                self.enterprise_config,
                mock_session,
                'nonMatchingedXCourseId',
            )

    @mock.patch('integrated_channels.canvas.utils.CanvasUtil.find_course_in_account')
    @mock.patch('integrated_channels.canvas.utils.CanvasUtil.find_root_canvas_account')
    @mock.patch('integrated_channels.canvas.utils.LOGGER')
    def test_find_course_under_root_account_with_logging(
        self, mock_logger, mock_find_root_canvas_account, mock_find_course_in_account
    ):
        """Test that logging occurs when course is found under root account."""
        # Mock the course object
        mock_course = {'id': 123, 'integration_id': 'test-course-id', 'name': 'Test Course'}

        # Mock the root account
        mock_root_account = {'id': 1, 'parent_account_id': None}

        # Setup the mock calls:
        # First call returns None (not found in enterprise account)
        # Second call returns the course (found in root account)
        mock_find_course_in_account.side_effect = [None, mock_course]
        mock_find_root_canvas_account.return_value = mock_root_account

        mock_session, _ = refresh_session_if_expired(self.get_oauth_access_token)

        # Call the method
        result = CanvasUtil.find_course_by_course_id(self.enterprise_config, mock_session, 'test-course-id')

        # Verify the result
        assert result == mock_course

        # Verify the logging call was made with correct parameters
        mock_logger.info.assert_called_once_with(
            'Found course under root Canvas account',
            extra={
                'channel_name': 'canvas',
                'enterprise_customer_uuid': self.enterprise_config.enterprise_customer.uuid,
                'course_or_course_run_key': 'test-course-id',
            },
        )
