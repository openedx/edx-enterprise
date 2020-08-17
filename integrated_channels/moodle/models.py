from logging import getLogger

from config_models.models import ConfigurationModel
from simple_history.models import HistoricalRecords

from django.db import models
from django.utils.encoding import python_2_unicode_compatible
from django.utils.translation import ugettext_lazy as _

from integrated_channels.integrated_channel.models import EnterpriseCustomerPluginConfiguration

LOGGER = getLogger(__name__)


# pylint: disable=feature-toggle-needs-doc
@python_2_unicode_compatible
class MoodleGlobalConfiguration(ConfigurationModel):
    """
    The global configuration for integrating with Moodle.

    .. no_pii:
    """

    api_token = models.CharField(
        max_length=100,
        verbose_name="Developer Token",
        help_text=_(
            "The token used to authenticate to Moodle. "
            "Created in Moodle at Site administration/Plugins/Web services/Manage tokens"
        )

    )

    class Meta:
        app_label = 'moodle'

    def __str__(self):
        """
        Return a human-readable string representation of the object.
        """
        return "<MoodleGlobalConfiguration with id {id}>".format(id=self.id)

    def __repr__(self):
        """
        Return uniquely identifying string representation.
        """
        return self.__str__()


@python_2_unicode_compatible
class MoodleEnterpriseCustomerConfiguration(EnterpriseCustomerPluginConfiguration):
    """
    The Enterprise-specific configuration we need for integrating with Moodle.

    .. no_pii:
    """

    moodle_base_url = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Moodle Base URL",
        help_text=_("The base URL used for API requests to Moodle")
    )

    history = HistoricalRecords()

    class Meta:
        app_label = 'moodle'

    def __str__(self):
        """
        Return human-readable string representation.
        """
        return "<MoodleEnterpriseCustomerConfiguration for Enterprise {enterprise_name}>".format(
            enterprise_name=self.enterprise_customer.name
        )

    def __repr__(self):
        """
        Return uniquely identifying string representation.
        """
        return self.__str__()

    @staticmethod
    def channel_code():
        """
        Returns an capitalized identifier for this channel class, unique among subclasses.
        """
        return 'MOODLE'
