# Buying Module

> Targets ERPNext v14–v16. Mirror image of Selling on the supplier side. Same transaction
> skeleton: `items` + `taxes` + totals + upstream links.

## DocTypes

| DocType | Submittable? | Purpose |
|---|---|---|
| Supplier | No (master) | The vendor. `supplier_name`, `supplier_group`, `supplier_type`, `default_currency`, `default_price_list`, `tax_withholding_category`, `on_hold`/`hold_type`/`release_date`. |
| Supplier Group | No (tree master) | Supplier segmentation tree; default payment terms. |
| Material Request | **Yes** | Internal request. `material_request_type`: Purchase / Material Transfer / Material Issue / Manufacture / Customer Provided. Child `items` (`qty`, `schedule_date`, `ordered_qty`). |
| Request for Quotation (RFQ) | **Yes** | Solicit prices from multiple suppliers. Child `suppliers` + `items`; can email a portal link. |
| Supplier Quotation | **Yes** | A supplier's offer (one per supplier). `supplier`, `items` (`rate`, `valid_till`). |
| Purchase Order (PO) | **Yes** | Commitment to buy. `supplier`, `schedule_date`, `items` (`received_qty`, `billed_amt`), `per_received`, `per_billed`, `status`. |
| Purchase Receipt (PR) | **Yes** | Goods received (stock voucher). Posts stock + SRBNB GL under perpetual inventory. Item `purchase_order`/`po_detail`; `is_return` for rejections. |
| Purchase Invoice (PI) | **Yes** | Supplier bill (see `accounting.md`). Item `purchase_order`/`purchase_receipt` links. `update_stock` skips a separate PR. |
| Supplier Scorecard | No (master + periodic) | Vendor rating: `Supplier Scorecard Period`, criteria, variables, standings. |
| Buying Settings | No (single) | `po_required`, `pr_required`, `maintain_same_rate`, `bill_for_rejected_quantity_in_purchase_invoice`, supplier naming. |

## Transaction flow

```
Material Request ─► RFQ ─► Supplier Quotation ─► Purchase Order ─┬─► Purchase Receipt ─► Purchase Invoice ─► Payment Entry
                                                                  └─► Purchase Invoice (update_stock) ─► Payment
```

- "Get Items From" / "Create" mappers copy items downstream and stamp links
  (`material_request`, `supplier_quotation`, `purchase_order`, `po_detail`).
- `per_received` / `per_billed` roll up on the PO as PR/PI are submitted.
- **Three-way match:** PO ↔ PR ↔ PI. `maintain_same_rate` enforces consistent rates.

## Key fields

- Supplier `default_currency` / `default_price_list` drive PO currency + rates (buying Item
  Price rows).
- `tax_withholding_category` on Supplier auto-applies TDS on PI/Payment.
- PR/PI item `rejected_qty` + `rejected_warehouse` for QA rejections; `received_qty` vs
  `accepted_qty`.

## Gotchas

1. **`po_required` / `pr_required`** (Buying Settings) may force the chain — a PI can be
   blocked without a preceding PO/PR.
2. **SRBNB timing** — Purchase Receipt credits "Stock Received But Not Billed"; the PI
   reverses it. Skipping the PR and using PI with `update_stock` makes the PI do the full
   stock + SRBNB handling. A lingering SRBNB balance usually means a PR exists without its PI.
   (For drop-ship/advance-pay flows, booking the PI with `update_stock=1` avoids the SRBNB
   residual class entirely — see the companion `/ar-ap` skill.)

   **SRBNB is not a stock account.** Its `account_type` is `"Stock Received But Not Billed"`
   (`root_type=Liability`), distinct from `account_type="Stock"`. Only the latter is
   protected by `validate_stock_accounts` / `StockAccountInvalidTransaction` in
   `journal_entry.py` (the validator pulls account names via `get_stock_accounts`, which
   filters strictly on `account_type=="Stock"`). **So direct Journal Entries to SRBNB are
   allowed and are the standard way to clean up SRBNB residuals at year-end** — see the
   gotcha list below for the failure modes that produce those residuals. Stock-In-Transit
   and warehouse accounts (genuine `account_type="Stock"`) remain off-limits to JEs.

3. **`maintain_same_rate`** rejects a PR/PI whose rate differs from the PO.
4. **Supplier `on_hold`** blocks new POs/payments; check `hold_type` (All/Invoices/Payments)
   and `release_date`.
5. **RFQ → Supplier Quotation** is one quotation per supplier; compare via the "Supplier
   Quotation Comparison" report.
6. **Returns are negative documents** (`is_return` + `return_against`), not edits — to
   reverse a receipt, create a return PR.
7. **SRBNB residual failure modes beyond "PR without PI"** — each leaves a balance on
   `Stock Received But Not Billed` after the cycle should have netted to zero.
   1. **Return PI's `expense_account` not flipped from SRBNB.** *Symptom:* phantom Cr
      balance on SRBNB after a credit-note PI. *Cause:* when amending a PI as a return
      (`is_return=1`), each item line's `expense_account` defaults from the parent — if
      the parent targeted SRBNB, the reversed sign credits SRBNB instead of the right
      expense/asset account. *Fix on submit:* manually change `expense_account` per line to
      Stock In Hand (reversing a stocked PR), COGS (reducing cost of already-sold
      drop-shipped goods), or Stock Adjustment (write-off). *Fix retroactively:* corrective
      JE Dr SRBNB / Cr [right account].
   2. **PI without matching PR (drop-ship pattern).** *Symptom:* orphan Dr on SRBNB.
      *Cause:* PI booked with `update_stock=0` and `expense_account=SRBNB`, but goods
      drop-shipped directly supplier → customer with no PR ever issued. Nothing clears the
      SRBNB leg. *Fix:* corrective JE Dr COGS / Cr SRBNB at the PI's posting date — goods
      are already at the customer; revenue was booked via a Sales Invoice with
      `update_stock=0`, so the cost belongs in COGS, not Stock In Transit.
   3. **FX rate mismatch between PI and PR for the same FCY amount.** *Symptom:* SRBNB
      carries a non-zero base-currency residual after PR/PI both submit at zero FCY net.
      *Cause:* PR booked at rate X (goods-received date), PI booked at rate Y (bill date)
      — SRBNB captures the rate-difference base-currency spread instead of it flowing to
      Exchange G/L. *Fix:* JE rolls the residual from SRBNB to `Exchange Gain/Loss` (no
      FCY impact).

## Key reports

Purchase Order Analysis · Purchase Order Trends · Purchase Register · Item-wise Purchase
History · Supplier Quotation Comparison · Procurement Tracker · Received Items To Be Billed ·
Supplier Scorecard.
