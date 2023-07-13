Getting Started
===============

Production setup
----------------

``Edx-enterprise`` is developed as a pluggable application for the edx-platform and can't currently be used outside of
``edx-platform``. ``Edx-enterprise`` is shipped with default edx-platform setup (see `edx-platform requirements file`_),
so new installs should already have it set up and enabled.

.. _edx-platform requirements file: https://github.com/openedx/edx-platform/blob/master/requirements/edx/base.txt

If you're migrating from an earlier (i.e. pre-Ficus) release, the only step you *might* have to do manually is to
perform database migrations.

.. code-block:: bash

    $ make migrate

    # Or use a more down-to-the-root command (replace aws with your version of config)
    $ ./manage.py lms migrate --settings=aws

Local development
-----------------

If you have not already done so, create/activate a `virtualenv`_.

.. _virtualenv: https://virtualenvwrapper.readthedocs.org/en/latest/

Alternatively, `docker`_ can be used to provide a containerized shell to run tests with.

.. _docker: https://www.docker.com/

.. code-block:: bash

    $ make test-shell

Dependencies can be installed via the command below.

.. code-block:: bash

    $ make requirements

Than you might want to run tests to make sure the setup went fine and there are no pre-existing problems (i.e. failed
tests or quality checks)

.. code-block:: bash

    $ make test-all

For details on performing other development-related tasks and high-level overview of ``edx-enterprise`` architecture
and development principles, see :ref:`development-section`
