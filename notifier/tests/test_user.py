"""
"""
from django.conf import settings
from django.test import TestCase
from django.test.utils import override_settings
from mock import MagicMock, Mock, patch

from notifier.user import get_digest_subscribers, DIGEST_NOTIFICATION_PREFERENCE_KEY


TEST_API_KEY = 'ZXY123!@#$%'


# some shorthand to quickly generate fixture results
mkuser = lambda n: {
    "id": n,
    "email": "email%d" % n, 
    "name": "name%d" % n, 
    "url": "url%d" % n,
    "username": "user%d" % n
}
mkresult = lambda n: {
    "url": "url%d" % n,
    "user": mkuser(n),
    "key": DIGEST_NOTIFICATION_PREFERENCE_KEY,
    "value": "value%d" % n
}
mkexpected = lambda d: {
    "id": d["user"]["id"],
    "name": d["user"]["name"],
    "email": d["user"]["email"],
    "username": d["user"]["username"]
}


@override_settings(US_API_KEY=TEST_API_KEY)
class UserTestCase(TestCase):
    """
    """

    def setUp(self):
        self.expected_api_url = "test_server_url/user_api/v1/user_prefs/"
        self.expected_params = {"key":DIGEST_NOTIFICATION_PREFERENCE_KEY,
                               "page_size":3,
                               "page":1}
        self.expected_headers = {'X-EDX-API-Key': TEST_API_KEY}


    @override_settings(US_URL_BASE="test_server_url", US_RESULT_PAGE_SIZE=3)
    def test_get_digest_subscribers_empty(self):
        """
        """

        # empty result
        expected_empty = {
            "count": 0, 
            "next": None, 
            "previous": None, 
            "results": []
        }

        with patch('requests.get', return_value=Mock(json=expected_empty)) as p:
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
        expected_single = {
            "count": 3,
            "next": None,
            "previous": None,
            "results": [mkresult(1), mkresult(2), mkresult(3)]
        }

        with patch('requests.get', return_value=Mock(json=expected_single)) as p:
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

        m = Mock()
        with patch('requests.get', return_value=m) as p:
            res = [] 
            m.json = expected_multi_p1 
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
            
            p.reset_mock() # reset call count
            self.expected_params['page']=2
            m.json = expected_multi_p2
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
        expected_single = {
            "count": 3,
            "next": None,
            "previous": None,
            "results": [mkresult(1), mkresult(2), mkresult(3)]
        }

        with patch('requests.get', return_value=Mock(json=expected_single)) as p:
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



