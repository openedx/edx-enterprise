"""
Comprehensive expert-level tests for the BrazeAPIClient in edx-enterprise.
"""
from unittest.mock import Mock, patch

import pytest
from requests.exceptions import HTTPError, RequestException, Timeout

from enterprise.api_client.braze_client import DEFAULT_TIMEOUT, MAX_RECIPIENTS_PER_REQUEST
from enterprise.api_client.braze_client import BrazeCampaignAPIClient as BrazeAPIClient
from enterprise.api_client.braze_client import BrazeClientError, BrazeValidationError

# ============================================================================
# Initialization Tests
# ============================================================================

class TestBrazeClientInitialization:
    """Test cases for BrazeAPIClient initialization."""

    def test_init_with_valid_parameters(self):
        """Test successful initialization with valid parameters."""
        client = BrazeAPIClient('test-api-key', 'https://api.braze.com')
        assert client.api_key == 'test-api-key'
        assert client.api_url == 'https://api.braze.com'
        assert client.timeout == DEFAULT_TIMEOUT
        assert client.session is not None

    def test_init_strips_trailing_slash_from_url(self):
        """Test that trailing slash is removed from API URL."""
        client = BrazeAPIClient('test-key', 'https://api.braze.com/')
        assert client.api_url == 'https://api.braze.com'

    def test_init_with_custom_timeout(self):
        """Test initialization with custom timeout."""
        client = BrazeAPIClient('key', 'url', timeout=60)
        assert client.timeout == 60

    def test_init_with_custom_max_retries(self):
        """Test initialization with custom max retries."""
        client = BrazeAPIClient('key', 'url', max_retries=5)
        assert client.session is not None

    def test_init_raises_error_for_empty_api_key(self):
        """Test that initialization raises error for empty API key."""
        with pytest.raises(BrazeValidationError, match="api_key must be a non-empty string"):
            BrazeAPIClient('', 'https://api.braze.com')

    def test_init_raises_error_for_none_api_key(self):
        """Test that initialization raises error for None API key."""
        with pytest.raises(BrazeValidationError, match="api_key must be a non-empty string"):
            BrazeAPIClient(None, 'https://api.braze.com')

    def test_init_raises_error_for_invalid_api_key_type(self):
        """Test that initialization raises error for non-string API key."""
        with pytest.raises(BrazeValidationError, match="api_key must be a non-empty string"):
            BrazeAPIClient(12345, 'https://api.braze.com')

    def test_init_raises_error_for_empty_api_url(self):
        """Test that initialization raises error for empty API URL."""
        with pytest.raises(BrazeValidationError, match="api_url must be a non-empty string"):
            BrazeAPIClient('test-key', '')

    def test_init_raises_error_for_none_api_url(self):
        """Test that initialization raises error for None API URL."""
        with pytest.raises(BrazeValidationError, match="api_url must be a non-empty string"):
            BrazeAPIClient('test-key', None)


# ============================================================================
# build_recipient Tests
# ============================================================================

