#!/usr/bin/env python3
"""Read-only pre-flight for an ERPNext site before bookkeeping / close work.

Surfaces the conditions that silently break common write paths:
- which Fiscal Years are open and which date falls in which
- Accounts Settings: `allow_stale`, `stale_days`, `allow_pegged_currencies_exchange_rates`,
  `exchange_gain_loss_posting_date`
- Per-Company freeze settings: `accounts_frozen_till_date` + `role_allowed_for_frozen_entries`
  (v16; earlier versions kept these on Accounts Settings as `acc_frozen_upto` +
  `frozen_accounts_modifier` — the script probes both locations)
- Company defaults: `default_currency`, `reporting_currency`
  (a blank `reporting_currency` produces the misleading "Unable to find exchange rate for
  {base} to None" error on every GL Entry validate — see accounting.md Gotcha #8)
- Currency Exchange Settings: on-demand-fetcher provider + `disabled` flag
- Scheduler status + pending job counts per queue
- Period Closing Voucher chain + per-PCV Account Closing Balance row count
  (a broken ACB chain causes Balance Sheet openings to disagree with the GL — see
  accounting.md Gotcha #9)
- Draft submittable docs by DocType (transactions left mid-flight)

USAGE:    bench --site <site> execute erpnext.scripts.health_check.run \\
              --kwargs '{"company":"{COMPANY_NAME}"}'
    OR:   docker exec -i <backend-container> bench --site <site> \\
              execute path.to.health_check.run --kwargs '{"company":"{COMPANY_NAME}"}'

REQUIRES:   bench env (frappe + erpnext installed)
READS:      Fiscal Year, Accounts Settings, Company, Currency Exchange Settings,
            Period Closing Voucher, Account Closing Balance, GL Entry, RQ queues.
WRITES:     read-only — never inserts, updates, or deletes anything.
IDEMPOTENT: trivially — no side effects.
VERSION:    tested on ERPNext v16. The Fiscal Year, Account Closing Balance, and
            Period Closing Voucher DocTypes exist back to v14.
"""
from collections import defaultdict
from datetime import date

import frappe


SUBMITTABLE_TRANSACTION_DOCTYPES = (
    "Sales Invoice", "Purchase Invoice", "Payment Entry", "Journal Entry",
    "Sales Order", "Purchase Order", "Delivery Note", "Purchase Receipt",
    "Stock Entry",
)


def _print_heading(label):
    print(f"\n=== {label} ===")


def _check_fiscal_years(today):
    """Open FYs and which one (if any) covers `today`."""
    _print_heading("Fiscal Years")
    rows = frappe.db.get_all(
        "Fiscal Year",
        fields=["name", "year_start_date", "year_end_date", "disabled"],
        order_by="year_start_date",
    )
    if not rows:
        print("  (no Fiscal Year configured — postings will fail)")
        return
    covering = None
    for r in rows:
        flags = []
        if r.disabled:
            flags.append("DISABLED")
        if r.year_start_date <= today <= r.year_end_date:
            flags.append("CURRENT")
            if not r.disabled:
                covering = r.name
        flag_str = f"  [{', '.join(flags)}]" if flags else ""
        print(f"  {r.name:>12}  {r.year_start_date}  →  {r.year_end_date}{flag_str}")
    if not covering:
        print(f"  ⚠ today ({today}) is not inside any enabled Fiscal Year")


def _meta_has_field(doctype, fieldname):
    try:
        meta = frappe.get_meta(doctype)
    except Exception:
        return False
    return bool(meta.get_field(fieldname))


def _check_accounts_settings():
    _print_heading("Accounts Settings (FX policy + universal flags)")
    fx_fields = [
        "allow_stale", "stale_days", "allow_pegged_currencies_exchange_rates",
        "exchange_gain_loss_posting_date", "book_deferred_entries_via_journal_entry",
        # Older v14/v15 freeze fields — printed only if they exist on this version.
        "acc_frozen_upto", "frozen_accounts_modifier",
    ]
    for f in fx_fields:
        if not _meta_has_field("Accounts Settings", f):
            continue
        v = frappe.db.get_single_value("Accounts Settings", f)
        print(f"  {f:>42} = {v!r}")


def _check_companies(want_company):
    _print_heading("Company defaults + per-company freeze (v16)")
    filters = {"name": want_company} if want_company else None
    base_fields = ["name", "default_currency", "country", "abbr"]
    optional = ["reporting_currency", "accounts_frozen_till_date",
                "role_allowed_for_frozen_entries"]
    fields = base_fields + [f for f in optional if _meta_has_field("Company", f)]
    rows = frappe.db.get_all("Company", fields=fields, filters=filters)
    if not rows:
        print(f"  (no Company found{' matching ' + repr(want_company) if want_company else ''})")
        return
    for r in rows:
        rep = r.get("reporting_currency")
        flag = ""
        if "reporting_currency" in fields:
            if not rep:
                flag = "  ⚠ blank reporting_currency — GL Entry validate will throw \"Unable to find exchange rate for X to None\""
            elif rep != r.default_currency:
                flag = "  (reporting_currency differs from default_currency — intentional?)"
        print(f"  {r.name}  default={r.default_currency}  reporting={rep or '∅'}  "
              f"({r.country}, abbr={r.abbr}){flag}")
        frozen = r.get("accounts_frozen_till_date")
        if "accounts_frozen_till_date" in fields:
            modifier = r.get("role_allowed_for_frozen_entries") or "∅"
            flag2 = "  ⚠ postings on/before this date blocked unless caller holds modifier role" if frozen else ""
            print(f"    frozen_till={frozen or '∅'}  modifier_role={modifier}{flag2}")


