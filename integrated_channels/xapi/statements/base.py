# -*- coding: utf-8 -*-

"""
Statements base for xAPI.
"""
from __future__ import absolute_import, unicode_literals

from tincan import Activity, ActivityDefinition, Agent, Context, Extensions, LanguageMap, Statement

from integrated_channels.xapi.constants import X_API_ACTIVITY_COURSE


class EnterpriseStatement(Statement):
    """
    Base statement for enterprise events.
    """

    def get_actor(self, username, email):
        """
        Get actor for the statement.
        """
        return Agent(
            name=username,
            mbox='mailto:{email}'.format(email=email),
        )

    def get_context(self, user_details, course_details):
        """
        Get Context for the statement.
        """
        return Context(
            extensions=Extensions(
                {
                    'http://id.tincanapi.com/extension/user-details': user_details,
                    'http://id.tincanapi.com/extension/course-details': course_details,
                },
            )
        )

    def get_object(self, name, description):
        """
        Get object for the statement.
        """
        return Activity(
            id=X_API_ACTIVITY_COURSE,
            definition=ActivityDefinition(
                name=LanguageMap({'en-US': (name or '').encode("ascii", "ignore").decode('ascii')}),
                description=LanguageMap({'en-US': (description or '').encode("ascii", "ignore").decode('ascii')}),
            ),
        )
