"""
Factoryboy factories.
"""

from uuid import UUID

import factory
from faker import Factory as FakerFactory

from django.contrib import auth
from django.contrib.sites.models import Site
from django.utils import timezone

from consent.models import DataSharingConsent, DataSharingConsentTextOverrides
from enterprise.models import (
    AdminNotification,
    EnrollmentNotificationEmailTemplate,
    EnterpriseAnalyticsUser,
    EnterpriseCatalogQuery,
    EnterpriseCourseEnrollment,
    EnterpriseCustomer,
    EnterpriseCustomerBrandingConfiguration,
    EnterpriseCustomerCatalog,
    EnterpriseCustomerIdentityProvider,
    EnterpriseCustomerInviteKey,
    EnterpriseCustomerReportingConfiguration,
    EnterpriseCustomerUser,
    LicensedEnterpriseCourseEnrollment,
    PendingEnrollment,
    PendingEnterpriseCustomerAdminUser,
    PendingEnterpriseCustomerUser,
    SystemWideEnterpriseUserRoleAssignment,
)
from enterprise.utils import SELF_ENROLL_EMAIL_TEMPLATE_TYPE, localized_utcnow
from integrated_channels.blackboard.models import (
    BlackboardEnterpriseCustomerConfiguration,
    BlackboardGlobalConfiguration,
)
from integrated_channels.canvas.models import CanvasEnterpriseCustomerConfiguration
from integrated_channels.cornerstone.models import (
    CornerstoneEnterpriseCustomerConfiguration,
    CornerstoneGlobalConfiguration,
    CornerstoneLearnerDataTransmissionAudit,
)
from integrated_channels.degreed2.models import Degreed2EnterpriseCustomerConfiguration
from integrated_channels.degreed.models import (
    DegreedEnterpriseCustomerConfiguration,
    DegreedGlobalConfiguration,
    DegreedLearnerDataTransmissionAudit,
)
from integrated_channels.integrated_channel.models import ContentMetadataItemTransmission, LearnerDataTransmissionAudit
from integrated_channels.moodle.models import MoodleEnterpriseCustomerConfiguration
from integrated_channels.sap_success_factors.models import (
    SAPSuccessFactorsEnterpriseCustomerConfiguration,
    SAPSuccessFactorsGlobalConfiguration,
    SapSuccessFactorsLearnerDataTransmissionAudit,
)
from integrated_channels.xapi.models import XAPILearnerDataTransmissionAudit, XAPILRSConfiguration

FAKER = FakerFactory.create()
User = auth.get_user_model()


# pylint: disable=no-member
class SiteFactory(factory.django.DjangoModelFactory):
    """
    Factory class for Site model.
    """

    class Meta:
        """
        Meta for ``SiteFactory``.
        """

        model = Site
        django_get_or_create = ("domain",)

    domain = factory.LazyAttribute(lambda x: FAKER.domain_name())
    name = factory.LazyAttribute(lambda x: FAKER.company())


class EnterpriseCustomerFactory(factory.django.DjangoModelFactory):
    """
    EnterpriseCustomer factory.

    Creates an instance of EnterpriseCustomer with minimal boilerplate - uses this class' attributes as default
    parameters for EnterpriseCustomer constructor.
    """

    class Meta:
        """
        Meta for EnterpriseCustomerFactory.
        """

        model = EnterpriseCustomer

    uuid = factory.LazyAttribute(lambda x: UUID(FAKER.uuid4()))
    name = factory.LazyAttribute(lambda x: FAKER.company())
    slug = factory.LazyAttribute(lambda x: FAKER.slug())
    active = True
    site = factory.SubFactory(SiteFactory)
    enable_data_sharing_consent = True
    enforce_data_sharing_consent = EnterpriseCustomer.AT_ENROLLMENT
    enable_audit_enrollment = False
    enable_audit_data_reporting = False
    hide_course_original_price = False
    country = 'US'
    contact_email = factory.LazyAttribute(lambda x: FAKER.email())
    default_language = 'en'
    sender_alias = factory.LazyAttribute(lambda x: FAKER.word())
    reply_to = factory.LazyAttribute(lambda x: FAKER.email())
    hide_labor_market_data = False


