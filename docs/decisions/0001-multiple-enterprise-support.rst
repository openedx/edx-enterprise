Multiple Enterprise Support
---------------------------

Status
======

Accepted

Context
=======

There is a business need to be able to support a learner being linked to multiple enterprises. Today, edX workflows only support a 1-to-1 linkage and our system does not prevent linking multiple Enterprises to a single learner. Hence not all workflows work as expected.

Some examples of these errant workflows are:

#. When a learner is linked with an enterprise and tries to link with another enterprise(through SSO), the learner is redirected to the login page instead of the registration page for the second enterprise. This is because the system detects that these credentials are already in the system.

#. Enrollment, Progression, Completion, Consent records become ambiguous if a learner completes a course from enterprise A and then attempts the same course through enterprise B.

#. Incorrect discounts are applied when an employee linked with multiple enterprises redeems the benefit applicable only to one of the enterprises.


Decisions
=========

Short term updates:

As part of the login flow the user would select one of the linked enterprises. This selection would only happen once, after user authentication in the login flow.

Long term updates:

An account/profile switcher like we have in New Relic, Google, etc. with a flow similar to the following could be Implemented.

#. User flow will allow the learner to login without any enterprise related barriers.

#. After login, user is reminded that they are linked to multiple Enterprises and that they need to select the "profile" they intend to use during this logged-in session before executing any enrollment or other transaction in the system.

#. The enterprise "profile" would be specified using a "switch enterprise" page.

#. If a learner logs in via SSO with account-A, but intends to proceed using account-B, they would be logged out so that they can then re-login via account-B.

#. The text on the new "switch enterprise" page makes the above user-flow and selection as clear as possible for the learner.



Consequences
============

#. Discounts applied correctly for users connected to multiple enterprises.

#. Unambiguous transactional data history for enterprise users.
