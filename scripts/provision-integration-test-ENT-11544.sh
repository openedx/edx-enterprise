#!/usr/bin/env bash
#
# Provision a devstack environment for integration-testing the three new
# openedx-filter pipeline steps added in ticket ENT-11544
# (DSC Courseware View Redirects).
#
# Run from the edx-enterprise directory with devstack already running:
#
#     ./scripts/provision-integration-test-ENT-11544.sh
#
# The script assumes a baseline devstack provision has already been run, which
# implies the following already exist and are NOT re-created here:
#   - course-v1:edX+DemoX+Demo_Course (live, past start date)
#   - users: honor@example.com, audit@example.com, verified@example.com,
#            staff@example.com (is_staff=True), edx@example.com (superuser)
#
set -eu -o pipefail
set -x

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

TEST_ENTERPRISE_NAME="Test Enterprise"
OTHER_ENTERPRISE_NAME="Other Enterprise"

DEMO_COURSE_ID="course-v1:edX+DemoX+Demo_Course"
FUTURE_COURSE_ID="course-v1:edX+FutureX+2027"
UNSCHEDULED_COURSE_ID="course-v1:edX+UnschedX+TBD"

# Users seeded by seed_enterprise_devstack_data --enterprise-name "Test Enterprise"
# (slug becomes "test-enterprise"):
TEST_ENT_LEARNER="enterprise_learner_test-enterprise"
TEST_ENT_LEARNER_1="test-enterprise_learner_1"
TEST_ENT_LEARNER_2="test-enterprise_learner_2"

DUAL_LINKED_LEARNER="dual_linked_learner"

# All users created by devstack_api are assigned the email "${username}@example.com".
TEST_ENT_LEARNER_2_EMAIL="${TEST_ENT_LEARNER_2}@example.com"
AUDIT_LEARNER_EMAIL="audit@example.com"

SUPERUSER_EMAIL="edx@example.com"

# ---------------------------------------------------------------------------
# Helpers — run a Django management command inside the LMS or CMS container
# ---------------------------------------------------------------------------

lms_manage() {
    docker exec -i edx.devstack.lms python manage.py lms --settings devstack "$@"
}

cms_manage() {
    docker exec -i edx.devstack.cms python manage.py cms --settings devstack "$@"
}

catalog_manage() {
    docker exec -i enterprise.catalog.app python manage.py "$@"
}

discovery_manage() {
    docker exec -i edx.devstack.discovery python manage.py "$@"
}

# ---------------------------------------------------------------------------
# Step 1: Create extra courses (future-dated + unscheduled)
# ---------------------------------------------------------------------------
# The demo course is already published by the baseline devstack provision.
# create_course and force_publish are CMS management commands.

cms_manage create_course split "$SUPERUSER_EMAIL" edX FutureX 2027 \
    "Future Course" 2030-01-01
echo "yes" | cms_manage force_publish "$FUTURE_COURSE_ID" --commit

cms_manage create_course split "$SUPERUSER_EMAIL" edX UnschedX TBD \
    "Unscheduled Course" 2040-01-01
echo "yes" | cms_manage force_publish "$UNSCHEDULED_COURSE_ID" --commit

# ---------------------------------------------------------------------------
# Step 2: Seed two enterprise customers and their linked users
# ---------------------------------------------------------------------------
# Each invocation creates the enterprise, its catalog, and a standard set of
# linked users (learners, admin, operator, service workers).

lms_manage seed_enterprise_devstack_data --enterprise-name "$TEST_ENTERPRISE_NAME"
lms_manage seed_enterprise_devstack_data --enterprise-name "$OTHER_ENTERPRISE_NAME"

# ---------------------------------------------------------------------------
# Step 2b: Sync enterprise catalogs to the enterprise-catalog service
# ---------------------------------------------------------------------------
# seed_enterprise_devstack_data fires a post_save signal that attempts to
# register the catalog with enterprise-catalog, but the call can fail silently
# (e.g. if the service wasn't fully ready).  Re-sync explicitly so that
# contains_content_items checks return accurate results.

