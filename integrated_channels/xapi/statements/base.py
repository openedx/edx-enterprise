# -*- coding: utf-8 -*-

"""
Statements base for xAPI.
"""
from __future__ import absolute_import, unicode_literals

from tincan import Activity, ActivityDefinition, Agent, LanguageMap, Statement

from integrated_channels.xapi.constants import X_API_ACTIVITY_COURSE


class EnterpriseStatement(Statement):
    """
    Base statement for enterprise events.
    """

    def get_actor(self, user, user_social_auth):
        """
        Get actor for the statement.
        """
        social_auth_uid = user_social_auth.uid if user_social_auth else ''
        sso_id = social_auth_uid.split(':')[-1]
        name = sso_id if sso_id else user.email
        return Agent(
            name=name,
            mbox=u'mailto:{email}'.format(email=user.email),
        )

    def get_object(self, course_overview):
        """
        Get object for the statement.
        """
        name = (course_overview.display_name or '').encode("ascii", "ignore").decode('ascii')
        description = (course_overview.short_description or '').encode("ascii", "ignore").decode('ascii')

        return Activity(
            id=course_overview.id,
            definition=ActivityDefinition(
                type=X_API_ACTIVITY_COURSE,
                name=LanguageMap({'en-US': name}),
                description=LanguageMap({'en-US': description}),
            ),
        )
