# -*- coding: utf-8 -*-

"""
Statements base for xAPI.
"""

from tincan import Activity, ActivityDefinition, Agent, LanguageMap, Statement

from integrated_channels.xapi.constants import X_API_ACTIVITY_COURSE


class EnterpriseStatement(Statement):
    """
    Base statement for enterprise events.
    """

    def _get_actor_name(self, user, user_social_auth):
        """
        Returns the name of the actor based on provided information and defined rules

        Arguments:
            user (User): User.
            user_social_auth (UserSocialAuth): UserSocialAuth.
        """
        social_auth_uid = user_social_auth.uid if user_social_auth else ''
        sso_id = social_auth_uid.split(':')[-1]
        actor_name = sso_id if sso_id else user.email
        return actor_name

    def get_actor(self, user, user_social_auth):
        """
        Returns the actor component of the Enterprise xAPI statement.
        Arguments:
            user (User): User.
            user_social_auth (UserSocialAuth): UserSocialAuth.
        """
        name = self._get_actor_name(user, user_social_auth)
        return Agent(
            name=name,
            mbox=u'mailto:{email}'.format(email=user.email),
        )

    def get_object(self, domain, course_overview, object_type):
        """
        Returns the object (activity) component of the Enterprise xAPI statement.
        Arguments:
            course_overview (CourseOverview): CourseOverview.
            object_type (string): Object type for activity.
        """
        name = (course_overview.display_name or '').encode("ascii", "ignore").decode('ascii')

        description = (course_overview.short_description or '').encode("ascii", "ignore").decode('ascii')

        activity_id = course_overview.id
        if object_type is not None and object_type == 'course':
            activity_id = course_overview.course_key

        xapi_activity_id = 'https://{domain}/xapi/activities/{object_type}/{activity_id}'.format(
            domain=domain,
            object_type=object_type,
            activity_id=activity_id
        )

        xapi_object_extensions = {}

        course_key_keyname = 'https://{domain}/course/key'.format(domain=domain)
        xapi_object_extensions[course_key_keyname] = course_overview.course_key

        course_uuid_keyname = 'https://{domain}/course/uuid'.format(domain=domain)
        xapi_object_extensions[course_uuid_keyname] = course_overview.course_uuid

        return Activity(
            id=xapi_activity_id,
            definition=ActivityDefinition(
                type=X_API_ACTIVITY_COURSE,
                name=LanguageMap({'en-US': name}),
                description=LanguageMap({'en-US': description}),
                extensions=xapi_object_extensions,
            ),
        )
