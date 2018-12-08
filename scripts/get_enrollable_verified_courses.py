#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""
Creates Enterprise User and Enrollment records for a given Enterprise and enrollment data file.
"""

from __future__ import absolute_import, unicode_literals

import logging

import argparse
import datetime
import sys
import os
import time

from edx_rest_api_client.client import EdxRestApiClient
from edx_rest_api_client.exceptions import HttpClientError

logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger(__name__)

API_BASE_URL = 'https://prod-edx-discovery.edx.org/api/v1/'


def process_catalog_results(results, course_keys):
    for course in results:
        for course_run in course['course_runs']:
            # is the end date already in the past?
            include_course = True
            if course_run['end']:
                try:
                    end_date = datetime.datetime.strptime(course_run['end'], '%Y-%m-%dT%H:%M:%SZ')
                    if end_date < datetime.datetime.now():
                        #LOGGER.info('Excluding {} because end date in the past'.format(course_run['key']))
                        include_course = False
                except ValueError:
                    LOGGER.exception('Unable to parse end date {} for course {}'.format(
                        course_run['end'], course_run['key']
                    ))

            verified_seat = None
            #LOGGER.info('Course seats: {}'.format(course_run['seats']))
            for seat in course_run['seats']:
                if seat['type'] in ['verified', 'professional', 'no-id-professional']:
                    verified_seat = seat
                    break

            # is there a verified seat?
            if not verified_seat:
                #LOGGER.info('Excluding {} because no verified seat'.format(course_run['key']))
                include_course = False
            # if that verified seat has an upgrade deadline, is it in the past?
            elif verified_seat and verified_seat['upgrade_deadline']:
                try:
                    upgrade_deadline = datetime.datetime.strptime(verified_seat['upgrade_deadline'], '%Y-%m-%dT%H:%M:%SZ')
                    if upgrade_deadline < datetime.datetime.now():
                        #LOGGER.info('Excluding {} because upgrade deadline in the past'.format(course_run['key']))
                        include_course = False
                except ValueError:
                    LOGGER.exception('Unable to parse upgrade deadline date {} for course {}'.format(
                        verified_seat['upgrade_deadline'], course_run['key']
                    ))

            # this course should get an enrollment code!
            if include_course:
                LOGGER.info('course: {}, mode: {}, bulk sku: {}'.format(
                    course_run['key'],
                    verified_seat['type'],
                    verified_seat['bulk_sku']
                ))
                course_keys.append(course_run['key'])



if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-a', '--access-token', required=True, type=str,
                        help="JWT Access Token for making calls to the Enterprise API")
    args = parser.parse_args()

    client = EdxRestApiClient(
        API_BASE_URL, append_slash=True, jwt=args.access_token,
    )

    endpoint = client.catalogs(1).courses
    page_count = 1
    querystring = {'page': page_count}
    results = {}
    course_keys = []
    try:
        results = endpoint.get(**querystring)
    except Exception:
        LOGGER.exception('Failed to hit the catalog api on the first try!')
        sys.exit(1)

    process_catalog_results(results['results'], course_keys)
    page_count += 1
    while results['next']:
        LOGGER.info('About to fetch page {}'.format(page_count))
        try:
            querystring['page'] = page_count
            results = endpoint.get(**querystring)
            process_catalog_results(results['results'], course_keys)
            page_count += 1
        except Exception:
            LOGGER.exception('Failed to hit the catalog api for query params {}'.format(querystring))

    LOGGER.info(course_keys)
    sys.exit(0)
