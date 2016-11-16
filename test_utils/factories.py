"""
Factoryboy factories.
"""
from __future__ import absolute_import, unicode_literals

from uuid import UUID

import factory
from faker import Factory as FakerFactory

from django.contrib.sites.models import Site
from enterprise.models import EnterpriseCustomer, EnterpriseCustomerUser

FAKER = FakerFactory.create()


class SiteFactory(factory.django.DjangoModelFactory):
    """
    Factory class for Site model.
    """

    class Meta(object):
        model = Site
        django_get_or_create = ('domain',)

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
    identity_provider = factory.LazyAttribute(lambda x: FAKER.slug())


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
