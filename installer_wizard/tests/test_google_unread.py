import unittest

from features.google.data import UNREAD_QUERY, GoogleData


class FakeGmail(GoogleData):
    def __init__(self, label=None, estimate=201, fail=False):
        self.label, self.estimate, self.fail = label, estimate, fail

    async def _get(self, url, **params):
        if url.endswith("/labels/INBOX"):
            if self.fail:
                raise RuntimeError("no label access")
            return self.label
        if url.endswith("/messages"):
            return {"resultSizeEstimate": self.estimate, "messages": []}
        raise AssertionError(url)


class UnreadCountTest(unittest.IsolatedAsyncioTestCase):
    async def test_unread_uses_the_exact_inbox_thread_count_not_the_estimate(self):
        total, _ = await FakeGmail({"threadsUnread": 3}).mails(UNREAD_QUERY, 0)
        self.assertEqual(total, 3)

    async def test_zero_unread_is_reported_as_zero(self):
        total, _ = await FakeGmail({"threadsUnread": 0}).mails(UNREAD_QUERY, 0)
        self.assertEqual(total, 0)

    async def test_falls_back_to_the_estimate_when_the_label_is_unavailable(self):
        for gmail in (FakeGmail(fail=True), FakeGmail({}), FakeGmail({"threadsUnread": "x"})):
            total, _ = await gmail.mails(UNREAD_QUERY, 0)
            self.assertEqual(total, 201)

    async def test_other_searches_keep_the_search_estimate(self):
        total, _ = await FakeGmail({"threadsUnread": 3}, estimate=7).mails("from:(mario) in:inbox", 0)
        self.assertEqual(total, 7)


if __name__ == "__main__":
    unittest.main()
