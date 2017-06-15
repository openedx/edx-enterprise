Change Log
==========

..
   All enhancements and patches to edx-enteprise will be documented
   in this file.  It adheres to the structure of http://keepachangelog.com/ ,
   but in reStructuredText instead of Markdown (for ease of incorporation into
   Sphinx documentation and the PyPI description).

   This project adheres to Semantic Versioning (http://semver.org/).

.. There should always be an "Unreleased" section for changes pending release.

Unreleased
----------

[0.35.0] - 2017-06-15
---------------------

* Allow account-level data sharing consent in a course-specific context


[0.34.7] - 2017-06-14
---------------------

* Enable "Continue" button flows on enterprise landing page


[0.34.6] - 2017-06-14
---------------------

* Fixed layout of data sharing consent decline modal on mobile view


[0.34.5] - 2017-06-09
----------------------

* Add Django 1.10 support back


[0.34.4] - 2017-06-09
---------------------

* Added course information overlay


[0.34.3] - 2017-06-07
---------------------

* Make enterprise landing page url available in the enterprise api and SAP course export.


[0.34.2] - 2017-06-06
---------------------

* Fix UI issues (unexpected html escape) on enterprise landing page.


[0.34.1] - 2017-06-06
----------------------

* Bug fix for Data sharing consent pop up page.


[0.34.0] - 2017-06-05
----------------------

* Update data backing and behavior of enterprise landing page
* Fix template prioritization bug
* Fix URL rendering in enterprise login decorator


[0.33.24] - 2017-06-02
----------------------

* UI updates for data sharing consent page.


[0.33.23] - 2017-06-02
----------------------

* Fix a bug with unexpected image data in SAP course export job.


[0.33.22] - 2017-06-02
----------------------

* Add an `EnterpriseApiClient` method for getting enrollment data about a single user+course pair
* Add logic to enterprise landing page that redirects users to the course when already registered


[0.33.21] - 2017-06-01
----------------------

* UI updates for course mode selection in enterprise landing page.


[0.33.20] - 2017-05-23
----------------------

* Migrate from mako templates to django templates


[0.33.19] - 2017-05-18
----------------------

* Display account created/linked messages on enterprise landing page


[0.33.18] - 2017-05-17
----------------------

* Add Enable audit enrollment flag


[0.33.17] - 2017-05-16
----------------------

* Add django admin for enterprise course enrollment models


[0.33.16] - 2017-05-15
----------------------

* Bug fixes for SAP learner completion data passback.

[0.33.15] - 2017-05-10
----------------------

* Additional minor UI updates for enterprise landing page.


[0.33.14] - 2017-05-10
----------------------

* Add new externally managed consent option for enterprise customers.

[0.33.13] - 2017-05-09
----------------------

* Fix invalid API Gateway URIs


[0.33.12] - 2017-05-03
----------------------

* Add enterprise landing page


[0.33.11] - 2017-05-02
----------------------

* Add tpa hint if available for launchURLs for SAP Course metadata push.

[0.33.10] - 2017-05-02
----------------------

* Fix bug with inactivating SAP courses that are no longer in the catalog.


[0.33.9] - 2017-04-26
---------------------

* Fix enterprise logo validation message for max image size limit


[0.33.8] - 2017-04-26
---------------------

* Updated calls to get_edx_api_data as its signature has changed in openedx.


[0.33.7] - 2017-04-24
---------------------

* Redirect to login instead of raising Http404 if EnterpriseCustomer missing.
* Add confirmation_alert_prompt_warning to context of account-level consent view.


[0.33.6] - 2017-04-21
---------------------

* Increase max size limit for enterprise logo


[0.33.5] - 2017-04-20
---------------------

* Added vertical hanging indent mode to isort settings and adjusted current imports


[0.33.4] - 2017-04-18
---------------------

* Enforce login for course-specific data sharing consent views.


[0.33.3] - 2017-04-18
---------------------

* Fixed the CSS for the expand arrow in the data sharing consent page.


[0.33.2] - 2017-04-17
---------------------

* Update Data Sharing Consent message.


[0.33.1] - 2017-04-17
---------------------

* Order enterprise customers by name on enterprise customer django admin


[0.33.0] - 2017-04-11
---------------------

* Improve accounting for inactive courses for SAP course export.


[0.32.1] - 2017-04-06
---------------------

* Bug Fix: Added Handling for user enrollment to courses that do not have a start date.


[0.32.0] - 2017-04-06
---------------------

* Refine SAP course export parameters


[0.31.4] - 2017-04-05
---------------------

* Added missing migration file for recent string updates


[0.31.3] - 2017-04-04
---------------------

* Modified SAP completion status data to correctly indicate a failing grade to SAP systems.

[0.31.2] - 2017-04-03
---------------------

* Bugfix: Resolve IntegrityError getting raised while linking existing enterprise users when data sharing consent is
  disabled for the related enterprise.

[0.31.1] - 2017-03-31
---------------------

* Bugfix: Allow unlinking of enterprise learners with plus sign or certain other characters in email address.

[0.31.0] - 2017-03-30
---------------------

* Edited UI and error strings.

[0.30.0] - 2017-03-27
---------------------

* Fully implements sap_success_factors transmitters and client to communicate with the SAP SuccessFactors API,
  and to handle auditing and other business logic for both catalog and learner data calls.


[0.29.1] - 2017-03-27
---------------------

* Support for segment.io events on data sharing consent flow


[0.29.0] - 2017-03-23
---------------------

* Updates integrated_channels management command `transmit_learner_data` to support sending completion data for
  self-paced courses, and to use the Certificates API for instructor-paced courses.

[0.28.0] - 2017-03-23
---------------------

* New data sharing consent view supporting failure_url parameter


[0.27.6] - 2017-03-21
---------------------

* Removed OAuth2Authentication class from API viewset definitions


[0.27.5] - 2017-03-17
---------------------

* Updated api.yaml to resolve swagger configuration issues.


[0.27.4] - 2017-03-17
---------------------

* Allows enterprise enrollments to be made on servers that sit behind a load balancer.


[0.27.3] - 2017-03-16
---------------------
* Added integrated_channels management command to transmit courseware metadata to SAP SuccessFactors.

[0.27.2] - 2017-03-10
---------------------

* Added integrated_channels management command to transmit learner completion data to SAP SuccessFactors.

[0.27.1] - 2017-03-13
---------------------

* Added api.yaml and api-compact.yaml files to introduce api endpoints for catalog api-manager.


[0.27.0] - 2017-03-02
---------------------

* Added API endpoint for fetching catalogs and catalog courses.

[0.26.3] - 2017-03-02
---------------------

* Added integrated_channels to MANIFEST.in to properly include migrations for the new packages.

[0.26.2] - 2017-03-02
---------------------

* Fixed package listing in setup.py to avoid import errors when using as a library

[0.26.1] - 2017-02-28
---------------------

* Added support for retrieving access token from SAP SuccessFactors
* Added indicator in Sap SuccessFactors admin tool for checking the configuration's access to SuccessFactors.

[0.26.0] - 2017-02-28
---------------------

* Formally introducing new integrated_channels apps
* Adding new models and admin interfaces for integrated_channel and sap_success_factors

[0.25.0] - 2017-02-28
---------------------

* Refactor _enroll_users() method to pay down technical debt
* Improve admin messaging around enrollment actions

[0.24.0] - 2017-02-27
---------------------

* API for SSO pipeline is simplified to a single element.
* SSO users are linked to relevant Enterprise Customer when data sharing consent is disabled.

[0.23.2] - 2017-02-22
---------------------

* SSO users are not created as EnterpriseCustomerUsers until all consent requirements have been fulfilled.


[0.22.1] - 2017-02-20
---------------------

* Course Catalog API degrades gracefully in absence of Course Catalog service.


[0.22.0] - 2017-02-14
---------------------

* Added API endpoint for fetching entitlements available to an enterprise learner


[0.21.2] - 2017-02-07
---------------------

* Add id in EnterpriseCustomerUserSerializer fields


[0.21.0] - 2017-01-30
---------------------

* Add UI handling for course-specific data sharing consent


[0.20.0] - 2017-01-30
---------------------

* Add ability to select existing learners to be enrolled in courses from admin


[0.19.1] - 2017-01-30
---------------------

* Resolved conflicting urls for User API endpoint.


[0.19.0] - 2017-01-30
---------------------

* Added read-only enterprise API endpoint for IDAs.
* Moved utility functions from api.py to utils.py


[0.18.0] - 2017-01-27
---------------------

* Add the ability to notify manually-enrolled learners via email.


[0.17.0] - 2017-01-25
---------------------

* Add the EnterpriseCourseEnrollment model and related methods


[0.16.0] - 2017-01-25
---------------------

* Fix a bug preventing a course catalog from being unlinked from an EnterpriseCustomer


[0.15.0] - 2017-01-25
---------------------

* Enroll users in a program.


[0.14.0] - 2017-01-20
---------------------

* Added view of seat entitlements on enterprise admin screen


[0.13.0] - 2017-01-06
---------------------

* Dynamically fetch available course modes in the Manage learners admin


[0.12.0] - 2017-01-05
---------------------

* Create pending enrollment for users who don't yet have an account.


[0.11.0] - 2017-01-05
---------------------

* Added links from the Manage Learners admin panel to individual learners.


[0.10.0] - 2017-01-04
---------------------

* Added the ability to search the Manage Learners admin panel by username and email address.


[0.9.0] - 2016-12-29
--------------------

* In django admin page for enterprise customer added alphabetical ordering for
  catalog drop down and displayed catalog details link next to selected catalog.


[0.8.0] - 2016-12-08
--------------------

* added the branding information api methods to return the enterprise customer logo on the basis of provider_id or uuid.
* Updated the logo image validator to take an image of size maximum of 4kb.


[0.7.0] - 2016-12-07
--------------------

* Added a feature to enroll users in a course while linking them to an
  enterprise customer.


[0.6.0] - 2016-12-04
--------------------

* Fixed EnterpriseCustomer form to make Catalog field optional
* Added user bulk linking option
* Added Data Sharing Consent feature


[0.5.0] - 2016-11-28
--------------------

* Added checks to make sure enterprise customer and identity provider has one-to-one relation.
* Added a helper method to retrieve enterprise customer branding information


[0.4.1] - 2016-11-24
--------------------

* Fixed User.post_save handler causing initial migrations to fail


[0.4.0] - 2016-11-21
--------------------

* Set up logic to call course catalog API to retrieve catalog listing to attach to EnterpriseCustomer.


[0.3.1] - 2016-11-21
--------------------

* Fixed missing migration.


[0.3.0] - 2016-11-16
--------------------

Added
^^^^^

* Added Pending Enterprise Customer User model - keeps track of user email linked to Enterprise Customer, but not
  yet used by any user.
* Added custom "Manage Learners" admin view.

Technical features
^^^^^^^^^^^^^^^^^^

* Added sphinx-napoleon plugin to support rendering Google Style docstrings into documentation properly (i.e.
  make it recognize function arguments, returns etc.)
* Added translation files


[0.2.0] - 2016-11-15
--------------------

* Linked EnterpriseCustomer model to Identity Provider model


[0.1.2] - 2016-11-04
--------------------

* Linked EnterpriseCustomer model to django Site model


[0.1.1] - 2016-11-03
--------------------

* Enterprise Customer Branding Model and Django admin integration


[0.1.0] - 2016-10-13
--------------------

* First release on PyPI.
* Models and Django admin integration