class EnrollmentNotificationEmailTemplateFactory(factory.django.DjangoModelFactory):
    """
    EnrollmentNotificationEmailTemplate factory.

    Creates an instance of EnrollmentNotificationEmailTemplate with minimal boilerplate.
    Defaults to using template_type=enterprise.utils.SELF_ENROLL_EMAIL_TEMPLATE_TYPE
    and enterprise_customer None
    """

    class Meta:
        """
        Meta for EnrollmentNotificationEmailTemplateFactory.
        """

        model = EnrollmentNotificationEmailTemplate

    enterprise_customer = factory.SubFactory(EnterpriseCustomerFactory)
    plaintext_template = ("{% load i18n %}{% if user_name %}{% blocktrans %}Dear {{ user_name }} "
                          + "{% endblocktrans %}{% endif %}{{ enrolled_in.url }}, "
                          + "{{ enrolled_in.name }}, {{ organization_name }}")
    html_template = ("{% load i18n %}<html>"
                     + "<body>{% if user_name %}{% blocktrans %}Dear {{ user_name }} "
                     + "{% endblocktrans %}{% endif %}"
                     + "{{ enrolled_in.url }}, {{ enrolled_in.name }}, {{ organization_name }}"
                     + "</body></html>")

    subject_line = 'You\'ve been enrolled in {course_name}!'
    template_type = SELF_ENROLL_EMAIL_TEMPLATE_TYPE


class EnterpriseCustomerUserFactory(factory.django.DjangoModelFactory):
    """
    EnterpriseCustomerUser factory.

    Creates an instance of EnterpriseCustomerUser with minimal boilerplate - uses this class' attributes as default
    parameters for EnterpriseCustomerUser constructor.
    """

    class Meta:
        """
        Meta for EnterpriseCustomerFactory.
        """

        model = EnterpriseCustomerUser
        django_get_or_create = ('enterprise_customer', 'user_id',)

    enterprise_customer = factory.SubFactory(EnterpriseCustomerFactory)
    user_id = factory.LazyAttribute(lambda x: FAKER.pyint())
    active = True
    linked = True
    invite_key = None


class EnterpriseAnalyticsUserFactory(factory.django.DjangoModelFactory):
    """
    EnterpriseAnalyticsUser factory.

    Creates an instance of EnterpriseAnalyticsUser with minimal boilerplate - uses this class' attributes as default
    parameters for EnterpriseAnalyticsUser constructor.
    """

    class Meta:
        """
        Meta for EnterpriseAnalyticsUserFactory.
        """

        model = EnterpriseAnalyticsUser
        django_get_or_create = ('enterprise_customer_user', 'analytics_user_id',)

    enterprise_customer_user = factory.SubFactory(EnterpriseCustomerUserFactory)
    analytics_user_id = factory.LazyAttribute(lambda x: FAKER.pyint())


class PendingEnterpriseCustomerUserFactory(factory.django.DjangoModelFactory):
    """
    PendingEnterpriseCustomerUser factory.

    Creates an instance of PendingEnterpriseCustomerUser with minimal boilerplate - uses
    this class' attributes as default parameters for PendingEnterpriseCustomerUser constructor.
    """

    class Meta:
        """
        Meta for PendingEnterpriseCustomerUserFactory.
        """

        model = PendingEnterpriseCustomerUser

    enterprise_customer = factory.SubFactory(EnterpriseCustomerFactory)
    user_email = factory.LazyAttribute(lambda x: FAKER.email())


