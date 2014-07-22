"""
"""

import datetime
import random

from dateutil.parser import parse as date_parse
from django.test import TestCase
from django.test.utils import override_settings
from mock import MagicMock, Mock, patch
import requests

from notifier.digest import _trunc, THREAD_ITEM_MAXLEN, \
                            _get_thread_url, _get_course_title, _get_course_url
from notifier.pull import CommentsServiceException, Parser, generate_digest_content


class ParserTestCase(TestCase):
    """
    """

    @staticmethod
    def _item(v):
        return {
            "body": "body: %s" % v,
            "username": "user_%s" % v,
            "updated_at": (datetime.datetime(2013, 1, 1) + \
                           datetime.timedelta(
                               days=random.randint(0,365), 
                               seconds=random.randint(0,86399)
                               )
                           ).isoformat()
            }

    @staticmethod
    def _thread(v, items=[]):
        return {
            "title": "title: %s" % v,
            "commentable_id": "commentable_id: %s" % v,
            "content": items
            }

    @staticmethod
    def _course(threads=[]):
        return dict(('id-%s' % random.random(), thread) for thread in threads)

    @staticmethod
    def _digest(courses=[]):
        return dict(('id-%s' % random.random(), course) for course in courses)

    @staticmethod
    def _payload(digests=[]):
        return dict(('id-%s' % random.random(), digest) for digest in digests)

    def _check_item(self, raw_item, parsed_item):
        self.assertEqual(parsed_item.body, _trunc(raw_item["body"], THREAD_ITEM_MAXLEN))
        self.assertEqual(parsed_item.author, raw_item["username"])
        self.assertEqual(parsed_item.dt, date_parse(raw_item["updated_at"]))
       
    def _find_raw_item(self, parsed_item, raw_items):
        for raw_item in raw_items:
            try:
                self._check_item(raw_item, parsed_item)
                return raw_item
            except AssertionError:
                pass

    def _check_thread(self, thread_id, course_id, raw_thread, parsed_thread):
        self.assertEqual(parsed_thread.title, raw_thread["title"])
        self.assertEqual(parsed_thread.url, _get_thread_url(course_id, thread_id, raw_thread["commentable_id"]))
        # each parsed item is a correct parsing of some raw item
        for parsed_item in parsed_thread.items:
            self.assertIsNotNone(self._find_raw_item(parsed_item, raw_thread["content"]))
        # parsed items occur in reverse order by datetime
        dts = [parsed_item.dt for parsed_item in parsed_thread.items]
        self.assertEqual(dts, sorted(dts, reverse=True))

    def _find_raw_thread(self, parsed_thread, course_id, raw_threads):
        for thread_id, raw_thread in raw_threads.iteritems():
            try:
                self._check_thread(thread_id, course_id, raw_thread, parsed_thread)
                return raw_thread
            except AssertionError:
                pass

    def _check_course(self, course_id, raw_course, parsed_course):
        self.assertEqual(parsed_course.title, _get_course_title(course_id))
        self.assertEqual(parsed_course.url, _get_course_url(course_id))
        # each parsed thread is a correct parsing of some raw thread
        for parsed_thread in parsed_course.threads:
            self.assertIsNotNone(self._find_raw_thread(parsed_thread, course_id, raw_course))
        # parsed threads  occur in reverse order by datetime
        dts = [parsed_thread.dt for parsed_thread in parsed_course.threads]
        self.assertEqual(dts, sorted(dts, reverse=True))

    def _find_raw_course(self, parsed_course, raw_courses):
        for course_id, raw_course in raw_courses.iteritems():
            try:
                self._check_course(course_id, raw_course, parsed_course)
                return raw_course
            except AssertionError:
                pass

    def _check_digest(self, user_id, raw_digest, parsed_digest):
        # each parsed course is a correct parsing of some raw course
        for parsed_course in parsed_digest.courses:
            self.assertIsNotNone(self._find_raw_course(parsed_course, raw_digest))
        # parsed courses occur sorted by title, case-insensitively 
        lower_titles = [parsed_course.title.lower() for parsed_course in parsed_digest.courses]
        self.assertEqual(lower_titles, sorted(lower_titles))

    def _find_raw_digest(self, parsed_digest, raw_payload):
        for user_id, raw_digest in raw_payload.iteritems():
            try:
                self._check_digest(user_id, raw_digest, parsed_digest)
                return raw_digest
            except AssertionError:
                pass

    def test_item_simple(self):
        i = self._item("a")
        self._check_item(i, Parser.item(i))

    def test_thread_simple(self):
        t = self._thread("t", [self._item("a"), self._item("b"), self._item("c")])
        self._check_thread("some_thread_id", "some_course_id", t, 
                Parser.thread('some_thread_id', 'some_course_id', t))
        
    def test_course_simple(self):
        c = self._course([
               self._thread("t0", [self._item("a"), self._item("b"), self._item("c")]),
               self._thread("t1", [self._item("d"), self._item("e"), self._item("f")]),
               self._thread("t2", [self._item("g"), self._item("h"), self._item("i")]),
            ])
        self._check_course("some_course_id", c, Parser.course("some_course_id", c))
        
    def test_digest_simple(self):
        d = self._digest([
                self._course([
                   self._thread("t00", [self._item("a"), self._item("b"), self._item("c")]),
                   self._thread("t01", [self._item("d"), self._item("e"), self._item("f")]),
                   self._thread("t02", [self._item("g"), self._item("h"), self._item("i")]),
                ]),
                self._course([
                   self._thread("t10", [self._item("j"), self._item("k"), self._item("l")]),
                   self._thread("t11", [self._item("m"), self._item("n"), self._item("o")]),
                   self._thread("t12", [self._item("p"), self._item("q"), self._item("r")]),
                ]),
            ])
        self._check_digest("some_user_id", d, Parser.digest("some_user_id", d))

    def test_parse(self):
        p = self._payload([
                self._digest([
                    self._course([
                       self._thread("t00", [self._item("a"), self._item("b"), self._item("c")]),
                       self._thread("t01", [self._item("d"), self._item("e"), self._item("f")]),
                       self._thread("t02", [self._item("g"), self._item("h"), self._item("i")]),
                    ]),
                    self._course([
                       self._thread("t10", [self._item("j"), self._item("k"), self._item("l")]),
                       self._thread("t11", [self._item("m"), self._item("n"), self._item("o")]),
                       self._thread("t12", [self._item("p"), self._item("q"), self._item("r")]),
                    ]),
                ]),
                self._digest([
                    self._course([
                       self._thread("t20", [self._item("A"), self._item("B"), self._item("C")]),
                       self._thread("t21", [self._item("D"), self._item("E"), self._item("F")]),
                       self._thread("t22", [self._item("G"), self._item("H"), self._item("I")]),
                    ]),
                    self._course([
                       self._thread("t30", [self._item("J"), self._item("K"), self._item("L")]),
                       self._thread("t31", [self._item("M"), self._item("N"), self._item("O")]),
                       self._thread("t32", [self._item("P"), self._item("Q"), self._item("R")]),
                    ]),
                ]),
            ])
        digest_count = 0
        for user_id, parsed_digest in Parser.parse(p):
            #self._check_user(user_id, u, Parser.user(user_id, u))
            self.assertIsNotNone(self._find_raw_digest(parsed_digest, p))
            digest_count += 1
        self.assertEqual(digest_count, len(p))


