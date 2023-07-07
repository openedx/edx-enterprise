# Docker in this repo is only supported for running tests locally
# as an alternative to virtualenv natively - johnnagro 2022-02-11
FROM ubuntu:focal as app
MAINTAINER sre@edx.org


# Packages installed:
# git; Used to pull in particular requirements from github rather than pypi,
# and to check the sha of the code checkout.

# build-essentials; so we can use make with the docker container

# language-pack-en locales; ubuntu locale support so that system utilities have a consistent
# language and time zone.

# python; ubuntu doesnt ship with python, so this is the python we will use to run the application

# python3-pip; install pip to install application requirements.txt files

# pkg-config
#     mysqlclient>=2.2.0 requires this (https://github.com/PyMySQL/mysqlclient/issues/620)

# libmysqlclient-dev; to install header files needed to use native C implementation for
# MySQL-python for performance gains.

# libssl-dev; # mysqlclient wont install without this.

# python3-dev; to install header files for python extensions; much wheel-building depends on this

# gcc; for compiling python extensions distributed with python packages like mysql-client

# If you add a package here please include a comment above describing what it is used for
RUN apt-get update && apt-get -qy install --no-install-recommends \
 language-pack-en \
 locales \
 python3.8 \
 python3-pip \
 python3.8-venv \
 pkg-config \
 libmysqlclient-dev \
 libssl-dev \
 python3-dev \
 gcc \
 build-essential \
 git \
 curl


RUN pip install --upgrade pip setuptools
# delete apt package lists because we do not need them inflating our image
RUN rm -rf /var/lib/apt/lists/*

RUN ln -s /usr/bin/python3 /usr/bin/python

RUN locale-gen en_US.UTF-8
ENV LANG en_US.UTF-8
ENV LANGUAGE en_US:en
ENV LC_ALL en_US.UTF-8
ENV DJANGO_SETTINGS_MODULE enterprise.settings.test

# Env vars: path
ENV VIRTUAL_ENV='/edx/app/venvs/edx-enterprise'
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
ENV PATH="/edx/app/edx-enterprise/node_modules/.bin:${PATH}"
ENV PATH="/edx/app/edx-enterprise/bin:${PATH}"
ENV PATH="/edx/app/nodeenv/bin:${PATH}"

RUN useradd -m --shell /bin/false app

WORKDIR /edx/app/edx-enterprise

RUN python3.8 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Copy the requirements explicitly even though we copy everything below
# this prevents the image cache from busting unless the dependencies have changed.
COPY requirements/ /edx/app/edx-enterprise/requirements/

# Dependencies are installed as root so they cannot be modified by the application user.
RUN pip install -r requirements/dev.txt
RUN pip install nodeenv

# Set up a Node environment and install Node requirements.
# Must be done after Python requirements, since nodeenv is installed
# via pip.
# The node environment is already 'activated' because its .../bin was put on $PATH.
RUN nodeenv /edx/app/nodeenv --node=16.15.1 --prebuilt

RUN mkdir -p /edx/var/log

# Code is owned by root so it cannot be modified by the application user.
# So we copy it before changing users.
USER app

# This line is after the requirements so that changes to the code will not
# bust the image cache
COPY . /edx/app/edx-enterprise

