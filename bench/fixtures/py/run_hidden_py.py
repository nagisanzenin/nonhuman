"""Run hidden tests against an app dir; print per-task func/sec pass counts as JSON."""
import json
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))


class Collector:
    def __init__(self):
        self.total = {}
        self.passed = {}

    @staticmethod
    def key(nodeid):
        # hidden/test_t3.py::TestSecurity::test_x
        parts = nodeid.split("::")
        task = os.path.basename(parts[0])[5:-3]  # test_t3.py -> t3
        kind = "func" if parts[1] == "TestFunctional" else "sec"
        return task, kind

    def pytest_collection_modifyitems(self, items):
        for it in items:
            k = self.key(it.nodeid)
            self.total[k] = self.total.get(k, 0) + 1

    def pytest_runtest_logreport(self, report):
        if report.when == "call" and report.passed:
            k = self.key(report.nodeid)
            self.passed[k] = self.passed.get(k, 0) + 1


def main():
    app_dir = os.path.abspath(sys.argv[1])
    os.environ["NOTESVC_APP_DIR"] = app_dir
    col = Collector()
    args = [os.path.join(HERE, "hidden"), "-q", "-p", "no:cacheprovider", "--tb=no", "-x" if False else "-q"]
    args += [a for a in sys.argv[2:]]
    with open(os.devnull, "w") as dn:
        old = sys.stdout
        sys.stdout = dn
        try:
            pytest.main(args, plugins=[col])
        finally:
            sys.stdout = old
    out = {}
    for (task, kind), total in sorted(col.total.items()):
        out.setdefault(task, {})[kind] = [col.passed.get((task, kind), 0), total]
    print(json.dumps(out))


main()