class TestBuildRecipient:
    """Test cases for build_recipient method."""

    def test_build_recipient_basic(self):
        """Test build_recipient with minimal arguments."""
        client = BrazeAPIClient('key', 'url')
        result = client.build_recipient('user1')
        assert result['external_user_id'] == 'user1'
        assert result['send_to_existing_only'] is False
        assert 'attributes' not in result

    def test_build_recipient_with_email(self):
        """Test build_recipient with email."""
        client = BrazeAPIClient('key', 'url')
        result = client.build_recipient('user1', email='test@example.com')
        assert result['external_user_id'] == 'user1'
        assert result['attributes']['email'] == 'test@example.com'

    def test_build_recipient_with_email_and_attributes(self):
        """Test build_recipient with email and attributes."""
        client = BrazeAPIClient('key', 'url')
        attrs = {'foo': 'bar', 'custom_field': 'value'}
        result = client.build_recipient('user2', email='test@example.com', attributes=attrs)
        assert result['attributes']['email'] == 'test@example.com'
        assert result['attributes']['foo'] == 'bar'
        assert result['attributes']['custom_field'] == 'value'

    def test_build_recipient_with_send_to_existing_only(self):
        """Test build_recipient with send_to_existing_only flag."""
        client = BrazeAPIClient('key', 'url')
        result = client.build_recipient('user1', send_to_existing_only=True)
        assert result['send_to_existing_only'] is True

    def test_build_recipient_attributes_not_mutated(self):
        """Test that original attributes dict is not mutated."""
        client = BrazeAPIClient('key', 'url')
        original_attrs = {'foo': 'bar'}
        result = client.build_recipient('user1', email='test@example.com', attributes=original_attrs)
        assert 'email' not in original_attrs  # Original should not be modified
        assert result['attributes']['email'] == 'test@example.com'
        assert result['attributes']['foo'] == 'bar'

    def test_build_recipient_raises_error_for_empty_user_id(self):
        """Test that build_recipient raises error for empty user ID."""
        client = BrazeAPIClient('key', 'url')
        with pytest.raises(BrazeValidationError, match="external_user_id must be a non-empty string"):
            client.build_recipient('')

    def test_build_recipient_raises_error_for_none_user_id(self):
        """Test that build_recipient raises error for None user ID."""
        client = BrazeAPIClient('key', 'url')
        with pytest.raises(BrazeValidationError, match="external_user_id must be a non-empty string"):
            client.build_recipient(None)

    def test_build_recipient_raises_error_for_invalid_user_id_type(self):
        """Test that build_recipient raises error for non-string user ID."""
        client = BrazeAPIClient('key', 'url')
        with pytest.raises(BrazeValidationError, match="external_user_id must be a non-empty string"):
            client.build_recipient(12345)


# ============================================================================
# send_campaign_message Tests
# ============================================================================

class TestSendCampaignMessage:
    """Test cases for send_campaign_message method."""

    def test_send_campaign_message_success_with_dict_recipients(self):
        """Test successful campaign send with dict recipients."""
        client = BrazeAPIClient('test-key', 'https://api.braze.com')

        mock_response = Mock()
        mock_response.json.return_value = {'message': 'success', 'dispatch_id': 'abc123'}
        mock_response.status_code = 200

        with patch.object(client.session, 'post', return_value=mock_response) as mock_post:
            recipients = [client.build_recipient('user1', email='user1@example.com')]
            result = client.send_campaign_message('campaign123', recipients)

            assert result['message'] == 'success'
            assert result['dispatch_id'] == 'abc123'
            mock_post.assert_called_once()

    def test_send_campaign_message_success_with_string_recipients(self):
        """Test successful campaign send with string recipients."""
        client = BrazeAPIClient('test-key', 'https://api.braze.com')

        mock_response = Mock()
        mock_response.json.return_value = {'message': 'success'}
        mock_response.status_code = 200

        with patch.object(client.session, 'post', return_value=mock_response):
            with patch.object(client, 'build_recipient', wraps=client.build_recipient) as mock_build_recipient:
                recipients = ['user1@example.com', 'user2@example.com']
                result = client.send_campaign_message('campaign123', recipients)

                assert result['message'] == 'success'
                assert mock_build_recipient.call_count == 2
                for expected_email, call in zip(recipients, mock_build_recipient.call_args_list):
                    assert call.kwargs == {
                        'external_user_id': expected_email,
                        'email': expected_email,
                        'send_to_existing_only': False,
                    }

    def test_send_campaign_message_with_trigger_properties(self):
        """Test campaign send with trigger properties."""
        client = BrazeAPIClient('test-key', 'https://api.braze.com')

        mock_response = Mock()
        mock_response.json.return_value = {'message': 'success'}

        with patch.object(client.session, 'post', return_value=mock_response) as mock_post:
            recipients = [client.build_recipient('user1')]
            trigger_props = {'course_name': 'Python 101', 'deadline': '2024-12-31'}
            client.send_campaign_message('campaign123', recipients, trigger_properties=trigger_props)

            # Verify trigger properties were included in payload
            call_args = mock_post.call_args
            payload = call_args[1]['json']
            assert payload['trigger_properties'] == trigger_props

    def test_send_campaign_message_with_broadcast_flag(self):
        """Test campaign send with broadcast flag."""
        client = BrazeAPIClient('test-key', 'https://api.braze.com')

        mock_response = Mock()
        mock_response.json.return_value = {'message': 'success'}

        with patch.object(client.session, 'post', return_value=mock_response) as mock_post:
            recipients = [client.build_recipient('user1')]
            client.send_campaign_message('campaign123', recipients, broadcast=True)

            call_args = mock_post.call_args
            payload = call_args[1]['json']
            assert payload['broadcast'] is True

    def test_send_campaign_message_validates_campaign_id(self):
        """Test that send_campaign_message validates campaign_id."""
        client = BrazeAPIClient('key', 'url')
        with pytest.raises(BrazeValidationError, match="campaign_id must be a non-empty string"):
            client.send_campaign_message('', [{'external_user_id': 'user1'}])

    def test_send_campaign_message_validates_recipients_not_empty(self):
        """Test that send_campaign_message validates recipients list is not empty."""
        client = BrazeAPIClient('key', 'url')
        with pytest.raises(BrazeValidationError, match="recipients must be a non-empty list"):
            client.send_campaign_message('campaign123', [])

    def test_send_campaign_message_validates_recipients_is_list(self):
        """Test that send_campaign_message validates recipients is a list."""
        client = BrazeAPIClient('key', 'url')
        with pytest.raises(BrazeValidationError, match="recipients must be a non-empty list"):
            client.send_campaign_message('campaign123', 'not-a-list')

    def test_send_campaign_message_raises_error_for_invalid_recipient_type(self):
        """Test that invalid recipient type raises clear error."""
        client = BrazeAPIClient('key', 'url')
        recipients = [12345]  # Invalid type
        with pytest.raises(BrazeValidationError, match="Invalid recipient type at index 0: int"):
            client.send_campaign_message('campaign123', recipients)

    def test_send_campaign_message_warns_for_large_batch(self):
        """Test that large recipient batches trigger warning."""
        client = BrazeAPIClient('test-key', 'https://api.braze.com')

        mock_response = Mock()
        mock_response.json.return_value = {'message': 'success'}

        with patch.object(client.session, 'post', return_value=mock_response):
            # Create more recipients than the limit
            recipients = [f'user{i}@example.com' for i in range(MAX_RECIPIENTS_PER_REQUEST + 10)]

            with patch('enterprise.api_client.braze_client.logger') as mock_logger:
                client.send_campaign_message('campaign123', recipients)
                mock_logger.warning.assert_called()
                warning_call = mock_logger.warning.call_args[0][0]
                assert 'exceeds recommended limit' in warning_call


