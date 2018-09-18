# -*- coding: utf-8 -*-
"""
Factoryboy factories.
"""

from __future__ import absolute_import, unicode_literals

from uuid import UUID

import factory
from faker import Factory as FakerFactory

from django.contrib.auth.models import Group, User
from django.contrib.sites.models import Site
from django.utils import timezone

from consent.models import DataSharingConsent, DataSharingConsentTextOverrides
from enterprise.models import (
    EnterpriseCourseEnrollment,
    EnterpriseCustomer,
    EnterpriseCustomerBrandingConfiguration,
    EnterpriseCustomerCatalog,
    EnterpriseCustomerEntitlement,
    EnterpriseCustomerIdentityProvider,
    EnterpriseCustomerReportingConfiguration,
    EnterpriseCustomerUser,
    PendingEnrollment,
    PendingEnterpriseCustomerUser,
)
from integrated_channels.degreed.models import (
    DegreedEnterpriseCustomerConfiguration,
    DegreedGlobalConfiguration,
    DegreedLearnerDataTransmissionAudit,
)
from integrated_channels.integrated_channel.models import LearnerDataTransmissionAudit
from integrated_channels.sap_success_factors.models import (
    SAPSuccessFactorsEnterpriseCustomerConfiguration,
    SAPSuccessFactorsGlobalConfiguration,
    SapSuccessFactorsLearnerDataTransmissionAudit,
)
from integrated_channels.xapi.models import XAPILRSConfiguration

FAKER = FakerFactory.create()


# pylint: disable=no-member
# pylint: disable=invalid-name
class SiteFactory(factory.django.DjangoModelFactory):
    """
    Factory class for Site model.
    """

    class Meta(object):
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

    class Meta(object):
        """
        Meta for EnterpriseCustomerFactory.
        """

        model = EnterpriseCustomer

    uuid = factory.LazyAttribute(lambda x: UUID(FAKER.uuid4()))
    name = factory.LazyAttribute(lambda x: FAKER.company())
    slug = factory.LazyAttribute(lambda x: FAKER.slug())
    active = True
    site = factory.SubFactory(SiteFactory)
    catalog = factory.LazyAttribute(lambda x: FAKER.random_int(min=0, max=1000000))
    enable_data_sharing_consent = True
    enforce_data_sharing_consent = EnterpriseCustomer.AT_ENROLLMENT
    hide_course_original_price = False


class EnterpriseCustomerUserFactory(factory.django.DjangoModelFactory):
    """
    EnterpriseCustomer factory.

    Creates an instance of EnterpriseCustomerUser with minimal boilerplate - uses this class' attributes as default
    parameters for EnterpriseCustomerUser constructor.
    """

    class Meta(object):
        """
        Meta for EnterpriseCustomerFactory.
        """

        model = EnterpriseCustomerUser

    enterprise_customer = factory.SubFactory(EnterpriseCustomerFactory)
    user_id = factory.LazyAttribute(lambda x: FAKER.pyint())
    active = True


class PendingEnterpriseCustomerUserFactory(factory.django.DjangoModelFactory):
    """
    EnterpriseCustomer factory.

    Creates an instance of EnterpriseCustomerUser with minimal boilerplate - uses this class' attributes as default
    parameters for EnterpriseCustomerUser constructor.
    """

    class Meta(object):
        """
        Meta for EnterpriseCustomerFactory.
        """

        model = PendingEnterpriseCustomerUser

    enterprise_customer = factory.SubFactory(EnterpriseCustomerFactory)
    user_email = factory.LazyAttribute(lambda x: FAKER.email())


class GroupFactory(factory.DjangoModelFactory):
    """
    Group factory.

    Creates an instance of Group with minimal boilerplate.
    """

    class Meta(object):
        model = Group
        django_get_or_create = ('name', )

    name = factory.Sequence(u'group{0}'.format)


class UserFactory(factory.DjangoModelFactory):
    """
    User factory.

    Creates an instance of User with minimal boilerplate - uses this class' attributes as default
    parameters for User constructor.
    """

    class Meta(object):
        """
        Meta for UserFactory.
        """

        model = User

    id = factory.LazyAttribute(lambda x: FAKER.random_int(min=1))
    email = factory.LazyAttribute(lambda x: FAKER.email())
    username = factory.LazyAttribute(lambda x: FAKER.user_name())
    first_name = factory.LazyAttribute(lambda x: FAKER.first_name())
    last_name = factory.LazyAttribute(lambda x: FAKER.last_name())
    is_staff = False
    is_active = False
    date_joined = factory.LazyAttribute(lambda x: FAKER.date_time_this_year(tzinfo=timezone.utc))


