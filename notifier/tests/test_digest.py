# coding=utf-8

from uuid import uuid4

from unittest import skip
from django.test import TestCase
from mock import patch

from notifier import settings
from notifier.digest import Digest, DigestCourse, DigestItem, DigestThread, render_digest
from notifier.user import DIGEST_NOTIFICATION_PREFERENCE_KEY, LANGUAGE_PREFERENCE_KEY

TEST_COURSE_ID = "test_org/test_num/test_course"
TEST_COMMENTABLE = "test_commentable"

@patch("notifier.digest.THREAD_ITEM_MAXLEN", 17)
class DigestItemTestCase(TestCase):
    def _test_unicode_data(self, input_text, expected_text):
        self.assertEqual(DigestItem(input_text, None, None).body, expected_text)

    def test_ascii(self):
        self._test_unicode_data(u"This post contains ASCII.", u"This post...")

    def test_latin_1(self):
        self._test_unicode_data(u"Thís pøst çòñtáins Lätin-1 tæxt", u"Thís pøst...")

    def test_CJK(self):
        self._test_unicode_data(u"ｲんﾉ丂 ｱo丂ｲ co刀ｲﾑﾉ刀丂 cﾌズ", u"ｲんﾉ丂 ｱo丂ｲ...")

    def test_non_BMP(self):
        self._test_unicode_data(u"𝕋𝕙𝕚𝕤 𝕡𝕠𝕤𝕥 𝕔𝕠𝕟𝕥𝕒𝕚𝕟𝕤 𝕔𝕙𝕒𝕣𝕒𝕔𝕥𝕖𝕣𝕤 𝕠𝕦𝕥𝕤𝕚𝕕𝕖 𝕥𝕙𝕖 𝔹𝕄ℙ", u"𝕋𝕙𝕚𝕤 𝕡𝕠𝕤𝕥...")

    def test_special_chars(self):
        self._test_unicode_data(u"\" This , post > contains < delimiter ] and [ other } special { characters ; that & may ' break things", u"\" This , post...")

    def test_string_interp(self):
        self._test_unicode_data(u"This post contains %s string interpolation #{syntax}", u"This post...")


@patch("notifier.digest.THREAD_TITLE_MAXLEN", 17)
class DigestThreadTestCase(TestCase):
    def _test_unicode_data(self, input_text, expected_text):
        self.assertEqual(DigestThread("0", TEST_COURSE_ID, TEST_COMMENTABLE, input_text, []).title, expected_text)

    def test_ascii(self):
        self._test_unicode_data(u"This post contains ASCII.", u"This post...")

    def test_latin_1(self):
        self._test_unicode_data(u"Thís pøst çòñtáins Lätin-1 tæxt", u"Thís pøst...")

    def test_CJK(self):
        self._test_unicode_data(u"ｲんﾉ丂 ｱo丂ｲ co刀ｲﾑﾉ刀丂 cﾌズ", u"ｲんﾉ丂 ｱo丂ｲ...")

    def test_non_BMP(self):
        self._test_unicode_data(u"𝕋𝕙𝕚𝕤 𝕡𝕠𝕤𝕥 𝕔𝕠𝕟𝕥𝕒𝕚𝕟𝕤 𝕔𝕙𝕒𝕣𝕒𝕔𝕥𝕖𝕣𝕤 𝕠𝕦𝕥𝕤𝕚𝕕𝕖 𝕥𝕙𝕖 𝔹𝕄ℙ", u"𝕋𝕙𝕚𝕤 𝕡𝕠𝕤𝕥...")

    def test_special_chars(self):
        self._test_unicode_data(u"\" This , post > contains < delimiter ] and [ other } special { characters ; that & may ' break things", u"\" This , post...")

    def test_string_interp(self):
        self._test_unicode_data(u"This post contains %s string interpolation #{syntax}", u"This post...")