discovery_manage refresh_course_metadata
lms_manage migrate_enterprise_catalogs --api_user enterprise-catalog_worker
catalog_manage update_content_metadata --no-async --force

# ---------------------------------------------------------------------------
# PR #338 — CoursewareViewStarted (DSC redirect)
# ---------------------------------------------------------------------------
# Scenarios:
#   - TEST_ENT_LEARNER: enrolled in demo course under "Test Enterprise",
#     DSC NOT granted -> triggers consent redirect.
#   - TEST_ENT_LEARNER_1: enrolled in demo course under "Test Enterprise",
#     DSC granted -> control (no redirect).
#   - honor@example.com: already enrolled in demo course, no enterprise link.
#     No action needed -> control (no redirect).

lms_manage enroll_enterprise_learner \
    --username "$TEST_ENT_LEARNER" \
    --course-id "$DEMO_COURSE_ID" \
    --enterprise-name "$TEST_ENTERPRISE_NAME"

lms_manage enroll_enterprise_learner \
    --username "$TEST_ENT_LEARNER_1" \
    --course-id "$DEMO_COURSE_ID" \
    --enterprise-name "$TEST_ENTERPRISE_NAME" \
    --grant-dsc

# ---------------------------------------------------------------------------
# PR #339 — CourseStartDateValidationFailed (enterprise start-date error)
# ---------------------------------------------------------------------------
# Scenarios:
#   - TEST_ENT_LEARNER: enrolled in the future and unscheduled courses under
#     "Test Enterprise" with DSC granted (so the start-date check runs instead
#     of the DSC check) -> enterprise-flavored start-date error.
#   - TEST_ENT_LEARNER_2: already linked to "Test Enterprise" by the seed
#     command. Gets a plain platform CourseEnrollment ONLY (no
#     EnterpriseCourseEnrollment) in the future course -> verifies the
#     non-subsidized path produces the generic start-date error.
#   - audit@example.com: plain non-enterprise learner. Gets a plain
#     CourseEnrollment in the future course -> generic start-date error.
#
# enroll_enterprise_learner always creates an EnterpriseCourseEnrollment and
# requires an enterprise link, so the two non-subsidized fixtures use the
# platform's enroll_user_in_course command (idempotent; takes -e email
# -c course-id) directly.

lms_manage enroll_enterprise_learner \
    --username "$TEST_ENT_LEARNER" \
    --course-id "$FUTURE_COURSE_ID" \
    --enterprise-name "$TEST_ENTERPRISE_NAME" \
    --grant-dsc

lms_manage enroll_enterprise_learner \
    --username "$TEST_ENT_LEARNER" \
    --course-id "$UNSCHEDULED_COURSE_ID" \
    --enterprise-name "$TEST_ENTERPRISE_NAME" \
    --grant-dsc

lms_manage enroll_user_in_course \
    -e "$TEST_ENT_LEARNER_2_EMAIL" \
    -c "$FUTURE_COURSE_ID"

lms_manage enroll_user_in_course \
    -e "$AUDIT_LEARNER_EMAIL" \
    -c "$FUTURE_COURSE_ID"

# ---------------------------------------------------------------------------
# PR #340 — CoursewareAccessChecksRequested (mismatch + DSC at access check)
# ---------------------------------------------------------------------------
# Scenarios:
#   - DUAL_LINKED_LEARNER: linked to both enterprises — "Test Enterprise"
#     active, "Other Enterprise" inactive — and enrolled in the demo course
#     under the INACTIVE enterprise -> triggers active-enterprise mismatch.
#   - TEST_ENT_LEARNER: already enrolled in the demo course under "Test
#     Enterprise" with DSC ungranted (from the PR #338 section above). No
#     additional action needed; exercises CourseHomeMetadataView DSC check.

lms_manage create_enterprise_linked_learner \
    --username "$DUAL_LINKED_LEARNER" \
    --enterprise-name "$TEST_ENTERPRISE_NAME" \
    --enterprise-name "$OTHER_ENTERPRISE_NAME"

