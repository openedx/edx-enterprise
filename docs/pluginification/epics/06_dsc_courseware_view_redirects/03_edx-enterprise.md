# [edx-enterprise] Add CoursewareViewRedirectURL pipeline steps

Blocked by: [openedx-filters] Add CoursewareViewRedirectURL filter

Create `enterprise/filters/courseware.py` with two pipeline steps: `ConsentRedirectStep` and `LearnerPortalRedirectStep`. `ConsentRedirectStep` replicates the logic of `get_enterprise_consent_url` — checking if the user has granted data sharing consent for the course, and if not, appending the consent URL to `redirect_urls`. `LearnerPortalRedirectStep` replicates the logic of `enterprise_learner_enrolled` — checking if the user is enrolled via an enterprise learner portal and appending the portal redirect URL if so. Both steps call enterprise_support utility functions internally (using deferred imports) until epic 17 migrates enterprise_support into edx-enterprise.

## A/C

- `enterprise/filters/courseware.py` defines `ConsentRedirectStep(PipelineStep)` and `LearnerPortalRedirectStep(PipelineStep)`.
- `ConsentRedirectStep.run_filter` checks DSC consent for the request user and course, appending a consent redirect URL to `redirect_urls` when consent is not granted.
- `LearnerPortalRedirectStep.run_filter` checks if the user is enrolled via enterprise portal and appends the portal redirect URL when applicable.
- Both steps use deferred imports from `openedx.features.enterprise_support.api` until epic 17.
- Unit tests in `tests/filters/test_courseware.py` cover both steps with mocked enterprise_support functions.
