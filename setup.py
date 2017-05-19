#!/usr/bin/env python
# -*- coding: utf-8 -*-
# pylint: disable=C0111,W6005,W6100
from __future__ import absolute_import, print_function

import os
import re
import sys

from setuptools import setup


def get_version(*file_paths):
    """
    Extract the version string from the file at the given relative path fragments.
    """
    filename = os.path.join(os.path.dirname(__file__), *file_paths)
    version_file = open(filename).read()
    version_match = re.search(r"^__version__ = ['\"]([^'\"]*)['\"]",
                              version_file, re.M)
    if version_match:
        return version_match.group(1)
    raise RuntimeError("Unable to find version string.")

VERSION = get_version("enterprise", "__init__.py")

if sys.argv[-1] == "tag":
    print("Tagging the version on github:")
    os.system("git tag -a %s -m 'version %s'" % (VERSION, VERSION))
    os.system("git push --tags")
    sys.exit()

README = open(os.path.join(os.path.dirname(__file__), "README.rst")).read()
CHANGELOG = open(os.path.join(os.path.dirname(__file__), "CHANGELOG.rst")).read()

setup(
    name="edx-enterprise",
    version=VERSION,
    description="""Provide enterprise features to the Open edX platform.""",
    long_description=README + "\n\n" + CHANGELOG,
    author="edX",
    author_email="oscm@edx.org",
    url="https://github.com/edx/edx-enterprise",
    packages=[
        "enterprise",
        "integrated_channels",
        "integrated_channels.integrated_channel",
        "integrated_channels.sap_success_factors",
    ],
    include_package_data=True,
    install_requires=[
        "Django>=1.8.15,<1.10",
        "djangorestframework>=3.2.3,<3.3.0",
        "django-config-models",
        "django-extensions>=1.7.4",
        "django-filter>=0.11.0,<1.0.0",
        "django-model-utils>=2.0",
        "django-object-actions>=0.8.2,<1.0.0",
        "django-simple-history",
        "edx-drf-extensions",
        "Pillow>=3.1.1",
        "unicodecsv>=0.14.1",
    ],
    license="AGPL 3.0",
    zip_safe=False,
    keywords="Django edx",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Framework :: Django",
        "Framework :: Django :: 1.8",
        "Framework :: Django :: 1.9",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: GNU Affero General Public License v3 or later (AGPLv3+)",
        "Natural Language :: English",
        "Programming Language :: Python :: 2",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.5",
    ],
)