@override_settings(CS_URL_BASE='*test_cs_url*', CS_API_KEY='*test_cs_key*')
class GenerateDigestContentTestCase(TestCase):
    """
    """

    def test_empty(self):
        """
        """
        from_dt = datetime.datetime(2013, 1, 1)
        to_dt = datetime.datetime(2013, 1, 2)
        mock_response = Mock(status_code=200)
        mock_response.json.return_value = {}
        with patch('requests.post', return_value=mock_response) as p:
            g = generate_digest_content(["a", "b", "c"], from_dt, to_dt)
            expected_api_url = '*test_cs_url*/api/v1/notifications'
            expected_headers = {
                'X-Edx-Api-Key': '*test_cs_key*',
            }
            expected_post_data = {
                'user_ids': 'a,b,c',
                'from': '2013-01-01 00:00:00', # TODO tz offset
                'to': '2013-01-02 00:00:00'
            }
            p.assert_called_once_with(expected_api_url, headers=expected_headers, data=expected_post_data)            
            self.assertRaises(StopIteration, g.next)

    # TODO: test_single_result, test_multiple_results

    def test_service_connection_error(self):
        from_dt = datetime.datetime(2013, 1, 1)
        to_dt = datetime.datetime(2013, 1, 2)
        with patch('requests.post', side_effect=requests.exceptions.ConnectionError) as p:
            self.assertRaises(CommentsServiceException, generate_digest_content, ["a"], from_dt, to_dt)

    def test_service_http_error(self):
        from_dt = datetime.datetime(2013, 1, 1)
        to_dt = datetime.datetime(2013, 1, 2)
        with patch('requests.post', return_value=Mock(status_code=401)) as p:
            self.assertRaises(CommentsServiceException, generate_digest_content, ["a"], from_dt, to_dt)