# ============================================================================
# Error Handling Tests
# ============================================================================

class TestErrorHandling:
    """Test cases for error handling in BrazeAPIClient."""

    def test_send_campaign_message_http_error_4xx(self):
        """Test handling of HTTP 4xx errors."""
        client = BrazeAPIClient('test-key', 'https://api.braze.com')

        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json.return_value = {'errors': ['Invalid campaign ID']}
        mock_response.text = '{"errors": ["Invalid campaign ID"]}'

        http_error = HTTPError(response=mock_response)
        mock_response.raise_for_status.side_effect = http_error

        with patch.object(client.session, 'post', return_value=mock_response):
            with pytest.raises(BrazeClientError) as exc_info:
                client.send_campaign_message('campaign123', ['user@example.com'])

            assert '400' in str(exc_info.value)
            assert exc_info.value.status_code == 400

    def test_send_campaign_message_http_error_5xx(self):
        """Test handling of HTTP 5xx errors."""
        client = BrazeAPIClient('test-key', 'https://api.braze.com')

        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.json.side_effect = ValueError()
        mock_response.text = 'Internal Server Error'

        http_error = HTTPError(response=mock_response)
        mock_response.raise_for_status.side_effect = http_error

        with patch.object(client.session, 'post', return_value=mock_response):
            with pytest.raises(BrazeClientError) as exc_info:
                client.send_campaign_message('campaign123', ['user@example.com'])

            assert '500' in str(exc_info.value)
            assert exc_info.value.status_code == 500

    def test_send_campaign_message_timeout_error(self):
        """Test handling of timeout errors."""
        client = BrazeAPIClient('test-key', 'https://api.braze.com', timeout=5)

        with patch.object(client.session, 'post', side_effect=Timeout('Request timed out')):
            with pytest.raises(BrazeClientError, match='timed out after 5s'):
                client.send_campaign_message('campaign123', ['user@example.com'])

    def test_send_campaign_message_connection_error(self):
        """Test handling of connection errors."""
        client = BrazeAPIClient('test-key', 'https://api.braze.com')

        with patch.object(client.session, 'post', side_effect=RequestException('Connection refused')):
            with pytest.raises(BrazeClientError, match='Connection refused'):
                client.send_campaign_message('campaign123', ['user@example.com'])

    def test_send_campaign_message_invalid_json_response(self):
        """Test handling of invalid JSON responses."""
        client = BrazeAPIClient('test-key', 'https://api.braze.com')

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError('Invalid JSON')

        with patch.object(client.session, 'post', return_value=mock_response):
            with pytest.raises(BrazeClientError, match='Invalid JSON response'):
                client.send_campaign_message('campaign123', ['user@example.com'])


