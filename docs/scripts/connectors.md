# Connector framework scripts

Connectors are off until used. These scripts hold the shared parts. The connectors that sit on them are described in `docs/scripts/connectors-plane.md`, `docs/scripts/connectors-comms.md` and `docs/scripts/connectors-data.md`. To write one, read `docs/connectors.md`.

| File | What it does |
|------|--------------|
| `scripts/connectors/registry.py` | `register`, `require`, `ensure`, the on/off state file, settings, and the one place a network client is made {src:scripts/connectors/registry.py:36} {src:scripts/connectors/registry.py:134} {src:scripts/connectors/registry.py:395} {src:scripts/connectors/registry.py:418} |
| `scripts/connectors/secret_store.py` | `SecretStore` (set, get, delete); macOS Keychain, Linux `secret-tool`, an in-memory fake, and a refusing store {src:scripts/connectors/secret_store.py:31} {src:scripts/connectors/secret_store.py:67} {src:scripts/connectors/secret_store.py:97} {src:scripts/connectors/secret_store.py:123} {src:scripts/connectors/secret_store.py:139} |
| `scripts/connectors/connect.py` | `on`, `off`, `status` command {src:scripts/connectors/connect.py:10} {src:scripts/connectors/connect.py:12} {src:scripts/connectors/connect.py:13} |

## Behavior

1. `require(name)` returns the client, or raises `NotSetUp` with `<name>: not set up` and the setup command. It never prompts and never calls the network {src:scripts/connectors/registry.py:395} {src:scripts/connectors/registry.py:396} {src:scripts/connectors/registry.py:399} {src:scripts/connectors/registry.py:325} {src:scripts/connectors/registry.py:326} {src:scripts/connectors/registry.py:327}.
2. `ensure(name)` does the same, but in a terminal it first asks for the address and key (key hidden), saves the key, and turns the connector on. With no terminal it raises `NotSetUp` {src:scripts/connectors/registry.py:418} {src:scripts/connectors/registry.py:423} {src:scripts/connectors/registry.py:424} {src:scripts/connectors/connect.py:30} {src:scripts/connectors/connect.py:43} {src:scripts/connectors/connect.py:44}. Setting `TOLLGATE_NONINTERACTIVE=1` counts as no terminal {src:scripts/connectors/registry.py:410} {src:scripts/connectors/registry.py:411}.
3. The state file (`TOLLGATE_CONNECTORS`) holds JSON with name, address, on/off and settings. Never a key {src:scripts/connectors/registry.py:10} {src:scripts/connectors/registry.py:11} {src:scripts/connectors/registry.py:264} {src:scripts/connectors/registry.py:312}. Without that variable every call raises `NotSetUp` {src:scripts/connectors/registry.py:265} {src:scripts/connectors/registry.py:266}.
4. The Keychain store sends its command on stdin (`security -i`), so the key is never in a process list. The Linux store sends the key on stdin. With neither tool, setup refuses. No plain-file fallback {src:scripts/connectors/secret_store.py:76} {src:scripts/connectors/secret_store.py:79} {src:scripts/connectors/secret_store.py:105} {src:scripts/connectors/secret_store.py:106} {src:scripts/connectors/secret_store.py:142} {src:scripts/connectors/secret_store.py:143} {src:scripts/connectors/secret_store.py:162}.
5. Turning on saves the key first and writes the state file second, so a failed save leaves the connector off {src:scripts/connectors/registry.py:372} {src:scripts/connectors/registry.py:380}.
6. `off` marks the connector off and deletes its key {src:scripts/connectors/registry.py:383} {src:scripts/connectors/registry.py:387} {src:scripts/connectors/registry.py:390}.
7. A Keychain key cannot contain a quote, backslash or line break. The store refuses those with a clear message {src:scripts/connectors/secret_store.py:72} {src:scripts/connectors/secret_store.py:73} {src:scripts/connectors/secret_store.py:74}.
8. An address with a user name or password in it is refused before anything is saved, and the error never repeats the address {src:scripts/connectors/registry.py:73} {src:scripts/connectors/registry.py:82} {src:scripts/connectors/registry.py:367}.

## Setting the key without a terminal

`connect.py on NAME --address URL --key-stdin` reads the key from stdin. `--key-from-env VAR` reads it from an environment variable instead. The two cannot be combined {src:scripts/connectors/connect.py:142} {src:scripts/connectors/connect.py:143} {src:scripts/connectors/connect.py:144} {src:scripts/connectors/connect.py:55} {src:scripts/connectors/connect.py:61}. With neither flag and no terminal it stops and says what to pass {src:scripts/connectors/connect.py:87} {src:scripts/connectors/connect.py:88} {src:scripts/connectors/connect.py:89}. `status [NAME]` prints on, off or not set up, and exits 1 for a named connector that is not on {src:scripts/connectors/connect.py:111} {src:scripts/connectors/connect.py:124} {src:scripts/connectors/connect.py:130} {src:scripts/connectors/connect.py:131}.

## Settings and redirects

9. Each entry may hold a `settings` object (plain values only). `get_settings` and `set_settings` read and write it; `connect.py on NAME --set KEY=VALUE` sets it; `status NAME` prints it. Names with key, token, secret or password are refused and nothing is written. `off` keeps the settings. CON-05 and CON-06 test this {src:scripts/connectors/registry.py:330} {src:scripts/connectors/registry.py:339} {src:scripts/connectors/registry.py:342} {src:scripts/connectors/registry.py:351} {src:scripts/connectors/registry.py:355} {src:scripts/connectors/connect.py:141} {src:scripts/connectors/connect.py:125} {src:scripts/connectors/registry.py:386}.
10. `UrlHttp` refuses redirects (the error shows the status code only) and allows only https or loopback http. Tests use a loopback stub server {src:scripts/connectors/registry.py:64} {src:scripts/connectors/registry.py:92} {src:scripts/connectors/registry.py:96} {src:scripts/connectors/registry.py:98} {src:scripts/connectors/registry.py:216} {src:scripts/connectors/registry.py:241} {src:scripts/connectors/registry.py:242}.
11. A connector's command line should end in `run_cli(main)`: it prints a `NotSetUp` message cleanly and exits 2 {src:scripts/connectors/registry.py:430} {src:scripts/connectors/registry.py:434} {src:scripts/connectors/registry.py:435} {src:scripts/connectors/registry.py:436}.

## Tests

`tests/scripts/connectors/run.sh`. CON-01 to CON-04 cover not set up, first use, restart, and off. The fake connector is in `tests/scripts/connectors/fake_connector.py` and is a model for new connectors.
