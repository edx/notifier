"""
Explicitly load all the test modules so django's test runner finds them.
"""

import unittest
import doctest

# imports to pick up unit tests
from notifier.tests import test_pull
from notifier.tests import test_tasks
from notifier.tests import test_user
from notifier.tests import test_commands
from notifier.tests import test_digest

# imports to pick up module doctests
from notifier import digest
from notifier import tasks


def add_unit_tests(suite, module):
    suite.addTest(unittest.TestLoader().loadTestsFromModule(module))

def add_doc_tests(suite, module):
    suite.addTest(doctest.DocTestSuite(module))

def suite():
    suite = unittest.TestSuite()

    # digest
    add_doc_tests(suite, digest)
    add_unit_tests(suite, test_digest)
    
    # pull
    add_unit_tests(suite, test_pull)

    # tasks
    add_unit_tests(suite, test_tasks)
    add_doc_tests(suite, tasks)

    # user
    add_unit_tests(suite, test_user)

    # commands
    add_unit_tests(suite, test_commands)

    return suite
