"""
Django management command to send monthly impact report to enterprise admins.
"""
import logging

import snowflake.connector

from django.conf import settings
from django.core.management import BaseCommand

from enterprise import utils

LOGGER = logging.getLogger(__name__)
QUERY = '''
    -- Admins [CHECK]
    -- Daily Sessions  [CHECK]
    -- Hours of Learning [CHECK]
    -- Enrollments [CHECK]
    -- Course Completions [CHECK]
    -- Last Month’s avg hours of learning per learner (and a percentile rank of how that compares with over organizations that month). [CHECK]
    -- Last Month’s % of linked users who had at least 1 daily session.
    -- Top 5 skills the learners enrolled in. [CHECK]

    WITH dynamic_dates as (
    /*
    Set up a CTE that tracks the start and end date
    of last month and the prior month. Use it to create
    dynamic filtering in the subqueries, and reduce dependency
    on manually set date ranges.
    */

    SELECT
        CURRENT_DATE as cd,
        dateadd('month', -1, (date_trunc('month', cd))) as last_month_start_range,
        dateadd('day',-1,(date_trunc('month', cd))) as last_month_end_range,
        dateadd('month', -1, (date_trunc('month', last_month_start_range))) as two_months_ago_start_range,
        dateadd('day',-1,(date_trunc('month', last_month_start_range))) as two_months_ago_end_range
    ),

    TWO_MONTHS_AGO as(

    /*
    Collect all results from the two months ago. This will be used to
    benchmark and context set for the results one month ago.
    */

    WITH admins as (

    /*
    Get a list of admins.
        */

    SELECT DISTINCT
        ec.uuid,
        ec.name as enterprise_name,
        au.email,
        role.name,
        ecu.created as enterprise_user_role_created,
        assign.created as admin_role_assigned
    FROM
        "PROD"."LMS_PII"."ENTERPRISE_ENTERPRISECUSTOMER" ec
    JOIN
        "PROD"."LMS_PII"."ENTERPRISE_ENTERPRISECUSTOMERUSER" ecu
    ON
        ec.uuid=ecu.ENTERPRISE_CUSTOMER_ID
    JOIN
        "PROD"."LMS_PII"."AUTH_USER" au
    ON
        ecu.user_id=au.id
    JOIN
        "PROD"."LMS_PII"."ENTERPRISE_SYSTEMWIDEENTERPRISEUSERROLEASSIGNMENT" assign
    ON
        assign.user_id=au.id
      AND
        assign.user_id=ecu.user_id
    JOIN
        "PROD"."LMS_PII"."ENTERPRISE_SYSTEMWIDEENTERPRISEROLE" role
    ON
        role.id=assign.role_id
    WHERE
        role.name like 'enterprise_admin'
    ORDER BY
        au.email),

    learning_hours as (
    /*
    Get the sum of learning hours, grouped by enterprise UUID.
    */
    SELECT
        enterprise_customer_uuid,
        round(sum(learning_time_seconds)/60/60,2) as learning_hrs
    FROM
        enterprise.fact_enrollment_engagement_day_admin_dash
    WHERE
        activity_date >= (SELECT two_months_ago_start_range FROM dynamic_dates)
    AND
        activity_date <= (SELECT two_months_ago_end_range FROM dynamic_dates)
    GROUP BY
        enterprise_customer_uuid),

    new_enrolls as (

    /*
    Gets number of new enrollment IDs created, grouped by enterprise UUID.
    */

    SELECT
        lpr.enterprise_customer_uuid,
        count( distinct enrollment_id) as new_enrolls
    FROM
        enterprise.learner_progress_report_external lpr
    WHERE
        enrollment_date >=(SELECT two_months_ago_start_range FROM dynamic_dates)
    AND
        enrollment_date <= (SELECT two_months_ago_end_range FROM dynamic_dates)
    GROUP BY
        1),

    completions as (
    /*
    Gets number of enrollment IDs that had a completoin event, grouped by enterprise UUID.
    */

    SELECT
        lpr.enterprise_customer_uuid,
        count( distinct enrollment_id) as new_completes
    FROM
        enterprise.learner_progress_report_external lpr
    WHERE
        passed_date >=(SELECT two_months_ago_start_range FROM dynamic_dates)
    AND
        passed_date <= (SELECT two_months_ago_end_range FROM dynamic_dates)
    GROUP BY
        1),

    daily_sessions as (
    /*
    Gets number of daily sessions, grouped by enterprise UUID.
    */

    SELECT
        enterprise_customer_uuid,
        count(*) as sessions
    FROM
        enterprise.fact_enrollment_engagement_day_admin_dash
    WHERE
        activity_date >=(SELECT two_months_ago_start_range FROM dynamic_dates)
    AND
        activity_date <= (SELECT two_months_ago_end_range FROM dynamic_dates)
    AND
        is_engaged = 1
    GROUP BY 1),

    top_5_enrolled as (
    /*
    Top five skills being enrolled in, grouped by enterprise.
    */

    SELECT
        enterprise_customer_uuid,
        listagg(distinct skill,', ') within group (order by skill) as top_5_skills
    FROM (
        SELECT DISTINCT
            enterprise_customer_uuid,
            s.name as skill,
            COUNT(distinct bee.course_key) as courses_with_skill,
            row_number() over(partition by enterprise_customer_uuid order by courses_with_skill desc) as rownum
        FROM
            enterprise.ent_base_enterprise_enrollment bee
        JOIN
            discovery.taxonomy_courseskills cs
        on
            bee.course_key=cs.course_key
        JOIN
            discovery.taxonomy_skill s
        on
            s.id=cs.skill_id
        WHERE
            enterprise_enrollment_created_at >=(SELECT two_months_ago_start_range FROM dynamic_dates)
        AND
             enterprise_enrollment_created_at <= (SELECT two_months_ago_end_range FROM dynamic_dates)
        GROUP BY
            1,2
        ORDER BY
            1,4 ASC)
    WHERE
        rownum <=5
    GROUP BY
        enterprise_customer_uuid),

    avg_learning_hrs as (
    /*
    Avg hours learned per learner, grouped by enterprise.
    */

    with hours as (
    /*
    Number of hours (numerator), grouped by enterprise.
    */

    SELECT
        enterprise_customer_uuid,
        round(sum(learning_time_seconds)/60/60,2) as learning_hrs
    FROM
        enterprise.fact_enrollment_engagement_day_admin_dash
    WHERE
        activity_date >= (SELECT two_months_ago_start_range FROM dynamic_dates)
    AND
        activity_date <= (SELECT two_months_ago_end_range FROM dynamic_dates)
    GROUP BY
        enterprise_customer_uuid),

    learners as (
    /*
    Number of learners (denominator), grouped by enterprise.
    */

    SELECT
        enterprise_customer_uuid,
        count(distinct email) as learners_who_learned
    FROM
        enterprise.fact_enrollment_engagement_day_admin_dash
    WHERE
        activity_date >= (SELECT two_months_ago_start_range FROM dynamic_dates)
    AND
        activity_date <= (SELECT two_months_ago_end_range FROM dynamic_dates)
    GROUP BY
        1)

    SELECT
        hours.enterprise_customer_uuid,
        learning_hrs,
        learners_who_learned,
        (learning_hrs/learners_who_learned) as avg_hours_per_learner,
        percent_rank() over (order by avg_hours_per_learner) as percent_rank
    FROM
        hours
    JOIN
        learners
    on
        hours.enterprise_customer_uuid=learners.enterprise_customer_uuid
    WHERE
        learners_who_learned > 0),

    with_sessions as (
    /*
    Calculates the % of learners who had at least
    one daily session in the time period, grouped by
    enterprise.
    */

    with linked as (

    /*
    Number of learners linked to the enterprise, grouped
    by enterprise.
    */

    SELECT
        enterprise_customer_id,
        count(distinct ecu.id) as linked_learners
    FROM
        lms_pii.enterprise_enterprisecustomeruser ecu
    GROUP BY
        1),

    learners_with_sessions as (

    /*
    Number of learners linked to the enterprise
    with at least on session, grouped by enterprise.
    */

    SELECT
        enterprise_customer_uuid,
        count(distinct email) as had_sessions
    FROM
        enterprise.fact_enrollment_engagement_day_admin_dash
    WHERE
        activity_date >=(SELECT two_months_ago_start_range FROM dynamic_dates)
    AND
        activity_date <= (SELECT two_months_ago_end_range FROM dynamic_dates)
    AND
        is_engaged = 1
    GROUP BY
        1)

    SELECT
        linked.enterprise_customer_id as uuid,
        linked.linked_learners,
        learners_with_sessions.had_sessions,
        (had_sessions/linked_learners) as perc_with_sessions
    FROM
        linked
    JOIN
        learners_with_sessions
    on
        linked.enterprise_customer_id=learners_with_sessions.enterprise_customer_uuid)
    /*
    Aggregate all the metrics for this month.
    */
    SELECT DISTINCT
        admins.uuid,
        admins.enterprise_name,
        admins.email,
        COALESCE(learning_hours.learning_hrs,0) as learning_hrs,
        COALESCE(new_enrolls.new_enrolls,0) as new_enrolls,
        COALESCE(completions.new_completes,0) as new_completes,
        COALESCE(daily_sessions.sessions,0) as sessions,
        top_5_enrolled.top_5_skills,
        avg_learning_hrs.avg_hours_per_learner,
        avg_learning_hrs.percent_rank,
        with_sessions.perc_with_sessions
    FROM
        admins
    LEFT JOIN
        learning_hours
    on
        learning_hours.enterprise_customer_uuid=admins.uuid
    LEFT JOIN
        new_enrolls
    on
        new_enrolls.enterprise_customer_uuid=admins.uuid
    LEFT JOIN
        completions
    on
        completions.enterprise_customer_uuid=admins.uuid
    LEFT JOIN
        daily_sessions
    on
        daily_sessions.enterprise_customer_uuid=admins.uuid
    LEFT JOIN
        top_5_enrolled
    on
        top_5_enrolled.enterprise_customer_uuid=admins.uuid
    LEFT JOIN
        avg_learning_hrs
    on
        avg_learning_hrs.enterprise_customer_uuid=admins.uuid
    LEFT JOIN
        with_sessions
    on
        with_sessions.uuid=admins.uuid
    LEFT JOIN
        lms_pii.enterprise_enterprisecustomer ec
    on
        ec.uuid=admins.uuid
    WHERE
        ec.enable_analytics_screen --- FILTER FOR ONLY CUSTOMERS WITH AA
    AND
        ec.customer_type_id != 3
            ),

    ONE_MONTH_AGO as(

    /*
    Collect all results from the one months ago. This will be used to
    report the progress report of "here's what happened last month".
    */

    with admins as (
    /*
    Get a list of admins.
    */

    SELECT DISTINCT
        ec.uuid,
        ec.name as enterprise_name,
        au.email,
        role.name,
        ecu.created as enterprise_user_role_created,
        assign.created as admin_role_assigned
    FROM
        "PROD"."LMS_PII"."ENTERPRISE_ENTERPRISECUSTOMER" ec
    JOIN
        "PROD"."LMS_PII"."ENTERPRISE_ENTERPRISECUSTOMERUSER" ecu
    on
        ec.uuid=ecu.ENTERPRISE_CUSTOMER_ID
    JOIN
        "PROD"."LMS_PII"."AUTH_USER" au
    on
        ecu.user_id=au.id
    JOIN
        "PROD"."LMS_PII"."ENTERPRISE_SYSTEMWIDEENTERPRISEUSERROLEASSIGNMENT" assign
    on
        assign.user_id=au.id
    and
        assign.user_id=ecu.user_id
    JOIN
        "PROD"."LMS_PII"."ENTERPRISE_SYSTEMWIDEENTERPRISEROLE" role on role.id=assign.role_id
    WHERE
        role.name like 'enterprise_admin'
    ORDER BY
        au.email),

    learning_hours as (

    /*
    Get the sum of learning hours, grouped by enterprise UUID.
    */

    SELECT
        enterprise_customer_uuid,
        round(sum(learning_time_seconds)/60/60,2) as learning_hrs
    FROM
        enterprise.fact_enrollment_engagement_day_admin_dash
    WHERE
        activity_date >= (SELECT last_month_start_range FROM dynamic_dates)
    AND
        activity_date <= (SELECT last_month_end_range FROM dynamic_dates)
    GROUP BY
        enterprise_customer_uuid),

    new_enrolls as (

    /*
    Gets number of new enrollment IDs created, grouped by enterprise UUID.
    */

    SELECT
        lpr.enterprise_customer_uuid,
        count( distinct enrollment_id) as new_enrolls
    FROM
        enterprise.learner_progress_report_external lpr
    WHERE
        enrollment_date >= (SELECT last_month_start_range FROM dynamic_dates)
    AND
        enrollment_date <= (SELECT last_month_end_range FROM dynamic_dates)
    GROUP BY
        1),

    completions as (

    /*
    Gets number of enrollment IDs that had a completoin event, grouped by enterprise UUID.
    */

    SELECT
        lpr.enterprise_customer_uuid,
        count( distinct enrollment_id) as new_completes
    FROM
        enterprise.learner_progress_report_external lpr
    WHERE
        passed_date >= (SELECT last_month_start_range FROM dynamic_dates)
    AND
        passed_date <= (SELECT last_month_end_range FROM dynamic_dates)
    GROUP BY
        1),

    daily_sessions as (

    /*
    Gets number of daily sessions, grouped by enterprise UUID.
    */

    SELECT
        enterprise_customer_uuid,
        count(*) as sessions
    FROM
        enterprise.fact_enrollment_engagement_day_admin_dash
    WHERE
        activity_date >= (SELECT last_month_start_range FROM dynamic_dates)
    AND
        activity_date <= (SELECT last_month_end_range FROM dynamic_dates)
    AND
        is_engaged = 1
    GROUP BY
        1),

    top_5_enrolled as (

    /*
    Top five skills being enrolled in, grouped by enterprise.
    */

    SELECT
        enterprise_customer_uuid,
        listagg(distinct skill,', ') within group (order by skill) as top_5_skills
    FROM (
        SELECT DISTINCT
            enterprise_customer_uuid,
            s.name as skill,
            COUNT(distinct bee.course_key) as courses_with_skill,
            row_number() over(partition by enterprise_customer_uuid order by courses_with_skill desc) as rownum
        FROM
            enterprise.ent_base_enterprise_enrollment bee
        JOIN
            discovery.taxonomy_courseskills cs
        on
            bee.course_key=cs.course_key
        JOIN
            discovery.taxonomy_skill s
        on
            s.id=cs.skill_id
        WHERE
            enterprise_enrollment_created_at >= (SELECT last_month_start_range FROM dynamic_dates)
        AND
            enterprise_enrollment_created_at <= (SELECT last_month_end_range FROM dynamic_dates)
        GROUP BY
            1,2
        ORDER BY
            1,4 ASC)
    WHERE
        rownum <=5
    GROUP BY
        enterprise_customer_uuid ),

    avg_learning_hrs as (

    /*
    Avg hours learned per learner, grouped by enterprise.
    */

    with hours as(

    /*
    Number of hours (numerator), grouped by enterprise.
    */

    SELECT
        enterprise_customer_uuid,
        round(sum(learning_time_seconds)/60/60,2) as learning_hrs
    FROM
        enterprise.fact_enrollment_engagement_day_admin_dash
    WHERE
        activity_date >= (SELECT last_month_start_range FROM dynamic_dates)
    AND
        activity_date <= (SELECT last_month_end_range FROM dynamic_dates)
    GROUP BY
        enterprise_customer_uuid),

    learners as (

    /*
    Number of learners (denominator), grouped by enterprise.
    */

    SELECT
        enterprise_customer_uuid,
        count(distinct email) as learners_who_learned
    FROM
        enterprise.fact_enrollment_engagement_day_admin_dash
    WHERE
        activity_date >= (SELECT last_month_start_range FROM dynamic_dates)
    AND
        activity_date <= (SELECT last_month_end_range FROM dynamic_dates)
    GROUP BY
        1)

    SELECT
        hours.enterprise_customer_uuid,
        learning_hrs,
        learners_who_learned,
        (learning_hrs/learners_who_learned) as avg_hours_per_learner,
        percent_rank() over (order by avg_hours_per_learner) as percent_rank
    FROM
        hours
    JOIN
        learners
    on
        hours.enterprise_customer_uuid=learners.enterprise_customer_uuid
    WHERE
        learners_who_learned > 0),

    with_sessions as (

    /*
    Calculates the % of learners who had at least
    one daily session in the time period, grouped by
    enterprise.
    */

    with linked as (

    /*
    Number of learners linked to the enterprise, grouped
    by enterprise.
    */

    SELECT
        enterprise_customer_id,
        count(distinct ecu.id) as linked_learners
    FROM
        lms_pii.enterprise_enterprisecustomeruser ecu
    GROUP BY 1),

    learners_with_sessions as (

    /*
    Number of learners linked to the enterprise
    with at least on session, grouped by enterprise.
    */

    SELECT
        enterprise_customer_uuid,
        count(distinct email) as had_sessions
    FROM
        enterprise.fact_enrollment_engagement_day_admin_dash
    WHERE
        activity_date >= (SELECT last_month_start_range FROM dynamic_dates)
    AND
        activity_date <= (SELECT last_month_end_range FROM dynamic_dates)
    AND
        is_engaged = 1
    GROUP BY
        1)

    SELECT
        linked.enterprise_customer_id as uuid,
        linked.linked_learners,
        learners_with_sessions.had_sessions,
        (had_sessions/linked_learners) as perc_with_sessions
    FROM
        linked
    JOIN
        learners_with_sessions
    on
        linked.enterprise_customer_id=learners_with_sessions.enterprise_customer_uuid),

    leader_board as (

    WITH TOP_TEN as (
    SELECT
        dash.enterprise_customer_uuid,
        au.username,
        round(sum(dash.learning_time_seconds)/60) as learning_minutes,
        SUM(coalesce(has_passed,0)) as num_completions,
        ROW_NUMBER() OVER (PARTITION BY dash.enterprise_customer_uuid ORDER BY learning_minutes DESC) as rank_
    FROM
        enterprise.fact_enrollment_engagement_day_admin_dash as dash
    LEFT JOIN
        lms_pii.auth_user as au
    ON
        dash.user_id = au.id
    LEFT JOIN
        enterprise.fact_enrollment_admin_dash as fead
    ON
        dash.user_id = fead.user_id AND dash.activity_date = fead.passed_date
    WHERE
        dash.activity_date >= (SELECT last_month_start_range FROM dynamic_dates)
    --      dash.activity_date >= '2021-1-1'
    AND
        dash.activity_date <= (SELECT last_month_end_range FROM dynamic_dates)
    --      dash.activity_date <= '2021-1-31'
    GROUP BY
        1,2
    HAVING
        learning_minutes > 0
    QUALIFY
        rank_ <= 10)

    SELECT
        enterprise_customer_uuid,
        MAX(CASE WHEN rank_ = 1 THEN username END) as username_1,
        MAX(CASE WHEN rank_ = 1 THEN CAST(learning_minutes as VARCHAR) || ' minutes' END) as learning_minutes_1,
        MAX(CASE WHEN rank_ = 1 THEN num_completions END) as num_completions_1,
        MAX(CASE WHEN rank_ = 2 THEN username END) as username_2,
        MAX(CASE WHEN rank_ = 2 THEN CAST(learning_minutes as VARCHAR) || ' minutes' END) as learning_minutes_2,
        MAX(CASE WHEN rank_ = 2 THEN num_completions END) as num_completions_2,
        MAX(CASE WHEN rank_ = 3 THEN username END) as username_3,
        MAX(CASE WHEN rank_ = 3 THEN CAST(learning_minutes as VARCHAR) || ' minutes' END) as learning_minutes_3,
        MAX(CASE WHEN rank_ = 3 THEN num_completions END) as num_completions_3,
        MAX(CASE WHEN rank_ = 4 THEN username END) as username_4,
        MAX(CASE WHEN rank_ = 4 THEN CAST(learning_minutes as VARCHAR) || ' minutes' END) as learning_minutes_4,
        MAX(CASE WHEN rank_ = 4 THEN num_completions END) as num_completions_4,
        MAX(CASE WHEN rank_ = 5 THEN username END) as username_5,
        MAX(CASE WHEN rank_ = 5 THEN CAST(learning_minutes as VARCHAR) || ' minutes' END) as learning_minutes_5,
        MAX(CASE WHEN rank_ = 5 THEN num_completions END) as num_completions_5,
        MAX(CASE WHEN rank_ = 6 THEN username END) as username_6,
        MAX(CASE WHEN rank_ = 6 THEN CAST(learning_minutes as VARCHAR) || ' minutes' END) as learning_minutes_6,
        MAX(CASE WHEN rank_ = 6 THEN num_completions END) as num_completions_6,
        MAX(CASE WHEN rank_ = 7 THEN username END) as username_7,
        MAX(CASE WHEN rank_ = 7 THEN CAST(learning_minutes as VARCHAR) || ' minutes' END) as learning_minutes_7,
        MAX(CASE WHEN rank_ = 7 THEN num_completions END) as num_completions_7,
        MAX(CASE WHEN rank_ = 8 THEN username END) as username_8,
        MAX(CASE WHEN rank_ = 8 THEN CAST(learning_minutes as VARCHAR) || ' minutes' END) as learning_minutes_8,
        MAX(CASE WHEN rank_ = 8 THEN num_completions END) as num_completions_8,
        MAX(CASE WHEN rank_ = 9 THEN username END) as username_9,
        MAX(CASE WHEN rank_ = 9 THEN CAST(learning_minutes as VARCHAR) || ' minutes' END) as learning_minutes_9,
        MAX(CASE WHEN rank_ = 9 THEN num_completions END) as num_completions_9,
        MAX(CASE WHEN rank_ = 10  THEN username END) as username_10,
        MAX(CASE WHEN rank_ = 10 THEN CAST(learning_minutes as VARCHAR) || ' minutes' END) as learning_minutes_10,
        MAX(CASE WHEN rank_ = 10 THEN num_completions END) as num_completions_10
    FROM
        TOP_TEN
    GROUP BY
        1
    )

    /*
    Aggregate all the metrics for this month.
    */

    SELECT DISTINCT
        admins.uuid,
        admins.enterprise_name,
        admins.email,
        COALESCE(learning_hours.learning_hrs,0) as learning_hrs,
        COALESCE(new_enrolls.new_enrolls,0) as new_enrolls,
        COALESCE(completions.new_completes,0) as new_completes,
        COALESCE(daily_sessions.sessions,0) as sessions,
        top_5_enrolled.top_5_skills,
        avg_learning_hrs.avg_hours_per_learner,
        avg_learning_hrs.percent_rank,
        with_sessions.perc_with_sessions,
        lb.*
    FROM
        admins
    LEFT JOIN
        learning_hours
    on
        learning_hours.enterprise_customer_uuid=admins.uuid
    LEFT JOIN
        new_enrolls
    on
        new_enrolls.enterprise_customer_uuid=admins.uuid
    LEFT JOIN
        completions
    on
        completions.enterprise_customer_uuid=admins.uuid
    LEFT JOIN
        daily_sessions
    on
        daily_sessions.enterprise_customer_uuid=admins.uuid
    LEFT JOIN
        top_5_enrolled
    on
        top_5_enrolled.enterprise_customer_uuid=admins.uuid
    LEFT JOIN
        avg_learning_hrs
    on
        avg_learning_hrs.enterprise_customer_uuid=admins.uuid
    LEFT JOIN
        with_sessions
    on
        with_sessions.uuid=admins.uuid
    LEFT JOIN
        lms_pii.enterprise_enterprisecustomer ec
    on
        ec.uuid=admins.uuid
    LEFT JOIN
        leader_board as lb
    ON
        admins.uuid = lb.enterprise_customer_uuid
    WHERE
        ec.enable_analytics_screen --- FILTER FOR ONLY CUSTOMERS WITH AA
    AND
        ec.customer_type_id != 3
                    )
    /*
    Combines the two month's together for one view, with all the fields needed to
    populate the email.
    */
    SELECT
        date_.year_month,
        oma.uuid,
        'portal.edx.org/' || eec.slug || '/admin/analytics' as admin_link, -- for cta link.
        oma.enterprise_name,
        oma.email,
        au.id as external_id, -- for braze.
        COALESCE(ROUND(oma.learning_hrs,1),0) as learning_hrs, -- formatting,handling nulls.
        COALESCE(oma.new_enrolls,0) as new_enrolls, -- formatting, handling nulls.
        COALESCE(oma.new_completes,0) as new_completes, -- formatting, handling nulls.
        COALESCE(oma.sessions,0) as sessions, -- formatting, handling nulls.
        CASE
            WHEN oma.top_5_skills IS NULL
            THEN 'No data available'
            ELSE oma.top_5_skills
            END as top_5_skills,
        COALESCE(ROUND(oma.avg_hours_per_learner*60,1),0) as avg_minutes_per_learner, -- formatting, handling nulls.
        CAST(ROUND(ROUND(oma.perc_with_sessions,2)*100,0) as VARCHAR) || '%' as perc_with_sessions, -- formatting.
        oma.percent_rank,
        CASE
            WHEN COALESCE(oma.learning_hrs,0) >= COALESCE(tma.learning_hrs,0)
            THEN CONCAT('+', CAST(ROUND(oma.learning_hrs - tma.learning_hrs,1) as VARCHAR), ' from last month')
            ELSE CONCAT(CAST(COALESCE(ROUND(oma.learning_hrs - tma.learning_hrs,1),0) as VARCHAR), ' from last month')
            END as learning_hours_delta_, -- +/- formatting.
        CASE
            WHEN COALESCE(oma.new_enrolls,0) >= COALESCE(tma.new_enrolls,0)
            THEN CONCAT('+', CAST(oma.new_enrolls - tma.new_enrolls as VARCHAR), ' from last month')
            ELSE CONCAT(CAST(COALESCE(oma.new_enrolls - tma.new_enrolls,0) as VARCHAR), ' from last month')
            END as new_enrolls_delta_, -- +/- formatting.
        CASE
            WHEN COALESCE(oma.new_completes,0) >= COALESCE(tma.new_completes,0)
            THEN CONCAT('+', CAST(oma.new_completes - tma.new_completes as VARCHAR), ' from last month')
            ELSE CONCAT(CAST(COALESCE(oma.new_completes - tma.new_completes,0) as VARCHAR), ' from last month')
            END as new_completes_delta_, -- +/- formatting.
        CASE
            WHEN COALESCE(oma.sessions,0) >= COALESCE(tma.sessions,0)
            THEN CONCAT('+', CAST(oma.sessions - tma.sessions as VARCHAR), ' from last month')
            ELSE CONCAT(CAST(COALESCE(oma.sessions - tma.sessions,0) as VARCHAR), ' from last month')
            END as sessions_delta_, -- +/- formatting.
        CASE
            WHEN COALESCE(oma.avg_hours_per_learner,0) >= COALESCE(tma.avg_hours_per_learner,0)
            THEN CONCAT('+', CAST(ROUND(oma.avg_hours_per_learner*60 - tma.avg_hours_per_learner*60,1) as VARCHAR), ' from last month')
            ELSE CONCAT(CAST(ROUND(oma.avg_hours_per_learner*60 - tma.avg_hours_per_learner*60,1) as VARCHAR), ' from last month')
            END as avg_minutes_per_learner_delta_, -- +/- formatting.
        CAST(ROUND(ROUND(oma.perc_with_sessions - tma.perc_with_sessions,2)*100,0) as VARCHAR) || '%' as perc_with_sessions_delta, --formatting
        IFNULL(oma.username_1,'---') as username_1,
        IFNULL(oma.learning_minutes_1,'---') as learning_minutes_1,
        num_completions_1,
        IFNULL(oma.username_2,'---') as username_2,
        IFNULL(oma.learning_minutes_2,'---') as learning_minutes_2,
        num_completions_2,
        IFNULL(oma.username_3,'---') as username_3,
        IFNULL(oma.learning_minutes_3,'---') as learning_minutes_3,
        num_completions_3,
        IFNULL(oma.username_4,'---') as username_4,
        IFNULL(oma.learning_minutes_4,'---') as learning_minutes_4,
        num_completions_4,
        IFNULL(oma.username_5,'---') as username_5,
        IFNULL(oma.learning_minutes_5,'---') as learning_minutes_5,
        num_completions_5,
        IFNULL(oma.username_6,'---') as username_6,
        IFNULL(oma.learning_minutes_6,'---') as learning_minutes_6,
        num_completions_6,
        IFNULL(oma.username_7,'---') as username_7,
        IFNULL(oma.learning_minutes_7,'---') as learning_minutes_7,
        num_completions_7,
        IFNULL(oma.username_8,'---') as username_8,
        IFNULL(oma.learning_minutes_8,'---') as learning_minutes_8,
        num_completions_8,
        IFNULL(oma.username_9,'---') as username_9,
        IFNULL(oma.learning_minutes_9,'---') as learning_minutes_9,
        num_completions_9,
        IFNULL(oma.username_10,'---') as username_10,
        IFNULL(oma.learning_minutes_10,'---') as learning_minutes_10,
        num_completions_10
    FROM
        TWO_MONTHS_AGO as tma
    JOIN
        ONE_MONTH_AGO as oma
    ON
        tma.uuid=oma.uuid
      AND
        tma.email=oma.email
    JOIN
        lms_pii.enterprise_enterprisecustomer as eec
    ON
        oma.uuid = eec.uuid
    JOIN
        lms_pii.auth_user as au
    ON
        oma.email = au.email
    JOIN
    -- Messy, but...one record CTE that returns the fancy month-year for emails.
        (
        SELECT
            date_column,
            month_name || ' ' || REPLACE(current_year,',','') as year_month
        FROM
            core.dim_date
        WHERE
            date_column = CURRENT_DATE - 30
    ) as date_
    WHERE
        -- control for people who have no new information.
        oma.new_enrolls > 0
    AND
        -- only customers where we know they have an active contract.
        oma.uuid IN (

        SELECT
            t.uuid
        FROM (

        SELECT
            acc.integration_enterprise_uuid_c as uuid,
            MAX(opp.contract_end_date_c) latest_contract_end_date
        FROM
            salesforce_prod_pii.opportunity as opp
        LEFT JOIN
            salesforce_prod_pii._account as acc
        ON
            opp.account_id = acc.id
        WHERE
            -- only closed won contracts
            opp.stage_name = 'Closed Won'
        GROUP BY
            1
        HAVING
            -- where the latest close won end date is in the future.
            latest_contract_end_date >= CURRENT_DATE()
        ) as t
        )
    AND
        au.id NOT IN (
    select distinct user_id
    from lms_pii.student_courseaccessrole
    where role ='staff'
        )
    ORDER BY
        tma.enterprise_name
'''


