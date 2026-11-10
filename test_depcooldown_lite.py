"""Offline tests for depcooldown-lite (no network: the registry fetch is faked)."""
import datetime
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr

import depcooldown_lite as dl

NOW = datetime.datetime(2026, 11, 10, 12, 0, tzinfo=datetime.timezone.utc)
TIMES = {
    ("pypi", "requests", "2.32.3"): "2024-05-29T15:37:47.000Z",
    ("pypi", "fresh-pkg", "1.0.1"): "2026-11-08T09:00:00Z",
    ("npm", "left-pad", "1.3.0"): "2018-04-09T01:56:36.000Z",
    ("npm", "@scope/new", "2.0.0"): "2026-11-09T10:00:00.123456789Z",
}


def fake_fetch(eco, name, ver):
    return TIMES.get((eco, name, ver))


def run(path, *extra):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = dl.main([path, *extra], fetch=fake_fetch, now=NOW)
    return code, out.getvalue(), err.getvalue()


class T(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()

    def write(self, name, text):
        p = os.path.join(self.d, name)
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(text)
        return p

    def test_parse_requirements(self):
        pins = dl.parse_requirements("# c\nRequests[socks]==2.32.3 ; python_version>'3'\nflask>=2\n-r other.txt\nmy_pkg==1.0 # x\n")
        self.assertEqual(pins, {"requests": "2.32.3", "my-pkg": "1.0"})

    def test_parse_lock_v3_and_v1(self):
        v3 = {"packages": {"": {"name": "root"}, "node_modules/left-pad": {"version": "1.3.0"},
                           "node_modules/@scope/new": {"version": "2.0.0"}}}
        self.assertEqual(dl.parse_package_lock(json.dumps(v3)), {"left-pad": "1.3.0", "@scope/new": "2.0.0"})
        v1 = {"dependencies": {"left-pad": {"version": "1.3.0"}}}
        self.assertEqual(dl.parse_package_lock(json.dumps(v1)), {"left-pad": "1.3.0"})

    def test_requirements_fail_on_fresh(self):
        p = self.write("requirements.txt", "requests==2.32.3\nfresh-pkg==1.0.1\n")
        code, out, _ = run(p)
        self.assertEqual(code, 1)
        self.assertIn("FAIL", out)
        self.assertIn("fresh-pkg==1.0.1", out)

    def test_cooldown_zero_passes(self):
        p = self.write("requirements.txt", "fresh-pkg==1.0.1\n")
        self.assertEqual(run(p, "--cooldown", "0")[0], 0)

    def test_npm_json(self):
        lock = {"packages": {"node_modules/left-pad": {"version": "1.3.0"}, "node_modules/@scope/new": {"version": "2.0.0"}}}
        p = self.write("package-lock.json", json.dumps(lock))
        code, out, _ = run(p, "--json")
        data = json.loads(out)
        self.assertEqual(code, 1)
        self.assertEqual(data["failed"], 1)
        self.assertEqual(data["ecosystem"], "npm")

    def test_unverified_does_not_fail(self):
        p = self.write("requirements.txt", "unknown==9.9.9\nrequests==2.32.3\n")
        code, out, _ = run(p)
        self.assertEqual(code, 0)
        self.assertIn("UNVERIFIED", out)

    def test_unsupported_file_is_usage_error(self):
        p = self.write("uv.lock", "")
        self.assertEqual(run(p)[0], 2)
        self.assertEqual(run(os.path.join(self.d, "missing.txt"))[0], 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
