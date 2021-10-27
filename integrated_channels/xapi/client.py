"""
xAPI Client to send payload data.
"""

import logging

from tincan.remote_lrs import RemoteLRS

from integrated_channels.exceptions import ClientError

LOGGER = logging.getLogger(__name__)


class EnterpriseXAPIClient:
    """
    xAPI to send payload data and handle responses.
    """

    def __init__(self, lrs_configuration):
        """
        Initialize xAPI client.

        Arguments:
             lrs_configuration (XAPILRSConfiguration): Configuration object for xAPI LRS.
        """
        self.lrs_configuration = lrs_configuration

    @property
    def lrs(self):
        """
        LRS client instance to be used for sending statements.
        """
        return RemoteLRS(
            version=self.lrs_configuration.version,
            endpoint=self.lrs_configuration.endpoint,
            auth=self.lrs_configuration.authorization_header,
        )

    def save_statement(self, statement):
        """
        Save xAPI statement.

        Arguments:
            statement (EnterpriseStatement): xAPI Statement to send to the LRS.

        Raises:
            ClientError: If xAPI statement fails to save.
        """
        LOGGER.info(
            "[Integrated Channel][xAPI] Sending statement %s to LRS endpoint %s ",
            statement.to_json(),
            self.lrs.endpoint
        )
        response = self.lrs.save_statement(statement)

        if not response:
            raise ClientError('EnterpriseXAPIClient request failed.')

        return response
