Configuration and usage
=======================

Getting around the administrator interface
------------------------------------------

The ``edx-enterprise`` project is integrated with edx-platform Django admin. It can be accessed at
``$LMS_SERVER_ADDRESS/admin/enterprise``. Current administrator interface is considered provisional until an independent
full-featured enterprise portal is built, so not much time was spent on improving admin tools UX.

.. image:: images/enterprise-admin.png

So far, there are four items in the admin interface:

* "Enrollment notification email templates" - manages templates used to build enrollment notifications.
* "Enterprise Customers" - lists and manages Enterprise Customer records.
* "Enterprise Customer Users" - lists and manages enterprise customer students.
* "Pending Enterprise Customer Users" - lists and manages "pending" enterprise customer students.

.. image:: images/enterprise-customer.png

The edx-enterpise admin site provides two ways to manage learners: The "Enterprise Customer Users" section mentioned
above, and the "Manage Learners" view. The "Manage Learners" view is recommended as it is easier to understand and
provides more features. To access it, first go to the "Enterprise Customer" section of the admin site, then click on a
customer, and then click on the "Manage Learners" button in the top-right corner of the page.

Manage Learners View
--------------------

The Manage Learners view is meant to be used by non-technical staff to administer enterprise learners.
It can be used to:

* Associate ("link") and disassociate ("unlink") existing students with Enterprise Customer.
* Associate learners with the Enterprise customer even if they don't have an account yet (these
  learners are known as "Pending Enterprise Customer Users"). Pending Enterprise Customer Users are
  referenced/identified by their email address only.
* Manually enroll groups of enterprise learners into courses and/or programs.

.. image:: images/manage-learners.png

Integrating with Course Catalog
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

In order for course enrollment features to work, ``edx-enterprise`` talks to the `Course Catalog Service`_. Instructions
on setting up and configuring Course Catalog can be found at corresponding `docs section`_ of Course Catalog and in
``edx-enterprise`` `Pull Request #7`_ (describes developer setup, but useful for a broader audience).

One particular quirk is that Course Catalog Service, being an independent application, restricts access to
courses/programs according to ownership rules, so only users with certain roles can list all programs and courses, as
``edx-enterprise`` admin interface expects. This is covered in greater detail in aforementioned docs section and pull
request.

.. _Course Catalog Service: https://open-edx-course-catalog.readthedocs.io/en/latest/getting_started.html
.. _docs section: https://open-edx-course-catalog.readthedocs.io/en/latest/getting_started.html#lms-integration
.. _Pull Request #7: https://github.com/edx/edx-enterprise/pull/7

Managing Linked Learners Lists
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Manage Learners view allows for two modes of linking users to an Enterprise Customer:

* Singular - single user email or username is provided.
* Bulk - CSV file containing single column of emails is uploaded.

When linking a single user by username, ``edx-enterprise`` tries to find an existing user with that username and fails
the linking if match was not found. When email is used (both in singular and bulk modes), existing users using that
email are linked to Enterprise Customer; if email match was not found a "Pending linked learner" record is created for
that email. If that email is used to register a new user that user is automatically linked with Enterprise customer.

**Note:** at the moment of writing, each learner can be linked only to one Enterprise Customer, so linking fails if the
learner is already associated with some other Enterprise Customer.

The view also allows unlinking "Linked Learners" and "Pending Linked Learners".

Enrolling Learners into Course or Program
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Enrolling learners into course or program depends on Course Catalog integration as ``edx-enterprise`` uses
Course Catalog Service API to fetch course/program information.

When "Course ID" input is filled, "Program ID" input is blocked and "Course Enrollment Mode" is automatically populated
with course modes available for chosen course.

When "Program ID" input is filled, "Course ID" input is blocked and "Course Enrollment Mode" is reset to a list of all
course enrollment modes\ [#f1]_

Enrollment notification email templates
---------------------------------------

When learners are enrolled into a course/program, admins might opt-in to send enrollment notification emails when
enrolling students. This admin section manages templates used to build such emails.

Template engine supports plaintext and HTML emails and allows substituting certain placeholders with real values,
pulled from enrollment data (i.e. username, organization, course/program name, etc.). For details, refer to help strings
provided by the form.

.. image:: images/enrollment-notification-email-template.png

Template edit view has preview capability - note "Preview (program)" and "Preview (course)" buttons in top-right corner.


.. rubric:: Footnotes

.. [#f1] Course Catalog Service API does not expose any means to get a list of modes supported by *all* courses in the
  program, so it relies on administrator to choose the right mode. However, validation is performed on the backend, and
  if unavailable mode is chosen a list of available modes is shown in an error message.
