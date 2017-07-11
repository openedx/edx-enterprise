.. _tests-section:

Testing
=======

enterprise has an assortment of test cases and code quality
checks to catch potential problems during development.  To run them all in the
version of Python you chose for your virtualenv:

.. code-block:: bash

    $ make validate

To run just the unit tests:

.. code-block:: bash

    $ make test

To run just the unit tests and check diff coverage

.. code-block:: bash

    $ make diff_cover

To run just the code quality checks:

.. code-block:: bash

    $ make quality

To run the unit tests under every supported Python version and the code
quality checks:

.. code-block:: bash

    $ make test-all

To generate and open an HTML report of how much of the code is covered by
test cases:

.. code-block:: bash

    $ make coverage

To run all tests under certain python versions and edx-platform dependency environments:

.. code-block:: bash

    $ tox -e py27-platform-ficus    # run all tests under python 2.7 and Ficus dependencies
    $ tox -e py35-platform-master   # run all tests under python 3.5 and master branch dependencies

Finally, various options to run only subset of tests:

.. code-block:: bash

    $ pytest tests/admin            # run all tests in tests/admin folder
    $ pytest tests/test_api.py      # run all tests in tests/test_api file

    # run all tests in TestEnterpriseCustomer test suite file
    $ pytest tests/test_api.py::TestEnterpriseCustomer

    # run only `test_ready_connects_user_post_save_handler` in `TestEnterpriseConfig` suite
    $ pytest tests/test_apps.py::TestEnterpriseConfig::test_ready_connects_user_post_save_handler
