#!/usr/bin/env python3
"""<one-line purpose of this script>.

Copy this file to scripts/<name>.py, fill in the header, implement, TEST AGAINST A
RUNNING SITE, then register it in scripts/README.md and link it from the relevant
references/*.md section. See CONTRIBUTING.md for the full workflow.

USAGE:    bench --site <site> execute erpnext.scripts.<name>.run --kwargs '{"dry_run": true}'
    OR:   docker exec -i <backend-container> bench --site <site> \\
              execute path.to.<name>.run --kwargs '{...}'
REQUIRES: frappe.init / bench env  (note any external libs)
READS:    <DocTypes this reads>
WRITES:   <DocTypes this writes — or "read-only">
IDEMPOTENT: yes/no — <how re-running behaves; how duplicates are avoided>
VERSION:  tested on ERPNext v<x>
"""

import frappe


def run(dry_run: bool = True, **kwargs):
    """Entry point. Defaults to dry_run=True so a mistaken call is harmless.

    When invoked via `bench execute`, frappe is already initialised + connected and the
    call auto-commits on success. When run as a standalone script, bootstrap yourself
    (see the __main__ block) and call frappe.db.commit() explicitly.
    """
    # --- 1. Read / compute the intended change -------------------------------------
    # Example: pre-check by business key BEFORE any insert (Universal Hard Rule #3).
    # existing = frappe.db.get_value("Sales Invoice", {"bill_no": kwargs["bill_no"]})
    # if existing:
    #     print(f"SKIP: already exists as {existing}")
    #     return existing

    intended = []  # collect a description of what WOULD change

    # --- 2. Dry-run guard ----------------------------------------------------------
    if dry_run:
        for line in intended:
            print(f"[DRY RUN] would: {line}")
        print(f"[DRY RUN] {len(intended)} change(s) — re-run with dry_run=False to apply.")
        return {"dry_run": True, "planned": len(intended)}

    # --- 3. Apply (writes) ---------------------------------------------------------
    # doc = frappe.get_doc({...}); doc.insert(); doc.submit()
    # frappe.db.commit()   # only needed in standalone/console; bench execute auto-commits
    print(f"Applied {len(intended)} change(s).")
    return {"applied": len(intended)}


if __name__ == "__main__":
    # Standalone invocation: bootstrap frappe yourself and commit explicitly.
    import sys

    site = sys.argv[1] if len(sys.argv) > 1 else None
    if not site:
        sys.exit("usage: env/bin/python <name>.py <site> [--apply]")
    frappe.init(site=site)
    frappe.connect()
    try:
        run(dry_run="--apply" not in sys.argv)
        frappe.db.commit()
    except Exception:
        frappe.db.rollback()
        raise
    finally:
        frappe.destroy()
