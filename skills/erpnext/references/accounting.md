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
- Rate resolution (`erpnext.setup.utils.get_exchange_rate`): (1) look up a `Currency
  Exchange` row for the pair + date within `stale_days` (default 1; bypassed by
  `Accounts Settings.allow_stale=1`); (2) fall back to the on-demand fetcher
  (`Currency Exchange Settings`, default service provider `frankfurter.dev`); (3) optional
  pegged-currency table if `allow_pegged_currencies_exchange_rates=1`. The fetched rate is
  cached ~6h in Redis but is **not** persisted to `Currency Exchange` — that table is a
  pure manual-override store.
- **No scheduled job pre-populates `Currency Exchange`.** Hooks `auto_create_exchange_rate_
  revaluation_{daily,weekly,monthly}` create *Exchange Rate Revaluation* JEs, not rate rows.
  If you need a documented year-end rate for an auditor, insert the `Currency Exchange`
  row yourself.
- `Journal Entry.voucher_type='Exchange Gain Or Loss'` is the only voucher type that
  permits an FCY-account line with base-currency-only movement (zero in account currency) — needed
  to clear base-currency residuals left by mismatched-rate JE pairs. Plain `Journal Entry` fails
  validation ("Both Debit and Credit values cannot be zero").

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
3. **Frozen / closed periods** — postings on/before the freeze date are blocked unless the
   caller's role matches the configured "modifier" role. Posting outside any open FY fails.
   *Location varies by version:* on **v14–v15** these live on `Accounts Settings` as
   `acc_frozen_upto` + `frozen_accounts_modifier`; on **v16** they moved to per-Company
   fields `Company.accounts_frozen_till_date` + `Company.role_allowed_for_frozen_entries`
   (`erpnext.accounts.general_ledger.validate_accounts_frozen`). Check both before
   backdating.
4. **Receivable/Payable legs require a party** — any GL leg on a Receivable/Payable-type
   account must carry `party_type`+`party`, or submit fails.
5. **Cancel cascades** — can't cancel an invoice with linked submitted PEs/returns without
   cancelling those first.
6. **`update_stock` on invoices** turns a Sales/Purchase Invoice into a stock voucher (posts
   stock/COGS GL + Stock Ledger Entries) — relevant when an invoice unexpectedly moves stock.
7. **`is_cancelled` on GL queries** — cancelled vouchers flip `is_cancelled=1` on the GL but
   keep the doc; always filter.
8. **`Company.reporting_currency` blank ⇒ misleading "Unable to find exchange rate for
   {base} to None" error** on every GL Entry validate. *Symptom:* posting any voucher
   throws an FX error citing `None` as the target currency. *Fix:* on Company master, not on
   `Currency Exchange` — set `reporting_currency` to the company's `default_currency`.
9. **Broken Account Closing Balance chain ⇒ wrong Balance Sheet opening.** From v14+, the
   Balance Sheet report reads `tabAccount Closing Balance` (ACB) rows produced by each
   submitted Period Closing Voucher, summing per-year activity across all prior PCVs. PCVs
   submitted on older versions (pre-ACB) leave no rows. *Symptom:* BS opening for a year
   diverges from `SUM(debit-credit)` over GL Entry at the same date, on accounts the GL/TB
   report as fine. *Diagnostic:* `SELECT period_closing_voucher, COUNT(*) FROM \`tabAccount
   Closing Balance\` GROUP BY 1` — older PCVs with zero rows indicate a broken chain.
   *Fix:* ACB-only backfill in chronological order via `make_closing_entries` (no PCV
   cancellation, no GL touched). The most recent PCV's ACB must be deleted and regenerated
   last so it folds in the now-backfilled prior chain.
10. **Payment Reconciliation can manufacture a phantom JE on an already-balanced FCY
    account.** *Symptom:* a party's FCY account is net 0 in both base and account currency,
    but PR still surfaces lingering allocation rows (often from `-1`/`-2` amendment chains).
    Clicking Reconcile on rows with non-zero Difference Amount posts a new JE with the FX
    spread on Exchange G/L — and an offsetting leg on the FCY party-account at base-currency-only
    (zero in account currency), creating an imbalance on a previously clean account. *Fix:*
    diagnostic SQL first — `SELECT SUM(debit-credit) net_base, SUM(debit_in_account_currency-
    credit_in_account_currency) net_ccy FROM \`tabGL Entry\` WHERE account=… AND party=…
    AND is_cancelled=0`. If both are zero, don't reconcile. If you already posted a phantom
    JE, cancel it.
11. **PR's default "Difference Posting Date" backdates into closed FYs.** *Symptom:*
    reconciling old payment JEs (booked at historical rates) against invoices silently posts
    Exchange G/L into a closed/audited fiscal year, breaking the signed accounts. *Fix:*
    per-row override the `gain_loss_posting_date` to a date in the current open FY (the
    pencil-edit icon on rows with non-zero Difference Amount); make sure a `Currency
    Exchange` row exists for that date + pair before reconciling.
12. **Self-referential Payment Ledger Entry rows from manual FX-narration JEs.** *Symptom:*
    PR keeps surfacing the same party row even after every invoice nets zero. *Cause:*
    JEs that "narrate" credit-note application by booking two FCY legs at different rates
    on the same party-account (net zero in account currency, base-currency spread absorbed in an
    Exchange G/L leg in the same voucher) generate PLE rows with `voucher_no =
    against_voucher_no`. *Diagnostic SQL:* `SELECT voucher_no, against_voucher_no, party,
    amount_in_account_currency, amount FROM \`tabPayment Ledger Entry\` WHERE voucher_no =
    against_voucher_no AND delinked = 0`. *Fix:* if both `SUM(amount)` and
    `SUM(amount_in_account_currency)` on those rows are zero, delink them with `UPDATE
    \`tabPayment Ledger Entry\` SET delinked = 1 WHERE …`. No GL impact (the underlying
    JE is unchanged); only the sub-ledger noise disappears. **Do not delink** if the net
    is non-zero — those represent real outstanding.
13. **FX residual after JE-based AP cleanup at mismatched rates.** *Symptom:* after a
    one-shot JE clears a party in account currency, the FCY Creditors account shows net 0
    FCY but non-zero in base currency. *Cause:* two FCY legs at different historical
    exchange rates whose base-currency delta wasn't routed to Exchange G/L explicitly.
    *Fix:* post a follow-up JE with `voucher_type='Exchange Gain Or Loss'` +
    `multi_currency=1`, charging the base-currency residual against `Exchange Gain/Loss`
    and offsetting on the FCY party-account at base-currency-only/zero FCY. Plain Journal
    Entry refuses (`Both Debit and Credit values cannot be zero`); the
    Exchange-Gain-Or-Loss voucher_type bypasses that check.

## Key reports

General Ledger · Trial Balance · Balance Sheet · Profit and Loss · Cash Flow · Accounts
Receivable / Payable (+ Summary, with ageing) · Sales/Purchase Register · Gross Profit ·
Budget Variance · Customer/Supplier Ledger Summary. Run via
`frappe.desk.query_report.run` (see `references/api.md`).
