#!/usr/bin/env python3
# Author: Dipen Patel (dipenpatel-dev)
# Date:
# Scope: Generate 100-folder fixture vault for timing test
# Ticket: none
# ChangeLog: initial

from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
VAULT_DIR = SCRIPT_DIR / "vault_100" / "02-tickets"

TEMPLATE = """\
---
ticket_id: {ticket_id}
status: OPEN
type: feature
---
"""


def main() -> None:
    VAULT_DIR.mkdir(parents=True, exist_ok=True)
    for n in range(1001, 1101):
        ticket_id = f"S-{n}"
        ticket_dir = VAULT_DIR / ticket_id
        ticket_dir.mkdir(exist_ok=True)
        state_file = ticket_dir / f"{ticket_id}-state.md"
        state_file.write_text(TEMPLATE.format(ticket_id=ticket_id), encoding="utf-8")
    print(f"Generated 100 ticket folders in {VAULT_DIR}")


if __name__ == "__main__":
    main()
