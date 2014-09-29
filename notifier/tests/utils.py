import mock


def make_mock_json_response(status_code=200, json={}):
    mock_response = mock.Mock()
    mock_response.status_code = status_code
    if 200 <= status_code < 300:
        mock_response.ok = True
    else:
        mock_response.ok = False
    mock_response.json.return_value = json
    return mock_response


def make_user_info(cs_notifications_data):
    """
    Returns the user_info data as would be returned by LMS' notifier_api.
    cs_notifications_data should be of the structure as returned by the comments service
    """
    user_info = {}
    for user_id, course_info in cs_notifications_data.iteritems():
        user_info[user_id] = {
            'course_info': {
                course_id: {"see_all_cohorts": True, "cohort_id": None}
                for course_id in course_info.keys()
            }
        }
    return user_info
