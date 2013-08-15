Part of `edX code`__.

__ http://code.edx.org/

Notifier
=======================

This is a django application for edX platform notifications.

It currently sends daily digests of new content to subscribed forums
users, with a goal of eventually supporting real-time and batched
notifications of various types of content across various channels
(e.g. SMS).

Getting Started
-------------------------------

To run tests: ``python manage.py test notifier``

To start the celery worker: ``python manage.py celery worker``

To run the nightly forums digest batch job (use --help to see
options): ``python manage.py forums_digest``

License
-------

The code in this repository is licensed under version 3 of the AGPL unless
otherwise noted.

Please see ``LICENSE.txt`` for details.

How to Contribute
-----------------

Contributions are very welcome. The easiest way is to fork this repo, and then
make a pull request from your fork. The first time you make a pull request, you
may be asked to sign a Contributor Agreement.

Please see ``CONTRIBUTING.rst`` for details.

Reporting Security Issues
-------------------------

Please do not report security issues in public. Please email security@edx.org

Mailing List and IRC Channel
----------------------------

You can discuss this code on the `edx-code Google Group`__ or in the
``edx-code`` IRC channel on Freenode.

__ https://groups.google.com/forum/#!forum/edx-code






