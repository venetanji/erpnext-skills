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
| [`bank_reconciliation_diagnostic.py`](bank_reconciliation_diagnostic.py) | GL Entry, Bank Transaction, Bank Transaction Payments | read-only | yes (read-only) | For a bank account + date range: feed close vs GL close, and list the *orphan vouchers* (post to the bank but reconcile to no feed line) that equal the gap. |
| [`cancel_and_amend_je.py`](cancel_and_amend_je.py) | Journal Entry, Bank Transaction(+Payments) | Journal Entry, Bank Transaction | yes (skips if marker exists) | Safe cancel + amended re-create of a JE — unreconciles/re-links its Bank Transactions, keeps the FCY rate via `ignore_exchange_rate`, dry-run by default. |

## Candidates for the second pass

Patterns worth turning into scripts (harvest from agent memories per CONTRIBUTING.md):

- **Bulk introspection** — dump a DocType's meta (fields/types/options) + custom fields to
  JSON, to learn a site's actual schema before automating against it.
- **Idempotent upsert-by-business-key** — generic "insert unless a doc with this key exists"
  helper wrapping the Universal Hard Rule #3 pre-check.
- **Report-to-CSV exporter** — run a Query Report via `frappe.desk.query_report.run` and
  write CSV with currency precision applied at source (see the companion repo's
  `export_audit_reports.py` for prior art).
- ~~**Safe cancel-and-amend**~~ — done: [`cancel_and_amend_je.py`](cancel_and_amend_je.py)
  (Journal Entry; generalize to other submittables as a follow-up).
- **Health check** — list open Fiscal Years, `acc_frozen_upto`, scheduler status, pending
  jobs, and any docs stuck in Draft — a pre-flight an agent can run before bookkeeping work.
- **Bank-feed reconstruction** — bulk-import statement rows as Bank Transactions, then
  reconcile oldest-first; pair with [`bank_reconciliation_diagnostic.py`](bank_reconciliation_diagnostic.py)
  to catch orphan vouchers after each pass. (See the companion repo's clean-rebuild runbook.)
- **Catch-up depreciation** — create back-dated/existing Assets (`is_existing_asset`,
  `opening_accumulated_depreciation`) then `post_depreciation_entries("<date>")` to book all
  schedule rows whose date is already past.
