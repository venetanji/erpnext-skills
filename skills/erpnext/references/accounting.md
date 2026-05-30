# Accounting Module

> Targets ERPNext v14–v16. Every document is a DocType in `tab<DocType>`. Submittable docs
> have `docstatus` (0 Draft / 1 Submitted / 2 Cancelled); **ledger postings happen only on
> submit** and reverse on cancel.

## Core principle: double-entry, ledger is derived

ERPNext is double-entry. You **never** write the ledger directly. **GL Entry** is a
read-only ledger: each submitted accounting voucher (Journal Entry, Payment Entry, Sales/
Purchase Invoice, and stock vouchers under perpetual inventory) auto-generates one GL Entry
row per account leg, with `debit`/`credit` (company currency) plus
`debit_in_account_currency`/`credit_in_account_currency`. Every voucher's GL Entries net to
zero. On **cancel**, ERPNext writes reversing entries (or flips `is_cancelled=1`) so the
ledger stays balanced. To fix something, cancel/amend the source voucher.

## DocTypes

| DocType | Submittable? | Purpose |
|---|---|---|
| Account | No (tree master) | Chart of Accounts node. `parent_account`, `is_group`, `lft`/`rgt`, `root_type` (Asset/Liability/Income/Expense/Equity), `account_type` (Bank, Cash, Receivable, Payable, Stock, Tax, COGS…), `account_currency`. Leaf accounts receive postings. |
| Company | No (master) | Owns CoA + default accounts (`default_receivable_account`, `default_payable_account`, `round_off_account`, stock accounts), `default_currency`. |
| Fiscal Year | No (master) | `year_start_date`, `year_end_date`. Postings must fall in an open FY. |
| Cost Center | No (tree master) | Departmental/segment P&L tracking; set on voucher lines. |
| Accounting Dimension | No (config) | Adds an extra slice dimension (Project, Branch) as a field on all voucher tables + GL Entry. |
| Journal Entry | **Yes** | Generic manual voucher. Child `accounts` (Journal Entry Account) with per-row `account`, `debit_in_account_currency`, `credit_in_account_currency`, `party_type`/`party`, `reference_type`/`reference_name` (to settle invoices). `voucher_type`: Journal Entry, Bank Entry, Cash Entry, Opening Entry, Exchange Gain Or Loss, Write Off… |
| Payment Entry | **Yes** | Money received/paid. `payment_type`: Receive/Pay/Internal Transfer. `party_type`+`party`, `paid_from`/`paid_to`, `paid_amount`/`received_amount`, `source_exchange_rate`/`target_exchange_rate`. Child `references` with `reference_doctype`, `reference_name`, `allocated_amount`. |
| Sales Invoice | **Yes** | Customer bill (AR). Dr Receivable, Cr Income (+tax). `is_pos`, `update_stock`, `is_return`/`return_against`. |
| Purchase Invoice | **Yes** | Supplier bill (AP). Cr Payable, Dr Expense/Asset (+tax). `bill_no`, `bill_date`, `is_return`, `update_stock`. |
| Payment Request | **Yes** | Request payment vs invoice/order; can carry a gateway link. |
| Payment Reconciliation | No (tool) | Match unallocated PEs/advances/JEs against outstanding invoices for a party. |
| Payment Terms / Template | No (master) | Installment due dates / credit periods → invoice `payment_schedule`. |
| Dunning | **Yes** | Overdue-invoice reminder/interest doc. |
| GL Entry | No (read-only, auto) | The general ledger. `account`, `debit`, `credit`, `against`, `voucher_type`/`voucher_no`, `party_type`/`party`, `cost_center`, `posting_date`, `is_cancelled`, `against_voucher`. **Never create/edit.** |
| Currency Exchange | No (master) | Stored FX rates: `from_currency`, `to_currency`, `exchange_rate`, `date`. |
| Mode of Payment | No (master) | Cash/Bank/Credit Card → default account per company. |
| Bank / Bank Account | No (master) | Institution / specific account (links a CoA Account, IBAN, `is_company_account`). |
| Bank Transaction | **Yes** | Imported statement line; reconciled vs PEs/JEs. `deposit`, `withdrawal`, `allocated_amount`, `unallocated_amount`. |
| Bank Reconciliation Tool | No (tool) | Match Bank Transactions to vouchers / auto-create PEs. |
| Sales/Purchase Taxes and Charges Template | No (master) | Reusable tax rows for the `taxes` table. Each row: `charge_type` (On Net Total/Actual/…), `category` (Total/Valuation/Total and Valuation), `add_deduct_tax`. |
| Item Tax Template | No (master) | Per-item tax-rate overrides. |
| Tax Withholding Category | No (master) | TDS/withholding rates + thresholds; auto-deducts on PI/Payment. |
| Tax Rule | No (master) | Auto-selects a tax template by customer/supplier/territory. |
| Period Closing Voucher | **Yes** | Year-end close: zeroes P&L into the closing (equity) account. |
| Accounts Settings | No (single) | `acc_frozen_upto`, `frozen_accounts_modifier`, allow stale FX rates, credit-limit checks, `book_deferred_entries_via_journal_entry`. |
| Budget | No | Spend limits per Cost Center/account (warn/stop). |
| Subscription | No | Auto-generates recurring invoices. |

