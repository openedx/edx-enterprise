# -*- coding: utf-8 -*-
"""
Canvas integrated_channel factories.
"""

import factory
from faker import Factory as FakerFactory

from integrated_channels.canvas.models import CanvasEnterpriseCustomerConfiguration, CanvasGlobalConfiguration

from .factories import EnterpriseCustomerFactory

FAKER = FakerFactory.create()

class CanvasGlobalConfigurationFactory(factory.django.DjangoModelFactory):
    """
    ``CanvasGlobalConfiguration`` factory.

    Creates an instance of ``CanvasGlobalConfiguration`` with minimal boilerplate.
    """

    class Meta:
        """
        Meta for ``CanvasGlobalConfigurationFactory``.
        """

        model = CanvasGlobalConfiguration

    course_api_path = factory.LazyAttribute(lambda x: FAKER.file_path())
    oauth_api_path = factory.LazyAttribute(lambda x: FAKER.file_path())


class CanvasEnterpriseCustomerConfigurationFactory(factory.django.DjangoModelFactory):
    """
    ``CanvasEnterpriseCustomerConfiguration`` factory.

    Creates an instance of ``CanvasEnterpriseCustomerConfiguration`` with minimal boilerplate.
    """

    class Meta:
        """
        Meta for ``CanvasEnterpriseCustomerConfigurationFactory``.
        """

        model = CanvasEnterpriseCustomerConfiguration

    enterprise_customer = factory.SubFactory(EnterpriseCustomerFactory)
    active = True
    canvas_company_id = factory.LazyAttribute(lambda x: FAKER.company())
    canvas_base_url = factory.LazyAttribute(lambda x: FAKER.file_path())
    provider_id = 'CANVAS'
