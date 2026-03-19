# Docker in this repo is only supported for running tests locally
# as an alternative to virtualenv natively - johnnagro 2022-02-11
FROM ubuntu:noble AS app
LABEL maintainer="sre@edx.org"


# Packages installed:
# git; Used to pull in particular requirements from github rather than pypi,
# and to check the sha of the code checkout.

# build-essentials; so we can use make with the docker container

# language-pack-en locales; ubuntu locale support so that system utilities have a consistent
# language and time zone.

# python; ubuntu doesnt ship with python, so this is the python we will use to run the application

# pkg-config
#     mysqlclient>=2.2.0 requires this (https://github.com/PyMySQL/mysqlclient/issues/620)

# default-libmysqlclient-dev; to install header files needed to use native C implementation for
# MySQL-python for performance gains.

# libssl-dev; # mysqlclient wont install without this.

# python3.12-dev; to install header files for python extensions; much wheel-building depends on this

# gcc; for compiling python extensions distributed with python packages like mysql-client

# If you add a package here please include a comment above describing what it is used for
RUN apt-get update && apt-get -qy install --no-install-recommends \
 language-pack-en \
 locales \
 python3.12 \
 python3.12-dev \
 python3.12-venv \
 pkg-config \
 default-libmysqlclient-dev \
 libssl-dev \
 gcc \
 build-essential \
 git \
 curl \
 && rm -rf /var/lib/apt/lists/*

RUN ln -s /usr/bin/python3 /usr/bin/python

RUN locale-gen en_US.UTF-8
ENV LANG=en_US.UTF-8
ENV LANGUAGE=en_US:en
ENV LC_ALL=en_US.UTF-8
ENV DJANGO_SETTINGS_MODULE=enterprise.settings.test

# Env vars: path
ENV VIRTUAL_ENV='/edx/venvs/edx-enterprise'
ENV NODE_ENV='/edx/nodeenvs/edx-enterprise'
ENV PATH="${VIRTUAL_ENV}/bin:${PATH}"
ENV PATH="/edx/app/edx-enterprise/node_modules/.bin:${PATH}"
ENV PATH="/edx/app/edx-enterprise/bin:${PATH}"
ENV PATH="${NODE_ENV}/bin:${PATH}"

WORKDIR /edx/app/edx-enterprise

RUN python3.12 -m venv $VIRTUAL_ENV

# Copy the requirements explicitly even though we copy everything below
# this prevents the image cache from busting unless the dependencies have changed.
COPY requirements/ /edx/app/edx-enterprise/requirements/
COPY package.json /edx/app/edx-enterprise/package.json
COPY package-lock.json /edx/app/edx-enterprise/package-lock.json

# Fetch and install dependencies.
RUN pip install -r requirements/dev.txt
RUN pip install nodeenv

# Set up a Node environment and install Node requirements.
# Must be done after Python requirements, since nodeenv is installed via pip.
# The node environment is already 'activated' because its .../bin was put on $PATH.
RUN nodeenv $NODE_ENV --node=18.15.0 --prebuilt
RUN npm ci
