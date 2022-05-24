"""
Database models for Enterprise Integrated Channel.
"""

import json
import logging

from jsonfield.fields import JSONField

from django.contrib import auth
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from model_utils.models import TimeStampedModel

from enterprise.models import EnterpriseCustomer, EnterpriseCustomerCatalog
from integrated_channels.integrated_channel.exporters.content_metadata import ContentMetadataExporter
from integrated_channels.integrated_channel.exporters.learner_data import LearnerExporter
from integrated_channels.integrated_channel.transmitters.content_metadata import ContentMetadataTransmitter
from integrated_channels.integrated_channel.transmitters.learner_data import LearnerTransmitter
from integrated_channels.utils import convert_comma_separated_string_to_list

LOGGER = logging.getLogger(__name__)
User = auth.get_user_model()


def set_default_display_name(*args, **kw):
    """
    post_save signal reciever to set default display name
    wired up in EnterpriseCustomerPluginConfiguration.__init_subclass__
    """
    this_display_name = kw['instance'].display_name
    # check if display_name is None, empty, or just spaces
    if not (this_display_name and this_display_name.strip()):
        kw['instance'].display_name = kw['instance'].generate_default_display_name()
        kw['instance'].save()


class EnterpriseCustomerPluginConfiguration(TimeStampedModel):
    """
    Abstract base class for information related to integrating with external systems for an enterprise customer.

    EnterpriseCustomerPluginConfiguration should be extended by configuration models in other integrated channel
    apps to provide uniformity across different integrated channels.

    The configuration provides default exporters and transmitters if the ``get_x_data_y`` methods aren't
    overridden, where ``x`` and ``y`` are (learner, course) and (exporter, transmitter) respectively.
    """

    display_name = models.CharField(
        max_length=255,
        blank=True,
        default='',
        help_text=_("A configuration nickname.")
    )

    enterprise_customer = models.ForeignKey(
        EnterpriseCustomer,
        blank=False,
        null=False,
        help_text=_("Enterprise Customer associated with the configuration."),
        on_delete=models.deletion.CASCADE
    )

    idp_id = models.CharField(
        max_length=255,
        blank=True,
        default='',
        help_text=_("If provided, will be used as IDP slug to locate remote id for learners")
    )

    active = models.BooleanField(
        blank=False,
        null=False,
        help_text=_("Is this configuration active?"),
    )

    dry_run_mode_enabled = models.BooleanField(
        blank=False,
        null=False,
        default=False,
        help_text=_("Is this configuration in dry-run mode? (experimental)"),
    )

    transmission_chunk_size = models.IntegerField(
        default=500,
        help_text=_("The maximum number of data items to transmit to the integrated channel with each request.")
    )

    channel_worker_username = models.CharField(
        max_length=255,
        blank=True,
        default='',
        help_text=_("Enterprise channel worker username to get JWT tokens for authenticating LMS APIs."),
    )
    catalogs_to_transmit = models.TextField(
        blank=True,
        default='',
        help_text=_(
            "A comma-separated list of catalog UUIDs to transmit. If blank, all customer catalogs will be transmitted. "
            "If there are overlapping courses in the customer catalogs, the overlapping course metadata will be "
            "selected from the newest catalog."
        ),
    )
    disable_learner_data_transmissions = models.BooleanField(
        default=False,
        verbose_name="Disable Learner Data Transmission",
        help_text=_("When set to True, the configured customer will no longer receive learner data transmissions, both"
                    " scheduled and signal based")
    )

    class Meta:
        abstract = True

    @classmethod
    def __init_subclass__(cls, **kwargs):
        """
        Finds every subclass and wires up the signal reciever to set default display name when blank
        """
        super().__init_subclass__(**kwargs)
        models.signals.post_save.connect(set_default_display_name, sender=cls)

    def clean(self):
        invalid_uuids = []
        for uuid in convert_comma_separated_string_to_list(self.catalogs_to_transmit):
            try:
                EnterpriseCustomerCatalog.objects.get(uuid=uuid, enterprise_customer=self.enterprise_customer)
            except (EnterpriseCustomerCatalog.DoesNotExist, ValidationError):
                invalid_uuids.append(str(uuid))
        if invalid_uuids:
            raise ValidationError(
                {
                    'catalogs_to_transmit': [
                        "These are the invalid uuids: {invalid_uuids}".format(invalid_uuids=invalid_uuids)
                    ]
                }
            )

    @property
    def channel_worker_user(self):
        """
        default worker username for channel
        """
        worker_username = self.channel_worker_username if self.channel_worker_username else 'enterprise_channel_worker'
        return User.objects.filter(username=worker_username).first()

    @property
    def customer_catalogs_to_transmit(self):
        """
        Return the list of EnterpriseCustomerCatalog objects.
        """
        catalogs_list = []
        if self.catalogs_to_transmit:
            catalogs_list = EnterpriseCustomerCatalog.objects.filter(
                uuid__in=convert_comma_separated_string_to_list(self.catalogs_to_transmit)
            )
        return catalogs_list

    @staticmethod
    def channel_code():
        """
        Returns an capitalized identifier for this channel class, unique among subclasses.
        """
        raise NotImplementedError('Implemented in concrete subclass.')

    def generate_default_display_name(self):
        """
        Returns a default display namem which can be overriden by a subclass.
        """
        return f'{self.channel_code()} {self.id}'

    def get_learner_data_exporter(self, user):
        """
        Returns the class that can serialize the learner course completion data to the integrated channel.
        """
        return LearnerExporter(user, self)

    def get_learner_data_transmitter(self):
        """
        Returns the class that can transmit the learner course completion data to the integrated channel.
        """
        return LearnerTransmitter(self)

    def get_content_metadata_exporter(self, user):
        """
        Returns a class that can retrieve and transform content metadata to the schema
        expected by the integrated channel.
        """
        return ContentMetadataExporter(user, self)

    def get_content_metadata_transmitter(self):
        """
        Returns a class that can transmit the content metadata to the integrated channel.
        """
        return ContentMetadataTransmitter(self)

    def transmit_learner_data(self, user):
        """
        Iterate over each learner data record and transmit it to the integrated channel.
        """
        exporter = self.get_learner_data_exporter(user)
        transmitter = self.get_learner_data_transmitter()
        transmitter.transmit(exporter)

    def transmit_single_learner_data(self, **kwargs):
        """
        Iterate over single learner data record and transmit it to the integrated channel.
        """
        exporter = self.get_learner_data_exporter(self.channel_worker_user)
        transmitter = self.get_learner_data_transmitter()
        transmitter.transmit(exporter, **kwargs)

    def transmit_content_metadata(self, user):
        """
        Transmit content metadata to integrated channel.
        """
        exporter = self.get_content_metadata_exporter(user)
        transmitter = self.get_content_metadata_transmitter()
        transmitter.transmit(*exporter.export())

    def transmit_single_subsection_learner_data(self, **kwargs):
        """
        Transmit a single subsection learner data record to the integrated channel.
        """
        exporter = self.get_learner_data_exporter(self.channel_worker_user)
        transmitter = self.get_learner_data_transmitter()
        transmitter.single_learner_assessment_grade_transmit(exporter, **kwargs)

    def transmit_subsection_learner_data(self, user):
        """
        Iterate over each assessment learner data record and transmit them to the integrated channel.
        """
        exporter = self.get_learner_data_exporter(user)
        transmitter = self.get_learner_data_transmitter()
        transmitter.assessment_level_transmit(exporter)

    def cleanup_duplicate_assignment_records(self, user):
        """
        Remove duplicated assessments transmitted through the integrated channel.
        """
        exporter = self.get_learner_data_exporter(user)
        transmitter = self.get_learner_data_transmitter()
        transmitter.deduplicate_assignment_records_transmit(exporter)

    def update_content_transmission_catalog(self, user):
        """
        Update transmission audits to contain the content's associated catalog uuid.
        """
        exporter = self.get_content_metadata_exporter(user)
        exporter.update_content_transmissions_catalog_uuids()


