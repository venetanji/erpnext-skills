# Stock / Inventory Module

> Targets ERPNext v14–v16. Inventory is a perpetual sub-ledger. **Stock Ledger Entry (SLE)**
> is the read-only stock ledger; **Bin** is the live per-item-per-warehouse balance — both
> are *derived* from submitted stock vouchers. Under perpetual inventory, stock vouchers also
> post **GL Entries** (stock and accounting stay in sync).

## DocTypes

| DocType | Submittable? | Purpose |
|---|---|---|
| Item | No (master) | Product/service. `item_code`, `item_group`, `stock_uom`, `is_stock_item`, `has_batch_no`, `has_serial_no`, `valuation_method` (FIFO/Moving Average/LIFO), `is_fixed_asset`, `item_defaults` (per-company warehouse/accounts), reorder levels, `is_purchase_item`/`is_sales_item`, `inspection_required_before_*`. |
| Item Group | No (tree master) | Item categorization tree; default tax/price. |
| Warehouse | No (tree master) | Storage location tree (`is_group`, `parent_warehouse`); links a stock Account for perpetual inventory. |
| UOM / UOM Conversion Factor | No (master) | Units + conversion factors; item-level `uoms` child. |
| Bin | No (read-only, auto) | Live balance per (item, warehouse): `actual_qty`, `reserved_qty`, `ordered_qty`, `indented_qty`, `planned_qty`, `projected_qty`, `valuation_rate`, `stock_value`. **Never edit.** |
| Stock Ledger Entry (SLE) | No (read-only, auto) | The stock ledger. `item_code`, `warehouse`, `actual_qty` (±), `qty_after_transaction`, `valuation_rate`, `stock_value`, `stock_value_difference`, `voucher_type`/`voucher_no`, `batch_no`, `serial_no`, `posting_date`/`posting_time`. Auto-generated on submit. |
| Stock Entry | **Yes** | Direct stock movement. `stock_entry_type`/`purpose`: **Material Issue** (out), **Material Receipt** (in), **Material Transfer**, **Material Transfer for Manufacture**, **Manufacture**, **Repack**, **Send to Subcontractor**. Child `items` (`s_warehouse`/`t_warehouse`, `qty`, `basic_rate`). |
| Stock Reconciliation | **Yes** | Set absolute qty/valuation (physical count / opening stock). Posts the *difference* as SLE + GL to Stock Adjustment. `purpose`: Opening Stock / Stock Reconciliation. |
| Delivery Note | **Yes** | Goods shipped out (stock out + COGS). |
| Purchase Receipt | **Yes** | Goods received (stock in + SRBNB). |
| Batch | No (master) | Lot tracking; `batch_id`, `expiry_date`, `manufacturing_date`. Only for `has_batch_no` items. |
| Serial No | No (master) | Per-unit tracking; `serial_no`, `status`, `warehouse`. Only for `has_serial_no` items. |
| Serial and Batch Bundle | **Yes** (v15+) | v15+ container holding serial/batch rows for a voucher line, replacing inline serial/batch fields. |
| Item Attribute | No (master) | Variant axes (Size, Color) + allowed values. |
| Item Variant | No (= Item) | Variant Items from a template + attribute combos (`variant_of`, `attributes`). |
| Putaway Rule | No (master) | Capacity-based auto-allocation of received qty into warehouses. |
| Pick List | **Yes** | Warehouse picking for outbound; feeds Delivery Note / Stock Entry. |
| Packing Slip | **Yes** | Splits a Delivery Note into physical packages. |
| Landed Cost Voucher | **Yes** | Distributes freight/duty/handling across received items, raising valuation. References PRs/PIs. |
| Quality Inspection | **Yes** | QC against received/delivered/manufactured items; can block submission. |
| Item Alternative | No (master) | Substitute items for manufacturing/purchase. |
| Stock Settings | No (single) | `valuation_method` default, `allow_negative_stock`, `default_warehouse`, `auto_insert_price_list_rate_if_missing`, perpetual inventory toggle. |

## Valuation

- **FIFO** — consumption valued at oldest received cost (FIFO queue on the SLE).
- **Moving Average** — `valuation_rate` recomputed as weighted average on each receipt;
  outflows use the current average.
- **LIFO** — supported, rare.
- Set per Item (`valuation_method`) with a global default in Stock Settings. **Landed Cost
  Voucher** adjusts valuation after receipt.

## How SLE & Bin are derived

```
Submit stock voucher (Stock Entry / Delivery Note / Purchase Receipt /
   Stock Reconciliation / Sales|Purchase Invoice with update_stock)
        ├─► creates Stock Ledger Entry rows (one per item-warehouse leg, signed actual_qty)
        │       └─► recomputes qty_after_transaction & valuation_rate (FIFO/MA)
        ├─► updates Bin (actual_qty, valuation_rate, stock_value) per (item, warehouse)
        └─► [perpetual inventory] creates GL Entries:
                in:  Dr Warehouse Stock,  Cr SRBNB (purchase) / source warehouse
                out: Cr Warehouse Stock,  Dr COGS (sales) / Stock Adjustment
```

On **cancel**, SLEs/GL reverse and Bin recomputes. SLEs after a backdated posting date are
re-posted ("repost item valuation") so historical valuation stays correct.

## Perpetual inventory accounts

- **Stock In Hand** (Warehouse account, Asset) — current inventory value.
- **Stock Received But Not Billed (SRBNB)** (Liability) — credited by PR, reversed by PI.
- **Cost of Goods Sold** (Expense) — debited at valuation when goods are delivered/sold.
- **Stock Adjustment** (Expense) — absorbs Stock Reconciliation / repack / manual differences.
- **Expenses Included In Valuation** — offsets purchase taxes/charges flagged "Valuation".

## Gotchas

1. **Bin and SLE are read-only/derived** — to change stock, submit a voucher (Stock Entry,
   Stock Reconciliation), never edit Bin/SLE. Correct opening/count differences via Stock
   Reconciliation.
2. **Negative stock** — issuing more than `actual_qty` fails unless `allow_negative_stock`.
3. **`projected_qty` ≠ `actual_qty`** — `projected = actual + ordered + indented + planned −
   reserved − …`. Use `actual_qty` for "physically there," `projected_qty` for planning.
4. **Backdated entries trigger reposting** — a voucher with an earlier `posting_date`
   re-runs valuation for all later SLEs of that item (slow; can change later valuation rates).
5. **Serial/Batch differs by version** — v13/v14 inline `serial_no`/`batch_no` text on lines;
   **v15+ uses Serial and Batch Bundle** — read the right structure for your version.
6. **`update_stock` on invoices** — an invoice with `update_stock=1` is a full stock voucher
   (SLEs + stock GL); don't double-count by also creating a separate DN/PR.
7. **Landed Cost Voucher** must reference a *submitted* Purchase Receipt; it re-posts
   valuation + stock GL retroactively.
8. **Warehouse must link a stock Account** for perpetual-inventory GL to post.

## Key reports

Stock Balance · Stock Ledger · Stock Projected Qty · Stock Ageing · Itemwise Recommended
Reorder Level · Item Shortage Report · Stock Analytics · Batch-Wise Balance History · Serial
No Status/Ledger · Warehouse Wise Stock Balance.
