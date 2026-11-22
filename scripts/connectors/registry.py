#!/usr/bin/env python3
"""Connector registry: register, require, ensure, and the on/off state file.

Author: Dipen Patel (dipenpatel-dev)
Date:
Purpose: A connector is off until a user tries to use it.
Change log:
  - First version.

State lives in the file named by TOLLGATE_CONNECTORS. It holds names,
addresses and on/off only, never a key. Keys live in the secret store.
Every network call goes through the `http` object built by `get_http()`,
and that object is only handed out once a connector is on.
"""
import ipaddress
import json
import os
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
try:
    from core.paths import NotSetUp
except ImportError:  # contract stub until core/paths.py exists
    class NotSetUp(Exception):
        pass

from connectors.secret_store import default_store, check_name

_FACTORIES = {}
_http_factory = None
_store = None


def register(name, factory):
    """Register a connector. factory(address, key, http) returns a client."""
    _FACTORIES[name] = factory


def registered():
    return sorted(_FACTORIES)


def set_store(store):
    """Use this secret store instead of the default (tests, or a custom one)."""
    global _store
    _store = store


def get_store():
    global _store
    if _store is None:
        _store = default_store()
    return _store


def set_http_factory(factory):
    """Replace how `http` is built (tests pass a mock client factory)."""
    global _http_factory
    _http_factory = factory


class RedirectRefused(Exception):
    pass


