"""
Views for Enterprise Integrated Channel.
"""

from __future__ import absolute_import, unicode_literals
from rest_framework.views import APIView


class PushLearnerDataToIntegratedChannel(APIView):
    """
    Provide an endpoint to route learner data to the appropriate channels based on Enterprise's configuration.
    """

    def post(self, request):
        """
        Hit when certificates are generated or when audit learners in self paced courses reach a passing grade.

        When this happens, this method will route the learners data appropriately.

        For a given learner who has completed a course, find out the following:
            if the learner is associated with an enterprise customer.
            if the course is part of an enterprise enrollment.
            if the enterprise customer is configured for an Integrated Channel.

        Continue if all the conditions above are met, otherwise abort processing.

        Based on the EnterpriseCustomerPluginConfiguration for the Enterprise, determine which endpoints are
        configured to receive learner data, and send a formatted request to each of those endpoints.
        If nothing is configured, abort processing.
        Note that the request format will be uniform across the different plugin endpoints.
        """
        raise NotImplementedError('Will be implemented as part of ENT-193')


class PushCatalogDataToIntegratedChannel(APIView):
    """
    Provide an endpoint to export a course catalog to the appropriate channels based on an Enterprise's configuration.
    """

    def post(self, request):
        """
        Trigger sending an enterprise's course catalog data to any configured endpoints.

        For a given enterprise customer, based on the EnterpriseCustomerPluginConfiguration for the Enterprise,
        determine which plugin endpoints are configured to receive course data, and send a formatted request to
        each of those endpoints.
        If nothing is configured, abort processing.
        Note that the request format will be uniform across the different plugin endpoints.
        """
        raise NotImplementedError('Will be implemented as part of ENT-192')
