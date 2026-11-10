#!/usr/bin/env python3
"""Run upstream's unittest suite and print one `RESULT tests=N passed=P failed=F skipped=S` line."""
import sys
import unittest

sys.path[:0] = ["/mayhem/build/oracle/lib", "/mayhem"]
import tests  # noqa: E402

res = unittest.TextTestRunner(verbosity=1).run(tests.test_suite())
failed = len(res.failures) + len(res.errors) + len(res.unexpectedSuccesses)
skipped = len(res.skipped)
print("RESULT tests=%d passed=%d failed=%d skipped=%d"
      % (res.testsRun, res.testsRun - failed - skipped, failed, skipped))
sys.exit(1 if failed else 0)
