"""
"""
from django.test import TestCase
from django.test.utils import override_settings
from mock import patch

from notifier.user import get_digest_subscribers, DIGEST_NOTIFICATION_PREFERENCE_KEY

from .utils import make_mock_json_response

TEST_API_KEY = 'ZXY123!@#$%'


# some shorthand to quickly generate fixture results
mkresult = lambda n: {
    "id": n,
    "email": "email%d" % n, 
    "name": "name%d" % n, 
    "preferences": {
        DIGEST_NOTIFICATION_PREFERENCE_KEY: "pref%d" % n,
    },
    "course_info": {},
}
mkexpected = lambda d: dict([(key, val) for (key, val) in d.items() if key != "url"])


@override_settings(US_API_KEY=TEST_API_KEY)
class UserTestCase(TestCase):
    """
    """

    def setUp(self):
        self.expected_api_url = "test_server_url/notifier_api/v1/users/"
        self.expected_params = {"page_size":3, "page":1}
        self.expected_headers = {'X-EDX-API-Key': TEST_API_KEY}


    @override_settings(US_URL_BASE="test_server_url", US_RESULT_PAGE_SIZE=3)
    def test_get_digest_subscribers_empty(self):
        """
        """

        # empty result
        mock_response = make_mock_json_response(json={
            "count": 0,
            "next": None,
            "previous": None,
            "results": []
        })

        with patch('requests.get', return_value=mock_response) as p:
            res = list(get_digest_subscribers())
            p.assert_called_once_with(
                    self.expected_api_url,
                    params=self.expected_params,
                    headers=self.expected_headers)
            self.assertEqual(0, len(res))


    @override_settings(US_URL_BASE="test_server_url", US_RESULT_PAGE_SIZE=3)
    def test_get_digest_subscribers_single_page(self):
        """
        """

        # single page result
        mock_response = make_mock_json_response(json={
            "count": 3,
            "next": None,
            "previous": None,
            "results": [mkresult(1), mkresult(2), mkresult(3)]
        })

        with patch('requests.get', return_value=mock_response) as p:
            res = list(get_digest_subscribers())
            p.assert_called_once_with(
                    self.expected_api_url,
                    params=self.expected_params,
                    headers=self.expected_headers)
            self.assertEqual([
                mkexpected(mkresult(1)), 
                mkexpected(mkresult(2)), 
                mkexpected(mkresult(3))], res)


    @override_settings(US_URL_BASE="test_server_url", US_RESULT_PAGE_SIZE=3)
    def test_get_digest_subscribers_multi_page(self):
        """
        """

        # multi page result
        expected_multi_p1 = {
            "count": 5,
            "next": "not none",
            "previous": None,
            "results": [mkresult(1), mkresult(2), mkresult(3)]
        }
        expected_multi_p2 = {
            "count": 5,
            "next": None,
            "previous": "not none",
            "results": [mkresult(4), mkresult(5)]
        }

        expected_pages = [expected_multi_p1, expected_multi_p2]
        def side_effect(*a, **kw):
            return expected_pages.pop(0)

        mock_response = make_mock_json_response(json=expected_multi_p1)
        with patch('requests.get', return_value=mock_response) as p:
            res = []
            g = get_digest_subscribers()
            res.append(g.next())
            p.assert_called_once_with(
                self.expected_api_url,
                params=self.expected_params,
                headers=self.expected_headers)
            res.append(g.next())
            res.append(g.next()) # result 3, end of page
            self.assertEqual([
                mkexpected(mkresult(1)),
                mkexpected(mkresult(2)),
                mkexpected(mkresult(3))], res)
            # still should only have called requests.get() once
            self.assertEqual(1, p.call_count)

        mock_response = make_mock_json_response(json=expected_multi_p2)
        with patch('requests.get', return_value=mock_response) as p:
            self.expected_params['page']=2
            self.assertEqual(mkexpected(mkresult(4)), g.next())
            p.assert_called_once_with(
                self.expected_api_url,
                params=self.expected_params,
                headers=self.expected_headers)
            self.assertEqual(mkexpected(mkresult(5)), g.next())
            self.assertEqual(1, p.call_count)
            self.assertRaises(StopIteration, g.next)


    @override_settings(US_URL_BASE="test_server_url", US_RESULT_PAGE_SIZE=3, US_HTTP_AUTH_USER='someuser', US_HTTP_AUTH_PASS='somepass')
    def test_get_digest_subscribers_basic_auth(self):
        """
        """
        # single page result
        mock_response = make_mock_json_response(json={
            "count": 3,
            "next": None,
            "previous": None,
            "results": [mkresult(1), mkresult(2), mkresult(3)]
        })

        with patch('requests.get', return_value=mock_response) as p:
            res = list(get_digest_subscribers())
            p.assert_called_once_with(
                    self.expected_api_url,
                    params=self.expected_params,
                    headers=self.expected_headers,
                    auth=('someuser', 'somepass'))
            self.assertEqual([
                mkexpected(mkresult(1)), 
                mkexpected(mkresult(2)), 
                mkexpected(mkresult(3))], res)



