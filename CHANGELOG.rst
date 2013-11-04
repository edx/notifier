Change Log
----------

These are notable changes in notifier.  This is a rolling list of changes,
in roughly chronological order, most recent first.  Add your entries at or near
the top.

**Comments Service Auth**
Use HTTP header auth instead of URL parameter auth for comments service. This
requires cs_comments_service commit cf39aab or later.

**Batch Query Size**
The setting FORUM_DIGEST_TASK_BATCH_SIZE, which sets the maximum number of users
per query when pulling updates from the comments service, has been reduced from
50 to 5.  This change is intended to reduce the amount of data that will be
processed / retrieved in any single query roundtrip.  As part of this change, it is
now possible to override this value by setting an environment variable using the
same name.

