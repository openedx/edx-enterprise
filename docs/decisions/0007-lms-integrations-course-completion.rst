Determining course completion for various course modes
------------------------------------------------------

Status
======

Draft

Context
=======

LMS integrations have a learner_data module that reports out (to external LMS systems),
a field (boolean) called `course_completed`, along with any available grading data.

For Non Audit-mode enrollments: the value `completed_date` is used as an indication
of course completion. This is deterministic for courses that issue certificates or grading info

However, for Audit mode enrollments, there is a case where the learner has already finished all non-gated content.
But in this state, `course_completed` will never be true for these learners who never upgrade to verified, for example.
Also there is no more content learner can do anything with. So in this sense, they are done with the course.

Also, these learners don't always have access to all the content. So we cannot rely on
certificate or grade information to detect if they are 'done' with a course.

In fact there is no one deterministic definition of course_completed for audit track.

Therefore, for LMS integration customers to get a sense of how audit learners are doing, with completion,
we need to offer a best approximation sense of `course_completed`.


Decisions
=========

Integrated channels will determine the `course_completed` for each enrollment with the following logic::

    if audit_enrollment:
        Transmit course as complete for this learner, if no non-gated content is remaining to be finished
    else:
        Transmit course as complete if certificate or grading data indicates completion_date is available.


Consequences
============

We will have more accurate reporting of completion of course (in some sense) for audit track.
There is no precise way to define that a learner is done with a course unless we are issuing a certificate.
Therefore this best approximation is being used for LMS integrations.
