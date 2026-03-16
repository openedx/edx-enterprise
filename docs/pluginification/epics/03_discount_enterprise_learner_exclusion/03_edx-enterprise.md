# [edx-enterprise] Add DiscountEligibilityStep pipeline step

Blocked by: [openedx-filters] Add DiscountEligibilityCheckRequested filter

Create a new file `enterprise/filters/discounts.py` containing the `DiscountEligibilityStep` pipeline step. This step implements the `DiscountEligibilityCheckRequested` filter by checking whether the user is an enterprise learner (via `is_enterprise_learner` from `enterprise_support.utils`, which is acceptable until epic 17 migrates that module). If the user is an enterprise learner, the step returns `{"is_eligible": False}` to exclude them from the discount. Otherwise it returns the inputs unchanged.

## A/C

- `enterprise/filters/discounts.py` defines `DiscountEligibilityStep(PipelineStep)`.
- `DiscountEligibilityStep.run_filter(self, user, course_key, is_eligible)` calls `is_enterprise_learner(user)` (imported from `enterprise_support.utils` until epic 17).
- If `is_enterprise_learner(user)` returns `True`, returns `{"user": user, "course_key": course_key, "is_eligible": False}`.
- Otherwise returns `{"user": user, "course_key": course_key, "is_eligible": is_eligible}`.
- Unit tests in `tests/filters/test_discounts.py` cover both the enterprise and non-enterprise branches.