class GenericEnterpriseCustomerPluginConfiguration(EnterpriseCustomerPluginConfiguration):
    """
    A generic implementation of EnterpriseCustomerPluginConfiguration which can be instantiated
    """
    def __str__(self):
        """
        Return human-readable string representation.
        """
        return "<GenericEnterpriseCustomerPluginConfiguration for Enterprise {enterprise_name}>".format(
            enterprise_name=self.enterprise_customer.name
        )

    @staticmethod
    def channel_code():
        """
        Returns an capitalized identifier for this channel class, unique among subclasses.
        """
        return 'GENERIC'


class LearnerDataTransmissionAudit(TimeStampedModel):
    """
    The payload we send to an integrated channel  at a given point in time for an enterprise course enrollment.

    .. no_pii:
    """

    # TODO: index customer uuid + plugin coinfig id together, with enrollment id?
    enterprise_customer_uuid = models.UUIDField(blank=True, null=True)
    plugin_configuration_id = models.IntegerField(blank=True, null=True)
    enterprise_course_enrollment_id = models.IntegerField(blank=True, null=True, db_index=True)
    course_id = models.CharField(max_length=255, blank=False, null=False)
    course_completed = models.BooleanField(default=True)
    completed_timestamp = models.DateTimeField(blank=True, null=True)
    instructor_name = models.CharField(max_length=255, blank=True)
    grade = models.FloatField(blank=True, null=True)
    total_hours = models.FloatField(null=True, blank=True)
    subsection_id = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    subsection_name = models.CharField(max_length=255, blank=False, null=True)
    status = models.CharField(max_length=100, blank=True, null=True)
    error_message = models.TextField(blank=True, null=True)

    class Meta:
        abstract = True
        app_label = 'integrated_channel'

    def __str__(self):
        """
        Return a human-readable string representation of the object.
        """
        return (
            f'<LearnerDataTransmissionAudit {self.id}'
            f' for enterprise enrollment {self.enterprise_course_enrollment_id}, '
            f', course_id: {self.course_id}>'
            f', grade: {self.grade}'
            f', completed_timestamp: {self.completed_timestamp}'
            f', enterprise_customer_uuid: {self.enterprise_customer_uuid}'
            f', course_completed: {self.course_completed}'
        )

    def __repr__(self):
        """
        Return uniquely identifying string representation.
        """
        return self.__str__()

    @property
    def provider_id(self):
        """
        Fetch ``provider_id`` from global configuration settings
        """
        return None

    def serialize(self, *args, **kwargs):
        """
        Return a JSON-serialized representation.

        Sort the keys so the result is consistent and testable.

        # TODO: When we refactor to use a serialization flow consistent with how course metadata
        # is serialized, remove the serialization here and make the learner data exporter handle the work.
        """
        return json.dumps(self._payload_data(), sort_keys=True)

    def _payload_data(self):
        """
        Convert the audit record's fields into SAP SuccessFactors key/value pairs.
        """
        return dict(
            courseID=self.course_id,
            courseCompleted="true" if self.course_completed else "false",
            completedTimestamp=self.completed_timestamp,
            grade=self.grade,
        )


