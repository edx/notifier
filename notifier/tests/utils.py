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