def _check_currency_exchange_settings():
    _print_heading("Currency Exchange Settings (on-demand fetcher)")
    if not frappe.db.exists("DocType", "Currency Exchange Settings"):
        print("  (Currency Exchange Settings doctype not present)")
        return
    for f in ("disabled", "service_provider", "api_endpoint", "result_key"):
        if _meta_has_field("Currency Exchange Settings", f):
            print(f"  {f:>42} = {frappe.db.get_single_value('Currency Exchange Settings', f)!r}")


def _check_scheduler():
    _print_heading("Scheduler & queues")
    try:
        from frappe.utils.scheduler import is_scheduler_inactive
        inactive = is_scheduler_inactive(verbose=False)
        print(f"  scheduler inactive? {inactive}")
    except Exception as e:
        print(f"  scheduler probe failed: {e}")

    try:
        from frappe.utils.background_jobs import get_queue, get_queue_list
        for q in get_queue_list():
            try:
                queue = get_queue(q)
                print(f"  queue {q:>8}: {queue.count} job(s) waiting")
            except Exception as e:
                print(f"  queue {q:>8}: probe failed ({e})")
    except Exception as e:
        print(f"  queue probe failed: {e}")


def _check_pcv_acb_chain(company):
    """Per-PCV ACB row counts — zero rows under a submitted PCV = broken chain."""
    _print_heading("Period Closing Voucher → Account Closing Balance chain")
    pcv_rows = frappe.db.get_all(
        "Period Closing Voucher",
        filters={"company": company, "docstatus": 1} if company else {"docstatus": 1},
        fields=["name", "fiscal_year", "period_end_date", "company"],
        order_by="period_end_date",
    )
    if not pcv_rows:
        print("  (no submitted Period Closing Vouchers)")
        return
    acb_counts = dict(
        frappe.db.sql(
            """SELECT period_closing_voucher, COUNT(*)
               FROM `tabAccount Closing Balance`
               GROUP BY period_closing_voucher"""
        )
    )
    broken = []
    for pcv in pcv_rows:
        n = int(acb_counts.get(pcv.name, 0))
        flag = ""
        if n == 0:
            flag = "  ⚠ ZERO ACB rows — Balance Sheet openings for downstream FYs will be wrong"
            broken.append(pcv.name)
        print(f"  {pcv.name:>32}  FY {pcv.fiscal_year}  end={pcv.period_end_date}  ACB rows={n}{flag}")
    if broken:
        print(f"  → broken chain: backfill ACB for {len(broken)} PCV(s) in chronological order")
        print("     (see accounting.md Gotcha #9 — call `make_closing_entries` per PCV)")


def _check_draft_transactions(company):
    """Submittable transaction docs left as Draft — usually mid-flight work."""
    _print_heading("Draft submittable transactions (top 10 by recency per DocType)")
    base_filters = {"docstatus": 0}
    if company:
        base_filters["company"] = company
    for dt in SUBMITTABLE_TRANSACTION_DOCTYPES:
        try:
            count = frappe.db.count(dt, filters=base_filters)
        except Exception as e:
            print(f"  {dt:>20}: probe failed ({e})")
            continue
        if not count:
            continue
        recent = frappe.db.get_all(
            dt, filters=base_filters,
            fields=["name", "modified"],
            order_by="modified desc", limit=3,
        )
        recent_str = ", ".join(f"{r.name} ({r.modified.date()})" for r in recent)
        print(f"  {dt:>20}: {count} Draft → recent: {recent_str}")


def run(company=None):
    """Run the pre-flight against the connected site.

    Pass `company` to scope Company/PCV/Draft probes to a single company. Bench-execute
    will return the connected site context with frappe already initialised + connected;
    no commit is needed — this script never writes.
    """
    today = date.today()
    print(f"ERPNext health check — site={frappe.local.site}, today={today}")
    if company:
        print(f"scope: company={company!r}")

    _check_fiscal_years(today)
    _check_accounts_settings()
    _check_companies(company)
    _check_currency_exchange_settings()
    _check_scheduler()
    _check_pcv_acb_chain(company)
    _check_draft_transactions(company)
    print()


if __name__ == "__main__":
    import sys
    site = sys.argv[1] if len(sys.argv) > 1 else None
    if not site:
        sys.exit("usage: env/bin/python health_check.py <site> [<company>]")
    company = sys.argv[2] if len(sys.argv) > 2 else None
    frappe.init(site=site)
    frappe.connect()
    try:
        run(company=company)
    finally:
        frappe.destroy()
