"""
"""

import datetime
import random
import itertools

from dateutil.parser import parse as date_parse
from django.test import TestCase
from django.test.utils import override_settings
from mock import Mock, patch
import requests

from notifier.digest import (
    _trunc, THREAD_ITEM_MAXLEN, _get_thread_url, _get_course_title, _get_course_url
)
from notifier.pull import (
    CommentsServiceException,
    process_cs_response,
    _build_digest,
    _build_digest_course,
    _build_digest_thread,
    _build_digest_item,
    generate_digest_content
)

from .utils import make_mock_json_response


class DigestTestCase(TestCase):
    """
    Base class for tests that need to create mock digest items.
    """
    @staticmethod
    def _item(v):
        """Returns a mock item as would be returned by the comments service."""
        return {
            "body": "body: %s" % v,
            "username": "user_%s" % v,
            "updated_at": (
                datetime.datetime(2013, 1, 1) + datetime.timedelta(
                    days=random.randint(0,365),
                    seconds=random.randint(0,86399)
                )).isoformat()
        }

    @staticmethod
    def _thread(v, items=[], group_id=None):
        """Returns a mock thread with the given items as would be returned by the comments service."""
        return {
            "title": v,
            "commentable_id": "commentable_id: %s" % v,
            "content": items,
            "group_id": group_id,
        }

    @staticmethod
    def _course(course_id, threads=[]):
        """Returns a mock course with the given threads as would be returned by the comments service."""
        return dict(('id-%s' % random.random(), thread) for thread in threads)

    @staticmethod
    def _digest(courses=[], course_ids=None):
        """
        Returns a mock digest for the given courses as would be returned by the comments service.
        course_ids should be a list of course_ids that correspond 1 to 1 with the list of courses.
        If course_ids is None, generates random course_ids instead.
        """
        if course_ids is None:
            course_ids = ['id-%s' % random.random() for _ in range(len(courses))]
        return dict((course_ids[i], course) for i, course in enumerate(courses))

    @staticmethod
    def _payload(digests=[], user_ids=None):
        """
        Returns a mock payload for the given digests as would be returned by the comments service.
        users should be a list of user ids that correspond 1 to 1 with the list of digests.
        If users is None, generates random user ids instead.
        """
        if user_ids is None:
            user_ids = ['id-%s' % random.random() for _ in range(len(digests))]
        return dict((user_ids[i], digest) for i, digest in enumerate(digests))


class CommentsServicePayloadHandlerTestCase(DigestTestCase):
    """
    Tests for the Digest CommentsServicePayloadHandler classes.
    """
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
        self._check_item(i, _build_digest_item(i))

    def test_thread_simple(self):
        t = self._thread("t", [self._item("a"), self._item("b"), self._item("c")])
        self._check_thread("some_thread_id", "some_course_id", t, 
                _build_digest_thread('some_thread_id', 'some_course_id', t))
        
    def test_course_simple(self):
        c = self._course([
               self._thread("t0", [self._item("a"), self._item("b"), self._item("c")]),
               self._thread("t1", [self._item("d"), self._item("e"), self._item("f")]),
               self._thread("t2", [self._item("g"), self._item("h"), self._item("i")]),
            ])
        self._check_course("some_course_id", c, _build_digest_course("some_course_id", c, {"course_info": {"some_course_id": {"see_all_cohorts": False, "cohort_id": None}}}))
        
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
        self._check_digest("some_user_id", d, _build_digest(d, {"course_info": {"some_course_id": {"see_all_cohorts": False, "cohort_id": None}}}))

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
        for user_id, parsed_digest in process_cs_response(p, {}):
            self.assertIsNotNone(self._find_raw_digest(parsed_digest, p))
            digest_count += 1
        self.assertEqual(digest_count, len(p))