class PendingEnterpriseCustomerAdminUserFactory(factory.django.DjangoModelFactory):
    """
    PendingEnterpriseCustomerAdminUser factory.

    Creates an instance of PendingEnterpriseCustomerAdminUser with minimal boilerplate.
    """

    class Meta:
        """
        Meta for PendingEnterpriseCustomerAdminUserFactory.
        """

        model = PendingEnterpriseCustomerAdminUser

    enterprise_customer = factory.SubFactory(EnterpriseCustomerFactory)
    user_email = factory.LazyAttribute(lambda x: FAKER.email())


class SystemWideEnterpriseUserRoleAssignmentFactory(factory.django.DjangoModelFactory):
    """
    SystemWideEnterpriseUserRoleAssignment factory.

    Creates an instance of SystemWideEnterpriseUserRoleAssignment.
    """

    class Meta:
        """
        Meta for SystemWideEnterpriseUserRoleAssignmentFactory.
        """

        model = SystemWideEnterpriseUserRoleAssignment

    enterprise_customer = factory.SubFactory(EnterpriseCustomerFactory)
    applies_to_all_contexts = False


class GroupFactory(factory.django.DjangoModelFactory):
    """
    Group factory.

    Creates an instance of Group with minimal boilerplate.
    """

    class Meta:
        model = auth.models.Group
        django_get_or_create = ('name', )

    name = factory.Sequence('group{}'.format)


class UserFactory(factory.django.DjangoModelFactory):
    """
    User factory.

    Creates an instance of User with minimal boilerplate - uses this class' attributes as default
    parameters for User constructor.
    """

    class Meta:
        """
        Meta for UserFactory.
        """

        model = User

    email = factory.LazyAttribute(lambda x: FAKER.email())
    username = factory.LazyAttribute(lambda x: FAKER.user_name())
    first_name = factory.LazyAttribute(lambda x: FAKER.first_name())
    last_name = factory.LazyAttribute(lambda x: FAKER.last_name())
    is_staff = False
    is_active = False
    date_joined = factory.LazyAttribute(lambda x: FAKER.date_time_this_year(tzinfo=timezone.utc))


class AnonymousUserFactory(factory.Factory):
    """
    Anonymous User factory.

    Creates an instance of AnonymousUser with minimal boilerplate - uses this class' attributes as default
    parameters for AnonymousUser constructor.
    """

    class Meta:
        """
        Meta for AnonymousUserFactory.
        """

        model = auth.models.AnonymousUser


class EnterpriseCustomerIdentityProviderFactory(factory.django.DjangoModelFactory):
    """
    Factory class for EnterpriseCustomerIdentityProvider model.
    """

    class Meta:
        """
        Meta for ``EnterpriseCustomerIdentityProviderFactory``.
        """

        model = EnterpriseCustomerIdentityProvider
        django_get_or_create = ("provider_id",)

    enterprise_customer = factory.SubFactory(EnterpriseCustomerFactory)
    provider_id = factory.LazyAttribute(lambda x: FAKER.slug())
    default_provider = False


class PendingEnrollmentFactory(factory.django.DjangoModelFactory):
    """
    PendingEnrollment factory.

    Create an instance of PendingEnrollment with minimal boilerplate
    """

    class Meta:
        """
        Meta for ``PendingEnrollmentFactory``.
        """

        model = PendingEnrollment

    course_id = factory.LazyAttribute(lambda x: FAKER.slug())
    course_mode = 'audit'
    user = factory.SubFactory(PendingEnterpriseCustomerUserFactory)
    cohort_name = None


class EnterpriseCustomerBrandingConfigurationFactory(factory.django.DjangoModelFactory):
    """
    EnterpriseCustomerBrandingConfiguration factory.

    Creates an instance of EnterpriseCustomerBrandingConfiguration with minimal boilerplate - uses this class'
     attributes as default parameters for EnterpriseCustomerBrandingFactory constructor.
    """

    class Meta:
        """
        Meta for EnterpriseCustomerBrandingConfigurationFactory.
        """

        model = EnterpriseCustomerBrandingConfiguration

    logo = factory.LazyAttribute(lambda x: FAKER.image_url())
    enterprise_customer = factory.SubFactory(EnterpriseCustomerFactory)
    primary_color = '#000000'
    secondary_color = '#ffffff'
    tertiary_color = '#888888'


