"""
Database models for Enterprise Integrated Channel.
"""

import json
import logging

from jsonfield.fields import JSONField

from django.contrib import auth
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.db.models.query import QuerySet
from django.utils.translation import gettext_lazy as _

from model_utils.models import TimeStampedModel

from enterprise.constants import TRANSMISSION_MARK_CREATE, TRANSMISSION_MARK_DELETE, TRANSMISSION_MARK_UPDATE
from enterprise.models import EnterpriseCustomer, EnterpriseCustomerCatalog
from enterprise.utils import localized_utcnow
from integrated_channels.integrated_channel.exporters.content_metadata import ContentMetadataExporter
from integrated_channels.integrated_channel.exporters.learner_data import LearnerExporter
from integrated_channels.integrated_channel.transmitters.content_metadata import ContentMetadataTransmitter
from integrated_channels.integrated_channel.transmitters.learner_data import LearnerTransmitter
from integrated_channels.utils import channel_code_to_app_label, convert_comma_separated_string_to_list

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


class SoftDeletionQuerySet(QuerySet):
    """
    Soft deletion query set.
    """

    def delete(self):
        return super().update(deleted_at=localized_utcnow())

    def hard_delete(self):
        return super().delete()

    def revive(self):
        return super().update(deleted_at=None)


class SoftDeletionManager(models.Manager):
    """
    Soft deletion manager overriding a model's query set in order to soft delete.
    """
    use_for_related_fields = True

    def __init__(self, *args, **kwargs):
        self.alive_only = kwargs.pop('alive_only', True)
        super().__init__(*args, **kwargs)

    def get_queryset(self):
        if self.alive_only:
            return SoftDeletionQuerySet(self.model, using=self._db, hints=self._hints).filter(deleted_at=None)
        return SoftDeletionQuerySet(self.model)

    def delete(self):
        return self.get_queryset().delete()

    def hard_delete(self):
        return self.get_queryset().hard_delete()

    def revive(self):
        return self.get_queryset().revive()


class SoftDeletionModel(TimeStampedModel):
    """
    Soft deletion model that sets a particular entries `deleted_at` field instead of removing the entry on delete.
    Use `hard_delete()` to permanently remove entries.
    """
    deleted_at = models.DateTimeField(blank=True, null=True)

    objects = SoftDeletionManager()
    all_objects = SoftDeletionManager(alive_only=False)

    class Meta:
        abstract = True


