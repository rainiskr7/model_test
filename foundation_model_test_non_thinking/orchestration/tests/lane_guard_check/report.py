"""Collect independent checks without converting missing evidence into PASS."""

import json


class Inconclusive(RuntimeError):
    """The environment cannot supply real-process evidence."""


class CheckFailed(AssertionError):
    """A failed check has already been recorded."""


class Report:
    def __init__(self):
        self.rows = []

    def record(self, status, name, detail=""):
        self.rows.append({"status": status, "name": name, "detail": detail})
        print(f"{status} {name}" + (f" — {detail}" if detail else ""), flush=True)

    def check(self, name, condition, detail=""):
        self.record("PASS" if condition else "FAIL", name, detail)
        if not condition:
            raise CheckFailed(name)

    def run(self, name, action):
        try:
            action()
        except Inconclusive as exc:
            self.record("INCONCLUSIVE", name, str(exc))
        except CheckFailed:
            pass
        except Exception as exc:
            self.record("FAIL", name, repr(exc))

    def finish(self, path):
        counts = {s: sum(r["status"] == s for r in self.rows)
                  for s in ("PASS", "FAIL", "INCONCLUSIVE")}
        path.write_text(json.dumps({"counts": counts, "checks": self.rows}, indent=2))
        print("SUMMARY " + json.dumps(counts), flush=True)
        return 1 if counts["FAIL"] else 77 if counts["INCONCLUSIVE"] else 0
