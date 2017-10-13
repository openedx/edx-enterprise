# -*- coding: utf-8 -*-
"""
Assist integrated channels with retrieving course metadata.

Module contains resources for integrated pipelines to retrieve all the
metadata for courses in the course catalog belonging to a particular
enterprise customer.
"""
from __future__ import absolute_import, unicode_literals

import json
from logging import getLogger

from enterprise.api_client.enterprise import EnterpriseApiClient

LOGGER = getLogger(__name__)


def get_course_runs(user, enterprise_customer):
    """
    List the course runs the given enterprise customer has in its catalog.

    Arguments:
        enterprise_customer: The given Enterprise Customer

    Returns:
        iterable: An iterable containing the details of each course run.
    """
    client = EnterpriseApiClient(user)

    enterprise_course_runs = client.get_enterprise_course_runs(
        enterprise_customer,
    )
    LOGGER.info('Retrieving course list for enterprise %s', enterprise_customer.name)

    for course_run in enterprise_course_runs.values():
        yield course_run


class BaseCourseExporter(object):
    """
    Base class for course metadata exporters to implement a "send" method on.
    """

    AVAILABILITY_CURRENT = 'Current'
    AVAILABILITY_UPCOMING = 'Upcoming'
    AVAILABILITY_ARCHIVED = 'Archived'

    data_transform = {}

    def __init__(self, user, plugin_configuration):
        """
        Save the appropriate details for use elsewhere in the object.
        """
        self.user = user
        self.enterprise_customer = plugin_configuration.enterprise_customer
        self.plugin_configuration = plugin_configuration
        self.courses = []
        for course_run in get_course_runs(self.user, self.enterprise_customer):
            self.add_course_run(course_run)

    def add_course_run(self, course_run_details):
        """
        Transform the details of a course run, and save it to our courses list.
        """
        transformed = self.transform_course_run_details(course_run_details)
        LOGGER.info(
            'Sending course with plugin configuration %s: %s',
            self.plugin_configuration,
            json.dumps(transformed, indent=4),
        )
        self.courses.append(transformed)

    def transform_course_run_details(self, course_run_details):
        """
        Parse the provided course into the format natively supported by the provider.
        """
        LOGGER.info(
            'Processing course with ID %s',
            course_run_details['key']
        )
        LOGGER.debug(
            'Parsing course for %s: %s',
            self.enterprise_customer,
            json.dumps(course_run_details, indent=4),
        )
        # Add the enterprise customer to the course run details so it can be used in the data transform
        course_run_details['enterprise_customer'] = self.enterprise_customer
        output = {}
        for key, transform in self.data_transform.items():
            output[key] = transform(course_run_details) if transform is not None else course_run_details.get(key)
        return output

    def get_serialized_data(self):
        """
        Abstract method to transform the data structure into the correct serialized bytestream.
        """
        raise NotImplementedError("Implemented in concrete subclass.")
