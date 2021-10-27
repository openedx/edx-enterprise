"""
Enterprise Django application tests constants.
"""

LIMITED_REPORT_TYPES = {
    'data_type': [
        ['catalog', 'catalog'],
        ['engagement', 'engagement'],
        ['progress_v3', 'progress']
    ],
    'day_of_week': [
        [0, 'Monday'],
        [1, 'Tuesday'],
        [2, 'Wednesday'],
        [3, 'Thursday'],
        [4, 'Friday'],
        [5, 'Saturday'],
        [6, 'Sunday']
    ],
    'delivery_method': [
        ['email', 'email'], ['sftp', 'sftp']
    ],
    'frequency': [
        ['daily', 'daily'],
        ['monthly', 'monthly'],
        ['weekly', 'weekly']
    ],
    'report_type': [
        ['csv', 'csv'], ['json', 'json']
    ]
}

FULL_REPORT_TYPES = {
    'data_type': [
        ['catalog', 'catalog'],
        ['engagement', 'engagement'],
        ['grade', 'grade'],
        ['completion', 'completion'],
        ['course_structure', 'course_structure'],
        ['progress_v3', 'progress']
    ],
    'day_of_week': [
        [0, 'Monday'],
        [1, 'Tuesday'],
        [2, 'Wednesday'],
        [3, 'Thursday'],
        [4, 'Friday'],
        [5, 'Saturday'],
        [6, 'Sunday']
    ],
    'delivery_method': [
        ['email', 'email'], ['sftp', 'sftp']
    ],
    'frequency': [
        ['daily', 'daily'],
        ['monthly', 'monthly'],
        ['weekly', 'weekly']
    ],
    'report_type': [
        ['csv', 'csv'], ['json', 'json']
    ]
}