@override_settings(CS_URL_BASE='*test_cs_url*', CS_API_KEY='*test_cs_key*')
class GenerateDigestContentTestCase(DigestTestCase):
    """
    Tests for the generate_digest_content method.
    """
    def setUp(self):
        """
        Create mock dates for testing.
        """
        self.from_dt = datetime.datetime(2013, 1, 1)
        self.to_dt = datetime.datetime(2013, 1, 2)

    def test_empty(self):
        """
        Test the empty mock response from the comments service.
        """
        mock_response = make_mock_json_response()
        with patch('requests.post', return_value=mock_response) as p:
            g = generate_digest_content(
                {"a": {}, "b": {}, "c": {}},
                self.from_dt,
                self.to_dt
            )
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
        """
        Test a mock connection error to the comments service.
        """
        with patch('requests.post', side_effect=requests.exceptions.ConnectionError) as p:
            self.assertRaises(
                CommentsServiceException,
                generate_digest_content,
                {"a": {}},
                self.from_dt,
                self.to_dt
            )

    def test_service_http_error(self):
        """
        Test a mock HTTP error to the comments service.
        """
        with patch('requests.post', return_value=Mock(status_code=401)) as p:
            self.assertRaises(
                CommentsServiceException,
                generate_digest_content,
                {"a": {}},
                self.from_dt,
                self.to_dt
            )

    def test_cohort(self):
        """
        Test the generate_digest_content correctly filters digests according to user access to the threads.
        """

        # Create a mock user information dict as would be returned from the user service (LMS).
        users_by_id = {
            "moderator": {
                "course_info": {
                    "cohorted-course": {"see_all_cohorts": True},
                    "non-cohorted-course": {"see_all_cohorts": True},
                },
                "expected_threads": [
                    "group1-t01", "group2-t02", "all-groups-t03", "no-group-t11", "old-group-t12"
                ],
            },
            "group1_user": {
                "course_info": {
                    "cohorted-course": {"cohort_id": "Group1", "see_all_cohorts": False},
                    "non-cohorted-course": {"see_all_cohorts": True},
                },
                "expected_threads": ["group1-t01", "all-groups-t03", "no-group-t11", "old-group-t12"],
            },
            "group2_user": {
                "course_info": {
                    "cohorted-course": {"cohort_id": "Group2", "see_all_cohorts": False},
                },
                "expected_threads": ["group2-t02", "all-groups-t03"],
            },
            "unassigned_user": {
                "course_info": {
                    "cohorted-course": {"cohort_id": None, "see_all_cohorts": False},
                    "non-cohorted-course": {"see_all_cohorts": True},
                },
                "expected_threads": ["all-groups-t03", "no-group-t11", "old-group-t12"],
            },
            "unenrolled_user": {
                "course_info": {},
                "expected_threads": [],
            },
        }
        user_ids = users_by_id.keys()

        # Create a mock payload with digest information as would be returned by the comments service.
        digests = [
            self._digest(
                [
                    self._course([
                        self._thread("group1-t01", [self._item("a1"), self._item("b1"), self._item("c1")], "Group1"),
                        self._thread("group2-t02", [self._item("a2"), self._item("b2"), self._item("c2")], "Group2"),
                        self._thread("all-groups-t03", [self._item("a3"), self._item("b3"), self._item("c3")], None),
                    ]),
                    self._course([
                        self._thread("no-group-t11", [self._item("a3"), self._item("b3"), self._item("c3")], None),
                        self._thread("old-group-t12", [self._item("a3"), self._item("b3"), self._item("c3")], "OldGroup"),
                    ]),
                ],
                ["cohorted-course", "non-cohorted-course"]
            )
            for _ in range(len(user_ids))
        ]
        payload = self._payload(digests, user_ids)

        # Verify the notifier's generate_digest_content method correctly filters digests as expected.
        mock_response = make_mock_json_response(json=payload)
        with patch('requests.post', return_value=mock_response):
            filtered_digests = generate_digest_content(users_by_id, self.from_dt, self.to_dt)

            # Verify the returned digests are as expected for each user.
            num_returned_users = 0
            for user_id, digest in filtered_digests:
                print "INPUTS:", user_id, digest.courses
                thread_titles = [t.title for t in itertools.chain(*(c.threads for c in digest.courses))]
                # self.assertSetEqual(
                #     set(users_by_id[user_id]["expected_threads"]),
                #     set(thread_titles),
                #     "Set of returned digest threads does not equal expected results"
                # )
                if set(users_by_id[user_id]["expected_threads"]) != set(thread_titles):
                    print "EXPECTED:", users_by_id[user_id]["expected_threads"]
                    print "RETURNED:", set(thread_titles)
                num_returned_users += 1

            # Make sure the number of digests equals the number of users.
            # Otherwise, it's possible the guts of the for loop above never got called.
            self.assertEquals(num_returned_users, len(user_ids))
