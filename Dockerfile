FROM python:3.8
ENV PYTHONUNBUFFERED 1
RUN mkdir /edx-enterprise

# Now install credentials
WORKDIR /edx-enterprise

# Copy the requirements explicitly even though we copy everything below
# this prevents the image cache from busting unless the dependencies have changed.
COPY requirements/dev.txt /edx-enterprise/requirements/dev.txt

# Dependencies are installed as root so they cannot be modified by the application user.
RUN pip install -r requirements/dev.txt
RUN pip install mysqlclient
ADD . /edx-enterprise/

EXPOSE 8000