class EnterpriseCourseEnrollmentFactory(factory.django.DjangoModelFactory):
    """
    EnterpriseCourseEnrollment factory.

    Creates an instance of EnterpriseCourseEnrollment with minimal boilerplate.
    """

    class Meta:
        """
        Meta for EnterpriseCourseEnrollmentFactory.
        """

        model = EnterpriseCourseEnrollment

    course_id = factory.LazyAttribute(lambda x: FAKER.slug())
    saved_for_later = False
    enterprise_customer_user = factory.SubFactory(EnterpriseCustomerUserFactory)


class LicensedEnterpriseCourseEnrollmentFactory(factory.django.DjangoModelFactory):
    """
    LicensedEnterpriseCourseEnrollment factory.
    """

    class Meta:
        """
        Meta for LicensedEnterpriseCourseEnrollment.
        """

        model = LicensedEnterpriseCourseEnrollment

    license_uuid = factory.LazyAttribute(lambda x: UUID(FAKER.uuid4()))
    enterprise_course_enrollment = factory.SubFactory(EnterpriseCourseEnrollmentFactory)
    is_revoked = False


class EnterpriseCatalogQueryFactory(factory.django.DjangoModelFactory):
    """
    EnterpriseCatalogQuery factory.

    Creates an instance of EnterpriseCatalogQuery with minimal boilerplate.
    """

    class Meta:
        """
        Meta for EnterpriseCatalogQuery.
        """

        model = EnterpriseCatalogQuery

    title = factory.Faker('sentence', nb_words=4)
    uuid = factory.LazyAttribute(lambda x: UUID(FAKER.uuid4()))


class EnterpriseCustomerCatalogFactory(factory.django.DjangoModelFactory):
    """
    EnterpriseCustomerCatalog factory.

    Creates an instance of EnterpriseCustomerCatalog with minimal boilerplate.
    """

    class Meta:
        """
        Meta for EnterpriseCustomerCatalog.
        """

        model = EnterpriseCustomerCatalog

    uuid = factory.LazyAttribute(lambda x: UUID(FAKER.uuid4()))
    enterprise_customer = factory.SubFactory(EnterpriseCustomerFactory)
    enterprise_catalog_query = factory.SubFactory(EnterpriseCatalogQueryFactory)


class DataSharingConsentFactory(factory.django.DjangoModelFactory):
    """
    ``DataSharingConsent`` factory.

    Creates an instance of ``DataSharingConsent`` with minimal boilerplate.
    """

    class Meta:
        """
        Meta for ``DataSharingConsentFactory``.
        """

        model = DataSharingConsent

    enterprise_customer = factory.SubFactory(EnterpriseCustomerFactory)
    username = factory.LazyAttribute(lambda x: FAKER.user_name())
    course_id = factory.LazyAttribute(lambda x: FAKER.slug())
    granted = True


class DataSharingConsentTextOverridesFactory(factory.django.DjangoModelFactory):
    """
    ``DataSharingConsentTextOverrides`` factory.

    Creates an instance of ``DataSharingConsentTextOverrides`` with minimal boilerplate.
    """

    class Meta:
        """
        Meta for ``DataSharingConsentTextOverridesFactory``.
        """

        model = DataSharingConsentTextOverrides

    enterprise_customer = factory.SubFactory(EnterpriseCustomerFactory)
    published = True


