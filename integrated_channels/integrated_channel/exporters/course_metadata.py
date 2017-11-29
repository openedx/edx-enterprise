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

from integrated_channels.integrated_channel.exporters import Exporter

from enterprise.api_client.enterprise import EnterpriseApiClient

LOGGER = getLogger(__name__)


class CourseExporter(Exporter):
    """
    Base class for course metadata exporters.
    """

    AVAILABILITY_CURRENT = 'Current'
    AVAILABILITY_UPCOMING = 'Upcoming'
    AVAILABILITY_ARCHIVED = 'Archived'

    def __init__(self, user, enterprise_configuration):
        """
        Instantiate the following variables for use by subclassing course metadata exporters:

        removed_courses_resolved (boolean): Indicates whether `resolve_removed_courses` has been called yet.
        courses (list): A list of courses to be exported.
        """
        super(CourseExporter, self).__init__(user, enterprise_configuration)
        self.removed_courses_resolved = False
        self.courses = []
        client = EnterpriseApiClient(self.user)
        enterprise_course_runs = client.get_enterprise_course_runs(self.enterprise_customer)
        LOGGER.info('Retrieving course run list for enterprise [%s]', self.enterprise_customer.name)
        for course_run in enterprise_course_runs.values():
            self.add_course_run(course_run)

    def export(self):
        """
        Export the set of courses generically by encoding them in JSON format, plus the HTTP method to use.
        """
        yield json.dumps(self.courses, sort_keys=True).encode('utf-8'), 'POST'

    @property
    def data(self):
        """
        Return blanket data by default.

        If a course exporter requires data transformation, it should override this property.
        """
        return {}

    def add_course_run(self, course_run):
        """
        Transform the details of a course run, and save it to our courses list.
        """
        transformed = self.transform(course_run)
        LOGGER.info(
            'Sending course run with plugin configuration [%s]: [%s]',
            self.enterprise_configuration,
            json.dumps(transformed, indent=4),
        )
        self.courses.append(transformed)

    def transform(self, course_run):
        """
        Parse the provided course into the format natively supported by the provider.
        """
        LOGGER.info('Processing course run with ID [%s]', course_run['key'])
        LOGGER.debug('Parsing course run for [%s]: [%s]', self.enterprise_customer, json.dumps(course_run, indent=4))

        # Add the enterprise customer to the course run details so it can be used in the data transform
        course_run['enterprise_customer'] = self.enterprise_customer
        transformed_data = {}
        for key, transform in self.data.items():
            transformed_data[key] = transform(course_run) if transform is not None else course_run.get(key)
        return transformed_data

    def resolve_removed_courses(self, *args, **kwargs):  # pylint: disable=unused-argument
        """
        Default way to resolve the removal of courses.

        This is implemented as such to allow certain integrated channels that do not really utilize
        this functionality to just return the entire set of ready-to-transmit courses for auditing
        purposes.

        Note that such integrated channels are presumed to be handling updating their course
        availability on upstream catalogs through some other technique, i.e. DELETE requests
        made to the integrated channel's API to remove a course from the upstream catalog.

        An example of an integrated channel that may utilize this: SAPSF -- this function
        would be overridden to generate a course metadata payload that embeds availability
        data to have a correct audit summary at the end of the transmission.
        """
        courses = self.courses if not self.removed_courses_resolved else {}
        self.removed_courses_resolved = True
        return courses