class EnterpriseCustomerPluginConfiguration(SoftDeletionModel):
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
    last_sync_attempted_at = models.DateTimeField(
        help_text='The DateTime of the most recent Content or Learner data record sync attempt',
        blank=True,
        null=True
    )
    last_content_sync_attempted_at = models.DateTimeField(
        help_text='The DateTime of the most recent Content data record sync attempt',
        blank=True,
        null=True
    )
    last_learner_sync_attempted_at = models.DateTimeField(
        help_text='The DateTime of the most recent Learner data record sync attempt',
        blank=True,
        null=True
    )
    last_sync_errored_at = models.DateTimeField(
        help_text='The DateTime of the most recent failure of a Content or Learner data record sync attempt',
        blank=True,
        null=True
    )
    last_content_sync_errored_at = models.DateTimeField(
        help_text='The DateTime of the most recent failure of a Content data record sync attempt',
        blank=True,
        null=True
    )
    last_learner_sync_errored_at = models.DateTimeField(
        help_text='The DateTime of the most recent failure of a Learner data record sync attempt',
        blank=True,
        null=True
    )
    last_modified_at = models.DateTimeField(
        help_text='The DateTime of the last change made to this configuration.',
        auto_now=True,
        blank=True,
        null=True
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

    def delete(self, *args, **kwargs):
        self.deleted_at = localized_utcnow()
        self.save()

    def revive(self):
        self.deleted_at = None
        self.save()

    def hard_delete(self):
        return super().delete()

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

    def fetch_orphaned_content_audits(self):
        """
        Helper method attached to customer configs to fetch all orphaned content metadata audits not linked to the
        customer's catalogs.
        """
        enterprise_customer_catalogs = self.customer_catalogs_to_transmit or \
            self.enterprise_customer.enterprise_customer_catalogs.all()

        customer_catalog_uuids = enterprise_customer_catalogs.values_list('uuid', flat=True)
        return ContentMetadataItemTransmission.objects.filter(
            integrated_channel_code=self.channel_code(),
            enterprise_customer=self.enterprise_customer,
            remote_deleted_at__isnull=True,
            remote_created_at__isnull=False,
        ).exclude(enterprise_customer_catalog_uuid__in=customer_catalog_uuids)

    def update_content_synced_at(self, action_happened_at, was_successful):
        """
        Given the last time a Content record sync was attempted and status update the appropriate timestamps.
        """
        if self.last_sync_attempted_at is None or action_happened_at > self.last_sync_attempted_at:
            self.last_sync_attempted_at = action_happened_at
        if self.last_content_sync_attempted_at is None or action_happened_at > self.last_content_sync_attempted_at:
            self.last_content_sync_attempted_at = action_happened_at
        if not was_successful:
            if self.last_sync_errored_at is None or action_happened_at > self.last_sync_errored_at:
                self.last_sync_errored_at = action_happened_at
            if self.last_content_sync_errored_at is None or action_happened_at > self.last_content_sync_errored_at:
                self.last_content_sync_errored_at = action_happened_at
        return self.save()

    def update_learner_synced_at(self, action_happened_at, was_successful):
        """
        Given the last time a Learner record sync was attempted and status update the appropriate timestamps.
        """
        if self.last_sync_attempted_at is None or action_happened_at > self.last_sync_attempted_at:
            self.last_sync_attempted_at = action_happened_at
        if self.last_learner_sync_attempted_at is None or action_happened_at > self.last_learner_sync_attempted_at:
            self.last_learner_sync_attempted_at = action_happened_at
        if not was_successful:
            if self.last_sync_errored_at is None or action_happened_at > self.last_sync_errored_at:
                self.last_sync_errored_at = action_happened_at
            if self.last_learner_sync_errored_at is None or action_happened_at > self.last_learner_sync_errored_at:
                self.last_learner_sync_errored_at = action_happened_at
        return self.save()

    @property
    def is_valid(self):
        """
        Returns whether or not the configuration is valid and ready to be activated

        Args:
            obj: The instance of EnterpriseCustomerConfiguration
                being rendered with this admin form.
        """
        missing_items = {'missing': []}
        incorrect_items = {'incorrect': []}
        return missing_items, incorrect_items

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

    @classmethod
    def get_class_by_channel_code(cls, channel_code):
        """
        Return the `EnterpriseCustomerPluginConfiguration` implementation for the particular channel_code, or None
        """
        for a_cls in cls.__subclasses__():
            if a_cls.channel_code().lower() == channel_code.lower():
                return a_cls
        return None

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


class ApiResponseRecord(TimeStampedModel):
    """
    Api response data for learner and content metadata transmissions

    .. no_pii;
    """
    status_code = models.PositiveIntegerField(
        help_text='The most recent remote API call response HTTP status code',
        blank=True,
        null=True
    )
    body = models.TextField(
        help_text='The most recent remote API call response body',
        blank=True,
        null=True
    )


class LearnerDataTransmissionAudit(TimeStampedModel):
    """
    The payload we send to an integrated channel  at a given point in time for an enterprise course enrollment.

    .. pii: The user_email model field contains PII

    """

    # TODO: index customer uuid + plugin coinfig id together, with enrollment id?
    enterprise_customer_uuid = models.UUIDField(blank=True, null=True)
    user_email = models.CharField(max_length=255, blank=True, null=True)
    plugin_configuration_id = models.IntegerField(blank=True, null=True)
    enterprise_course_enrollment_id = models.IntegerField(blank=True, null=True, db_index=True)
    course_id = models.CharField(max_length=255, blank=False, null=False)
    content_title = models.CharField(max_length=255, default=None, null=True, blank=True)
    course_completed = models.BooleanField(default=True)
    progress_status = models.CharField(max_length=255, blank=True)
    completed_timestamp = models.DateTimeField(blank=True, null=True)
    instructor_name = models.CharField(max_length=255, blank=True)
    grade = models.FloatField(blank=True, null=True)
    total_hours = models.FloatField(null=True, blank=True)
    subsection_id = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    subsection_name = models.CharField(max_length=255, blank=False, null=True)
    status = models.CharField(max_length=100, blank=True, null=True)
    error_message = models.TextField(blank=True, null=True)
    friendly_status_message = models.CharField(
        help_text='A user-friendly API response status message.',
        max_length=255,
        default=None,
        null=True,
        blank=True
    )
    api_record = models.OneToOneField(
        ApiResponseRecord,
        blank=True,
        null=True,
        on_delete=models.CASCADE,
        help_text=_('Data pertaining to the transmissions API request response.')
    )

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

    @classmethod
    def audit_type(cls):
        """
        The base learner data transmission audit type - defaults to `completion`
        """
        return "completion"

    @classmethod
    def get_completion_class_by_channel_code(cls, channel_code):
        """
        Return the `LearnerDataTransmissionAudit` implementation related to completion reporting for
        the particular channel_code, or None
        """
        app_label = channel_code_to_app_label(channel_code)
        for a_cls in cls.__subclasses__():
            if a_cls._meta.app_label == app_label and a_cls.audit_type() == "completion":
                return a_cls
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
        return {
            'courseID': self.course_id,
            'courseCompleted': 'true' if self.course_completed else 'false',
            'completedTimestamp': self.completed_timestamp,
            'grade': self.grade,
        }


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
    class Meta:
        index_together = [('enterprise_customer', 'integrated_channel_code', 'plugin_configuration_id', 'content_id')]

    enterprise_customer = models.ForeignKey(EnterpriseCustomer, on_delete=models.CASCADE)
    integrated_channel_code = models.CharField(max_length=30)
    plugin_configuration_id = models.PositiveIntegerField(blank=True, null=True)
    content_id = models.CharField(max_length=255)
    content_title = models.CharField(max_length=255, default=None, null=True, blank=True)
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
    remote_deleted_at = models.DateTimeField(
        help_text='Date when the content transmission was deleted in the remote API',
        blank=True,
        null=True
    )
    remote_created_at = models.DateTimeField(
        help_text='Date when the content transmission was created in the remote API',
        blank=True,
        null=True
    )
    remote_updated_at = models.DateTimeField(
        help_text='Date when the content transmission was last updated in the remote API',
        blank=True,
        null=True
    )
    api_response_status_code = models.PositiveIntegerField(
        help_text='The most recent remote API call response HTTP status code',
        blank=True,
        null=True
    )
    friendly_status_message = models.CharField(
        help_text='A user-friendly API response status message.',
        max_length=255,
        default=None,
        null=True,
        blank=True
    )
    marked_for = models.CharField(
        help_text='Flag marking a record as needing a form of transmitting',
        max_length=32,
        blank=True,
        null=True
    )
    api_record = models.OneToOneField(
        ApiResponseRecord,
        blank=True,
        null=True,
        on_delete=models.CASCADE,
        help_text=_('Data pertaining to the transmissions API request response.')
    )

    @classmethod
    def deleted_transmissions(cls, enterprise_customer, plugin_configuration_id, integrated_channel_code, content_id):
        """
        Return any pre-existing records for this customer/plugin/content which was previously deleted
        """
        return ContentMetadataItemTransmission.objects.filter(
            enterprise_customer=enterprise_customer,
            plugin_configuration_id=plugin_configuration_id,
            content_id=content_id,
            integrated_channel_code=integrated_channel_code,
            remote_deleted_at__isnull=False,
        )

    @classmethod
    def incomplete_create_transmissions(
        cls,
        enterprise_customer,
        plugin_configuration_id,
        integrated_channel_code,
        content_id
    ):
        """
        Return any pre-existing records for this customer/plugin/content which was created but never sent or failed
        """
        in_db_but_unsent_query = Q(
            enterprise_customer=enterprise_customer,
            plugin_configuration_id=plugin_configuration_id,
            content_id=content_id,
            integrated_channel_code=integrated_channel_code,
            remote_created_at__isnull=True,
            remote_updated_at__isnull=True,
            remote_deleted_at__isnull=True,
        )
        in_db_but_failed_to_send_query = Q(
            enterprise_customer=enterprise_customer,
            plugin_configuration_id=plugin_configuration_id,
            content_id=content_id,
            integrated_channel_code=integrated_channel_code,
            remote_created_at__isnull=False,
            remote_updated_at__isnull=True,
            remote_deleted_at__isnull=True,
            api_response_status_code__gte=400,
        )
        in_db_but_unsent_query.add(in_db_but_failed_to_send_query, Q.OR)
        return ContentMetadataItemTransmission.objects.filter(in_db_but_unsent_query)

    @classmethod
    def incomplete_update_transmissions(
        cls,
        enterprise_customer,
        plugin_configuration_id,
        integrated_channel_code,
        content_id
    ):
        """
        Return any pre-existing records for this customer/plugin/content which was updated but never sent or failed
        """
        in_db_but_failed_to_send_query = Q(
            enterprise_customer=enterprise_customer,
            plugin_configuration_id=plugin_configuration_id,
            content_id=content_id,
            integrated_channel_code=integrated_channel_code,
            remote_created_at__isnull=False,
            remote_updated_at__isnull=False,
            remote_deleted_at__isnull=True,
            api_response_status_code__gte=400,
        )
        return ContentMetadataItemTransmission.objects.filter(in_db_but_failed_to_send_query)

    @classmethod
    def incomplete_delete_transmissions(
        cls,
        enterprise_customer,
        plugin_configuration_id,
        integrated_channel_code,
        content_id
    ):
        """
        Return any pre-existing records for this customer/plugin/content which was deleted but never sent or failed
        """
        in_db_but_failed_to_send_query = Q(
            enterprise_customer=enterprise_customer,
            plugin_configuration_id=plugin_configuration_id,
            content_id=content_id,
            integrated_channel_code=integrated_channel_code,
            remote_created_at__isnull=False,
            remote_deleted_at__isnull=False,
            api_response_status_code__gte=400,
        )
        return ContentMetadataItemTransmission.objects.filter(in_db_but_failed_to_send_query)

    def _mark_transmission(self, mark_for):
        """
        Helper method to tag a transmission for any operation
        """
        self.marked_for = mark_for
        self.save()

    def mark_for_create(self):
        """
        Mark a transmission for creation
        """
        self._mark_transmission(TRANSMISSION_MARK_CREATE)

    def mark_for_update(self):
        """
        Mark a transmission for update
        """
        self._mark_transmission(TRANSMISSION_MARK_UPDATE)

    def mark_for_delete(self):
        """
        Mark a transmission for delete
        """
        self._mark_transmission(TRANSMISSION_MARK_DELETE)

    def remove_marked_for(self):
        """
        Remove and mark on a transmission
        """
        self._mark_transmission(None)

    def prepare_to_recreate(self, content_last_changed, enterprise_customer_catalog_uuid):
        """
        Prepare a deleted or unsent record to be re-created in the remote API by resetting dates and audit fields
        """
        # maintaining status code on the transmission record to aid with querying
        self.api_response_status_code = None
        if self.api_record:
            self.api_record.body = None
            self.api_record.status_code = None
        self.remote_deleted_at = None
        self.remote_created_at = None
        self.remote_updated_at = None
        self.channel_metadata = None
        self.content_last_changed = content_last_changed
        self.enterprise_customer_catalog_uuid = enterprise_customer_catalog_uuid
        self.marked_for = TRANSMISSION_MARK_CREATE
        self.save()
        return self

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


class OrphanedContentTransmissions(TimeStampedModel):
    """
    A model to track content metadata transmissions that were successfully sent to the integrated channel but then
    subsequently were orphaned by a removal of their associated catalog from the customer.
    """
    class Meta:
        index_together = [('integrated_channel_code', 'plugin_configuration_id', 'resolved')]

    integrated_channel_code = models.CharField(max_length=30)
    plugin_configuration_id = models.PositiveIntegerField(blank=False, null=False)
    content_id = models.CharField(max_length=255, blank=False, null=False)
    transmission = models.ForeignKey(
        ContentMetadataItemTransmission,
        related_name='orphaned_record',
        on_delete=models.CASCADE,
    )
    resolved = models.BooleanField(default=False)
