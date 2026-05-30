#!/usr/bin/env python3
"""Cancel a submitted Journal Entry and re-create an amended copy — safely.

Use when a posted JE has a wrong contra account / amount and you must AMEND the original
(audit-clean) rather than post a separate reversal JE. Handles the traps that bite a naive
cancel+copy: bank-reconciliation links, the multi-currency `exchange_rate==1` refetch, and
the stale-doc TimestampMismatchError. Defaults to dry_run.

Steps: (1) unreconcile any Bank Transactions linked to the JE (remove the child row + save);
(2) reload + cancel the original; (3) copy_doc, apply `swap_accounts` + `set_fields`;
(4) insert+submit with `flags.ignore_exchange_rate` so FCY lines keep their rate;
(5) re-link the same Bank Transactions to the new JE.

USAGE:    bench --site <site> execute erpnext.scripts.cancel_and_amend_je.run --kwargs \\
              '{"je": "<JE-NAME>", "swap_accounts": [["<Wrong Account> - {ABBR}", "<Right Account> - {ABBR}"]], "set_fields": {"user_remark": "amended: contra corrected"}, "dry_run": false}'
REQUIRES: frappe.init / bench env
READS:    Journal Entry, Bank Transaction, Bank Transaction Payments
WRITES:   Journal Entry (cancel + create), Bank Transaction (re-link)
IDEMPOTENT: yes — skips if an amended JE with the same `marker` cheque_no already exists
VERSION:  tested on ERPNext v16
"""

import frappe


def run(je: str, swap_accounts=None, set_fields=None, reconcile: bool = True,
        marker: str = None, dry_run: bool = True, **kwargs):
    swap_accounts = swap_accounts or []          # [[old_account, new_account], ...]
    set_fields = set_fields or {}                # header fields to set on the amended doc
    marker = marker or f"AMEND-{je}"             # idempotency key, stored in cheque_no

    if frappe.db.exists("Journal Entry", {"cheque_no": marker, "docstatus": 1}):
        print(f"SKIP: already amended ({marker} exists)")
        return {"skipped": True}
    if frappe.db.get_value("Journal Entry", je, "docstatus") != 1:
        print(f"SKIP: {je} is not submitted")
        return {"skipped": True}

    orig = frappe.get_doc("Journal Entry", je)
    # Bank Transactions currently reconciled to this JE
    bts = [r.parent for r in frappe.get_all(
        "Bank Transaction Payments",
        filters={"payment_document": "Journal Entry", "payment_entry": je},
        fields=["parent"])]

    # Build the amended copy (not yet inserted) to describe the change
    new = frappe.copy_doc(orig)
    for old_acc, new_acc in swap_accounts:
        for row in new.accounts:
            if row.account == old_acc:
                row.account = new_acc
    for k, v in set_fields.items():
        setattr(new, k, v)
    new.cheque_no = marker

    if dry_run:
        print(f"[DRY RUN] would cancel {je}; unreconcile {len(bts)} BT(s): {bts}")
        for old_acc, new_acc in swap_accounts:
            print(f"[DRY RUN]   swap line account {old_acc!r} -> {new_acc!r}")
        print(f"[DRY RUN]   set {set_fields}; re-link BTs={reconcile}; marker={marker}")
        print("[DRY RUN] re-run with dry_run=False to apply.")
        return {"dry_run": True, "bts": bts}

    # 1. unreconcile (Bank Transaction allows update_after_submit)
    for bt_name in bts:
        bt = frappe.get_doc("Bank Transaction", bt_name)
        bt.payment_entries = [r for r in bt.payment_entries if r.payment_entry != je]
        bt.save(ignore_permissions=True)
    # 2. reload fresh THEN cancel (avoids TimestampMismatchError)
    frappe.get_doc("Journal Entry", je).cancel()
    # 3+4. insert the amended copy, forcing FCY lines to keep their stated rate
    for row in new.accounts:
        if not row.exchange_rate:
            row.exchange_rate = 1
    new.flags.ignore_exchange_rate = True        # else exchange_rate==1 is refetched to the system rate
    new.insert(ignore_permissions=True)
    new.submit()
    # 5. re-link the same Bank Transactions to the new JE
    if reconcile:
        for bt_name in bts:
            bt = frappe.get_doc("Bank Transaction", bt_name)
            amt = abs(flt(bt.withdrawal) - flt(bt.deposit))
            bt.append("payment_entries", {"payment_document": "Journal Entry",
                                          "payment_entry": new.name, "allocated_amount": amt})
            bt.save(ignore_permissions=True)
    frappe.db.commit()
    print(f"Amended {je} -> {new.name}; re-linked {len(bts) if reconcile else 0} BT(s).")
    return {"old": je, "new": new.name, "bts": bts}


def flt(x):
    return float(x or 0)
