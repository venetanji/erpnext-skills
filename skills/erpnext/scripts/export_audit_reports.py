#!/usr/bin/env python3
"""Export the standard year-end audit-pack reports (Trial Balance, Balance Sheet,
Profit and Loss, Accounts Receivable, General Ledger) as CSV — with currency-typed
columns rounded at source so the GL running-balance column doesn't ship as
`-8.53e-13` float-drift noise to the auditor.

USAGE:    bench --site <site> execute erpnext.scripts.export_audit_reports.run \\
              --kwargs '{"company":"{COMPANY_NAME}","fiscal_year":"2025","out_dir":"/tmp/audit_fy2025"}'
    OR:   docker exec -i <backend-container> bash -c "cd /home/frappe/frappe-bench/sites && \\
              ../env/bin/python /path/to/export_audit_reports.py --site <site> \\
              --company '{COMPANY_NAME}' --fiscal-year 2025 --out /tmp/audit_fy2025"

REQUIRES:   bench env (frappe + erpnext installed)
READS:      Trial Balance, Balance Sheet, Profit and Loss Statement, Accounts Receivable,
            General Ledger query reports; System Settings (currency_precision).
WRITES:     read-only as far as the DB is concerned. Writes CSV files to `out_dir`.
IDEMPOTENT: yes — re-running overwrites the CSVs deterministically.
VERSION:    tested on ERPNext v16.

Background:
- `frappe.desk.query_report.run()` returns raw floats. The General Ledger report sums
  hundreds of rows for the running-balance column; floating-point drift accumulates to
  ~1e-13 per row and serialises as exponential-notation cells. The ERPNext UI's built-in
  CSV export sidesteps this by formatting each numeric cell via
  `frappe.utils.flt(value, precision)` — same call this script makes here.
- Balance Sheet needs `filter_based_on: Fiscal Year` + `accumulated_values: 1` to produce
  *closing balances*. The default flow shows period activity only and bank/cash numbers
  won't reconcile to GL — looks broken but isn't, just the wrong report mode. P&L is the
  inverse: `accumulated_values: 0`.
"""
import argparse
import csv
import json
import os
import sys

import frappe
from frappe.desk.query_report import run as run_query_report
from frappe.utils import flt


NUMERIC_FIELDTYPES = {"Currency", "Float", "Int", "Percent"}


_currency_precision_cache = None


def get_currency_precision():
    global _currency_precision_cache
    if _currency_precision_cache is None:
        _currency_precision_cache = int(
            frappe.db.get_default("currency_precision")
            or frappe.db.get_single_value("System Settings", "currency_precision")
            or 2
        )
    return _currency_precision_cache


def column_meta(col):
    """Return (label, fieldname, fieldtype, precision) for one query-report column.

    Query reports return columns as either dicts or `"Label:Fieldtype:Width"` strings.
    """
    if isinstance(col, dict):
        return (
            col.get("label") or col.get("fieldname") or "",
            col.get("fieldname") or col.get("label"),
            col.get("fieldtype") or "Data",
            col.get("precision"),
        )
    parts = col.split(":")
    label = parts[0] if parts else ""
    fieldtype = parts[1] if len(parts) > 1 and parts[1] else "Data"
    return (label, label, fieldtype, None)


def format_cell(value, fieldtype, precision):
    if value in (None, ""):
        return ""
    if fieldtype in NUMERIC_FIELDTYPES:
        prec = precision or get_currency_precision()
        try:
            return f"{flt(value, prec):.{prec}f}"
        except (TypeError, ValueError):
            return str(value)
    return str(value)


