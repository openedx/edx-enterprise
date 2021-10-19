Bulk Enrollment endpoint for Subscription learners
--------------------------------------------------

Status
======

Accepted

Context
=======

Business need: The admin portal feature to enroll multiple learners in multiple subscription-courses
needs a suitable backend.

Various enrollment apis exist, but they do not cater to or optimize for multiple enrollments.

There is an `EnrollmentApiClient` which has an `enroll_user_in_course()` method used by:
  * models::EnterpriseCustomerUser::enroll()
  * utils::enroll_user() ( handles multiple courses )
  * views::CourseEnrollmentView::post()
  * views::HandleConsentEnrollment::get()
  * views::GrantDataSharingPermission::_enroll_learner_in_course()

There is also a method to create pending user enrollments for non-edX users at:
  `models::EnterpriseCustomer::enroll_user_pending_registration()`

This method also handles multiple courses.

Due to the scale and volume considerations, an api endpoint is needed that caters to the bulk
use case without hitting rate limiting issues or server overload.

Decisions
=========

* We will add a new endpoint to edx-enterprise to handle bulk enrollment in a single request.
* For existing edX users, we will reuse the `utils::enroll_user()` method.
  This method handles multiple courses already, but still calls the `EnrollmentApiClient` for now.
  There is a cleanup effort anticipated to replace the HttpClient calls embedded in the `utils::enroll_user()` method with direct database call utilties in the edx-platform Django application.
  Such a cleanup is not in scope for this feature work.
* For emails not matching existing users in edX LMS Django application, we will use the `models::EnterpriseCustomer::enroll_user_pending_registration()` method
* We will create an ecommerce order for each successful enrollment of an existing edX user.
  For this we will use the `EcommerceApiClient::create_manual_enrollment_orders()` method which creates an order for each enrollment passed.
* Any failures in individual enrollments will not cause failures of the entire batch.
  In other words, the endpoint will be non transactional. This avoid wasteful and confusing workflow for the client of the api, by performing a 'best effort' enrollment and reporting the failures.
* We will not have MFEs call this endpoint directly. Rather they will call a license-manager endpoint which will call this endpoint.
  There are several reasons for this:
  #. Only licensed learners should be enrolled in the subscription's courses. This design will guard against any frontend requests containing non-desired learners.
  #. Calling license-manager from edx-enterprise requires edx-enterprise to know about license-manager which is counter to the archiectural design for edx-enterprise
  #. Finally, semantically it makes sense to request a license management service to authorize license based enrollments.
* The edx-enterprise endpoint will return a response with these pieces of information:
  `{'successes': [], 'pending': [], 'failures': []}`. Note, pending enrollments are supported.
  This will allow the license-manager to inform the user if any enrollments failed, while successfully (meaning: success or pending) enrolling the rest, in a single request cycle.
* The endpoint will be safe to invoke with pre-existing enrollment pairs (meaning learner email + course_id). These enrollments will also be added to 'successes' in the response.
* The endpoint will also support a boolean input to notify learners of enrollments (or not) by email

Consequences
============

#. MFEs can make a single reliable request for bulk enrollment
#. Spurious enrollments of non-eligible learners is avoided
#. Partially enrolling 'what it can' and recording the rest in a response, allows for a better
   user experience for admins and the use of a single coherent endpoint.
