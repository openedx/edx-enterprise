"""
Database models for Enterprise Integrated Channel.
"""
from __future__ import absolute_import, unicode_literals

from django.db import models
from django.utils.encoding import python_2_unicode_compatible
from django.utils.translation import ugettext_lazy as _
from model_utils.models import TimeStampedModel

from enterprise.models import EnterpriseCustomer, EnterpriseCourseEnrollment
from enterprise.utils import NotConnectedToOpenEdX

try:
    from certificates.api import GeneratedCertificate
except ImportError:
    GeneratedCertificate = None

try:
    from opaque_keys.edx.keys import CourseKey
except ImportError:
    CourseKey = None


@python_2_unicode_compatible
class EnterpriseIntegratedChannel(TimeStampedModel):
    """
    Store information related to integrating with external enterprise systems.

    EnterpriseIntegratedChannel is an external system that the Enterprise Customer uses to manage enterprise
    related data. Each of these requires an edx plugin in order to send data to these systems, this model stores
    information related to what and where to send data from the enterprise app.
    """

    name = models.CharField(max_length=255, blank=False, null=False, help_text=_("Third Party name."))
    data_type = models.CharField(max_length=100, blank=False, null=False, help_text=_("Data Type"))

    class Meta:
        app_label = 'integrated_channel'
        verbose_name = _("Enterprise Integrated Channel")
        verbose_name_plural = _("Enterprise Integrated Channels")
        unique_together = (("name", "data_type"),)

    def __str__(self):
        """
        Return human-readable string representation.
        """
        return "<EnterpriseIntegratedChannel {name} for {data_type} data with id {id}>".format(
            name=self.name,
            data_type=self.data_type,
            id=self.id
        )

    def __repr__(self):
        """
        Return uniquely identifying string representation.
        """
        return self.__str__()


class EnterpriseCustomerPluginConfiguration(TimeStampedModel):
    """
    Abstract base class for information related to integrating with external systems for an enterprise customer.

    EnterpriseCustomerPluginConfiguration will be extended by the configuration models in other integrated channel's
    apps to provide uniformity across different integrated channels.
    """

    enterprise_customer = models.OneToOneField(
        EnterpriseCustomer, blank=False, null=False
    )
    active = models.BooleanField(blank=False, null=False)

    class Meta:
        abstract = True

    @staticmethod
    def channel_code():
        """
        Returns an capitalized identifier for this channel class, unique among subclasses.
        """
        raise NotImplementedError(_('Implemented in concrete subclass.'))

    def transmit_learner_data(self):
        """
        Collect and transmit learner data for the ``EnterpriseCustomer``.
        """
        transmitter = self.get_learner_data_transmitter()
        for learner_data in self.collect_learner_data():
            transmitter.transmit(learner_data)

    def collect_learner_data(self):
        """
        Collect learner data for the ``EnterpriseCustomer`` where data sharing consent is granted.

        Yields a learner data object for each enrollment, containing:

        * ``enterprise_enrollment``: ``EnterpriseCourseEnrollment`` object.
        * ``certificate``: ``GeneratedCertificate`` for the user+course; None if not found.
          "Course completion" occurs when course certificates are issued.
        """

        if CourseKey is None or GeneratedCertificate is None:
            raise NotConnectedToOpenEdX(_('This package must be installed in an OpenEdX environment.'))

        # Fetch the consenting enrollment data, including the enterprise_customer_user
        enrollment_queryset = EnterpriseCourseEnrollment.objects.select_related(
            'enterprise_customer_user'
        ).filter(
            enterprise_customer_user__enterprise_customer=self.enterprise_customer,
        )
        for enterprise_enrollment in enrollment_queryset:

            # Omit any enrollments where consent has not been granted
            if not enterprise_enrollment.consent_available():
                continue

            # Fetch the user+course certificate, if found
            try:
                certificate = GeneratedCertificate.eligible_certificates.get(
                    user__id=enterprise_enrollment.enterprise_customer_user.user_id,
                    course_id=CourseKey.from_string(enterprise_enrollment.course_id),
                )
            except GeneratedCertificate.DoesNotExist:
                certificate = None

            yield self.get_learner_data(
                enterprise_enrollment=enterprise_enrollment,
                certificate=certificate,
            )

    def get_learner_data(self, enterprise_enrollment, certificate):
        """
        Returns the class that can serialize the learner completion data to the integrated channel.
        """
        raise NotImplementedError(_('Implemented in concrete subclass.'))

    def get_learner_data_transmitter(self):
        """
        Returns the class that can transmit the learner completion data to the integrated channel.
        """
        raise NotImplementedError("Implemented in concrete subclass.")

    def get_course_data_exporter(self, user):
        """
        Returns a class that can retrieve, transform, and serialize the courseware data to the integrated channel.
        """
        raise NotImplementedError("Implemented in concrete subclass.")

    def get_course_data_transmitter(self):
        """
        Returns a class that can transmit the courseware data to the integrated channel.
        """
        raise NotImplementedError("Implemented in concrete subclass.")

    def transmit_course_data(self, user):
        """
        Compose the details from the concrete subclass to transmit the relevant data.
        """
        course_data_exporter = self.get_course_data_exporter(user)
        transmitter = self.get_course_data_transmitter()
        transmitter.transmit(course_data_exporter)
