.. _tests-section:

Testing
=======

edx-enterprise has an assortment of test cases and code quality
checks to catch potential problems during development.

Running all of the python tests
-------------------------------
To run all unit tests and quality checks in the version of Python you chose for your virtualenv.

Alternatively, `docker`_ can be used to provide a containerized shell to run the commands below inside.

.. _docker: https://www.docker.com/

.. code-block:: bash

    $ make test-shell

.. code-block:: bash

    $ make validate

To run just the unit tests:

.. code-block:: bash

    $ make test

To run just the unit tests and check diff coverage

.. code-block:: bash

    $ make diff_cover

To run the unit tests under every supported Python version and the code
quality checks:

.. code-block:: bash

    $ make test-all

To run all tests under certain python versions and edx-platform dependency environments:

.. code-block:: bash

    $ tox -e py35-master   # run all tests under python 3.5 and master branch dependencies


Code coverage
-------------

To generate and open an HTML report of how much of the code is covered by
test cases:

.. code-block:: bash

    $ make coverage

There is a useful ``pytest.local.ini`` file that helps with looking at coverage of only a single module at a time:

.. code-block:: bash

    $ pytest tests/test_enterprise/api -c pytest.local.ini --cov=enterprise.api


Running subsets of tests
------------------------

Various options to run only subset of tests:

.. code-block:: bash

    $ pytest tests/test_admin/              # run all tests in tests/admin folder
    $ pytest tests/test_enterprise/api      # run all tests in tests/test_enterprise_api folder
    $ pytest tests/test_enterprise/api/test_permissions.py  # run all the tests in the test_permissions.py file

    # run all tests in TestEnterpriseCustomer test suite file
    $ pytest tests/test_models.py::TestEnterpriseCustomer

    # run only `test_ready_connects_user_post_save_handler` in `TestEnterpriseConfig` suite
    $ pytest tests/test_apps.py::TestEnterpriseConfig::test_ready_connects_user_post_save_handler


Quality
-------
To run just the code quality checks:

.. code-block:: bash

    $ tox -e quality

To run quality checks on specific files:

.. code-block:: bash

    # run the PEP8-style checks on one file (fast)
    $ pycodestyle enterprise/api/v1/views.py

    # run pylint on one file (not as fast)
    $ pylint enterprise/api/v1/views.py

    # use isort to fix imports, --check-only means see what isort would change without actually changing it
    $ isort --check-only enterprise/api/v1/views.py

    # use isort to actually change the file(s)
    $ isort enterprise/api/v1/views.py enterprise/api/v1/permissions.py