class EnterpriseCustomerReportingConfigFactory(factory.django.DjangoModelFactory):
    """
    ``EnterpriseCustomerReportingConfiguration`` factory.

    Creates an instance of EnterpriseCustomerReportingConfiguration with minimal boilerplate
    uses this class' attributes as default parameters for EnterpriseCustomerReportingConfiguration constructor.
    """

    class Meta:
        """
        Meta for ``EnterpriseCustomerReportingConfigFactory``.
        """

        model = EnterpriseCustomerReportingConfiguration

    active = True
    email = factory.LazyAttribute(lambda x: FAKER.email())
    day_of_month = 1
    hour_of_day = 1
    enterprise_customer = factory.SubFactory(EnterpriseCustomerFactory)


class SAPSuccessFactorsGlobalConfigurationFactory(factory.django.DjangoModelFactory):
    """
    ``SAPSuccessFactorsGlobalConfiguration`` factory.

    Creates an instance of ``SAPSuccessFactorsGlobalConfiguration`` with minimal boilerplate.
    """

    class Meta:
        """
        Meta for ``SAPSuccessFactorsGlobalConfigurationFactory``.
        """

        model = SAPSuccessFactorsGlobalConfiguration

    completion_status_api_path = factory.LazyAttribute(lambda x: FAKER.file_path())
    course_api_path = factory.LazyAttribute(lambda x: FAKER.file_path())
    oauth_api_path = factory.LazyAttribute(lambda x: FAKER.file_path())
    provider_id = 'SAP'


class SAPSuccessFactorsEnterpriseCustomerConfigurationFactory(factory.django.DjangoModelFactory):
    """
    ``SAPSuccessFactorsEnterpriseCustomerConfiguration`` factory.

    Creates an instance of ``SAPSuccessFactorsEnterpriseCustomerConfiguration`` with minimal boilerplate.
    """

    class Meta:
        """
        Meta for ``SAPSuccessFactorsEnterpriseCustomerConfigurationFactory``.
        """

        model = SAPSuccessFactorsEnterpriseCustomerConfiguration

    enterprise_customer = factory.SubFactory(EnterpriseCustomerFactory)
    active = True
    sapsf_base_url = factory.LazyAttribute(lambda x: FAKER.url())
    sapsf_company_id = factory.LazyAttribute(lambda x: FAKER.company())
    sapsf_user_id = factory.LazyAttribute(lambda x: FAKER.pyint())
    user_type = SAPSuccessFactorsEnterpriseCustomerConfiguration.USER_TYPE_USER
    idp_id = ''


class SapSuccessFactorsLearnerDataTransmissionAuditFactory(factory.django.DjangoModelFactory):
    """
    ``SapSuccessFactorsLearnerDataTransmissionAudit`` factory.

    Creates an instance of ``SapSuccessFactorsLearnerDataTransmissionAudit`` with minimal boilerplate.
    """

    class Meta:
        """
        Meta for ``SapSuccessFactorsLearnerDataTransmissionAuditFactory``.
        """

        model = SapSuccessFactorsLearnerDataTransmissionAudit

    sapsf_user_id = factory.LazyAttribute(lambda x: FAKER.pyint())
    enterprise_course_enrollment_id = factory.LazyAttribute(lambda x: FAKER.random_int(min=1))
    course_id = factory.LazyAttribute(lambda x: FAKER.slug())
    course_completed = True
    completed_timestamp = factory.LazyAttribute(lambda x: FAKER.random_int(min=1))
    instructor_name = factory.LazyAttribute(lambda x: FAKER.name())
    grade = factory.LazyAttribute(lambda x: FAKER.bothify('?', letters='ABCDF') + FAKER.bothify('?', letters='+-'))
    status = factory.LazyAttribute(lambda x: FAKER.word())


class DegreedGlobalConfigurationFactory(factory.django.DjangoModelFactory):
    """
    ``DegreedGlobalConfiguration`` factory.

    Creates an instance of ``DegreedGlobalConfiguration`` with minimal boilerplate.
    """

    class Meta:
        """
        Meta for ``DegreedGlobalConfigurationFactory``.
        """

        model = DegreedGlobalConfiguration

    completion_status_api_path = factory.LazyAttribute(lambda x: FAKER.file_path())
    course_api_path = factory.LazyAttribute(lambda x: FAKER.file_path())
    oauth_api_path = factory.LazyAttribute(lambda x: FAKER.file_path())