class Command(BaseCommand):
    """
    Django management command to send monthly impact report to enterprise admins.

    Example usage:
    ./manage.py lms monthly_impact_report
    ./manage.py lms monthly_impact_report --no-commit
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
        utils.track_event(kwargs['EXTERNAL_ID'], 'edx.bi.enterprise.user.admin.impact_report', kwargs)
        LOGGER.info(
            '[Monthly Impact Report] Segment event fired for monthly impact report. '
            'lms_user_id: {user_id}, Enterprise Name: {enterprise_name}'.format(
                user_id=kwargs['EXTERNAL_ID'],
                enterprise_name=kwargs['ENTERPRISE_NAME']
            )
        )

    def handle(self, *args, **options):
        should_commit = not options['no_commit']

        LOGGER.info('[Monthly Impact Report]  Process started.')
        for next_row in self.get_query_results_from_snowflake():
            message_data = {
                'EXTERNAL_ID': next_row[5],
                'ENTERPRISE_NAME': next_row[3],
                'ADMIN_LINK': next_row[2],
                'YEAR_MONTH': next_row[0],
                'PERC_WITH_SESSIONS': next_row[12],
                'SESSIONS': next_row[9],
                'SESSIONS_DELTA_': next_row[17],
                'LEARNING_HRS': next_row[6],
                'LEARNING_HOURS_DELTA_': next_row[14],
                'NEW_ENROLLS': next_row[7],
                'NEW_ENROLLS_DELTA_': next_row[15],
                'NEW_COMPLETES': next_row[8],
                'NEW_COMPLETES_DELTA_': next_row[16],
                'TOP_5_SKILLS': next_row[10],
                'AVG_MINUTES_PER_LEARNER': next_row[11],
                'AVG_MINUTES_PER_LEARNER_DELTA_': next_row[18],
                'NUM_COMPLETIONS_1': next_row[22],
                'LEARNING_MINUTES_1': next_row[21],
                'NUM_COMPLETIONS_2': next_row[25],
                'LEARNING_MINUTES_2': next_row[24],
                'NUM_COMPLETIONS_3': next_row[28],
                'LEARNING_MINUTES_3': next_row[27],
                'NUM_COMPLETIONS_4': next_row[31],
                'LEARNING_MINUTES_4': next_row[30],
                'NUM_COMPLETIONS_5': next_row[34],
                'LEARNING_MINUTES_5': next_row[33],
                'NUM_COMPLETIONS_6': next_row[37],
                'LEARNING_MINUTES_6': next_row[36],
                'NUM_COMPLETIONS_7': next_row[40],
                'LEARNING_MINUTES_7': next_row[39],
                'NUM_COMPLETIONS_8': next_row[43],
                'LEARNING_MINUTES_8': next_row[42],
                'NUM_COMPLETIONS_9': next_row[46],
                'LEARNING_MINUTES_9': next_row[45],
                'NUM_COMPLETIONS_10': next_row[49],
                'LEARNING_MINUTES_10': next_row[48]
            }
            if should_commit:
                self.emit_event(**message_data)

        LOGGER.info('[Monthly Impact Report] Execution completed.')
