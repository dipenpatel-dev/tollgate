# Module:      test_pytest_bridge.py
# Description: Runs the pytest style test modules in this folder as unittest cases, using
#              the small stand-in in minipytest.py. unittest discovery calls load_tests
#              here and gets one case per test function and parameter set.
# Author:      Dipen Patel (dipenpatel-dev)
# Date:
# Version:     1.0
# ChangeLog:
#   Initial version
import importlib
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
MODULES = (
    "test_vault_census",
    "test_backfill_vault_frontmatter",
    "test_backfill_ticket_policy",
    "test_backfill_nonticket_policy",
)


def load_tests(loader, standard_tests, pattern):
    if str(HERE) not in sys.path:
        sys.path.insert(0, str(HERE))
    import minipytest
    suite = unittest.TestSuite()
    for name in MODULES:
        module = importlib.import_module(name)
        for case in minipytest.make_cases(module):
            suite.addTests(loader.loadTestsFromTestCase(case))
    return suite


if __name__ == "__main__":
    unittest.main()