class _NoRedirect(__import__("urllib.request").request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None  # never follow; the 3xx surfaces as an HTTPError


def check_no_credentials(url):
    """Refuse an address with a user name or password in it.

    The error never repeats any part of the address, so a password in it is
    not printed or logged.
    """
    from urllib.parse import urlparse
    try:
        u = urlparse(url)
        has_login = u.username is not None or u.password is not None or "@" in u.netloc
    except ValueError:
        has_login = False
    if has_login:
        raise ValueError("address must not contain a user name or password; "
                         "keys go only through the secret store "
                         "(connect.py on NAME --key-stdin)")


def check_address(url):
    """Allow https anywhere, or http only to a loopback host."""
    from urllib.parse import urlparse
    check_no_credentials(url)
    u = urlparse(url)
    if u.scheme == "https" and u.hostname:
        return
    if u.scheme == "http" and u.hostname in ("127.0.0.1", "localhost", "::1"):
        return
    raise ValueError("address must be https, or http on a loopback host")


# ---- host allowlist ----
#
# A key is only ever sent to a host on the built-in list for that connector,
# or to a host the owner recorded with `connect.py on NAME --allow-host HOST`
# (state file, field allowed_hosts). A leading dot means any subdomain.
BUILTIN_HOSTS = {
    "jira": (".atlassian.net", ".atlassian.com", "api.atlassian.com"),
    "slack": ("slack.com", ".slack.com"),
    "notion": ("api.notion.com", "notion.com"),
    "databricks": (".databricks.com", ".azuredatabricks.net",
                   ".gcp.databricks.com"),
    "calendar": ("www.googleapis.com", "calendar.googleapis.com"),
}
# Connectors that never make a network call (the address is a folder).
LOCAL_ONLY = ("git-commits",)

_LABEL = r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
_HOSTNAME_RE = re.compile(r"^%s(?:\.%s)*$" % (_LABEL, _LABEL))


class HostRefused(ValueError):
    pass


def _host_key(host, port):
    return host if port == 443 else "%s:%d" % (host, port)


def parse_host(url):
    """Return (host, port) from an https or loopback-http address, or refuse.

    Refuses a login, a trailing dot, odd characters, and anything urllib
    reads differently from a browser. The host is lowercased.
    """
    from urllib.parse import urlparse
    if not isinstance(url, str) or any(c.isspace() or ord(c) < 33 or ord(c) > 126
                                       for c in url):
        raise HostRefused("address has spaces or unusual characters")
    check_no_credentials(url)
    check_address(url)
    u = urlparse(url)
    if "\\" in u.netloc:
        raise HostRefused("address has a backslash in the host")
    try:
        host, port = u.hostname, u.port
    except ValueError:
        raise HostRefused("address has an invalid port") from None
    if not host or host.endswith("."):
        raise HostRefused("address host is empty or ends with a dot")
    if port is None:
        port = 443 if u.scheme == "https" else 80
    try:
        ipaddress.ip_address(host)
    except ValueError:
        if not _HOSTNAME_RE.match(host):
            raise HostRefused("address host has invalid characters") from None
    return host, port


def _is_ip(host):
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return False


def _builtin_match(name, host, port):
    if port != 443 or _is_ip(host):
        return False
    for pat in BUILTIN_HOSTS.get(name, ()):
        if pat.startswith("."):
            if host.endswith(pat) and len(host) > len(pat):
                return True
        elif host == pat:
            return True
    return False


def normalize_allowed_host(text):
    """Turn `HOST` or `HOST:PORT` into the stored form, or refuse."""
    t = text.strip().lower() if isinstance(text, str) else ""
    host, sep, port = t.rpartition(":") if t.count(":") == 1 else (t, "", "")
    if not sep:
        host, port = t, "443"
    if (not port.isdigit() or not 0 < int(port) < 65536
            or "[" in host or "]" in host or host.endswith(".")
            or not (_HOSTNAME_RE.match(host) or _is_ip(host))):
        raise ValueError("--allow-host needs a plain host name or HOST:PORT "
                         "(no scheme, path, wildcard or trailing dot)")
    return _host_key(host, int(port))


def recorded_hosts(name, env=None):
    return list(load_state(env).get(name, {}).get("allowed_hosts") or [])


def check_host(name, url, env=None, extra=()):
    """Refuse a connector address whose host is neither built in nor recorded."""
    if name in LOCAL_ONLY:
        return
    host, port = parse_host(url)
    if _builtin_match(name, host, port):
        return
    if _host_key(host, port) in set(recorded_hosts(name, env)) | set(extra):
        return
    raise HostRefused(
        "%s: this host is not on the allowed list, so the key is not sent. "
        "If you trust it, run this yourself in a terminal: python3 "
        "$TOLLGATE_HOME/scripts/connectors/connect.py on %s --allow-host %s"
        % (name, name, _host_key(host, port)))


class UrlHttp:
    """Small real client built on urllib. Only built once a connector is on.

    It never follows redirects, so a key header is never sent to a second
    address. A 3xx raises RedirectRefused naming only the status code.
    Built for a connector name, it also checks the host on every request.
    """

    def __init__(self, name=None, env=None):
        self.name, self.env = name, env

    def request(self, method, url, headers=None, data=None, timeout=30):
        import urllib.error
        import urllib.request
        check_address(url)
        if self.name:
            check_host(self.name, url, self.env)
        body = data.encode() if isinstance(data, str) else data
        req = urllib.request.Request(url, data=body, method=method,
                                     headers=headers or {})
        opener = urllib.request.build_opener(_NoRedirect)
        try:
            with opener.open(req, timeout=timeout) as resp:
                return {"status": resp.status, "body": resp.read().decode()}
        except urllib.error.HTTPError as e:
            if 300 <= e.code < 400:
                raise RedirectRefused(
                    "HTTP %d: the server answered with a redirect; Tollgate "
                    "does not follow redirects. Check the connector address."
                    % e.code) from None
            raise

    def get(self, url, **kw):
        return self.request("GET", url, **kw)

    def post(self, url, **kw):
        return self.request("POST", url, **kw)


def get_http(name=None, env=None):
    """The one place a network client is made."""
    return _http_factory() if _http_factory else UrlHttp(name, env)


# ---- state file ----

def state_path(env=None):
    env = os.environ if env is None else env
    p = env.get("TOLLGATE_CONNECTORS")
    if not p:
        raise NotSetUp("TOLLGATE_CONNECTORS is not set; run the Tollgate "
                       "installer so it points at a connectors file")
    return pathlib.Path(os.path.expanduser(p))


def load_state(env=None):
    p = state_path(env)
    try:
        data = json.loads(p.read_text())
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    return _clean_entries(data)


def _clean_entries(data):
    """A hand-edited file may hold anything. Keep only well-formed entries.

    An entry that is not a map is dropped (the connector reads as not set up).
    A wrong-typed field is made safe: `on` is true only for the JSON value
    true, an address that is not text becomes empty, settings that are not a
    map are ignored.
    """
    clean = {}
    for name, e in data.items():
        if not isinstance(name, str) or not isinstance(e, dict):
            continue
        item = {"address": e["address"] if isinstance(e.get("address"), str) else "",
                "on": e.get("on") is True}
        if isinstance(e.get("settings"), dict) and e["settings"]:
            item["settings"] = e["settings"]
        hosts = e.get("allowed_hosts")
        if isinstance(hosts, list):
            ok = [h for h in hosts if isinstance(h, str) and h]
            if ok:
                item["allowed_hosts"] = ok
        clean[name] = item
    return clean


def save_state(state, env=None):
    p = state_path(env)
    p.parent.mkdir(parents=True, exist_ok=True)
    clean = {}
    for n, e in state.items():
        item = {"address": e.get("address", ""), "on": bool(e.get("on"))}
        if e.get("settings"):
            item["settings"] = e["settings"]
        if e.get("allowed_hosts"):
            item["allowed_hosts"] = list(e["allowed_hosts"])
        clean[n] = item
    p.write_text(json.dumps(clean, indent=2, sort_keys=True) + "\n")


def is_on(name, env=None):
    return bool(load_state(env).get(name, {}).get("on"))


def how_to_set_up(name):
    return ("%s: not set up\nTo set it up, run: python3 "
            "$TOLLGATE_HOME/scripts/connectors/connect.py on %s" % (name, name))


SECRET_WORDS = ("key", "token", "secret", "password")


def _plain(v):
    if isinstance(v, (str, int, float, bool)):
        return True
    return isinstance(v, list) and all(_plain(i) for i in v)


def check_settings(mapping):
    """Refuse secret-looking names and non-plain values. Writes nothing."""
    for k, v in mapping.items():
        if any(w in str(k).lower() for w in SECRET_WORDS):
            raise ValueError(
                "setting '%s' looks like a secret; secrets go only through "
                "the secret store (connect.py on NAME --key-stdin)" % k)
        if not _plain(v):
            raise ValueError("setting '%s' must be a string, number, boolean "
                             "or a list of those" % k)


def get_settings(name, env=None):
    return dict(load_state(env).get(name, {}).get("settings") or {})


def set_settings(name, mapping, env=None):
    check_settings(mapping)
    state = load_state(env)
    entry = state.setdefault(name, {"address": "", "on": False})
    merged = dict(entry.get("settings") or {})
    merged.update(mapping)
    entry["settings"] = merged
    save_state(state, env)


def turn_on(name, address, key, env=None, settings=None, allow_hosts=None):
    check_name(name)                    # before anything reaches the secret store
    check_no_credentials(address)       # before the key or state is written
    if settings:
        check_settings(settings)
    extra = [normalize_allowed_host(h) for h in allow_hosts or []]
    check_host(name, address, env, extra)   # before the key is stored
    get_store().set(name, key)          # key first; state only after it saved
    state = load_state(env)
    old = (state.get(name) or {}).get("settings") or {}
    hosts = sorted(set(((state.get(name) or {}).get("allowed_hosts") or []) + extra))
    state[name] = {"address": address, "on": True,
                   "settings": dict(old, **(settings or {}))}
    if hosts:
        state[name]["allowed_hosts"] = hosts
    save_state(state, env)


def turn_off(name, env=None):
    check_name(name)
    state = load_state(env)
    if name in state:
        state[name]["on"] = False
        state[name].pop("allowed_hosts", None)   # approvals end with the key
        save_state(state, env)
    get_store().delete(name)


# ---- use ----

def require(name, env=None):
    """Return the configured client, or raise NotSetUp. Never prompts."""
    entry = load_state(env).get(name)
    if not entry or not entry.get("on"):
        raise NotSetUp(how_to_set_up(name))
    if name not in _FACTORIES:
        raise NotSetUp("%s: no connector module is loaded for this name" % name)
    key = get_store().get(name)
    if not key:
        raise NotSetUp(how_to_set_up(name))
    return _FACTORIES[name](entry.get("address", ""), key, get_http(name, env))


def interactive(env=None):
    env = os.environ if env is None else env
    if env.get("TOLLGATE_NONINTERACTIVE") == "1":
        return False
    try:
        return sys.stdin.isatty() and sys.stdout.isatty()
    except Exception:
        return False


def ensure(name, env=None, prompt=None):
    """require(), but run the first-use flow first when in a terminal."""
    try:
        return require(name, env)
    except NotSetUp:
        if not interactive(env):
            raise
    from connectors import connect
    connect.first_use(name, env=env, prompt=prompt)
    return require(name, env)


def run_cli(main):
    """Run a connector's main(); print NotSetUp cleanly and exit non-zero."""
    try:
        return main()
    except NotSetUp as e:
        print(str(e), file=sys.stderr)
        sys.exit(2)