class EnterpriseCustomerIdentityProviderFactory(factory.django.DjangoModelFactory):
    """
    Factory class for EnterpriseCustomerIdentityProvider model.
    """

    class Meta(object):
        """
        Meta for ``EnterpriseCustomerIdentityProviderFactory``.
        """

        model = EnterpriseCustomerIdentityProvider
        django_get_or_create = ("provider_id",)

    enterprise_customer = factory.SubFactory(EnterpriseCustomerFactory)
    provider_id = factory.LazyAttribute(lambda x: FAKER.slug())


class PendingEnrollmentFactory(factory.django.DjangoModelFactory):
    """
    PendingEnrollment factory.

    Create an instance of PendingEnrollment with minimal boilerplate
    """

    class Meta(object):
        """
        Meta for ``PendingEnrollmentFactory``.
        """

        model = PendingEnrollment

    course_id = factory.LazyAttribute(lambda x: FAKER.slug())
    course_mode = 'audit'
    user = factory.SubFactory(PendingEnterpriseCustomerUserFactory)
    cohort_name = None


class EnterpriseCustomerEntitlementFactory(factory.django.DjangoModelFactory):
    """
    EnterpriseCustomerEntitlement factory.

    Creates an instance of EnterpriseCustomerEntitlement with minimal boilerplate - uses this class' attributes as
    default parameters for EnterpriseCustomerEntitlementFactory constructor.
    """

    class Meta(object):
        """
        Meta for EnterpriseCustomerEntitlementFactory.
        """

        model = EnterpriseCustomerEntitlement

    id = factory.LazyAttribute(lambda x: FAKER.random_int(min=1))
    entitlement_id = factory.LazyAttribute(lambda x: FAKER.random_int(min=1))
    enterprise_customer = factory.SubFactory(EnterpriseCustomerFactory)


class EnterpriseCustomerBrandingConfigurationFactory(factory.django.DjangoModelFactory):
    """
    EnterpriseCustomerBrandingConfiguration factory.

    Creates an instance of EnterpriseCustomerBrandingConfiguration with minimal boilerplate - uses this class'
     attributes as default parameters for EnterpriseCustomerBrandingFactory constructor.
    """

    class Meta(object):
        """
        Meta for EnterpriseCustomerBrandingConfigurationFactory.
        """

        model = EnterpriseCustomerBrandingConfiguration

    id = factory.LazyAttribute(lambda x: FAKER.random_int(min=1))
    logo = factory.LazyAttribute(lambda x: FAKER.image_url())
    enterprise_customer = factory.SubFactory(EnterpriseCustomerFactory)


class EnterpriseCourseEnrollmentFactory(factory.django.DjangoModelFactory):
    """
    EnterpriseCourseEnrollment factory.

    Creates an instance of EnterpriseCourseEnrollment with minimal boilerplate.
    """

    class Meta(object):
        """
        Meta for EnterpriseCourseEnrollmentFactory.
        """

        model = EnterpriseCourseEnrollment

    id = factory.LazyAttribute(lambda x: FAKER.random_int(min=1))
    course_id = factory.LazyAttribute(lambda x: FAKER.slug())
    enterprise_customer_user = factory.SubFactory(EnterpriseCustomerUserFactory)


class EnterpriseCustomerCatalogFactory(factory.django.DjangoModelFactory):
    """
    EnterpriseCustomerCatalog factory.

    Creates an instance of EnterpriseCustomerCatalog with minimal boilerplate.
    """

    class Meta(object):
        """
        Meta for EnterpriseCustomerCatalog.
        """

        model = EnterpriseCustomerCatalog

    uuid = factory.LazyAttribute(lambda x: UUID(FAKER.uuid4()))
    enterprise_customer = factory.SubFactory(EnterpriseCustomerFactory)


class DataSharingConsentFactory(factory.django.DjangoModelFactory):
    """
    ``DataSharingConsent`` factory.

    Creates an instance of ``DataSharingConsent`` with minimal boilerplate.
    """

    class Meta(object):
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

    class Meta(object):
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

    class Meta(object):
        """
        Meta for ``EnterpriseCustomerReportingConfigFactory``.
        """

        model = EnterpriseCustomerReportingConfiguration

    id = factory.LazyAttribute(lambda x: FAKER.random_int(min=1))
    active = True
    email = factory.LazyAttribute(lambda x: FAKER.email())
    day_of_month = 1
    hour_of_day = 1
    enterprise_customer = factory.SubFactory(EnterpriseCustomerFactory)