def write_report(report_name, filters, out_path):
    res = run_query_report(report_name, json.dumps(filters))
    columns = res.get("columns", [])
    rows = res.get("result", [])

    meta = [column_meta(c) for c in columns]
    headers = [m[0] for m in meta]
    fieldnames = [m[1] for m in meta]

    with open(out_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(headers)
        for r in rows:
            if isinstance(r, dict):
                vals = [r.get(fn, "") for fn in fieldnames]
            elif isinstance(r, list):
                vals = list(r) + [""] * (len(meta) - len(r))
            else:
                vals = [r] + [""] * (len(meta) - 1)
            w.writerow([format_cell(v, m[2], m[3]) for v, m in zip(vals, meta)])
    print(f"  wrote {out_path} ({len(rows)} rows)")


def _build_filters(company, fiscal_year, presentation_currency):
    from_date = f"{fiscal_year}-01-01"
    to_date = f"{fiscal_year}-12-31"

    tb_filters = {
        "company": company,
        "from_date": from_date, "to_date": to_date,
        "fiscal_year": fiscal_year,
        "filter_based_on": "Date Range",
        "periodicity": "Yearly",
        "presentation_currency": presentation_currency,
        "with_period_closing_entry_for_opening": 1,
        "show_net_values_in_party_account": 0,
    }
    fs_filters = {
        "company": company,
        "filter_based_on": "Fiscal Year",
        "from_fiscal_year": fiscal_year, "to_fiscal_year": fiscal_year,
        "period_start_date": from_date, "period_end_date": to_date,
        "periodicity": "Yearly",
        "presentation_currency": presentation_currency,
        "accumulated_values": 1,
    }
    pl_filters = {**fs_filters, "accumulated_values": 0}
    ar_filters = {
        "company": company,
        "report_date": to_date,
        "ageing_based_on": "Posting Date",
        "range1": 30, "range2": 60, "range3": 90, "range4": 120,
        "show_future_payments": 0, "based_on_payment_terms": 0,
    }
    gl_filters = {
        "company": company,
        "from_date": from_date, "to_date": to_date,
        "include_dimensions": 1,
        "show_opening_entries": 0,
        "include_default_book_entries": 1,
        "categorize_by": "Categorize by Voucher (Consolidated)",
        "group_by": "Group by Voucher (Consolidated)",
        "presentation_currency": presentation_currency,
    }
    return [
        ("Trial Balance",              tb_filters, f"Trial_Balance_FY{fiscal_year}.csv"),
        ("Balance Sheet",              fs_filters, f"Balance_Sheet_FY{fiscal_year}.csv"),
        ("Profit and Loss Statement",  pl_filters, f"Profit_and_Loss_Statement_FY{fiscal_year}.csv"),
        ("Accounts Receivable",        ar_filters, f"Accounts_Receivable_FY{fiscal_year}.csv"),
        ("General Ledger",             gl_filters, f"General_Ledger_FY{fiscal_year}.csv"),
    ]


def run(company, fiscal_year, out_dir, presentation_currency=None, dry_run=False):
    """Bench-execute entry point. ``presentation_currency`` defaults to the company's base.

    `dry_run=True` lists the reports it would emit without actually writing them.
    """
    if presentation_currency is None:
        presentation_currency = frappe.get_cached_value("Company", company, "default_currency")
        if not presentation_currency:
            frappe.throw(f"Company {company!r} not found or has no default_currency")

    jobs = _build_filters(company, str(fiscal_year), presentation_currency)

    if dry_run:
        for name, filters, fname in jobs:
            print(f"[DRY RUN] would emit {os.path.join(out_dir, fname)} ({name})")
        print(f"[DRY RUN] {len(jobs)} report(s) — re-run with dry_run=False to write.")
        return {"dry_run": True, "planned": len(jobs)}

    os.makedirs(out_dir, exist_ok=True)
    for name, filters, fname in jobs:
        print(f"{name}...")
        write_report(name, filters, os.path.join(out_dir, fname))
    return {"written": len(jobs), "out_dir": out_dir}


def _main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--site", required=True)
    ap.add_argument("--company", required=True)
    ap.add_argument("--fiscal-year", required=True)
    ap.add_argument("--out", required=True, help="output directory")
    ap.add_argument("--presentation-currency", default=None,
                    help="default: company's default_currency")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    frappe.init(site=args.site)
    frappe.connect()
    try:
        run(args.company, args.fiscal_year, args.out,
            presentation_currency=args.presentation_currency,
            dry_run=args.dry_run)
        frappe.db.commit()
    except Exception:
        frappe.db.rollback()
        raise
    finally:
        frappe.destroy()


if __name__ == "__main__":
    _main()
