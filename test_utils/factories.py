"""
Factoryboy factories.
"""
from __future__ import absolute_import, unicode_literals

from uuid import UUID

import factory
from consent.models import DataSharingConsent
from faker import Factory as FakerFactory

from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from django.utils import timezone

from enterprise.models import (
    EnterpriseCourseEnrollment,
    EnterpriseCustomer,
    EnterpriseCustomerCatalog,
    EnterpriseCustomerEntitlement,
    EnterpriseCustomerIdentityProvider,
    EnterpriseCustomerUser,
    PendingEnrollment,
    PendingEnterpriseCustomerUser,
    UserDataSharingConsentAudit,
)

FAKER = FakerFactory.create()


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

    domain = factory.LazyAttribute(lambda x: FAKER.domain_name())  # pylint: disable=no-member
    name = factory.LazyAttribute(lambda x: FAKER.company())  # pylint: disable=no-member


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

    uuid = factory.LazyAttribute(lambda x: UUID(FAKER.uuid4()))  # pylint: disable=no-member
    name = factory.LazyAttribute(lambda x: FAKER.company())  # pylint: disable=no-member
    active = True
    site = factory.SubFactory(SiteFactory)
    catalog = factory.LazyAttribute(lambda x: FAKER.random_int(min=0, max=1000000))  # pylint: disable=no-member
    enable_data_sharing_consent = True
    enforce_data_sharing_consent = EnterpriseCustomer.AT_ENROLLMENT


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
    user_id = factory.LazyAttribute(lambda x: FAKER.pyint())  # pylint: disable=no-member


class UserDataSharingConsentAuditFactory(factory.django.DjangoModelFactory):
    """
    UserDataSharingConsentAuditFactory.

    Creates an instance of UserDataSharingConsentAudit with minimal boilerplate.
    """

    class Meta(object):
        """
        Meta for ``UserDataSharingConsentAuditFactory``.
        """

        model = UserDataSharingConsentAudit

    user = factory.SubFactory(EnterpriseCustomerUserFactory)
    state = 'not_set'


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
    user_email = factory.LazyAttribute(lambda x: FAKER.email())  # pylint: disable=no-member


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

    id = factory.LazyAttribute(lambda x: FAKER.random_int(min=1))  # pylint: disable=invalid-name,no-member
    email = factory.LazyAttribute(lambda x: FAKER.email())  # pylint: disable=no-member
    username = factory.LazyAttribute(lambda x: FAKER.user_name())  # pylint: disable=no-member
    first_name = factory.LazyAttribute(lambda x: FAKER.first_name())  # pylint: disable=no-member
    last_name = factory.LazyAttribute(lambda x: FAKER.last_name())  # pylint: disable=no-member
    is_staff = False
    is_active = False
    date_joined = factory.LazyAttribute(lambda x: FAKER.date_time_this_year(  # pylint: disable=no-member
        tzinfo=timezone.utc))


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
    provider_id = factory.LazyAttribute(lambda x: FAKER.slug())  # pylint: disable=no-member


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

    course_id = factory.LazyAttribute(lambda x: FAKER.slug())  # pylint: disable=no-member
    course_mode = 'audit'
    user = factory.SubFactory(PendingEnterpriseCustomerUserFactory)


class EnterpriseCustomerEntitlementFactory(factory.django.DjangoModelFactory):
    """
    EnterpriseCustomerEntitlement factory.

    Creates an instance of EnterpriseCustomerEntitlement with minimal boilerplate - uses this class' attributes as
    default parameters for EnterpriseCustomerBrandingFactory constructor.
    """

    class Meta(object):
        """
        Meta for EnterpriseCustomerEntitlementFactory.
        """

        model = EnterpriseCustomerEntitlement

    id = factory.LazyAttribute(lambda x: FAKER.random_int(min=1))  # pylint: disable=invalid-name,no-member
    entitlement_id = factory.LazyAttribute(lambda x: FAKER.random_int(min=1))  # pylint: disable=no-member
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

    id = factory.LazyAttribute(lambda x: FAKER.random_int(min=1))  # pylint: disable=invalid-name,no-member
    course_id = factory.LazyAttribute(lambda x: FAKER.slug())  # pylint: disable=no-member
    consent_granted = True
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

    uuid = factory.LazyAttribute(lambda x: UUID(FAKER.uuid4()))  # pylint: disable=no-member
    enterprise_customer = factory.SubFactory(EnterpriseCustomerFactory)
    query = ''


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
    username = factory.LazyAttribute(lambda x: FAKER.user_name())  # pylint: disable=no-member
    course_id = factory.LazyAttribute(lambda x: FAKER.slug())  # pylint: disable=no-member
    granted = True
