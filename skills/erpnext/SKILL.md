---
name: erpnext
description: Core operating knowledge for Frappe Framework and ERPNext — the metadata/DocType data model, how to drive a running instance via bench CLI and the REST/RPC API, and the full module map (Accounting, Selling, Buying, Stock, Manufacturing, HR/Payroll, Projects, Assets, Support, Quality, Customization). Use whenever a task involves reading, creating, or reasoning about ERPNext data, calling the Frappe API, running bench, or knowing which DocType holds what. Distilled from docs.frappe.io.
---

# ERPNext / Frappe — core knowledge skill

This skill gives an agent the *core* knowledge needed to operate a running ERPNext
instance correctly: the data model (what DocTypes exist and how they relate), how to
talk to the system (bench CLI + the API), and a module-by-module map of the business
domain. It is **knowledge**, not a workflow runbook — for opinionated back-office
procedures (bookkeeping, AR/AP, audit reconciliation) see the companion
`shicheng-agents/claude-skills` repo, which builds *on top of* the facts here.

> **Targets Frappe/ERPNext v14–v16.** Where versions diverge (e.g. subcontracting was
> reworked in v15, HR/CRM split into separate apps), the references call it out.
> This is distilled from the official docs at <https://docs.frappe.io/erpnext/> and
> <https://docs.frappe.io/framework/>. Verify against the live instance — see
> "Introspect the live system" below — because every site can be customized.

## The one mental model: everything is a DocType

Frappe is a **metadata-driven, full-stack web framework** (Python + a Vue/JS desk UI).
ERPNext is a large set of apps built on it. The single most important idea:

> **Every "thing" in the system — a Sales Invoice, a Customer, even configuration like
> "Stock Settings" — is a `DocType`. A DocType is a model definition; each record is a
> `Document` (`doc`). Most DocTypes are backed by a SQL table named `tab<DocType>`** (so
> `Sales Invoice` → `tabSales Invoice`).

If you understand DocTypes, fieldtypes, the document lifecycle (`docstatus`), and how
ledgers (GL Entry, Stock Ledger Entry) are *derived* from submitted documents, you can
reason about anything in ERPNext. Start with **`references/data-model.md`**.

## How to use this skill (routing)

Pick the reference file for the task. Each is self-contained and dense.

| You need to… | Read |
|---|---|
| Understand DocTypes, fieldtypes, naming, child tables, single doctypes, customization | **`references/data-model.md`** |
| Run/operate the instance: bench commands, sites, backups, migrate, docker, scheduler | **`references/bench.md`** |
| Read/write data programmatically: REST API, RPC methods, Python ORM, auth, reports | **`references/api.md`** |
| Accounting: Account/JE/Payment Entry/Invoices/GL Entry, multi-currency, reports | **`references/accounting.md`** |
| Selling & CRM: Customer, Quotation, Sales Order, Delivery Note, Lead, pricing | **`references/selling-crm.md`** |
| Buying: Supplier, Material Request, Purchase Order/Receipt/Invoice, RFQ | **`references/buying.md`** |
| Stock: Item, Warehouse, Stock Entry, Stock Ledger Entry, Bin, valuation, batches | **`references/stock.md`** |
| Manufacturing: BOM, Work Order, Job Card, Production Plan, subcontracting | **`references/manufacturing.md`** |
| HR & Payroll (`hrms` app): Employee, Attendance, Leave, Salary, Payroll Entry | **`references/hr-payroll.md`** |
| Projects, Assets, Support, Quality | **`references/projects-assets-support.md`** |
| Customization & admin: Custom Field, Client/Server Script, Workflow, Roles, Reports | **`references/customization.md`** |
| Contribute scripts / operational knowledge back to this skill | **`CONTRIBUTING.md`** |

## Connect to the instance (cheat sheet)

There are two ways in. Use the API for portable read/write from outside; use bench for
operations, multi-step transactions, and anything privileged. Full detail in
`references/api.md` and `references/bench.md`.

