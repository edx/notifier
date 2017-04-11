#!/bin/bash -xe
. /edx/app/notifier/virtualenvs/notifier/bin/activate
cd /edx/app/notifier/notifier
coverage xml