class DegreedEnterpriseCustomerConfigurationFactory(factory.django.DjangoModelFactory):
    """
    ``DegreedEnterpriseCustomerConfiguration`` factory.

    Creates an instance of ``DegreedEnterpriseCustomerConfiguration`` with minimal boilerplate.
    """

    class Meta:
        """
        Meta for ``DegreedEnterpriseCustomerConfigurationFactory``.
        """

        model = DegreedEnterpriseCustomerConfiguration

    enterprise_customer = factory.SubFactory(EnterpriseCustomerFactory)
    active = True
    degreed_company_id = factory.LazyAttribute(lambda x: FAKER.company())
    degreed_base_url = factory.LazyAttribute(lambda x: FAKER.url())
    degreed_user_id = factory.LazyAttribute(lambda x: FAKER.user_name())
    degreed_user_password = factory.LazyAttribute(lambda x: FAKER.word())
    provider_id = 'DEGREED'


class Degreed2EnterpriseCustomerConfigurationFactory(factory.django.DjangoModelFactory):
    """
    ``Degreed2EnterpriseCustomerConfiguration`` factory.

    Creates an instance of ``Degreed2EnterpriseCustomerConfiguration`` with minimal boilerplate.
    """

    class Meta:
        """
        Meta for ``Degreed2EnterpriseCustomerConfigurationFactory``.
        """

        model = Degreed2EnterpriseCustomerConfiguration

    enterprise_customer = factory.SubFactory(EnterpriseCustomerFactory)
    active = True
    degreed_base_url = factory.LazyAttribute(lambda x: FAKER.url())
    degreed_token_fetch_base_url = factory.LazyAttribute(lambda x: FAKER.url())
    client_id = factory.LazyAttribute(lambda x: FAKER.uuid4())
    client_secret = factory.LazyAttribute(lambda x: FAKER.uuid4())


class DegreedLearnerDataTransmissionAuditFactory(factory.django.DjangoModelFactory):
    """
    ``DegreedLearnerDataTransmissionAudit`` factory.

    Creates an instance of ``DegreedLearnerDataTransmissionAudit`` with minimal boilerplate.
    """

    class Meta:
        """
        Meta for ``DegreedLearnerDataTransmissionAuditFactory``.
        """

        model = DegreedLearnerDataTransmissionAudit

    degreed_user_email = factory.LazyAttribute(lambda x: FAKER.email())
    enterprise_course_enrollment_id = factory.LazyAttribute(lambda x: FAKER.random_int(min=1))
    course_id = factory.LazyAttribute(lambda x: FAKER.slug())
    course_completed = True
    completed_timestamp = factory.LazyAttribute(lambda x: FAKER.random_int(min=1))
    status = factory.LazyAttribute(lambda x: FAKER.word())


class CornerstoneLearnerDataTransmissionAuditFactory(factory.django.DjangoModelFactory):
    """
    ``CornerstoneLearnerDataTransmissionAudit`` factory.

    Creates an instance of ``CornerstoneLearnerDataTransmissionAudit`` with minimal boilerplate.
    """

    class Meta:
        """
        Meta for ``CornerstoneLearnerDataTransmissionAuditFactory``.
        """

        model = CornerstoneLearnerDataTransmissionAudit
        django_get_or_create = ('user_id', 'course_id', )

    user_id = factory.LazyAttribute(lambda x: FAKER.pyint())
    course_id = factory.LazyAttribute(lambda x: FAKER.slug())
    user_guid = factory.LazyAttribute(lambda x: FAKER.slug())
    session_token = factory.LazyAttribute(lambda x: FAKER.slug())
    callback_url = factory.LazyAttribute(lambda x: FAKER.slug())
    subdomain = factory.LazyAttribute(lambda x: FAKER.slug())