class GenericLearnerDataTransmissionAudit(LearnerDataTransmissionAudit):
    """
    A generic implementation of LearnerDataTransmissionAudit which can be instantiated
    """
    class Meta:
        app_label = 'integrated_channel'

    def __str__(self):
        """
        Return a human-readable string representation of the object.
        """
        return (
            '<GenericLearnerDataTransmissionAudit {transmission_id} for enterprise enrollment {enrollment}, '
            'and course {course_id}>'.format(
                transmission_id=self.id,
                enrollment=self.enterprise_course_enrollment_id,
                course_id=self.course_id
            )
        )

    def __repr__(self):
        """
        Return uniquely identifying string representation.
        """
        return self.__str__()


class ContentMetadataItemTransmission(TimeStampedModel):
    """
    A content metadata item that has been transmitted to an integrated channel.

    This model can be queried to find the content metadata items that have been
    transmitted to an integrated channel. It is used to synchronize the content
    metadata items available in an enterprise's catalog with the integrated channel.

    .. no_pii:
    """

    enterprise_customer = models.ForeignKey(EnterpriseCustomer, on_delete=models.CASCADE)
    integrated_channel_code = models.CharField(max_length=30)
    plugin_configuration_id = models.PositiveIntegerField(blank=True, null=True)
    content_id = models.CharField(max_length=255)
    channel_metadata = JSONField()
    content_last_changed = models.DateTimeField(
        help_text='Date of the last time the enterprise catalog associated with this metadata item was updated',
        blank=True,
        null=True
    )
    enterprise_customer_catalog_uuid = models.UUIDField(
        help_text='The enterprise catalog that this metadata item was derived from',
        blank=True,
        null=True,
    )
    deleted_at = models.DateTimeField(
        help_text='Date when the content transmission was deleted',
        blank=True,
        null=True
    )

    def __str__(self):
        """
        Return a human-readable string representation of the object.
        """
        return (
            '<Content item {content_id} for Customer {customer} with Channel {channel}>'.format(
                content_id=self.content_id,
                customer=self.enterprise_customer,
                channel=self.integrated_channel_code
            )
        )

    def __repr__(self):
        """
        Return uniquely identifying string representation.
        """
        return self.__str__()
