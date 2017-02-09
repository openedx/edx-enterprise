Configuration and usage
=======================

Getting around the administrator interface
------------------------------------------

The ``edx-enterprise`` project is integrated with ``edx-platform`` Django admin. It can be accessed at
``$LMS_SERVER_ADDRESS/admin/enterprise``. The current administrator interface is considered provisional until an
independent full-featured enterprise portal is built, so not much time was spent on improving admin tools UX.

.. image:: images/enterprise-admin.png

So far, there are four items in the admin interface:

* "Enrollment notification email templates" - manages templates used to build enrollment notifications.
* "Enterprise Customers" - lists and manages Enterprise Customer records.
* "Enterprise Customer Users" - lists and manages students associated with Enterprise Customers.
* "Pending Enterprise Customer Users" - lists and manages "pending" Enterprise Customer students.

.. image:: images/enterprise-customer.png

The ``edx-enterprise`` admin site provides two ways to manage learners: The "Enterprise Customer Users" section
mentioned above, and the "Manage Learners" view. The "Manage Learners" view is recommended as it is easier to understand
and provides more features. To access it, first go to the "Enterprise Customer" section of the admin site, then click
on a customer, and then click on the "Manage Learners" button in the top-right corner of the page.

Manage Learners View
--------------------

The Manage Learners view is meant to be used by non-technical staff to administer enterprise learners.
It can be used to:

* Associate ("link") and disassociate ("unlink") existing students with an Enterprise Customer.
* Associate learners with an Enterprise customer even if they don't have an account yet (these
  learners are known as "Pending Enterprise Customer Learners"). Pending Enterprise Customer Learners are
  identified by their email address only.
* Manually enroll groups of enterprise learners into courses and/or programs.

.. image:: images/manage-learners.png

Integrating with the Course Catalog
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

In order for course enrollment features to work, ``edx-enterprise`` talks to the `Course Catalog Service`_. Instructions
on how to set up and configure the Course Catalog service can be found at corresponding `docs section`_ of Course
Catalog and in ``edx-enterprise`` `Pull Request #7`_ (describes developer setup, but useful for a broader audience).

One particular quirk is that the Course Catalog Service, being an independent application, restricts access to
courses and programs according to ownership rules, so only users with certain roles can list all programs and courses,
as the ``edx-enterprise`` admin interface expects. This is covered in greater detail in aforementioned docs section.

.. _Course Catalog Service: https://open-edx-course-catalog.readthedocs.io/en/latest/getting_started.html
.. _docs section: https://open-edx-course-catalog.readthedocs.io/en/latest/getting_started.html#lms-integration
.. _Pull Request #7: https://github.com/edx/edx-enterprise/pull/7

Managing Linked Learners Lists
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The Manage Learners view allows for two modes of linking users to an Enterprise Customer:

* Singular - A single user email address or username is provided.
* Bulk - A CSV file containing a single column of email addresses is uploaded.

When linking a single user by username, ``edx-enterprise`` tries to find an existing user with that username and fails
the linking if a match was not found. When email address is used (either in singular or bulk mode), existing users using
that email address are linked to the Enterprise Customer. If an email address match was not found, a "Pending Linked
Learner" record is created for that email address. If that email address is used to register a new user, then that user
is automatically linked with the Enterprise Customer.

**Note:** Each learner can be linked only to one Enterprise Customer, so linking fails if the learner is already
associated with some other enterprise customer.

The Manage Learners view also enables unlinking "Linked Learners" and "Pending Linked Learners."

Enrolling Learners into a Course or Program
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Enrolling learners into courses or programs depends on Course Catalog integration, because ``edx-enterprise`` uses the
Course Catalog API to fetch course and program information.

When "Course ID" input is filled, "Program ID" input is blocked and "Course Enrollment Mode" is automatically populated
with course modes available for chosen course.

When "Program ID" input is filled, "Course ID" input is blocked and "Course Enrollment Mode" is reset to a list of all
course enrollment modes\ [#f1]_

Enrollment notification email templates
---------------------------------------

When learners are enrolled into a course or program, admins might choose to send enrollment notification emails.
This admin section manages templates used to build such emails.

The template engine supports plaintext and HTML emails and allows substituting certain placeholders with real values,
which are pulled from enrollment data (i.e. username, organization, course or program name, etc.). For details, refer
to the help strings provided by the form.

.. image:: images/enrollment-notification-email-template.png

You can preview emails in the template edit view using the "Preview (program)" and "Preview (course)" buttons in
top-right corner.

.. rubric:: Footnotes

.. [#f1] Course Catalog Service API does not expose any means to get a list of modes supported by *all* courses in the
  program, so it relies on the administrator to choose the right mode. However, validation is performed on the back
  end, and if an unavailable mode is chosen, a list of available modes is shown in an error message.