## Multi-currency

- Each Account has `account_currency`. Vouchers store `currency`/`conversion_rate`
  (party currency → company base).
- Amounts exist twice: account/transaction currency (`*_in_account_currency`) and base
  (`base_*`). GL Entry stores both base `debit`/`credit` and `*_in_account_currency`.
- Payment Entry uses `source_exchange_rate` + `target_exchange_rate`; FX gain/loss auto-books
  to the Exchange Gain/Loss account.
- Currency Exchange records + Accounts Settings ("Allow Stale Exchange Rates") govern rate
  defaulting (falls back to frankfurter.dev auto-fetch if enabled).

## Transaction flow

```
Sales:    Sales Invoice (submit) ─Dr Receivable, Cr Income+Tax─► GL Entry
            └─► Payment Entry / JE (settle via references) ─► GL Entry, reduces outstanding
                  └─► Payment Reconciliation (match advances/unallocated)
Purchase: Purchase Invoice (submit) ─Cr Payable, Dr Expense+Tax─► GL Entry
            └─► Payment Entry (Pay) ─► GL Entry
Bank:     Bank Transaction (import) ─► Bank Reconciliation Tool ─► Payment/Journal Entry
Year-end: Period Closing Voucher ─► moves net P&L to equity
```

An invoice's `outstanding_amount` reduces as PEs/JEs allocate against it via reference
tables. Status (Paid/Unpaid/Overdue/Partly Paid) derives from `outstanding_amount` +
`payment_schedule` due dates.

## Gotchas

1. **Never write GL Entry directly** — auto-generated on submit, reversed on cancel. To
   change a posted amount, cancel + amend the source voucher.
2. **Submit, don't just save** — a Draft invoice posts *nothing*.
3. **Frozen / closed periods** — if `acc_frozen_upto` is set, postings on/before that date
   are blocked unless your role matches `frozen_accounts_modifier`. Posting outside any open
   FY fails.
4. **Receivable/Payable legs require a party** — any GL leg on a Receivable/Payable-type
   account must carry `party_type`+`party`, or submit fails.
5. **Cancel cascades** — can't cancel an invoice with linked submitted PEs/returns without
   cancelling those first.
6. **`update_stock` on invoices** turns a Sales/Purchase Invoice into a stock voucher (posts
   stock/COGS GL + Stock Ledger Entries) — relevant when an invoice unexpectedly moves stock.
7. **`is_cancelled` on GL queries** — cancelled vouchers flip `is_cancelled=1` on the GL but
   keep the doc; always filter.
8. **Multi-currency JE — `exchange_rate == 1` is treated as "unset" and refetched.** *Symptom:*
   a JE touching a foreign-currency account you want booked **at par** (a near-dormant FCY
   bank, or a pegged currency) fails *"Total Debit must be equal to Total Credit. The difference
   is `<amount × (rate−1)>`"* on `insert` **even though you set `exchange_rate=1`**.
   `JournalEntry.set_exchange_rate()` refetches the system rate when the line rate is falsy
   **or `== 1`** (`accounts/doctype/journal_entry/journal_entry.py`). *Fix:* set
   `doc.flags.ignore_exchange_rate = True` before `insert()`, keep `exchange_rate=1` on the FCY
   line, and pass **only** `debit_in_account_currency`/`credit_in_account_currency` (never the
   base `debit`/`credit`, or ERPNext recomputes the base at the fetched rate). v14–v16.
9. **Bank Transaction reconciles via its child table after submit** — it allows
   `update_after_submit`. *Reconcile:* append a row to `payment_entries`
   (`payment_document`, `payment_entry`, `allocated_amount`) and `.save()`. *Unreconcile:*
   remove that row and `.save()` (the `before_update_after_submit` hook recomputes
   `allocated_amount` / `unallocated_amount` / `status`). No need to cancel the BT — handy when
   swapping which voucher a feed line matches.
10. **Importing a Bank Transaction is staging, not posting** — it does **not** move the GL; the
    GL only changes when you reconcile the BT to a Payment Entry / JE. A bank account whose feed
    ties to the statement but whose **GL is higher** = *orphan vouchers* posting to that account
    that aren't in any `Bank Transaction Payments` row (find them with
    `scripts/bank_reconciliation_diagnostic.py`).
11. **An Account with cancelled GL entries can't be deleted.** *Symptom:*
    `delete_doc("Account", …)` → *"Account with existing transaction can not be deleted"* even
    after you cancelled the only voucher that used it — cancelled `GL Entry` rows persist. *Fix:*
    rename it (`ZZ-UNUSED …`) or purge `is_cancelled=1` rows first; don't fight the delete.

## Key reports

General Ledger · Trial Balance · Balance Sheet · Profit and Loss · Cash Flow · Accounts
Receivable / Payable (+ Summary, with ageing) · Sales/Purchase Register · Gross Profit ·
Budget Variance · Customer/Supplier Ledger Summary. Run via
`frappe.desk.query_report.run` (see `references/api.md`).
