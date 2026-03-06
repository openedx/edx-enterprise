"""
Tests for enterprise.constants module.
"""
from enterprise.constants import AdminInviteStatus, BrazeAPIEndpoints


class TestBrazeAPIEndpoints:
    """
    Tests for BrazeAPIEndpoints constants.
    """

    def test_send_campaign_endpoint(self):
        """Test SEND_CAMPAIGN endpoint is correctly defined."""
        assert BrazeAPIEndpoints.SEND_CAMPAIGN == '/campaigns/trigger/send'

    def test_send_canvas_endpoint(self):
        """Test SEND_CANVAS endpoint is correctly defined."""
        assert BrazeAPIEndpoints.SEND_CANVAS == '/canvas/trigger/send'

    def test_export_ids_endpoint(self):
        """Test EXPORT_IDS endpoint is correctly defined."""
        assert BrazeAPIEndpoints.EXPORT_IDS == '/users/export/ids'

    def test_send_message_endpoint(self):
        """Test SEND_MESSAGE endpoint is correctly defined."""
        assert BrazeAPIEndpoints.SEND_MESSAGE == '/messages/send'

    def test_new_alias_endpoint(self):
        """Test NEW_ALIAS endpoint is correctly defined."""
        assert BrazeAPIEndpoints.NEW_ALIAS == '/users/alias/new'

    def test_track_user_endpoint(self):
        """Test TRACK_USER endpoint is correctly defined."""
        assert BrazeAPIEndpoints.TRACK_USER == '/users/track'

    def test_identify_users_endpoint(self):
        """Test IDENTIFY_USERS endpoint is correctly defined."""
        assert BrazeAPIEndpoints.IDENTIFY_USERS == '/users/identify'

    def test_unsubscribe_user_email_endpoint(self):
        """Test UNSUBSCRIBE_USER_EMAIL endpoint is correctly defined."""
        assert BrazeAPIEndpoints.UNSUBSCRIBE_USER_EMAIL == '/email/status'

    def test_unsubscribed_emails_endpoint(self):
        """Test UNSUBSCRIBED_EMAILS endpoint is correctly defined."""
        assert BrazeAPIEndpoints.UNSUBSCRIBED_EMAILS == '/email/unsubscribes'

    def test_all_endpoints_are_strings(self):
        """Test that all BrazeAPIEndpoints are strings."""
        endpoints = [
            BrazeAPIEndpoints.SEND_CAMPAIGN,
            BrazeAPIEndpoints.SEND_CANVAS,
            BrazeAPIEndpoints.EXPORT_IDS,
            BrazeAPIEndpoints.SEND_MESSAGE,
            BrazeAPIEndpoints.NEW_ALIAS,
            BrazeAPIEndpoints.TRACK_USER,
            BrazeAPIEndpoints.IDENTIFY_USERS,
            BrazeAPIEndpoints.UNSUBSCRIBE_USER_EMAIL,
            BrazeAPIEndpoints.UNSUBSCRIBED_EMAILS,
        ]
        for endpoint in endpoints:
            assert isinstance(endpoint, str), f"Endpoint {endpoint} is not a string"

    def test_all_endpoints_start_with_slash(self):
        """Test that all BrazeAPIEndpoints start with a forward slash."""
        endpoints = [
            BrazeAPIEndpoints.SEND_CAMPAIGN,
            BrazeAPIEndpoints.SEND_CANVAS,
            BrazeAPIEndpoints.EXPORT_IDS,
            BrazeAPIEndpoints.SEND_MESSAGE,
            BrazeAPIEndpoints.NEW_ALIAS,
            BrazeAPIEndpoints.TRACK_USER,
            BrazeAPIEndpoints.IDENTIFY_USERS,
            BrazeAPIEndpoints.UNSUBSCRIBE_USER_EMAIL,
            BrazeAPIEndpoints.UNSUBSCRIBED_EMAILS,
        ]
        for endpoint in endpoints:
            assert endpoint.startswith('/'), f"Endpoint {endpoint} does not start with '/'"

    def test_endpoints_are_not_empty(self):
        """Test that all BrazeAPIEndpoints are not empty or just a slash."""
        endpoints = [
            BrazeAPIEndpoints.SEND_CAMPAIGN,
            BrazeAPIEndpoints.SEND_CANVAS,
            BrazeAPIEndpoints.EXPORT_IDS,
            BrazeAPIEndpoints.SEND_MESSAGE,
            BrazeAPIEndpoints.NEW_ALIAS,
            BrazeAPIEndpoints.TRACK_USER,
            BrazeAPIEndpoints.IDENTIFY_USERS,
            BrazeAPIEndpoints.UNSUBSCRIBE_USER_EMAIL,
            BrazeAPIEndpoints.UNSUBSCRIBED_EMAILS,
        ]
        for endpoint in endpoints:
            assert len(endpoint) > 1, f"Endpoint {endpoint} is too short"


class TestAdminInviteStatus:
    """
    Tests for AdminInviteStatus constants.
    """

    def test_existing_admin_status(self):
        """Test EXISTING_ADMIN status is correctly defined."""
        assert AdminInviteStatus.EXISTING_ADMIN == 'already admin'

    def test_pending_invite_status(self):
        """Test PENDING_INVITE status is correctly defined."""
        assert AdminInviteStatus.PENDING_INVITE == 'already sent'

    def test_new_invite_status(self):
        """Test NEW_INVITE status is correctly defined."""
        assert AdminInviteStatus.NEW_INVITE == 'invite sent'

    def test_all_statuses_are_strings(self):
        """Test that all AdminInviteStatus constants are strings."""
        statuses = [
            AdminInviteStatus.EXISTING_ADMIN,
            AdminInviteStatus.PENDING_INVITE,
            AdminInviteStatus.NEW_INVITE,
        ]
        for status in statuses:
            assert isinstance(status, str), f"Status {status} is not a string"

    def test_all_statuses_are_not_empty(self):
        """Test that all AdminInviteStatus constants are not empty."""
        statuses = [
            AdminInviteStatus.EXISTING_ADMIN,
            AdminInviteStatus.PENDING_INVITE,
            AdminInviteStatus.NEW_INVITE,
        ]
        for status in statuses:
            assert len(status) > 0, f"Status {status} is empty"

    def test_all_statuses_are_unique(self):
        """Test that all AdminInviteStatus constants are unique."""
        statuses = [
            AdminInviteStatus.EXISTING_ADMIN,
            AdminInviteStatus.PENDING_INVITE,
            AdminInviteStatus.NEW_INVITE,
        ]
        assert len(statuses) == len(set(statuses)), "Duplicate status values found"
