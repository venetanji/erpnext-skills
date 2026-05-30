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

## Key reports

General Ledger · Trial Balance · Balance Sheet · Profit and Loss · Cash Flow · Accounts
Receivable / Payable (+ Summary, with ageing) · Sales/Purchase Register · Gross Profit ·
Budget Variance · Customer/Supplier Ledger Summary. Run via
`frappe.desk.query_report.run` (see `references/api.md`).