class LearnerDataTransmissionAuditFactory(factory.django.DjangoModelFactory):
    """
    ``LearnerDataTransmissionAudit`` factory.

    Creates an instance of ``LearnerDataTransmissionAudit`` with minimal boilerplate.
    """

    class Meta(object):
        """
        Meta for ``LearnerDataTransmissionAuditFactory``.
        """

        model = LearnerDataTransmissionAudit

    enterprise_course_enrollment_id = factory.LazyAttribute(lambda x: FAKER.random_int(min=1))
    course_id = factory.LazyAttribute(lambda x: FAKER.slug())
    course_completed = True
    completed_timestamp = factory.LazyAttribute(lambda x: FAKER.random_int(min=1))
    instructor_name = factory.LazyAttribute(lambda x: FAKER.name())
    grade = factory.LazyAttribute(lambda x: FAKER.bothify('?', letters='ABCDF') + FAKER.bothify('?', letters='+-'))
    status = factory.LazyAttribute(lambda x: FAKER.word())


class SAPSuccessFactorsGlobalConfigurationFactory(factory.django.DjangoModelFactory):
    """
    ``SAPSuccessFactorsGlobalConfiguration`` factory.

    Creates an instance of ``SAPSuccessFactorsGlobalConfiguration`` with minimal boilerplate.
    """

    class Meta(object):
        """
        Meta for ``SAPSuccessFactorsGlobalConfigurationFactory``.
        """

        model = SAPSuccessFactorsGlobalConfiguration

    id = factory.LazyAttribute(lambda x: FAKER.random_int(min=1))
    completion_status_api_path = factory.LazyAttribute(lambda x: FAKER.file_path())
    course_api_path = factory.LazyAttribute(lambda x: FAKER.file_path())
    oauth_api_path = factory.LazyAttribute(lambda x: FAKER.file_path())
    provider_id = 'SAP'


class SAPSuccessFactorsEnterpriseCustomerConfigurationFactory(factory.django.DjangoModelFactory):
    """
    ``SAPSuccessFactorsEnterpriseCustomerConfiguration`` factory.

    Creates an instance of ``SAPSuccessFactorsEnterpriseCustomerConfiguration`` with minimal boilerplate.
    """

    class Meta(object):
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


class SapSuccessFactorsLearnerDataTransmissionAuditFactory(factory.django.DjangoModelFactory):
    """
    ``SapSuccessFactorsLearnerDataTransmissionAudit`` factory.

    Creates an instance of ``SapSuccessFactorsLearnerDataTransmissionAudit`` with minimal boilerplate.
    """

    class Meta(object):
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

    class Meta(object):
        """
        Meta for ``DegreedGlobalConfigurationFactory``.
        """

        model = DegreedGlobalConfiguration

    id = factory.LazyAttribute(lambda x: FAKER.random_int(min=1))
    completion_status_api_path = factory.LazyAttribute(lambda x: FAKER.file_path())
    course_api_path = factory.LazyAttribute(lambda x: FAKER.file_path())
    oauth_api_path = factory.LazyAttribute(lambda x: FAKER.file_path())


class DegreedEnterpriseCustomerConfigurationFactory(factory.django.DjangoModelFactory):
    """
    ``DegreedEnterpriseCustomerConfiguration`` factory.

    Creates an instance of ``DegreedEnterpriseCustomerConfiguration`` with minimal boilerplate.
    """

    class Meta(object):
        """
        Meta for ``DegreedEnterpriseCustomerConfigurationFactory``.
        """

        model = DegreedEnterpriseCustomerConfiguration

    enterprise_customer = factory.SubFactory(EnterpriseCustomerFactory)
    active = True
    degreed_company_id = factory.LazyAttribute(lambda x: FAKER.company())
    degreed_base_url = factory.LazyAttribute(lambda x: FAKER.file_path())
    degreed_user_id = factory.LazyAttribute(lambda x: FAKER.user_name())
    degreed_user_password = factory.LazyAttribute(lambda x: FAKER.word())
    provider_id = 'DEGREED'


class DegreedLearnerDataTransmissionAuditFactory(factory.django.DjangoModelFactory):
    """
    ``DegreedLearnerDataTransmissionAudit`` factory.

    Creates an instance of ``DegreedLearnerDataTransmissionAudit`` with minimal boilerplate.
    """

    class Meta(object):
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


class XAPILRSConfigurationFactory(factory.django.DjangoModelFactory):
    """
    ``XAPILRSConfiguration`` factory.

    Creates an instance of ``XAPILRSConfiguration`` with minimal boilerplate.
    """

    class Meta(object):
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
