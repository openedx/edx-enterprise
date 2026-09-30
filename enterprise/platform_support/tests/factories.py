"""
Factoryboy factories.
"""
# These tests exercise openedx-platform fixtures (student factories, the modulestore,
# the completion app) which are not installed in this repo's standalone test
# environment, so pylint cannot resolve them here.
# pylint: disable=import-error


from uuid import UUID

import factory
from faker import Factory as FakerFactory
from openedx.core.djangoapps.site_configuration.tests.factories import SiteFactory

from enterprise.models import (
    EnterpriseCourseEnrollment,
    EnterpriseCustomer,
    EnterpriseCustomerBrandingConfiguration,
    EnterpriseCustomerIdentityProvider,
    EnterpriseCustomerUser,
)

FAKER = FakerFactory.create()


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

    uuid = factory.LazyAttribute(lambda x: UUID(FAKER.uuid4()))  # pylint: disable=no-member
    name = factory.LazyAttribute(lambda x: FAKER.company())  # pylint: disable=no-member
    slug = factory.LazyAttribute(lambda x: FAKER.slug())  # pylint: disable=no-member
    active = True
    site = factory.SubFactory(SiteFactory)
    enable_data_sharing_consent = True
    enforce_data_sharing_consent = EnterpriseCustomer.AT_ENROLLMENT
    enable_learner_portal = False


class EnterpriseCustomerUserFactory(factory.django.DjangoModelFactory):
    """
    EnterpriseCustomer factory.

    Creates an instance of EnterpriseCustomerUser with minimal boilerplate - uses this class' attributes as default
    parameters for EnterpriseCustomerUser constructor.
    """

    class Meta:
        """
        Meta for EnterpriseCustomerFactory.
        """

        model = EnterpriseCustomerUser

    enterprise_customer = factory.SubFactory(EnterpriseCustomerFactory)
    user_id = factory.LazyAttribute(lambda x: FAKER.pyint())  # pylint: disable=no-member


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

    course_id = factory.LazyAttribute(lambda x: FAKER.slug())  # pylint: disable=no-member
    enterprise_customer_user = factory.SubFactory(EnterpriseCustomerUserFactory)


class EnterpriseCustomerBrandingConfigurationFactory(factory.django.DjangoModelFactory):
    """
    EnterpriseCustomerBrandingConfiguration factory

    Creates an instance of EnterpriseCustomerBrandingConfiguration with minimal boilerplate.
    """

    class Meta:
        """
        Meta for EnterpriseCustomerBrandingConfigurationFactory.
        """

        model = EnterpriseCustomerBrandingConfiguration

    logo = FAKER.image_url()  # pylint: disable=no-member
    primary_color = FAKER.color()  # pylint: disable=no-member
    secondary_color = FAKER.color()  # pylint: disable=no-member
    tertiary_color = FAKER.color()  # pylint: disable=no-member


class EnterpriseCustomerIdentityProviderFactory(factory.django.DjangoModelFactory):
    """
    EnterpriseCustomerIdentityProvider factory.
    """

    class Meta:
        """
        Meta for EnterpriseCustomerIdentityProviderFactory.
        """

        model = EnterpriseCustomerIdentityProvider

    enterprise_customer = factory.SubFactory(EnterpriseCustomerFactory)
    provider_id = factory.LazyAttribute(lambda x: FAKER.slug())  # pylint: disable=no-member