class CornerstoneEnterpriseCustomerConfigurationFactory(factory.django.DjangoModelFactory):
    """
    ``CornerstoneEnterpriseCustomerConfiguration`` factory.

    Creates an instance of ``CornerstoneEnterpriseCustomerConfiguration`` with minimal boilerplate.
    """

    class Meta:
        """
        Meta for ``CornerstoneEnterpriseCustomerConfiguration``.
        """

        model = CornerstoneEnterpriseCustomerConfiguration

    enterprise_customer = factory.SubFactory(EnterpriseCustomerFactory)
    active = True
    cornerstone_base_url = factory.LazyAttribute(lambda x: FAKER.url())


class CornerstoneGlobalConfigurationFactory(factory.django.DjangoModelFactory):
    """
    ``CornerstoneGlobalConfiguration`` factory.

    Creates an instance of ``CornerstoneGlobalConfiguration`` with minimal boilerplate.
    """

    class Meta:
        """
        Meta for ``CornerstoneGlobalConfiguration``.
        """

        model = CornerstoneGlobalConfiguration

    completion_status_api_path = '/progress'
    key = factory.LazyAttribute(lambda x: FAKER.slug())
    secret = factory.LazyAttribute(lambda x: FAKER.uuid4())
    oauth_api_path = factory.LazyAttribute(lambda x: FAKER.file_path())
    subject_mapping = {
        "Technology": ["Computer Science"],
        "Business Skills": ["Communication"],
        "Creative": ["Music", "Design"]
    }
    languages = {"Languages": ["es-ES", "en-US", "ja-JP", "zh-CN"]}


class XAPILRSConfigurationFactory(factory.django.DjangoModelFactory):
    """
    ``XAPILRSConfiguration`` factory.

    Creates an instance of ``XAPILRSConfiguration`` with minimal boilerplate.
    """

    class Meta:
        """
        Meta for ``XAPILRSConfiguration``.
        """

        model = XAPILRSConfiguration

    enterprise_customer = factory.SubFactory(EnterpriseCustomerFactory)
    version = '1.0.1'
    endpoint = factory.LazyAttribute(lambda x: FAKER.url())
    key = factory.LazyAttribute(lambda x: FAKER.slug())
    secret = factory.LazyAttribute(lambda x: FAKER.uuid4())
    active = True


class XAPILearnerDataTransmissionAuditFactory(factory.django.DjangoModelFactory):
    """
    ``XAPILearnerDataTransmissionAudit`` factory.

    Creates an instance of ``XAPILearnerDataTransmissionAudit`` with minimal boilerplate.
    """

    class Meta:
        """
        Meta for ``XAPILearnerDataTransmissionAuditFactory``.
        """

        model = XAPILearnerDataTransmissionAudit

    user_id = factory.LazyAttribute(lambda x: FAKER.pyint())
    course_id = factory.LazyAttribute(lambda x: FAKER.slug())


class BlackboardGlobalConfigurationFactory(factory.django.DjangoModelFactory):
    """
    ``BlackboardGlobalConfiguration`` factory.

    Creates an instance of ``BlackboardGlobalConfiguration`` with minimal boilerplate.
    """

    class Meta:
        """
        Meta for ``BlackboardGlobalConfiguration``.
        """

        model = BlackboardGlobalConfiguration

    app_key = factory.LazyAttribute(lambda x: FAKER.random_int(min=1))
    app_secret = factory.LazyAttribute(lambda x: FAKER.uuid4())


