"""
Tests for clients in integrated_channels.blackboard.
"""
import base64
import json
import random
import unittest
from urllib.parse import urljoin

import pytest
import responses
from requests.models import Response

from integrated_channels.blackboard.apps import CHANNEL_NAME, VERBOSE_NAME
from integrated_channels.blackboard.client import BlackboardAPIClient
from integrated_channels.exceptions import ClientError
from test_utils.factories import BlackboardEnterpriseCustomerConfigurationFactory, BlackboardGlobalConfigurationFactory

COURSE_NOT_FOUND_RESPONSE = unittest.mock.Mock(spec=Response)
COURSE_NOT_FOUND_RESPONSE.text = 'NOT FOUND'
COURSE_NOT_FOUND_RESPONSE.json.return_value = {}
COURSE_NOT_FOUND_RESPONSE.status_code = 404

SUCCESSFUL_RESPONSE = unittest.mock.Mock(spec=Response)
SUCCESSFUL_RESPONSE.status_code = 200


@pytest.mark.django_db
class TestBlackboardApiClient(unittest.TestCase):
    """
    Test Blackboard API client methods.
    """

    # pylint: disable=protected-access
    def setUp(self):
        super().setUp()
        self.token = 'token'
        self.global_config = BlackboardGlobalConfigurationFactory()
        self.enterprise_config = BlackboardEnterpriseCustomerConfigurationFactory(
            decrypted_client_id='id',
            decrypted_client_secret='secret',
            blackboard_base_url='https://base.url',
            refresh_token=self.token,
        )
        self.user_email = 'testemail@example.com'
        self.course_id = 'course-edx+{}'.format(str(random.randint(100, 999)))
        self.course_subsection_id = 'subsection_id:{}'.format(str(random.randint(100, 999)))
        self.blackboard_course_id = random.randint(100, 999)
        self.blackboard_user_id = random.randint(100, 999)
        self.blackboard_grade_column_id = random.randint(100, 999)
        self.blackboard_grade_column_name = 'ayylmao'
        self.grade = round(random.uniform(0, 1), 2)
        self.learner_data_payload = '{{"courseID": "{}", "grade": {}}}'.format(self.course_id, self.grade)

        SUCCESSFUL_RESPONSE.json.return_value = {
            'score': self.grade * 100
        }

    def _create_new_mock_client(self):
        """Test client instance with oauth token filled in"""
        client = BlackboardAPIClient(self.enterprise_config)
        client._get_oauth_access_token = unittest.mock.MagicMock(
            name='_get_oauth_access_token',
            return_value=(self.token, 10000)
        )
        return client

    def test_client_pulls_auth_creds_from_global_if_not_found(self):
        enterprise_config = BlackboardEnterpriseCustomerConfigurationFactory(
            decrypted_client_id='',
            decrypted_client_secret='',
        )
        client = BlackboardAPIClient(enterprise_config)
        auth_header = client._create_auth_header()
        global_secret = self.global_config.app_secret
        global_key = self.global_config.app_key
        assert auth_header == f"Basic {base64.b64encode(f'{global_key}:{global_secret}'.encode('utf-8')).decode()}"

    def test_oauth_absent_refresh_token_fails(self):
        enterprise_config = BlackboardEnterpriseCustomerConfigurationFactory(
            decrypted_client_id='id2',
            decrypted_client_secret='secret',
            blackboard_base_url='https://base.url.2',
            refresh_token='',
        )
        client = BlackboardAPIClient(enterprise_config)
        with self.assertRaises(ClientError):
            client._get_oauth_access_token()
        assert enterprise_config.refresh_token == ''

    def test_oauth_valid_refresh_token_replaces_existing(self):
        """
        Our db already contains the initial refresh_token
        a valid refresh_token is used to replace it, and access_token is obtained
        """
        enterprise_config = BlackboardEnterpriseCustomerConfigurationFactory(
            decrypted_client_id='id3',
            decrypted_client_secret='secret',
            blackboard_base_url='https://base.url.3',
            refresh_token='a-token',
        )
        client = BlackboardAPIClient(enterprise_config)
        auth_token_url = urljoin(
            enterprise_config.blackboard_base_url,
            client.config.oauth_token_auth_path
        )
        with responses.RequestsMock() as rsps:
            rsps.add(
                responses.POST,
                auth_token_url,
                json={
                    'refresh_token': 'new-refresh-token',
                    'token_type': 'refresh_token',
                    'expires_in': '2020-02-01',
                    'access_token': 'a0token',
                },
                status=200
            )
            assert enterprise_config.refresh_token == 'a-token'
            access_token, expires_in = client._get_oauth_access_token()
            assert access_token == 'a0token'
            assert expires_in == '2020-02-01'

            # refresh_token update won't be visible until we fetch updated value
            assert enterprise_config.refresh_token == 'a-token'
            # because the refresh token can be updated within the boundary of
            # the _get_oauth_access_token in a transaction, we won't detect
            # the new value until we refresh_from_db
            # the actual usage of the code only uses refresh_token
            # within the atomic block so we are not violating usage checks
            # with this being in this test
            enterprise_config.refresh_from_db()
            assert enterprise_config.refresh_token == 'new-refresh-token'

    def test_client_has_valid_configs(self):
        api_client = BlackboardAPIClient(self.enterprise_config)
        assert api_client.config is not None
        assert api_client.config.name == CHANNEL_NAME
        assert api_client.config.verbose_name == VERBOSE_NAME
        assert api_client.enterprise_configuration == self.enterprise_config

    def test_get_blackboard_course_404s(self):
        """Test that we properly handle failure cases when retrieving the blackboard course ID for a learner."""
        client = self._create_new_mock_client()

        # Create the session so that we can mock the requests made in the course completion transmission flow
        client._create_session()

        response_404 = unittest.mock.Mock(spec=Response)
        response_404.status_code = 404
        response_404.text = "{'error': 'No course found.'}"

        client.session.get = unittest.mock.MagicMock(
            name="_get",
            return_value=response_404
        )

        with pytest.raises(ClientError) as client_error:
            client._resolve_blackboard_course_id(self.course_id)

        assert client_error.value.message == response_404.text
        assert client_error.value.status_code == response_404.status_code

    def test_get_blackboard_course_success(self):
        """
        Test that we properly return the BB course ID matching the external ID, even if multiple courses are
        returned.
        """
        wrong_course_external_id = 'external_id_2'
        wrong_bb_course_id = 2

        client = self._create_new_mock_client()

        # Create the session so that we can mock the requests made in the course completion transmission flow
        client._create_session()

        success_response = unittest.mock.Mock(spec=Response)
        success_response.status_code = 200
        success_response.json.return_value = {
            'results': [
                {'externalId': self.course_id, 'id': self.blackboard_course_id},
                {'externalId': wrong_course_external_id, 'id': wrong_bb_course_id}
            ]
        }

        client.session.get = unittest.mock.MagicMock(
            name="_get",
            return_value=success_response
        )

        assert client._resolve_blackboard_course_id(self.course_id) == self.blackboard_course_id

    def test_get_blackboard_user_404s(self):
        """Test that we properly handle failure cases when retrieving the blackboard user ID."""
        client = self._create_new_mock_client()

        # Create the session so that we can mock the requests made in the course completion transmission flow
        client._create_session()

        response_404 = unittest.mock.Mock(spec=Response)
        response_404.status_code = 404
        response_404.text = "{'error': 'No user found.'}"

        client.session.get = unittest.mock.MagicMock(
            name="_get",
            return_value=response_404
        )

        with pytest.raises(ClientError) as client_error:
            client._get_bb_user_id_from_enrollments(self.user_email, self.blackboard_course_id)

        assert client_error.value.message == response_404.text
        assert client_error.value.status_code == response_404.status_code

    def test_get_blackboard_user_success(self):
        """Test that we properly return the user ID given a successful response from Blackboard."""
        wrong_user_email = 'ayy@lmao.com'
        wrong_bb_user_id = 111

        client = self._create_new_mock_client()

        # Create the session so that we can mock the requests made in the course completion transmission flow
        client._create_session()

        success_response = unittest.mock.Mock(spec=Response)
        success_response.status_code = 200
        success_response.json.return_value = {
            'results': [
                {
                    'courseRoleId': 'Student',
                    'user': {'contact': {'email': wrong_user_email}},
                    'userId': wrong_bb_user_id
                },
                {
                    'courseRoleId': 'Student',
                    'user': {'contact': {'email': self.user_email}},
                    'userId': self.blackboard_user_id
                }
            ]
        }

        client.session.get = unittest.mock.MagicMock(
            name="_get",
            return_value=success_response
        )

        assert client._get_bb_user_id_from_enrollments(
            self.user_email,
            self.blackboard_course_id
        ) == self.blackboard_user_id

    def test_retrieve_blackboard_grade_column_fails(self):
        """Test that we properly handle an error response from Blackboard when requesting course grade columns."""
        client = self._create_new_mock_client()

        # Create the session so that we can mock the requests made in the course completion transmission flow
        client._create_session()

        response_500 = unittest.mock.Mock(spec=Response)
        response_500.status_code = 500
        response_500.text = "{'error': 'Something went wrong'}"

        client.session.get = unittest.mock.MagicMock(
            name="_get",
            return_value=response_500
        )

        with pytest.raises(ClientError) as client_error:
            client._get_or_create_integrated_grade_column(
                self.blackboard_course_id,
                self.blackboard_grade_column_name,
                self.course_subsection_id,
                points_possible=100
            )

        assert client_error.value.message == response_500.text
        assert client_error.value.status_code == response_500.status_code

    def test_create_blackboard_grade_column_fails(self):
        """
        Test that when successfully failing (lol) to not find an existing grade column, we properly handle failure
        cases when posting a new Blackboard grade column.
        """
        client = self._create_new_mock_client()

        wrong_bb_user_id = 1
        wrong_external_id = 'ayylmao'

        # Create the session so that we can mock the requests made in the course completion transmission flow
        client._create_session()

        success_get_response = unittest.mock.Mock(spec=Response)
        success_get_response.status_code = 200
        success_get_response.json.return_value = {
            'results': [
                {
                    'externalId': wrong_external_id,
                    'id': wrong_bb_user_id
                },
            ]
        }
        client.session.get = unittest.mock.MagicMock(
            name="_get",
            return_value=success_get_response
        )

        failed_post_response = unittest.mock.Mock(spec=Response)
        failed_post_response.status_code = 500
        failed_post_response.text = "{'error': 'Something went wrong'}"
        client.session.post = unittest.mock.MagicMock(
            name="_post",
            return_value=failed_post_response
        )

        with pytest.raises(ClientError) as client_error:
            client._get_or_create_integrated_grade_column(
                self.blackboard_course_id,
                self.blackboard_grade_column_name,
                self.course_subsection_id,
                points_possible=100
            )

        assert client_error.value.message == failed_post_response.text
        assert client_error.value.status_code == failed_post_response.status_code

    def test_retrieve_existing_blackboard_grade_column(self):
        """Test that we properly return an existing Blackboard grade column."""
        client = self._create_new_mock_client()

        # Create the session so that we can mock the requests made in the course completion transmission flow
        client._create_session()

        success_get_response = unittest.mock.Mock(spec=Response)
        success_get_response.status_code = 200
        success_get_response.json.return_value = {
            'results': [
                {
                    'externalId': self.course_subsection_id,
                    'id': self.blackboard_grade_column_id
                },
            ]
        }

        client.session.get = unittest.mock.MagicMock(
            name="_get",
            return_value=success_get_response
        )

        result = client._get_or_create_integrated_grade_column(
            self.blackboard_course_id,
            self.blackboard_grade_column_name,
            self.course_subsection_id,
            points_possible=100
        )
        assert result == self.blackboard_grade_column_id

    def test_retrieve_created_blackboard_grade_column(self):
        """Test that we properly return after successfully posting a new grade column to Blackboard."""
        client = self._create_new_mock_client()

        wrong_bb_user_id = 1
        wrong_external_id = 'ayylmao'

        # Create the session so that we can mock the requests made in the course completion transmission flow
        client._create_session()

        success_get_response = unittest.mock.Mock(spec=Response)
        success_get_response.status_code = 200
        success_get_response.json.return_value = {
            'results': [
                {
                    'externalId': wrong_external_id,
                    'id': wrong_bb_user_id
                },
            ]
        }
        client.session.get = unittest.mock.MagicMock(
            name="_get",
            return_value=success_get_response
        )

        success_post_response = unittest.mock.Mock(spec=Response)
        success_post_response.status_code = 200
        success_post_response.json.return_value = {
            'id': self.blackboard_grade_column_id
        }
        client.session.post = unittest.mock.MagicMock(
            name="_post",
            return_value=success_post_response
        )

        result = client._get_or_create_integrated_grade_column(
            self.blackboard_course_id,
            self.blackboard_grade_column_name,
            self.course_subsection_id,
            points_possible=100
        )

        assert result == self.blackboard_grade_column_id

    def test_submitting_grade_fails(self):
        """Test that we properly handle failure cases when submitting grade scores to Blackboard."""
        client = self._create_new_mock_client()

        # Create the session so that we can mock the requests made in the course completion transmission flow
        client._create_session()

        failed_patch_response = unittest.mock.Mock(spec=Response)
        failed_patch_response.status_code = 500
        failed_patch_response.text = "{'error': 'Something went wrong'}"
        client.session.patch = unittest.mock.MagicMock(
            name="_patch",
            return_value=failed_patch_response
        )

        with pytest.raises(ClientError) as client_error:
            client._submit_grade_to_blackboard(
                100,
                self.blackboard_course_id,
                self.blackboard_grade_column_id,
                self.blackboard_user_id
            )

        assert client_error.value.message == failed_patch_response.text
        assert client_error.value.status_code == failed_patch_response.status_code

    def test_blackboard_grade_submission_success(self):
        """Test that we properly return responses when successfully posting grade scores to Blackboard."""
        client = self._create_new_mock_client()

        # Create the session so that we can mock the requests made in the course completion transmission flow
        client._create_session()

        grade = 100

        success_patch_response = unittest.mock.Mock(spec=Response)
        success_patch_response.status_code = 200
        success_patch_response.json.return_value = {'score': grade}
        client.session.patch = unittest.mock.MagicMock(
            name="_patch",
            return_value=success_patch_response
        )

        result = client._submit_grade_to_blackboard(
            grade,
            self.blackboard_course_id,
            self.blackboard_grade_column_id,
            self.blackboard_user_id
        )

        assert result.status_code == success_patch_response.status_code
        assert result.json() == success_patch_response.json.return_value

    def test_course_completion_with_no_course(self):
        """Test that we properly raise exceptions if the client receives a 404 from Blackboard"""
        client = self._create_new_mock_client()

        # Create the session so that we can mock the requests made in the course completion transmission flow
        client._create_session()
        client.session.get = unittest.mock.MagicMock(
            name='_get',
            return_value=COURSE_NOT_FOUND_RESPONSE
        )
        with pytest.raises(ClientError) as client_error:
            client.create_course_completion(self.user_email, self.learner_data_payload)

        assert client_error.value.message == COURSE_NOT_FOUND_RESPONSE.text
        assert client_error.value.status_code == COURSE_NOT_FOUND_RESPONSE.status_code == 404

    def test_create_content_metadata_success(self):
        client = self._create_new_mock_client()
        course_id = 'a-course-id'
        bb_course_id = 'test bb course id'
        metadata_content = {
            'externalId': course_id,
            'course_metadata': {'courseId': 'test course ID'},
            'course_content_metadata': 'test course content metadata ',
            'course_child_content_metadata': 'test course child content metadata',
        }
        serialized_data = json.dumps(metadata_content).encode('utf-8')

        success_response = unittest.mock.Mock(spec=Response)
        success_response.status_code = 200
        success_response.json.return_value = {'id': bb_course_id}

        client._create_session()
        client._post = unittest.mock.MagicMock(
            name="_post",
            return_value=success_response
        )

        status_code, status_text = client.create_content_metadata(serialized_data)

        assert status_code == success_response.status_code
        assert status_text == 'Successfully created Blackboard integration course={bb_course_id} with' \
                              ' integration content={bb_course_id}'.format(bb_course_id=bb_course_id)

        expected_url = client.generate_create_course_content_child_url(bb_course_id, bb_course_id)
        client._post.assert_called_with(
            expected_url, metadata_content.get('course_child_content_metadata')
        )

    def test_update_content_metadata_success(self):
        client = self._create_new_mock_client()
        content_metadata = {
            'externalId': 'a-course-id',
            'course_metadata': 'test course metadata'
        }
        serialized_data = json.dumps(content_metadata).encode('utf-8')
        success_response = unittest.mock.Mock(spec=Response)
        success_response.status_code = 200
        success_response.text = 'hooray'
        success_response.json.return_value = {'id': self.blackboard_course_id}

        course_content_success_response = unittest.mock.Mock(spec=Response)
        course_content_success_response.status_code = 200
        course_content_success_response.json.return_value = {'results': [{'title': 'edX Integration'}]}

        client._create_session()
        client._patch = unittest.mock.MagicMock(
            name='_patch',
            return_value=success_response
        )
        client._delete = unittest.mock.MagicMock(
            name='_delete',
            return_value=success_response
        )
        client._post = unittest.mock.MagicMock(
            name='_post',
            return_value=success_response
        )
        client._get = unittest.mock.MagicMock(
            name='_get',
            return_value=course_content_success_response
        )
        client._resolve_blackboard_course_id = unittest.mock.MagicMock(
            name='_resolve_blackboard_course_id',
            return_value='a-course-id'
        )

        status_code, status_text = client.update_content_metadata(serialized_data)

        assert status_code == 200
        assert status_text == 'hooray'

        expected_url = client.generate_course_update_url('a-course-id')
        client._patch.assert_called_with(
            expected_url,
            content_metadata.get('course_metadata')
        )
        assert client._resolve_blackboard_course_id.CalledProcessError

    def test_delete_no_course_found(self):
        client = self._create_new_mock_client()
        serialized_data = json.dumps({
            'externalId': 'a-course-id'
        }).encode('utf-8')

        client._create_session()
        client._delete = unittest.mock.MagicMock(name='_delete')
        client._resolve_blackboard_course_id = unittest.mock.MagicMock(
            name='_resolve_blackboard_course_id',
            return_value=None
        )

        status_code, status_text = client.delete_content_metadata(serialized_data)
        assert client._resolve_blackboard_course_id.CalledProcessError
        assert not client._delete.called
        assert status_code == 200
        assert status_text == 'Course:a-course-id already removed.'

    def test_delete_content_metadata(self):
        client = self._create_new_mock_client()
        serialized_data = json.dumps({
            'externalId': 'a-course-id'
        }).encode('utf-8')
        success_response = unittest.mock.Mock(spec=Response)
        success_response.status_code = 202
        success_response.text = ''
        success_response.json.return_value = {}

        client._create_session()
        client._delete = unittest.mock.MagicMock(
            name='_delete',
            return_value=success_response
        )
        client._resolve_blackboard_course_id = unittest.mock.MagicMock(
            name='_resolve_blackboard_course_id',
            return_value='a-course-id'
        )

        status_code, status_text = client.delete_content_metadata(serialized_data)

        assert status_code == 202
        assert status_text == ''

        expected_url = client.generate_course_update_url('a-course-id')
        client._delete.assert_called_with(expected_url)
        assert client._resolve_blackboard_course_id.CalledProcessError

    def test_client_behavior_on_successful_learner_data_transmission(self):
        """
        Test that given successful requests for Blackboard learner data,
        the client makes the appropriate _patch call to update a user's grade
        """
        client = self._create_new_mock_client()

        # Mock the course ID request
        client._resolve_blackboard_course_id = unittest.mock.MagicMock(
            name='_resolve_blackboard_course_id',
            return_value=self.course_id,
        )

        # Mock the enrollments request
        client._get_bb_user_id_from_enrollments = unittest.mock.MagicMock(
            name='_get_bb_user_id_from_enrollments',
            return_value=self.blackboard_user_id
        )

        # Mock the gradebook/column request
        client._get_or_create_integrated_grade_column = unittest.mock.MagicMock(
            name='_get_or_create_integrated_grade_column',
            return_value=self.blackboard_grade_column_id
        )

        # Create the session so that we can mock the requests made in the course completion transmission flow
        client._create_session()
        client.session.patch = unittest.mock.MagicMock(
            name='_patch',
            return_value=SUCCESSFUL_RESPONSE
        )

        expected_success_body = 'Successfully posted grade of {grade} to ' \
                                'course:{course_id} for user:{user_email}.'.format(
                                    grade=self.grade * 100,
                                    course_id=self.course_id,
                                    user_email=self.user_email,
                                )

        assert client.create_course_completion(
            self.user_email,
            self.learner_data_payload
        ) == (SUCCESSFUL_RESPONSE.status_code, expected_success_body)

    def test_content_customization_failure(self):
        """
        Test that when content customization for either update and create, fails, we
        properly log and handle the clean up.
        """
        client = self._create_new_mock_client()
        client._create_session()
        content_metadata = {
            'course_content_metadata': {'test': 'a-course-id'}
        }

        successful_response = unittest.mock.Mock(spec=Response)
        successful_response.status_code = 200
        successful_response.text = 'course deleted'
        successful_response.json.return_value = {}

        client.delete_course_from_blackboard = unittest.mock.MagicMock(
            name='delete blackboard course',
            return_value=successful_response
        )

        content_url = client.generate_create_course_content_url(self.blackboard_course_id)
        with responses.RequestsMock() as rsps:
            # Stub the content creation request to fail
            rsps.add(
                responses.POST,
                content_url,
                json={'error': 'something went wrong'},
                status=400
            )

            with pytest.raises(ClientError) as client_error:
                client.create_integration_content_for_course(self.blackboard_course_id, content_metadata)
                assert client_error.value.message == 'Something went wrong while creating course content object on ' \
                                                     'Blackboard. Could not retrieve content ID and received error' \
                                                     ' response={}. Deleted course with response (status_code={},' \
                                                     ' body={})'.format(
                                                         client_error.message,
                                                         successful_response.status_code,
                                                         successful_response.text
                                                     )

                # Assert that the client attempted to delete the course.
                client.delete_course_from_blackboard.assert_called_with(self.blackboard_course_id)

            with pytest.raises(ClientError) as client_error:
                client.update_integration_content_for_course(self.blackboard_course_id, content_metadata)
                assert client_error.value.message == 'Something went wrong while creating course content object on ' \
                                                     'Blackboard. Could not retrieve content ID and received error ' \
                                                     'response={}.'.format(
                                                         client_error.message
                                                     )

                # Assert that the client made no attempt to delete anything.
                assert not client.delete_course_from_blackboard.called
                assert not client.delete_course_content_from_blackboard.called

    def test_content_child_customization_failure(self):
        """
        Test that when content child customization for either update and create, fails, we
        properly log and handle the clean up.
        """
        client = self._create_new_mock_client()
        client._create_session()
        bb_content_id = 'test_bb_content_id'
        content_metadata = {
            'course_content_metadata': {'test': 'a-course-id'}
        }

        successful_response = unittest.mock.Mock(spec=Response)
        successful_response.status_code = 200
        successful_response.text = 'delete request successful'
        successful_response.json.return_value = {}

        client.delete_course_from_blackboard = unittest.mock.MagicMock(
            name='delete blackboard course',
            return_value=successful_response
        )

        client.delete_course_content_from_blackboard = unittest.mock.MagicMock(
            name='delete blackboard content',
            return_value=successful_response
        )

        content_url = client.generate_create_course_content_url(self.blackboard_course_id)
        content_child_url = client.generate_create_course_content_child_url(self.blackboard_course_id, bb_content_id)
        with responses.RequestsMock() as rsps:
            # Stub the content request to be successful
            rsps.add(
                responses.POST,
                content_url,
                json={'id': bb_content_id},
                status=200
            )

            # Stub the content child request to fail
            rsps.add(
                responses.POST,
                content_child_url,
                json={'error': 'something went wrong'},
                status=400
            )

            with pytest.raises(ClientError) as client_error:
                client.create_integration_content_for_course(self.blackboard_course_id, content_metadata)
                assert client_error.value.message == 'Something went wrong while creating course content object on ' \
                                                     'Blackboard. Could not retrieve content child ID and received ' \
                                                     'error response={}. Deleted associated course and content with ' \
                                                     'response (status_code={}, body={})'.format(
                                                         client_error.message,
                                                         successful_response.status_code,
                                                         successful_response.text
                                                     )

                # Assert that the client attempted to delete the entire course
                client.delete_course_from_blackboard.assert_called_with(self.blackboard_course_id, bb_content_id)

            with pytest.raises(ClientError) as client_error:
                client.update_integration_content_for_course(self.blackboard_course_id, content_metadata)
                assert client_error.value.message == 'Something went wrong while creating course content object on' \
                                                     ' Blackboard. Could not retrieve content ID and received error ' \
                                                     'response={}.'.format(
                                                         client_error.message
                                                     )

                # Assert that the client attempted to delete the content child and NOT the whole course.
                client.delete_course_content_from_blackboard.assert_called_with(
                    self.blackboard_course_id,
                    bb_content_id
                )
                assert not client.delete_course_from_blackboard.called

    def test_client_assignment_update_on_find(self):
        """
        Test that the _get_or_create_integrated_grade_column method properly updates courses
        with the correct `include_in_calculations` settings as it searches for them
        """
        client = self._create_new_mock_client()
        client._create_session()

        blackboard_search_response = {
            'results': [{
                'id': self.blackboard_grade_column_id,
                'externalId': self.course_id,
                'name': self.blackboard_grade_column_name,
                'description': "edX learner's grade.",
                'created': '2021-07-16T19:46:29.698Z',
                'score': {'possible': 100.0},
                'availability': {'available': 'Yes'},
                'includeInCalculations': True,
            }],
        }

        with responses.RequestsMock() as rsps:
            # Requests mock will iteratively return registered responses on subsequent calls
            rsps.add(
                responses.GET,
                client.generate_gradebook_url(self.blackboard_course_id),
                json=blackboard_search_response
            )
            rsps.add(
                responses.PATCH,
                client.generate_update_grade_column_url(self.blackboard_course_id, self.blackboard_grade_column_id),
                json={"includeInCalculations": False}
            )

            # find the grade column on the second page of results
            column_id = client._get_or_create_integrated_grade_column(
                self.blackboard_course_id,
                self.blackboard_grade_column_name,
                self.course_id,
                include_in_calculations=False
            )

        assert column_id == self.blackboard_grade_column_id

    def test_client_finds_assignment_on_second_results_page(self):
        """
        Test that the _get_or_create_integrated_grade_column method properly traverses over paginated results from
        Blackboard and correctly finds a gradebook column on a follow up page of results.
        """
        client = self._create_new_mock_client()
        client._create_session()

        blackboard_page_one_response = {
            'results': [{
                'id': 'bad ID',
                'name': 'Weighted Total',
                'description': 'description',
                'score': {'possible': 0.0},
                'availability': {'available': 'Yes'},
                'grading': {'type': 'Calculated'}
            }],
            'paging': {
                'nextPage': '/learn/api/public/v1/courses/{}/gradebook/columns?offset=1'.format(
                    self.blackboard_course_id
                )
            },
        }
        blackboard_page_two_response = {
            'results': [{
                'id': self.blackboard_grade_column_id,
                'externalId': self.course_id,
                'name': self.blackboard_grade_column_name,
                'description': "edX learner's grade.",
                'created': '2021-07-16T19:46:29.698Z',
                'score': {'possible': 100.0},
                'availability': {'available': 'Yes'}
            }],
            'paging': {
                'nextPage': '/learn/api/public/v1/courses/{}/gradebook/columns?offset=2'.format(
                    self.blackboard_course_id
                )
            },
        }

        with responses.RequestsMock() as rsps:
            # Requests mock will iteratively return registered responses on subsequent calls
            rsps.add(
                responses.GET,
                client.generate_gradebook_url(self.blackboard_course_id),
                json=blackboard_page_one_response
            )
            rsps.add(
                responses.GET,
                client.generate_gradebook_url(self.blackboard_course_id),
                json=blackboard_page_two_response
            )

            # find the grade column on the second page of results
            column_id = client._get_or_create_integrated_grade_column(
                self.blackboard_course_id,
                self.blackboard_grade_column_name,
                self.course_id
            )

        assert column_id == self.blackboard_grade_column_id

    def test_pagination_properly_handles_column_not_found(self):
        """
        Test that _get_or_create_integrated_grade_column will properly exhaust all pages of results before determining
        that a gradebook column does not exist.
        """
        client = self._create_new_mock_client()
        client._create_session()

        blackboard_page_one_response = {
            'results': [{
                'id': 'bad ID',
                'name': 'Weighted Total',
                'description': 'description',
                'score': {'possible': 0.0},
                'availability': {'available': 'Yes'},
                'grading': {'type': 'Calculated'}
            }],
            'paging': {
                'nextPage': '/learn/api/public/v1/courses/{}/gradebook/columns?offset=1'.format(
                    self.blackboard_course_id
                )
            },
        }
        blackboard_page_two_response = {
            'results': [{
                'id': 'bad ID 2',
                'name': 'Final Grade',
                'score': {'possible': 0.0},
                'availability': {'available': 'Yes'},
                'grading': {'type': 'Calculated'}
            }],
        }

        with responses.RequestsMock() as rsps:
            # Requests mock will iteratively return registered responses on subsequent calls
            rsps.add(
                responses.GET,
                client.generate_gradebook_url(self.blackboard_course_id),
                json=blackboard_page_one_response
            )
            rsps.add(
                responses.GET,
                client.generate_gradebook_url(self.blackboard_course_id),
                json=blackboard_page_two_response
            )
            rsps.add(
                responses.POST,
                client.generate_create_grade_column_url(self.blackboard_course_id),
                json={'id': self.blackboard_grade_column_id}
            )

            # traverse over all pages, post a new column if column isn't found
            column_id = client._get_or_create_integrated_grade_column(
                self.blackboard_course_id,
                self.blackboard_grade_column_name,
                self.course_id
            )

        assert column_id == self.blackboard_grade_column_id
    # pylint: enable=protected-access