```bash
# --- bench, bare-metal install ---
bench --site <site> execute frappe.client.get_list \
  --kwargs '{"doctype":"Sales Invoice","filters":{"docstatus":1},"fields":["name","grand_total"]}'

# --- bench, dockerized install (common) ---
EB="docker exec <backend-container>"        # e.g. frappe_docker-backend-1
$EB bench --site <site> execute frappe.client.get \
  --kwargs '{"doctype":"Customer","name":"<CUST>"}'

# --- REST API (token auth), from anywhere ---
curl -s 'https://<host>/api/resource/Sales Invoice?filters=[["docstatus","=",1]]&fields=["name","grand_total"]' \
  -H 'Authorization: token <api_key>:<api_secret>'
```

**Reads** can use `bench execute frappe.client.*` or the REST API directly. **Writes that
must persist** (anything multi-step / transactional) should drop into the Python env with
`frappe.init` + explicit `frappe.db.commit()` — see the pattern in `references/bench.md`.
The classic trap: `bench console` exits before your `frappe.db.commit()` fires, leaving
documents that *look* submitted but were never persisted.

## Universal hard rules (apply to almost every task)

These cut across modules. The per-module references add domain-specific ones.

1. **`docstatus` is the lifecycle.** `0`=Draft, `1`=Submitted, `2`=Cancelled. Submittable
   DocTypes (invoices, entries, orders) only affect ledgers once **submitted**. Submit is
   one-way; to change a submitted doc you **cancel → amend** (creates an `-1` sibling).
2. **Ledgers are read-only and derived.** `GL Entry` (accounting) and `Stock Ledger Entry`
   (inventory) are *generated* from submitted vouchers. **Never INSERT into them.** To
   change the ledger, post/cancel the source voucher (e.g. a Journal Entry).
3. **POST/insert is not idempotent.** `frappe.client.insert` / REST POST creates a *new*
   document every call. Before inserting, pre-check by business key (`bill_no`, `po_no`,
   `voucher_no`, etc.) with `get_list`/`get_value` to avoid duplicates.
4. **Never set `naming_series` counters by hand.** Let the server default fire. The counter
   in `tabSeries` does **not** roll back when you delete a doc.
5. **Cancel, don't delete, submitted docs** — and don't cancel a voucher that has downstream
   links (payment refs, reconciliations, stock against it); post a correcting entry instead.
6. **Permissions differ by API.** `frappe.get_all` / `frappe.db.*` **ignore** user
   permissions; `frappe.get_list` and the REST API **respect** them. Pick deliberately.
7. **Multi-currency is explicit.** On non-base-currency documents set `conversion_rate` /
   `exchange_rate`; amounts exist twice (account currency vs base currency).
8. **Validate the period is open.** Posting dates must fall in an open Fiscal Year; watch
   "Accounts Frozen Upto" / Period Closing Vouchers before backdating.

## Introspect the live system (don't guess — verify)

Every site can have custom fields, custom DocTypes, and customized behavior. When unsure,
ask the instance:

```bash
# What fields does this DocType actually have here?
$EB bench --site <site> execute frappe.client.get --kwargs '{"doctype":"DocType","name":"Sales Invoice"}'
# Programmatic meta (fieldnames, types, options):
$EB bench --site <site> execute frappe.get_meta --kwargs '{"doctype":"Sales Invoice"}'
# List custom fields on a doctype:
$EB bench --site <site> execute frappe.client.get_list \
  --kwargs '{"doctype":"Custom Field","filters":{"dt":"Sales Invoice"},"fields":["fieldname","fieldtype","label"]}'
# Which apps/version is installed:
$EB bench --site <site> list-apps
$EB bench version
```

When the live system contradicts this skill, **trust the live system** and (if the
divergence is general) note it back into the skill per `CONTRIBUTING.md`.

## What's NOT here (yet)

Per-task automation scripts live in `scripts/` and are intentionally sparse — this skill is
being built knowledge-first, with a planned second pass to add vetted Python helpers and
operational know-how. If you find yourself writing the same `frappe.init` script twice,
that's a candidate for `scripts/`. See **`CONTRIBUTING.md`** for how to add one.
