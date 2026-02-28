# [edx-enterprise] Add GradeEventContextEnricher pipeline step

Blocked by: [openedx-filters] Add GradeEventContextRequested filter

Create a new file `enterprise/filters/grades.py` containing the `GradeEventContextEnricher` pipeline step. This step implements the `GradeEventContextRequested` filter by querying `EnterpriseCourseEnrollment.get_enterprise_uuids_with_user_and_course` to determine whether the user is enrolled in the course through an enterprise. If an enterprise UUID is found, the step returns an enriched copy of the context dict containing an `"enterprise_uuid"` key. If no enterprise enrollment is found, the step returns the context unchanged. An `__init__.py` is also created so the `enterprise/filters/` directory is a proper Python package.

## A/C

- `enterprise/filters/grades.py` defines `GradeEventContextEnricher(PipelineStep)`.
- `GradeEventContextEnricher.run_filter(self, context, user_id, course_id)` queries `EnterpriseCourseEnrollment.get_enterprise_uuids_with_user_and_course(str(user_id), str(course_id))`.
- When at least one UUID is found, returns `{"context": {**context, "enterprise_uuid": str(uuids[0])}}`.
- When no UUIDs are found, returns `{"context": context}` (unchanged).
- Unit tests are added in `tests/filters/test_grades.py` covering both branches.
- No import of `openedx.features.enterprise_support` in the new pipeline step file.
