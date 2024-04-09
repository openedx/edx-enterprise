"""
Django management command to send nudge email to dormant enrolled enterprise learners.
"""
import logging

import snowflake.connector

from django.conf import settings
from django.core.management import BaseCommand

from enterprise import utils

LOGGER = logging.getLogger(__name__)
QUERY = '''
    WITH first_video as (
        -- fetch first unhidden video in a course.
        SELECT
            course_id,                        -- the course run key.
            ROW_NUMBER() OVER
            (PARTITION BY course_id
             ORDER BY order_index) row_,      -- the order of the video in the course.
            block_type,                       -- the type of block (should be "video" for all).
            display_name,                     -- the name of the video.
            lms_web_url                       -- the link to the area in the course where the video is.
        FROM
            core_sources.course_structure
        WHERE
            block_type = 'video'              -- filter videos only.
        AND
            is_visible_to_staff_only = False  -- filter hidden videos out.
        QUALIFY
            row_ = 1                          -- only get the first video for each course.
    ),
    not_started as (
        SELECT
            lms_user_id,
            lms_courserun_key,
            split_part(course_key,'+',1) as org_name,
            course_title,
            consent_created,
            lms_enrollment_created,
            lms_enrollment_mode,
            block_count
        FROM
            enterprise.ent_base_enterprise_enrollment
        WHERE
            DATE(lms_enrollment_created) BETWEEN CURRENT_DATE - 13 AND CURRENT_DATE - 7
        AND
            COALESCE(block_count,0) = 0
        AND
            consent_granted = True
    ),
    course_data as (
        SELECT
            dcr.courserun_key,
            dcr.start_datetime,
            cmcr.min_effort,
            cmcr.max_effort,
            cmcr.enrollment_count,
            CASE WHEN cmcr.pacing_type = 'self_paced' THEN 'Self Paced' ELSE 'Instructor Paced' END as pacing_type,
            cmcr.weeks_to_complete,
            'https://prod-discovery.edx-cdn.org/' || cmc.image as course_image
        FROM
            core.dim_courseruns as dcr
        LEFT JOIN
            discovery.course_metadata_courserun as cmcr
        ON
            dcr.courserun_key = cmcr.key
        LEFT JOIN
            discovery.course_metadata_course as cmc
        ON
            cmcr.course_id = cmc.id
        WHERE
            cmcr.draft = False
        AND
            cmc.draft = False
    )
    SELECT
        not_started.lms_user_id as external_id,
        not_started.org_name,
        not_started.course_title,
        course_data.enrollment_count,
        course_data.min_effort,
        course_data.max_effort,
        course_data.weeks_to_complete,
        course_data.pacing_type,
        CASE WHEN pacing_type = 'Instructor Paced' THEN 'Led on a course schedule' ELSE 'Move at your speed' END as pacing_subtitle,
        COALESCE(CASE WHEN first_video.display_name = 'Video' THEN 'First Video' ELSE first_video.display_name END,'First Video') as display_name,
        course_data.course_image,
        first_video.lms_web_url,
        'https://courses.edx.org/courses/' || not_started.lms_courserun_key || '/discussion/forum/' as discussion_link,
        'https://learning.edx.org/course/' || not_started.lms_courserun_key || '/home' as home_link
    FROM
        not_started
    LEFT JOIN
        first_video
    ON
        not_started.lms_courserun_key = first_video.course_id
    LEFT JOIN
        course_data
    ON
        not_started.lms_courserun_key = course_data.courserun_key
    WHERE
        -- start date is in the past.
        course_data.start_datetime <= CURRENT_DATE
    AND
        -- there is a video.
        lms_web_url IS NOT NULL
    -- Note: this filters out so the learner only has one sample in the dataset. In a productized feature, this constraint would probably be removed,
    -- and the learner would get an email when any of the enrollment hit this stage.
    QUALIFY
        ROW_NUMBER() OVER (PARTITION BY not_started.lms_user_id ORDER BY lms_enrollment_created DESC) = 1
'''


class Command(BaseCommand):
    """
    Django management command to send nudge email to dormant enrolled enterprise learners.

    Example usage:
    ./manage.py lms nudge_dormant_enrolled_enterprise_learners
    ./manage.py lms nudge_dormant_enrolled_enterprise_learners --no-commit
    """

    def add_arguments(self, parser):
        parser.add_argument(
            '--no-commit',
            action='store_true',
            dest='no_commit',
            default=False,
            help='Dry Run, print log messages without committing anything.',
        )

    def get_query_results_from_snowflake(self):
        """
        Get query results from Snowflake and yield each row.
        """
        ctx = snowflake.connector.connect(
            user=settings.SNOWFLAKE_SERVICE_USER,
            password=settings.SNOWFLAKE_SERVICE_USER_PASSWORD,
            account='edx.us-east-1',
            database='prod'
        )
        cs = ctx.cursor()
        try:
            cs.execute(QUERY)
            rows = cs.fetchall()
            yield from rows
        finally:
            cs.close()
        ctx.close()

    def emit_event(self, **kwargs):
        """
         Emit the Segment event which will be used by Braze to send the email
        """
        utils.track_event(kwargs['EXTERNAL_ID'], 'edx.bi.enterprise.user.dormant.nudge', kwargs)
        LOGGER.info(
            '[Dormant Nudge] Segment event fired for nudge email to dormant enrolled enterprise learners. '
            'LMS User Id: {user_id}, Organization Name: {org_name}, Course Title: {course_title}'.format(
                user_id=kwargs['EXTERNAL_ID'],
                org_name=kwargs['ORG_NAME'],
                course_title=kwargs['COURSE_TITLE']
            )
        )

    def handle(self, *args, **options):
        should_commit = not options['no_commit']

        LOGGER.info('[Dormant Nudge]  Process started.')
        for next_row in self.get_query_results_from_snowflake():
            message_data = {
                'EXTERNAL_ID': next_row[0],
                'ORG_NAME': next_row[1],
                'COURSE_TITLE': next_row[2],
                'ENROLLMENT_COUNT': next_row[3],
                'MIN_EFFORT': next_row[4],
                'MAX_EFFORT': next_row[5],
                'WEEKS_TO_COMPLETE': next_row[6],
                'PACING_TYPE': next_row[7],
                'PACING_SUBTITLE': next_row[8],
                'DISPLAY_NAME': next_row[9],
                'COURSE_IMAGE': next_row[10],
                'LMS_WEB_URL': next_row[11],
                'DISCUSSION_LINK': next_row[12],
                'HOME_LINK': next_row[13]
            }
            if should_commit:
                self.emit_event(**message_data)

        LOGGER.info('[Dormant Nudge] Execution completed.')
