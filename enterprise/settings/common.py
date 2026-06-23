"""
Common plugin settings for the enterprise app.
"""
from typing import Any

# Shape of an OPEN_EDX_FILTERS_CONFIG map: ``{filter_type: {'fail_silently': bool, 'pipeline': list[str]}}``.
FiltersConfig = dict[str, dict[str, Any]]


ENTERPRISE_FILTERS_CONFIG: FiltersConfig = {
    "org.openedx.learning.account.settings.read_only_fields.requested.v1": {
        "fail_silently": False,
        "pipeline": ["enterprise.filters.accounts.AccountSettingsEnterpriseReadOnlyFieldsStep"],
    },
    "org.openedx.learning.dashboard.render.started.v1": {
        "fail_silently": False,
        "pipeline": ["enterprise.filters.dashboard.DashboardContextEnricher"],
    },
    "org.openedx.learning.grade.context.requested.v1": {
        "fail_silently": False,
        "pipeline": ["enterprise.filters.grades.GradeEventContextEnricher"],
    },
    "org.openedx.learning.course.enrollment.view.started.v1": {
        "fail_silently": False,
        "pipeline": ["enterprise.filters.enrollment.EnterpriseEnrollmentViewProcessor"],
    },
    "org.openedx.learning.course.start_date.validation_failed.v1": {
        "fail_silently": False,
        "pipeline": ["enterprise.filters.courseware.EnterpriseStartDateAccessFailureStep"],
    },
    # NOTE: Pipeline ordering matters here. ActiveEnterpriseCheckStep must run before
    # consent's DataSharingConsentCourseAccessStep to match the original platform behavior
    # (the incorrect-enterprise redirect took priority over the DSC redirect). This ordering
    # is guaranteed because setup.py lists "enterprise" before "consent" in entry_points,
    # stevedore preserves intra-distribution order, and consent's plugin_settings appends
    # its step after enterprise's via _merge_filters_config.
    "org.openedx.learning.courseware.access_checks.requested.v1": {
        "fail_silently": False,
        "pipeline": ["enterprise.filters.courseware.ActiveEnterpriseCheckStep"],
    },
}


def _merge_filters_config(existing: FiltersConfig, additions: FiltersConfig) -> None:
    """
    Merge ``additions`` into ``existing`` in place without overwriting operator-defined entries.

    For each filter type in ``additions``:
      - If the filter type is not already present, copy it in.
      - If it is present, append the new pipeline steps after any existing steps and
        only set ``fail_silently`` when the existing entry has not specified it.
    """
    for filter_type, filter_config in additions.items():
        if filter_type in existing:
            existing_pipeline = existing[filter_type].setdefault('pipeline', [])
            for step in filter_config.get('pipeline', []):
                if step not in existing_pipeline:
                    existing_pipeline.append(step)
            existing[filter_type].setdefault('fail_silently', filter_config.get('fail_silently', True))
        else:
            # Copy so subsequent merges/mutations don't leak back into the plugin default dict.
            existing[filter_type] = {
                'fail_silently': filter_config.get('fail_silently', True),
                'pipeline': list(filter_config.get('pipeline', [])),
            }


def plugin_settings(settings):
    """
    Override platform settings for the enterprise app.

    This is called by the Open edX plugin system during LMS/CMS startup. Add
    any Django settings overrides here (e.g. ``settings.SOME_FLAG = True``).

    Args:
        settings: The Django settings module being configured.
    """
    # Skip injecting ANY default enterprise settings if the enterprise feature is entirely disabled.
    if not getattr(settings, 'ENABLE_ENTERPRISE_INTEGRATION', False):
        return

    settings.OVERRIDE_COURSE_HOME_PROGRESS_USERNAME = (
        'enterprise.overrides.course_home_progress.enterprise_obfuscated_username'
    )

    pipeline = getattr(settings, 'SOCIAL_AUTH_PIPELINE', None)
    if pipeline is not None:
        email_step = 'enterprise.tpa_pipeline.enterprise_associate_by_email'
        oauth_step = 'common.djangoapps.third_party_auth.pipeline.associate_by_email_if_oauth'
        if email_step not in pipeline:
            # pipeline.index() intentionally raises ValueError if the reference step is
            # missing — this prevents Django from starting with a misconfigured pipeline.
            pipeline.insert(pipeline.index(oauth_step), email_step)

        logistration_step = 'enterprise.tpa_pipeline.handle_enterprise_logistration'
        associate_step = 'social_core.pipeline.social_auth.associate_user'
        if logistration_step not in pipeline:
            # pipeline.index() intentionally raises ValueError if the reference step is
            # missing — this prevents Django from starting with a misconfigured pipeline.
            pipeline.insert(pipeline.index(associate_step) + 1, logistration_step)

    # Merge enterprise filter pipeline steps into OPEN_EDX_FILTERS_CONFIG so we never clobber
    # operator-defined entries (e.g. extra pipeline steps configured via YAML).
    filters_config = getattr(settings, 'OPEN_EDX_FILTERS_CONFIG', None)
    if filters_config is None:
        filters_config = {}
        settings.OPEN_EDX_FILTERS_CONFIG = filters_config
    _merge_filters_config(filters_config, ENTERPRISE_FILTERS_CONFIG)
