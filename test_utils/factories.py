"""
Factoryboy factories.
"""
from __future__ import absolute_import, unicode_literals

from uuid import UUID

import factory
from faker import Factory as FakerFactory

from django.contrib.auth.models import User
from django.contrib.sites.models import Site

from enterprise.models import (EnterpriseCourseEnrollment, EnterpriseCustomer, EnterpriseCustomerBrandingConfiguration,
                               EnterpriseCustomerEntitlement, EnterpriseCustomerIdentityProvider,
                               EnterpriseCustomerUser, PendingEnrollment, PendingEnterpriseCustomerUser,
                               UserDataSharingConsentAudit)

FAKER = FakerFactory.create()


class SiteFactory(factory.django.DjangoModelFactory):
    """
    Factory class for Site model.
    """

    class Meta(object):
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
    active = True
    site = factory.SubFactory(SiteFactory)
    catalog = factory.LazyAttribute(lambda x: FAKER.random_int(min=0, max=1000000))
    enable_data_sharing_consent = True
    enforce_data_sharing_consent = EnterpriseCustomer.AT_LOGIN


class EnterpriseCustomerUserFactory(factory.django.DjangoModelFactory):
    """
    EnterpriseCustomerUser factory.

    Creates an instance of EnterpriseCustomerUser with minimal boilerplate - uses this class' attributes as default
    parameters for EnterpriseCustomerUser constructor.
    """

    class Meta(object):
        """
        Meta for EnterpriseCustomerUserFactory.
        """

        model = EnterpriseCustomerUser

    enterprise_customer = factory.SubFactory(EnterpriseCustomerFactory)
    user_id = factory.LazyAttribute(lambda x: FAKER.pyint())


class EnterpriseCourseEnrollmentFactory(factory.django.DjangoModelFactory):
    """
    EnterpriseCourseEnrollment factory.

    Creates an instance of EnterpriseCourseEnrollment with minimal boilerplate - uses this class' attributes as default
    parameters for EnterpriseCourseEnrollment constructor.
    """

    class Meta(object):
        """
        Meta for EnterpriseCourseEnrollmentFactory.
        """

        model = EnterpriseCourseEnrollment

    enterprise_customer_user = factory.SubFactory(EnterpriseCustomerUserFactory)
    course_id = factory.LazyAttribute(lambda x: FAKER.slug())


class UserDataSharingConsentAuditFactory(factory.django.DjangoModelFactory):
    """
    UserDataSharingConsentAuditFactory.

    Creates an instance of UserDataSharingConsentAudit with minimal boilerplate.
    """

    class Meta(object):

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
    user_email = factory.LazyAttribute(lambda x: FAKER.email())


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

    id = factory.LazyAttribute(lambda x: FAKER.random_int(min=1))  # pylint: disable=invalid-name
    email = factory.LazyAttribute(lambda x: FAKER.email())
    username = factory.LazyAttribute(lambda x: FAKER.user_name())
    first_name = factory.LazyAttribute(lambda x: FAKER.first_name())
    last_name = factory.LazyAttribute(lambda x: FAKER.last_name())
    is_staff = False
    is_active = False
    date_joined = factory.LazyAttribute(lambda x: FAKER.date_time_this_year())


class EnterpriseCustomerIdentityProviderFactory(factory.django.DjangoModelFactory):
    """
    Factory class for EnterpriseCustomerIdentityProvider model.
    """

    class Meta(object):
        model = EnterpriseCustomerIdentityProvider
        django_get_or_create = ("provider_id",)

    enterprise_customer = factory.SubFactory(EnterpriseCustomerFactory)
    provider_id = factory.LazyAttribute(lambda x: FAKER.slug())


class EnterpriseCustomerBrandingFactory(factory.django.DjangoModelFactory):
    """
    EnterpriseCustomerBrandingFactory factory.

    Creates an instance of EnterpriseCustomerBranding with minimal boilerplate - uses this class' attributes as
    default parameters for EnterpriseCustomerBrandingFactory constructor.
    """

    class Meta(object):
        """
        Meta for EnterpriseCustomerBrandingFactory.
        """

        model = EnterpriseCustomerBrandingConfiguration

    id = factory.LazyAttribute(lambda x: FAKER.random_int(min=1))  # pylint: disable=invalid-name
    enterprise_customer = factory.SubFactory(EnterpriseCustomerFactory)


class PendingEnrollmentFactory(factory.django.DjangoModelFactory):
    """
    PendingEnrollment factory.

    Create an instance of PendingEnrollment with minimal boilerplate
    """

    class Meta(object):
        model = PendingEnrollment

    course_id = factory.LazyAttribute(lambda x: FAKER.slug())
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

    id = factory.LazyAttribute(lambda x: FAKER.random_int(min=1))  # pylint: disable=invalid-name
    entitlement_id = factory.LazyAttribute(lambda x: FAKER.random_int(min=1))
    enterprise_customer = factory.SubFactory(EnterpriseCustomerFactory)
