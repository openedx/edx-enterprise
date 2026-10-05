"""
xAPI statement for course completion.
"""

from tincan import LanguageMap, Result, Score, Verb

from integrated_channels.xapi.constants import MAX_SCORE, MIN_SCORE, X_API_VERB_COMPLETED
from integrated_channels.xapi.statements.base import EnterpriseStatement


class LearnerCourseCompletionStatement(EnterpriseStatement):
    """
    xAPI Statement to serialize data related to course completion.
    """

    def __init__(self, site, user, user_social_auth, course_overview, course_grade, object_type, *args, **kwargs):
        """
        Initialize and populate statement with learner info and course info.

        Arguments:
            user (User): Auth User object containing information about the learner enrolling in the course.
            user_social_auth (UserSocialAuth): UserSocialAuth object for learner
            course_overview (CourseOverview): course overview object containing course details.
            course_grade (CourseGrade): User grade in the course.
        """
        kwargs.update(
            actor=self.get_actor(user, user_social_auth),
            verb=self.get_verb(),
            object=self.get_object(site.domain, course_overview, object_type),
            result=self.get_result(course_grade),
        )
        super().__init__(*args, **kwargs)

    def get_verb(self):
        """
        Get verb for the statement.
        """
        return Verb(
            id=X_API_VERB_COMPLETED,
            display=LanguageMap({'en-US': 'completed'}),
        )

    def get_result(self, persistent_course_grade):
        """
        Get result for the statement.

        Arguments:
            persistent_course_grade (PersistentCourseGrade): PersistentCourseGrade record
        """
        completed = 0
        success = 0

        if persistent_course_grade.passed_timestamp is not None:
            completed = 1
            success = 1

        return Result(
            score=Score(
                scaled=persistent_course_grade.percent_grade,
                raw=persistent_course_grade.percent_grade * 100,
                min=MIN_SCORE,
                max=MAX_SCORE,
            ),
            success=success,
            completion=completed
        )
