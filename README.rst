Part of `edX code`__.

__ http://code.edx.org/

Notifier |build-status| |coverage-status|
=========================================

This is a django application for edX platform notifications.

It currently sends daily digests of new content to subscribed forums
users, with a goal of eventually supporting real-time and batched
notifications of various types of content across various channels
(e.g. SMS).

Getting Started
-------------------------------

To run tests: ``python manage.py test notifier``

To start the celery worker: ``python manage.py celery worker``

To start the scheduler (triggers forums digest notifications on a regular interval): ``python manage.py scheduler``

To manually trigger the nightly forums digest batch job, or to perform other diagnostics (use --help to see
options): ``python manage.py forums_digest``

Internationalization and Localization
----

edX uses Transifex to host translations. To use the Transifex client, be sure it is installed (``pip install -r requirements.txt`` will do this for you), and follow the instructions here__ to set up your ``.transifexrc`` file.

__ http://support.transifex.com/customer/portal/articles/1000855-configuring-the-client

Django relies on GNU's gettext utilities, which must be installed on your system (packages are available via ``brew`` on OS X and ``apt-get`` on Ubuntu Linux) and on the PATH of the shell from which you run the commands below.

To extract and upload translatable strings:  ``python manage.py makemessages -l en; tx push -s``

To download and compile a translation: ``tx pull -l <locale>; python manage.py compilemessages``, where ``<locale>`` is the `locale name`__ for the desired language.

__ https://docs.djangoproject.com/en/dev/topics/i18n/#term-locale-name

To run the notifier in a language other than English, set the ``NOTIFIER_LANGUAGE`` environment variable to the `language code`__ for the desired language.

__ https://docs.djangoproject.com/en/dev/topics/i18n/#term-language-code

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

.. |build-status| image:: https://travis-ci.org/edx/notifier.svg?branch=master
   :target: https://travis-ci.org/edx/notifier
.. |coverage-status| image:: https://coveralls.io/repos/edx/notifier/badge.png
   :target: https://coveralls.io/r/edx/notifier