class BlackboardEnterpriseCustomerConfigurationFactory(factory.django.DjangoModelFactory):
    """
    ``BlackboardEnterpriseCustomerConfiguration`` factory.

    Creates an instance of ``BlackboardEnterpriseCustomerConfiguration`` with minimal boilerplate.
    """

    class Meta:
        """
        Meta for ``BlackboardEnterpriseCustomerConfiguration``.
        """

        model = BlackboardEnterpriseCustomerConfiguration

    enterprise_customer = factory.SubFactory(EnterpriseCustomerFactory)
    active = True
    blackboard_base_url = factory.LazyAttribute(lambda x: FAKER.url())
    client_id = factory.LazyAttribute(lambda x: FAKER.random_int(min=1))
    client_secret = factory.LazyAttribute(lambda x: FAKER.uuid4())
    refresh_token = factory.LazyAttribute(lambda x: FAKER.uuid4())


class CanvasEnterpriseCustomerConfigurationFactory(factory.django.DjangoModelFactory):
    """
    ``CanvasEnterpriseCustomerConfiguration`` factory.

    Creates an instance of ``CanvasEnterpriseCustomerConfiguration`` with minimal boilerplate.
    """

    class Meta:
        """
        Meta for ``CanvasEnterpriseCustomerConfiguration``.
        """

        model = CanvasEnterpriseCustomerConfiguration

    enterprise_customer = factory.SubFactory(EnterpriseCustomerFactory)
    active = True
    canvas_account_id = 2
    canvas_base_url = factory.LazyAttribute(lambda x: FAKER.url())


class MoodleEnterpriseCustomerConfigurationFactory(factory.django.DjangoModelFactory):
    """
    ``MoodleEnterpriseCustomerConfiguration`` factory.

    Creates an instance of ``MoodleEnterpriseCustomerConfiguration`` with minimal boilerplate.
    """

    class Meta:
        """
        Meta for ``MoodleGlobalConfigurationFactory``.
        """

        model = MoodleEnterpriseCustomerConfiguration

    active = True
    enterprise_customer = factory.SubFactory(EnterpriseCustomerFactory)
    moodle_base_url = factory.LazyAttribute(lambda x: FAKER.url())
    service_short_name = factory.LazyAttribute(lambda x: FAKER.slug())
    token = factory.LazyAttribute(lambda x: FAKER.slug())


class AdminNotificationFactory(factory.django.DjangoModelFactory):
    """
    ``AdminNotification`` factory.

    Creates an instance of ``AdminNotification`` with minimal boilerplate.
    """

    class Meta:
        """
        Meta for ``AdminNotification``.
        """

        model = AdminNotification

    is_active = True
    text = factory.LazyAttribute(lambda x: FAKER.word())
    start_date = factory.Faker('date_object')
    expiration_date = factory.Faker('date_object')


class ContentMetadataItemTransmissionFactory(factory.django.DjangoModelFactory):
    """
    ``ContentMetadataItemTransmission`` factory.

    Create an instance of ``ContentMetadataItemTransmission`` with minimal boilerplate.
    """

    class Meta:
        """
        Meta for ``ContentMetadataItemTransmission``.
        """
        model = ContentMetadataItemTransmission

    enterprise_customer = factory.SubFactory(EnterpriseCustomerFactory)
    integrated_channel_code = 'CORNERSTONE'
    content_id = factory.LazyAttribute(lambda x: FAKER.slug())
    channel_metadata = {
        'title': 'edX Demonstration Course',
        'key': 'edX+DemoX',
        'content_type': 'course',
        'start': '2030-01-01T00:00:00Z',
        'end': '2030-03-01T00:00:00Z'
    }


class EnterpriseCustomerInviteKeyFactory(factory.django.DjangoModelFactory):
    """
    EnterpriseCustomerInviteKey factory.

    Creates an instance of EnterpriseCustomerInviteKey with minimal boilerplate.
    """

    class Meta:
        """
        Meta for EnterpriseCustomerInviteKeyFactory.
        """

        model = EnterpriseCustomerInviteKey

    uuid = factory.LazyAttribute(lambda x: UUID(FAKER.uuid4()))
    enterprise_customer = factory.SubFactory(EnterpriseCustomerFactory)
    usage_limit = 10
    expiration_date = localized_utcnow()
    is_active = True
