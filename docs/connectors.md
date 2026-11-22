# Writing a connector

A connector links Tollgate to one outside tool (a tracker, a chat app, a notes app). This page is for the person writing one.

## The rule

A connector is off until someone tries to use it. With no setup it prints `<name>: not set up` and how to set it up, exits non-zero, and makes no network call. The first use asks for the address and key, saves the key in the user's own secret store (macOS Keychain, or Linux `secret-tool`), writes the name and address to the file named by `TOLLGATE_CONNECTORS`, and turns the connector on. That file never holds a key. If no secret store exists, setup refuses. It never writes a key to a plain file.

## What you write

One module in `scripts/connectors/` that registers a factory, and a client class that uses the `http` it is given.

```python
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from connectors.registry import register, ensure

class PlaneClient:
    def __init__(self, address, key, http):
        self.address, self.key, self.http = address, key, http

    def list_cards(self):
        return self.http.get(self.address + "/cards",
                             headers={"Authorization": "Bearer " + self.key})

register("plane", lambda address, key, http: PlaneClient(address, key, http))

def main():
    client = ensure("plane")   # asks on first use, or raises NotSetUp
    print(client.list_cards())
```

Rules for your module:

1. Register at import time with `register(name, factory)`. The factory takes `address`, `key` and `http` and returns your client.
2. Get the client only through `ensure(name)` (or `require(name)` when you must never prompt). Never read a key yourself.
3. Make every network call through the `http` you were handed. It checks the host on every request (see Host allowlist). A new connector needs an entry in `BUILTIN_HOSTS` in `scripts/connectors/registry.py` {src:scripts/connectors/registry.py:108-115}, or its users must approve each host with `--allow-host`. Never import a request library in the client. That is how tests prove no call happens when the connector is off.
4. Catch `NotSetUp` at your entry point, print its message, and exit non-zero. `registry.run_cli(main)` does this for you.
5. Never print or log the key. Never put it in an argument list.

## Setting up by hand

```
python3 scripts/connectors/connect.py on plane            # asks for address and key
python3 scripts/connectors/connect.py on plane --address URL --key-from-env PLANE_KEY
printf '%s' "$KEY" | python3 scripts/connectors/connect.py on plane --address URL --key-stdin
python3 scripts/connectors/connect.py status
python3 scripts/connectors/connect.py off plane
```

`off` turns the connector off and removes its key from the secret store.

## What to test

Use the fake secret store and mock client from `tests/harness/connector_helpers.py`. See `tests/scripts/connectors/fake_connector.py` for a model. Every connector needs these four checks:

1. Not set up: message names the connector, exit is non-zero, no network call.
2. First use: the key goes to the secret store and appears in no file.
3. After first use: it stays on after a restart and the next call reaches the mock client.
4. After `off`: back to the not set up behavior.

Build fake keys at run time. Never write a real one into a test.

Importing `connector_helpers` also lets the test connector names use fake `.invalid` hosts {src:tests/harness/connector_helpers.py:105-108}, so a test address such as `https://x.invalid` passes the host check. A test of the host rules themselves restores the real list from `REAL_BUILTIN_HOSTS` {src:tests/harness/connector_helpers.py:104}; see `tests/scripts/connectors/test_host_allowlist.py`.

## Settings and redirects

1. Non-secret settings (warehouse, catalog, project) live in the connector's entry in the connectors file. Set them with `connect.py on NAME --set KEY=VALUE` (repeatable) or `registry.set_settings(name, mapping)`; read them with `registry.get_settings(name)`. Values are strings, numbers, booleans or lists of those. A name containing `key`, `token`, `secret` or `password` is refused. Secrets go only through the secret store. `off` keeps the settings.
2. The built-in `http` never follows redirects. A 3xx raises an error that names only the status code, so a key header can never reach a second address. Addresses must be https, or http on a loopback host, and the host must also pass the allowlist below.

## Host allowlist

A key is only ever sent to a host the connector is allowed to talk to. The registry checks this twice: when you turn the connector on {src:scripts/connectors/registry.py:371}, before the key is stored, and on every request the connector makes {src:scripts/connectors/registry.py:231-232}. So editing the connectors file later to point a connector at another host is caught on the next call, and the key is not sent.

Built-in hosts, all on port 443 {src:scripts/connectors/registry.py:108-115} {src:scripts/connectors/registry.py:171-172}:

| Connector | Allowed without any extra step |
|---|---|
| `jira` | `*.atlassian.net`, `*.atlassian.com`, `api.atlassian.com` |
| `slack` | `slack.com`, `*.slack.com` |
| `notion` | `api.notion.com`, `notion.com` (no other subdomain) |
| `databricks` | `*.databricks.com`, `*.azuredatabricks.net`, `*.gcp.databricks.com` |
| `calendar` | `www.googleapis.com`, `calendar.googleapis.com` |
| `plane` | none: Plane has no built-in host, so every Plane host must be approved |
| `git-commits` | not checked, because it makes no network call {src:scripts/connectors/registry.py:116-117} |

A leading `*.` means a real subdomain; the bare suffix does not match {src:scripts/connectors/registry.py:174-176}. IP addresses never match a built-in entry {src:scripts/connectors/registry.py:171}.

For any other host (self-hosted Jira, Plane, a custom Databricks host, a non-standard port), the owner approves it once, in a real terminal:

```
python3 scripts/connectors/connect.py on NAME --address https://HOST --allow-host HOST --key-from-env VAR
```

`HOST` or `HOST:PORT`, with no scheme, path or wildcard {src:scripts/connectors/registry.py:184-192}. The step is refused when there is no terminal, so a script or an assistant cannot do it for you {src:scripts/connectors/connect.py:79-82}. The approval is stored in the connector's entry in the connectors file, under `allowed_hosts` {src:scripts/connectors/registry.py:375-379}. It matches that exact host and port only, and `off` clears it {src:scripts/connectors/registry.py:207} {src:scripts/connectors/registry.py:388}. A refused host prints the exact command to run {src:scripts/connectors/registry.py:209-213}.

**After updating from an earlier version:** if you use self-hosted Jira, Plane or a custom Databricks host, run the `--allow-host` step once for each. Until you do, the connector refuses the host and no key is sent.

