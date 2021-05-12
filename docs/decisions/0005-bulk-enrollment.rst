Multiple Enterprise Support
---------------------------

Status
======

Accepted

Context
=======

Business need: The admin portal feature to enroll multiple learners in multiple courses that belong to subscriptions with ease needs a suitable backend.

Various enrollment apis exist, but they do not cater or optimize for multiple enrollments.

models:

`EnterpriseCustomerUser` model has an `enroll()` method
`EnrollmentApiClient` has a `enroll_user_in_course()` method

enterprise/utils.py:

* `enroll_user`: calls the `EnrollmentApiClient#enroll_user_in_course` method
* `enroll_users_in_course`: multiple users one course

Views:

* there is a `_enroll_learner_in_course()` method in `views.py::GrantDataSharingPermission`

Also for bulk enrollment, there is a desire to avoid calling the REST based facilities, which is also true in general.
This is because edx-enterprise runs in situ with edx-platform.


Decisions
=========

* We will add a new endpoint to edx-enterprise to handle bulk enrollment in a single request.
  We are not reusing the existing methods because none is optimized for multiple enrollments
* Any failures in individual enrollments will not cause failures of the entire batch. In other words, the endpoint will be non transactional.
* We will not have MFEs call this endpoint directly. Rather they will call a license-manager has an endpoint which will call this endpoint.
  There are several reasons for this:
  * Only licensed learners should be enrolled in the subscription's courses. This design will guard against any frontend requests containing non desired learners.
  * Calling license-manager from edx-enterprise requires edx-enterprise ti know about license-manager which breaks the current design
  * Finally, semantically it makes sense to request a license management service to handle license based enrollments.
* The edx-enterprise endpoint will return a response with `{'successes': [], 'pending': [], 'failures': []}`. This will allow the license-manager to
  inform the user if any enrollments failed, while successfully (or pending) enrolling the rest, in a single request cycle.

Consequences
============

#. MFEs can make a single license-manager request for bulk enrollment
#. Spurious enrollments of non-eligible learners is avoided
#. Partially enrolling from a batch of large requests allows for a better user experience for admins, while receiving info on failed enrollments
