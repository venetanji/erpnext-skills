# `scripts/` — reusable Python/shell helpers

Vetted, reusable automation that the `erpnext` skill references. **Intentionally sparse** —
this skill was built knowledge-first; the planned second pass fills this directory with
helpers proven against a running instance. See [`../CONTRIBUTING.md`](../CONTRIBUTING.md) for
the full workflow, and [`_template.py`](_template.py) for a ready-to-copy skeleton (header
block, dry-run guard, idempotency pre-check, `frappe.init` standalone runner).

## How to run a script

```bash
# Via bench (auto-commits on success):
bench --site <site> execute erpnext.scripts.<name>.run --kwargs '{"dry_run": true}'

# Dockerized:
docker exec -i <backend-container> bench --site <site> \
  execute path.to.<name>.run --kwargs '{"dry_run": true}'

# Standalone (you commit explicitly — see _template.py __main__):
cd /home/frappe/frappe-bench && ./env/bin/python <name>.py <site> --apply
```

Most scripts default to `dry_run=True` — re-run with `dry_run=False` (or `--apply`) to write.

## Registry

Add one row per script when you contribute it. Keep it sorted.

| Script | Reads | Writes | Idempotent | Purpose |
|---|---|---|---|---|
| [`_template.py`](_template.py) | — | — | — | Skeleton to copy; not a real script. |

<!-- second-pass additions go here, e.g.:
| `reconcile_party.py` | Payment Ledger Entry, GL Entry | Journal Entry | yes (pre-checks by party) | Diagnostic + FX-residual cleanup for one counterparty. |
-->

## Candidates for the second pass

Patterns worth turning into scripts (harvest from agent memories per CONTRIBUTING.md):

- **Bulk introspection** — dump a DocType's meta (fields/types/options) + custom fields to
  JSON, to learn a site's actual schema before automating against it.
- **Idempotent upsert-by-business-key** — generic "insert unless a doc with this key exists"
  helper wrapping the Universal Hard Rule #3 pre-check.
- **Report-to-CSV exporter** — run a Query Report via `frappe.desk.query_report.run` and
  write CSV with currency precision applied at source (see the companion repo's
  `export_audit_reports.py` for prior art).
- **Safe cancel-and-amend** — cancel a submittable doc only after checking for downstream
  links, then create the amended sibling.
- **Health check** — list open Fiscal Years, `acc_frozen_upto`, scheduler status, pending
  jobs, and any docs stuck in Draft — a pre-flight an agent can run before bookkeeping work.
