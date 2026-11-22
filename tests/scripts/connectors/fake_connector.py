#!/usr/bin/env python3
"""A fake connector used only by tests. Model for connector authors.

Author: Dipen Patel (dipenpatel-dev)
Date:
Purpose: Show the interface: register, ensure, use the given http.
Change log:
  - First version.
"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
from connectors.registry import register, ensure, run_cli


class FakeClient:
    def __init__(self, address, key, http):
        self.address, self.key, self.http = address, key, http

    def ping(self):
        return self.http.get(self.address + "/ping",
                             headers={"Authorization": "Bearer " + self.key})


register("fakeconn", lambda address, key, http: FakeClient(address, key, http))


def main():
    client = ensure("fakeconn")
    client.ping()
    print("fakeconn: ok")
    return 0


if __name__ == "__main__":
    sys.exit(run_cli(main) or 0)
