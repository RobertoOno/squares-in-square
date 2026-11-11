"""Run: python3 -m unittest discover -s tests -v   (from the repo root)"""
import json
import math
import os
import subprocess
import sys
import tempfile
import unittest
from fractions import Fraction as F

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from verify import CertError, build, check, compare  # noqa: E402


def run(cert):
    n, S, sqs = build(cert)
    return check(n, S, sqs), S


def grid(k, side):
    sq = [{"cx": f"{2*i+1}/2", "cy": f"{2*j+1}/2"} for i in range(k) for j in range(k)]
    return {"n": k * k, "side": side, "squares": sq}


T45 = "41421356237/100000000000"  # ~ tan(22.5 deg) -> ~45 deg rotation


class TestVerify(unittest.TestCase):
    def test_grid_valid(self):
        errs, S = run(grid(2, "2"))
        self.assertEqual(errs, [])
        self.assertEqual(S, 2)

    def test_grid_too_small(self):
        errs, _ = run(grid(2, "1999/1000"))
        self.assertTrue(any("outside" in e for e in errs))

    def test_overlap_axis_aligned(self):
        cert = {"n": 2, "side": "3", "squares": [{"cx": "1/2", "cy": "1/2"}, {"cx": "1.4", "cy": "1/2"}]}
        errs, _ = run(cert)
        self.assertTrue(any("overlap" in e for e in errs))

    def test_touching_allowed(self):
        cert = {"n": 2, "side": "2", "squares": [{"cx": "1/2", "cy": "1/2"}, {"cx": "3/2", "cy": "1/2"}]}
        errs, _ = run(cert)
        self.assertEqual(errs, [])

    def test_rotated_overlap_and_clearance(self):
        # 45-degree square has half-diagonal ~0.7071; axis-aligned neighbour edge at x=0.5
        base = {"cx": "0", "cy": "0"}
        over = {"n": 2, "side": "10", "squares": [base, {"cx": "1.2", "cy": "0", "t": T45}]}
        clear = {"n": 2, "side": "10", "squares": [base, {"cx": "1.21", "cy": "0", "t": T45}]}
        self.assertTrue(any("overlap" in e for e in run(over)[0]))
        self.assertFalse(any("overlap" in e for e in run(clear)[0]))

    def test_rejects_non_unit_rotation(self):
        cert = {"n": 1, "side": "5", "squares": [{"cx": "2", "cy": "2", "c": "1/2", "s": "1/2"}]}
        with self.assertRaises(CertError):
            build(cert)

    def test_rejects_wrong_count(self):
        cert = grid(2, "2")
        cert["n"] = 5
        with self.assertRaises(CertError):
            build(cert)

    def test_rejects_json_float_via_cli(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            f.write('{"n": 1, "side": 1.0, "squares": [{"cx": "1/2", "cy": "1/2"}]}')
        out = subprocess.run([sys.executable, os.path.join(ROOT, "verify.py"), f.name],
                             capture_output=True, text=True)
        self.assertEqual(out.returncode, 1)
        self.assertIn("JSON float", out.stdout)


class TestCertifyRoundTrip(unittest.TestCase):
    def test_five_squares_known_optimum(self):
        # s(5) = 2 + 1/sqrt(2): four corner squares + one at 45 degrees, all tight
        S = 2 + 1 / math.sqrt(2)
        fl = {"n": 5, "squares": [
            {"x": 0.5, "y": 0.5, "theta": 0}, {"x": S - 0.5, "y": 0.5, "theta": 0},
            {"x": 0.5, "y": S - 0.5, "theta": 0}, {"x": S - 0.5, "y": S - 0.5, "theta": 0},
            {"x": S / 2, "y": S / 2, "theta": math.pi / 4}]}
        d = tempfile.mkdtemp()
        fin, fout = os.path.join(d, "f.json"), os.path.join(d, "c.json")
        json.dump(fl, open(fin, "w"))
        r = subprocess.run([sys.executable, os.path.join(ROOT, "certify.py"), fin, fout],
                           capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        v = subprocess.run([sys.executable, os.path.join(ROOT, "verify.py"), fout],
                           capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(v.returncode, 0, v.stdout)
        cert = json.load(open(fout))
        Sc = F(cert["side"])
        self.assertTrue(S - 1e-9 < float(Sc) < S + 1e-6, float(Sc))

        # record comparison logic
        recs = os.path.join(d, "r.json")
        json.dump({"records": [{"n": 5, "upper": "2.7071", "source": "test"}]}, open(recs, "w"))
        self.assertIn("does not beat", compare(5, Sc, recs))
        json.dump({"records": [{"n": 5, "upper": "2.7072", "source": "test"}]}, open(recs, "w"))
        self.assertIn("CERTIFIED IMPROVEMENT", compare(5, Sc, recs))
        json.dump({"records": [{"n": 5, "upper": "2.7071", "proven_optimal": True, "source": "test"}]}, open(recs, "w"))
        self.assertIn("PROVEN OPTIMAL", compare(5, Sc, recs))


if __name__ == "__main__":
    unittest.main()
