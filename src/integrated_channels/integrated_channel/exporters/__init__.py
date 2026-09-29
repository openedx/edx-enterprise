"""
Package for generic data exporters which serialize data to be transmitted to integrated channels.
"""


class Exporter:
    """
    Interface for exporting data to be transmitted to an integrated channel.

    The interface contains the following method(s):

    export()
        Yields a serialized piece of data plus the HTTP method to be used by the transmitter.
    """

    def __init__(self, user, enterprise_configuration):
        """
        Store the data needed to export the learner data to the integrated channel.

        Arguments:
            * user: User instance with access to the Grades API for the Enterprise Customer's courses.
            * enterprise_configuration - The configuration connecting an enterprise to an integrated channel.
        """
        self.user = user
        self.enterprise_configuration = enterprise_configuration
        self.enterprise_customer = enterprise_configuration.enterprise_customer

    def export(self, **kwargs):
        """
        Export (read: serialize) data to be used by a transmitter to transmit to an integrated channel.
        """
        raise NotImplementedError('Implement in concrete subclass transmitter.')