@patch("notifier.digest.THREAD_TITLE_MAXLEN", 17)
class RenderDigestTestCase(TestCase):
    def set_digest(self, thread_title):
        self.digest = Digest([
            DigestCourse(
                TEST_COURSE_ID,
                [DigestThread(
                    "0",
                    TEST_COURSE_ID,
                    TEST_COMMENTABLE,
                    thread_title,
                    [DigestItem("test content", None, None)]
                )]
            )
        ])

    def setUp(self):
        self.user = {
            "id": "0",
            "preferences": {
                DIGEST_NOTIFICATION_PREFERENCE_KEY: uuid4(),
            }
        }
        self.set_digest("test title")

    def _test_unicode_data(self, input_text, expected_text, expected_html=None):
        self.set_digest(input_text)
        (rendered_text, rendered_html) = render_digest(self.user, self.digest, "Test Title", "Test Description")
        self.assertIn(expected_text, rendered_text)
        self.assertIn(expected_html if expected_html else expected_text, rendered_html)

    def test_ascii(self):
        self._test_unicode_data(u"This post contains ASCII.", u"This post...")

    def test_latin_1(self):
        self._test_unicode_data(u"Thís pøst çòñtáins Lätin-1 tæxt", u"Thís pøst...")

    def test_CJK(self):
        self._test_unicode_data(u"ｲんﾉ丂 ｱo丂ｲ co刀ｲﾑﾉ刀丂 cﾌズ", u"ｲんﾉ丂 ｱo丂ｲ...")

    def test_non_BMP(self):
        self._test_unicode_data(u"𝕋𝕙𝕚𝕤 𝕡𝕠𝕤𝕥 𝕔𝕠𝕟𝕥𝕒𝕚𝕟𝕤 𝕔𝕙𝕒𝕣𝕒𝕔𝕥𝕖𝕣𝕤 𝕠𝕦𝕥𝕤𝕚𝕕𝕖 𝕥𝕙𝕖 𝔹𝕄ℙ", u"𝕋𝕙𝕚𝕤 𝕡𝕠𝕤𝕥...")

    def test_special_chars(self):
        self._test_unicode_data(
            u"\" This , post > contains < delimiter ] and [ other } special { characters ; that & may ' break things",
            u"\" This , post...",
            u"&quot; This , post..."
        )

    def test_string_interp(self):
        self._test_unicode_data(u"This post contains %s string interpolation #{syntax}", u"This post...")

    @patch("notifier.digest.deactivate")
    @patch("notifier.digest.activate")
    def test_user_lang_pref_supported(self, mock_activate, mock_deactivate):
        user_lang = "fr"
        self.user["preferences"][LANGUAGE_PREFERENCE_KEY] = user_lang
        render_digest(self.user, self.digest, "dummy", "dummy")
        mock_activate.assert_called_with(user_lang)
        mock_deactivate.assert_called()

    @patch("notifier.digest.activate")
    def test_user_lang_pref_unsupported(self, mock_activate):
        user_lang = "x-unsupported-lang"
        self.user["preferences"][LANGUAGE_PREFERENCE_KEY] = user_lang
        render_digest(self.user, self.digest, "dummy", "dummy")
        mock_activate.assert_not_called()

    @patch("notifier.digest.activate")
    def test_user_lang_pref_absent(self, mock_activate):
        if LANGUAGE_PREFERENCE_KEY in self.user["preferences"]:
            del self.user["preferences"][LANGUAGE_PREFERENCE_KEY]
        render_digest(self.user, self.digest, "dummy", "dummy")
        mock_activate.assert_not_called()

    def test_unsubscribe_url(self):
        text, html = render_digest(self.user, self.digest, "dummy", "dummy")
        expected_url = "{lms_url_base}/notification_prefs/unsubscribe/{token}/".format(
            lms_url_base=settings.LMS_URL_BASE,
            token=self.user["preferences"][DIGEST_NOTIFICATION_PREFERENCE_KEY]
        )
        self.assertIn(expected_url, text)
        self.assertIn(expected_url, html)