lms_manage enroll_enterprise_learner \
    --username "$DUAL_LINKED_LEARNER" \
    --course-id "$DEMO_COURSE_ID" \
    --enterprise-name "$OTHER_ENTERPRISE_NAME"

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

set +x
cat <<EOF

=============================================================================
ENT-11544 integration test fixtures provisioned.
=============================================================================

Courses created:
  ${DEMO_COURSE_ID}        (live, started in the past — baseline devstack)
  ${FUTURE_COURSE_ID}      (start: 2030-01-01, "Future Course")
  ${UNSCHEDULED_COURSE_ID} (start: 2040-01-01, "Unscheduled Course")

Enterprises created (with the standard seeded user set each):
  "${TEST_ENTERPRISE_NAME}"
  "${OTHER_ENTERPRISE_NAME}"

-----------------------------------------------------------------------------
PR #338 — CoursewareViewStarted (DSC redirect)
-----------------------------------------------------------------------------

  1. [redirect] DSC-ungranted enterprise learner is redirected to the
     consent page when opening the courseware.
     a. Login using ${TEST_ENT_LEARNER}@example.com / edx
     b. Open courseware for ${DEMO_COURSE_ID}
     c. Expect a redirect to the DSC consent page (not the courseware unit).

  2. [control] DSC-granted enterprise learner sees the courseware
     normally (no redirect).
     a. Login using ${TEST_ENT_LEARNER_1}@example.com / edx
     b. Open courseware for ${DEMO_COURSE_ID}
     c. Expect the courseware unit to render with no consent redirect.

  3. [control] Non-enterprise learner sees the courseware normally.
     a. Login using honor@example.com / edx
     b. Open courseware for ${DEMO_COURSE_ID}
     c. Expect the courseware unit to render with no consent redirect.

-----------------------------------------------------------------------------
PR #339 — CourseStartDateValidationFailed (start-date error)
-----------------------------------------------------------------------------

  4. [ent err] Enterprise-linked learner sees the enterprise-flavored
     start-date error on a future-dated course.
     a. Login using ${TEST_ENT_LEARNER}@example.com / edx
     b. Open courseware for ${FUTURE_COURSE_ID}, then ${UNSCHEDULED_COURSE_ID}
     c. Expect an enterprise-branded "course not yet started" error
        (developer_message / user_message populated by the plugin step).

  5. [generic] Enterprise-linked learner WITHOUT an EnterpriseCourseEnrollment
     on the future course falls through to the generic error.
     a. Login using ${TEST_ENT_LEARNER_2_EMAIL} / edx
     b. Open courseware for ${FUTURE_COURSE_ID}
     c. Expect a generic StartDateFiltersError (non-enterprise flavor) —
        the plain CourseEnrollment bypasses the enterprise-specific gating.

  6. [generic] Pure non-enterprise learner sees the generic start-date
     error on the future course.
     a. Login using ${AUDIT_LEARNER_EMAIL} / edx
     b. Open courseware for ${FUTURE_COURSE_ID}
     c. Expect a generic StartDateFiltersError with no enterprise branding.

-----------------------------------------------------------------------------
PR #340 — CoursewareAccessChecksRequested (mismatch + DSC at access check)
-----------------------------------------------------------------------------

  7. [mismatch] Learner linked to two enterprises (Test=active,
     Other=inactive) but enrolled under the INACTIVE one triggers the
     active-enterprise mismatch check.
     a. Login using ${DUAL_LINKED_LEARNER}@example.com / edx
     b. Open courseware for ${DEMO_COURSE_ID}
     c. Expect an active-enterprise mismatch error (access denied because
        the enrollment's enterprise does not match the active one).

  8. [dsc chk] DSC check is enforced at CourseHomeMetadataView (not just
     the courseware view). Re-uses scenario 1's enrollment.
     a. Login using ${TEST_ENT_LEARNER}@example.com / edx
     b. Open course home / outline for ${DEMO_COURSE_ID}
     c. Expect a DSC failure surfaced by CourseHomeMetadataView (the home
        page is blocked, mirroring scenario 1's courseware redirect).

EOF
