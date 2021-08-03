#!/usr/bin/env python
# -*- coding: utf-8 -*-
# pylint: disable=C0111,W6005,W6100


import os
import re
import sys

from setuptools import setup

VCS_PREFIXES = ('git+', 'hg+', 'bzr+', 'svn+', '-e git+')


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


def get_requirements(requirements_file):
    """
    Get the contents of a file listing the requirements
    """
    lines = open(requirements_file).readlines()
    dependencies = []
    dependency_links = []

    for line in lines:
        package = line.strip()
        if package.startswith('#'):
            # Skip pure comment lines
            continue

        package, __, __ = package.partition(' #')
        package = package.strip()

        if any(package.startswith(prefix) for prefix in VCS_PREFIXES):
            # VCS reference for dev purposes, expect a trailing comment
            # with the normal requirement
            package_link, __, package = package.rpartition('#')

            # Remove -e <version_control> string
            package_link = re.sub(r'(.*)(?P<dependency_link>https?.*$)', r'\g<dependency_link>', package_link)
            package = re.sub(r'(egg=)?(?P<package_name>.*)==.*$', r'\g<package_name>', package)
            package_version = re.sub(r'.*[^=]==', '', line.strip())

            if package:
                dependency_links.append(
                    '{package_link}#egg={package}-{package_version}'.format(
                        package_link=package_link,
                        package=package,
                        package_version=package_version,
                    )
                )
        else:
            # Ignore any trailing comment
            package, __, __ = package.partition('#')
            # Remove any whitespace and assume non-empty results are dependencies
            package = package.strip()

        if package:
            dependencies.append(package)
    return dependencies, dependency_links


VERSION = get_version("enterprise", "__init__.py")

if sys.argv[-1] == "tag":
    print("Tagging the version on github:")
    os.system("git tag -a %s -m 'version %s'" % (VERSION, VERSION))
    os.system("git push --tags")
    sys.exit()

base_path = os.path.dirname(__file__)

README = open(os.path.join(base_path, "README.rst")).read()
CHANGELOG = open(os.path.join(base_path, "CHANGELOG.rst")).read()
REQUIREMENTS, DEPENDENCY_LINKS = get_requirements(os.path.join(base_path, 'requirements', 'base.in'))

setup(
    name="edx-enterprise",
    version=VERSION,
    description="""Your project description goes here""",
    long_description=README + "\n\n" + CHANGELOG,
    author="edX",
    author_email="oscm@edx.org",
    url="https://github.com/edx/edx-enterprise",
    packages=[
        "enterprise",
        "consent",
        "integrated_channels",
        "integrated_channels.integrated_channel",
        "integrated_channels.degreed",
        "integrated_channels.canvas",
        "integrated_channels.blackboard",
        "integrated_channels.cornerstone",
        "integrated_channels.moodle",
        "integrated_channels.sap_success_factors",
        "integrated_channels.xapi",
        "enterprise_learner_portal",
    ],
    include_package_data=True,
    install_requires=REQUIREMENTS,
    dependency_links=DEPENDENCY_LINKS,
    license="AGPL 3.0",
    zip_safe=False,
    keywords="Django edx",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Framework :: Django",
        "Framework :: Django :: 2.2",
        "Framework :: Django :: 3.0",
        "Framework :: Django :: 3.1",
        "Framework :: Django :: 3.2",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: GNU Affero General Public License v3 or later (AGPLv3+)",
        "Natural Language :: English",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
    ],
)
