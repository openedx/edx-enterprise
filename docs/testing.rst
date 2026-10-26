.. _tests-section:

Testing
=======

edx-enterprise has an assortment of test cases and code quality
checks to catch potential problems during development.

Running all of the python tests
-------------------------------
To run all unit tests and quality checks in the version of Python/Node you previously configured:

.. code-block:: bash

    $ make validate

To run just the unit tests:

.. code-block:: bash

    $ make test

To run just the unit tests and check diff coverage

.. code-block:: bash

    $ make diff_cover

To run the unit tests under every supported Python/Django combination via tox:

.. code-block:: bash

    $ tox                    # run all supported combinations
    $ tox -e py312-django52  # run one specific combination

When testing a subset of tests, use ``pytest.local.ini`` to disable coverage:

.. code-block:: bash

    $ pytest -c pytest.local.ini tests/test_enterprise/api/
    $ pytest -c pytest.local.ini tests/test_apps.py::TestEnterpriseConfig::test_ready_connects_user_post_save_handler

Alternatively, `docker`_ can be used to provide a containerized environment to run tests.

.. _docker: https://www.docker.com/

.. code-block:: bash

    $ make dev.up
    $ docker compose exec test-shell make test
    $ docker compose exec test-shell make validate
    $ docker compose exec test-shell pytest -c pytest.local.ini tests/test_enterprise/api/
    $ docker compose exec test-shell pytest -c pytest.local.ini tests/test_apps.py::TestEnterpriseConfig::test_ready_connects_user_post_save_handler

Code coverage
-------------

To generate and open an HTML report of how much of the code is covered by
test cases:

.. code-block:: bash

    $ make coverage

Quality
-------
To run just the code quality checks:

.. code-block:: bash

    $ make quality

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

`docker`_ can also be used to provide a containerized environment to run quality checks.

.. code-block:: bash

    $ make dev.up
    $ docker compose exec test-shell make quality
    $ docker compose exec test-shell pycodestyle enterprise/api/v1/views.py
    $ docker compose exec test-shell pylint enterprise/api/v1/views.py
    $ docker compose exec test-shell isort --check-only enterprise/api/v1/views.py
    $ docker compose exec test-shell isort enterprise/api/v1/views.py enterprise/api/v1/permissions.py