# ============================================================================
# Integration Tests
# ============================================================================

class TestBrazeClientIntegration:
    """Integration test cases for BrazeAPIClient."""

    def test_end_to_end_campaign_send(self):
        """Test end-to-end campaign send flow."""
        client = BrazeAPIClient('test-key', 'https://api.braze.com')

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'message': 'success',
            'dispatch_id': 'dispatch-123',
            'status_code': 201
        }

        with patch.object(client.session, 'post', return_value=mock_response) as mock_post:
            # Build mixed recipient types
            recipients = [
                client.build_recipient('user1', email='user1@example.com', attributes={'role': 'admin'}),
                'user2@example.com',  # String recipient
                client.build_recipient('user3', email='user3@example.com', send_to_existing_only=True)
            ]

            trigger_props = {
                'course_name': 'Advanced Python',
                'start_date': '2024-01-01',
                'instructor': 'Dr. Smith'
            }

            result = client.send_campaign_message(
                campaign_id='python-course-launch',
                recipients=recipients,
                trigger_properties=trigger_props,
                broadcast=False
            )

            # Verify response
            assert result['message'] == 'success'
            assert result['dispatch_id'] == 'dispatch-123'

            # Verify request was made correctly
            mock_post.assert_called_once()
            call_kwargs = mock_post.call_args[1]

            # Verify headers
            assert 'Authorization' in call_kwargs['headers']
            assert call_kwargs['headers']['Authorization'] == 'Bearer test-key'
            assert call_kwargs['headers']['Content-Type'] == 'application/json'

            # Verify payload
            payload = call_kwargs['json']
            assert payload['campaign_id'] == 'python-course-launch'
            assert len(payload['recipients']) == 3
            assert payload['trigger_properties'] == trigger_props
            assert payload['broadcast'] is False
            assert call_kwargs['timeout'] == DEFAULT_TIMEOUT


# Legacy tests for backward compatibility
def test_build_recipient_basic():
    """Legacy test - kept for backward compatibility."""
    client = BrazeAPIClient('key', 'url')
    result = client.build_recipient('user1')
    assert result['external_user_id'] == 'user1'
    assert result['send_to_existing_only'] is False
    assert 'attributes' not in result


def test_build_recipient_with_email_and_attributes():
    """Legacy test - kept for backward compatibility."""
    client = BrazeAPIClient('key', 'url')
    attrs = {'foo': 'bar'}
    result = client.build_recipient('user2', email='test@example.com', attributes=attrs)
    assert result['attributes']['email'] == 'test@example.com'
    assert result['attributes']['foo'] == 'bar'


def test_send_campaign_message_dict_and_str():
    """Legacy test adapted for new implementation."""
    mock_response = Mock()
    mock_response.json.return_value = {'result': 'success'}
    mock_response.status_code = 200

    with patch('enterprise.api_client.braze_client.requests.Session') as mock_session_class:
        mock_session = Mock()
        mock_session.post.return_value = mock_response
        mock_session_class.return_value = mock_session

        client = BrazeAPIClient('key', 'http://fake-url')
        recipients = [client.build_recipient('user1'), 'user2@example.com']
        resp = client.send_campaign_message('cid', recipients, {'x': 1}, True)
        assert resp == {'result': 'success'}


def test_send_campaign_message_error():
    """Legacy test adapted for new error handling."""
    client = BrazeAPIClient('key', 'url')

    with patch.object(client.session, 'post', side_effect=RequestException('Network error')):
        with pytest.raises(BrazeClientError):
            client.send_campaign_message('cid', ['user1'])
