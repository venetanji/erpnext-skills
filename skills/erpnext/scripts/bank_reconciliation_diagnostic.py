#!/usr/bin/env python3
"""Diagnose a bank account whose GL balance disagrees with its statement feed.

For one bank GL account over a date range, compare the *feed* close (opening +
sum of Bank Transaction deposits - withdrawals) against the *GL* close. When the GL
is higher than the feed, the gap is almost always "orphan vouchers": Payment Entries
or Journal Entries that post to the bank account but are NOT linked to any
`Bank Transaction Payments` row (so they inflate the GL without being a real statement
line). The sum of the orphans equals the gap, exactly. Read-only.

USAGE:    bench --site <site> execute erpnext.scripts.bank_reconciliation_diagnostic.run \\
              --kwargs '{"account": "Bank - HSBC - {ABBR}", "from_date": "2017-04-01", "to_date": "2018-03-31", "opening": 77556.28}'
    OR:   docker exec -i <backend-container> bench --site <site> execute path.to.run --kwargs '{...}'
REQUIRES: frappe.init / bench env
READS:    GL Entry, Bank Transaction, Bank Transaction Payments
WRITES:   read-only
IDEMPOTENT: yes (read-only)
VERSION:  tested on ERPNext v16
"""

import frappe


def run(account: str, from_date: str, to_date: str, opening: float = None, **kwargs):
    """Reconcile a bank account's GL against its Bank Transaction feed and list orphans.

    account  : the bank GL account name (e.g. "Bank - HSBC - {ABBR}").
    opening  : GL opening balance at from_date; if omitted it is computed from GL < from_date.
    """
    if opening is None:
        opening = flt(frappe.db.sql(
            "select sum(debit-credit) from `tabGL Entry` where is_cancelled=0 and account=%s and posting_date < %s",
            (account, from_date))[0][0])

    # GL close over the window
    gl_close = opening + flt(frappe.db.sql(
        "select sum(debit-credit) from `tabGL Entry` where is_cancelled=0 and account=%s and posting_date between %s and %s",
        (account, from_date, to_date))[0][0])

    # Feed close: the Bank Transaction rows for this account
    bt = frappe.db.sql("""
        select coalesce(sum(deposit),0) dep, coalesce(sum(withdrawal),0) wd
        from `tabBank Transaction`
        where docstatus=1 and bank_account in (
            select name from `tabBank Account` where account=%s)
          and date between %s and %s""", (account, from_date, to_date), as_dict=True)[0]
    feed_close = opening + flt(bt.dep) - flt(bt.wd)

    # Vouchers posting to the bank account in-window, and which are reconciled
    vouchers = frappe.db.sql("""
        select voucher_type, voucher_no, round(sum(debit-credit),2) net
        from `tabGL Entry`
        where is_cancelled=0 and account=%s and posting_date between %s and %s
        group by voucher_type, voucher_no""", (account, from_date, to_date), as_dict=True)
    reconciled = set(r.payment_entry for r in frappe.db.sql("""
        select btp.payment_entry from `tabBank Transaction Payments` btp
        join `tabBank Transaction` bt on bt.name=btp.parent
        where bt.bank_account in (select name from `tabBank Account` where account=%s)""",
        (account,), as_dict=True))

    orphans = [v for v in vouchers if v.voucher_no not in reconciled]
    orphan_sum = round(sum(flt(v.net) for v in orphans), 2)

    print(f"account        : {account}")
    print(f"opening        : {opening:,.2f}")
    print(f"feed close     : {feed_close:,.2f}   (opening + {flt(bt.dep):,.2f} - {flt(bt.wd):,.2f})")
    print(f"GL close       : {gl_close:,.2f}")
    print(f"GL - feed gap  : {gl_close - feed_close:,.2f}")
    print(f"orphan sum     : {orphan_sum:,.2f}   ({len(orphans)} voucher(s) post to bank but reconcile to no feed line)")
    if abs((gl_close - feed_close) - orphan_sum) < 0.01 and orphans:
        print("  -> the gap IS the orphans. Each is a double/phantom: reconcile it to its real")
        print("     feed Bank Transaction (swapping out any lesser voucher), or cancel a true duplicate.")
    for v in sorted(orphans, key=lambda x: -abs(flt(x.net)))[:50]:
        print(f"    ORPHAN {v.voucher_type:<14} {v.voucher_no:<22} {flt(v.net):>14,.2f}")
    return {"feed_close": feed_close, "gl_close": gl_close,
            "gap": round(gl_close - feed_close, 2), "orphans": [o.voucher_no for o in orphans]}


def flt(x):
    return float(x or 0)


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 5:
        sys.exit("usage: env/bin/python bank_reconciliation_diagnostic.py <site> <account> <from_date> <to_date>")
    frappe.init(site=sys.argv[1]); frappe.connect()
    try:
        run(account=sys.argv[2], from_date=sys.argv[3], to_date=sys.argv[4])
    finally:
        frappe.destroy()
