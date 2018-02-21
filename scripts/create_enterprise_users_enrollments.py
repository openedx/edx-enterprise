#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""
Creates Enterprise User and Enrollment records for a given Enterprise and enrollment data file.
"""

from __future__ import absolute_import, unicode_literals

import logging

import argparse
import csv
import sys
import os
import time

from edx_rest_api_client.client import EdxRestApiClient
from edx_rest_api_client.exceptions import HttpClientError

logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger(__name__)

API_BASE_URL = 'https://courses.edx.org/' + 'enterprise/api/v1/'
CREATE_USER_PATH = 'enterprise-learner'
CREATE_ENROLLMENT_PATH = 'enterprise-course-enrollment'


def create_enterprise_enrollment(client, username, course_id):
    try:
        LOGGER.info('Creating enterprise enrollment for user {}, course {}'.format(username, course_id))
        endpoint = getattr(client, CREATE_ENROLLMENT_PATH)
        endpoint.post({'username': username, 'course_id': course_id})
    except HttpClientError:
        LOGGER.error('Hit the rate limit, try again later!')
    except Exception:
        LOGGER.exception('Failed to create enterprise enrollment for user {}, course {}'.format(username, course_id))


def create_enterprise_user(client, username, enterprise_customer):
    try:
        LOGGER.info('Creating enterprise user {} for enterprise {}'.format(username, enterprise_customer))
        endpoint = getattr(client, CREATE_USER_PATH)
        endpoint.post({'username': username, 'enterprise_customer': enterprise_customer})
    except HttpClientError:
        LOGGER.error('Hit the rate limit, try again later!')
    except Exception:
        LOGGER.exception('Failed to create enterprise user {} for enterprise {}'.format(username, enterprise_customer))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-e', '--enterprise-customer', required=True, type=str,
                        help="EnterpriseCustomer UUID.")
    parser.add_argument('-f', '--enrollment-file', required=True, type=str,
                        help="Enrollment Data CSV Filename.")
    parser.add_argument('-a', '--access-token', required=True, type=str,
                        help="JWT Access Token for making calls to the Enterprise API")
    args = parser.parse_args()

    if not os.path.exists(args.enrollment_file):
        LOGGER.error('Unable to locate given enrollment file name: {}'.format(args.enrollment_file))

    existing_users = {}
    client = EdxRestApiClient(
        API_BASE_URL, append_slash=True, jwt=args.access_token,
    )

    with open(args.enrollment_file, 'r') as csv_file:
        csv_reader = csv.reader(csv_file, delimiter=str(u','))
        call_count = 0
        for row in csv_reader:
            if call_count < 58:
                username = row[0]
                course_id = row[1]

                if username not in existing_users:
                    create_enterprise_user(client, username, args.enterprise_customer)
                    existing_users[username] = 1
                    call_count += 1

                create_enterprise_enrollment(client, username, course_id)
                call_count += 1
            else:
                LOGGER.info('Sleeping for a minute to avoid rate limits')
                time.sleep(60)
                call_count = 0


    sys.exit(0)
