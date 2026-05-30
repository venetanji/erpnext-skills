# Selling & CRM Module

> Targets ERPNext v14–v16. Selling transactions share a skeleton: a child `items` table, a
> `taxes` table, totals, and `*_against` links upstream.
>
> **Two different CRMs exist.** ERPNext ships a built-in CRM (Lead, Opportunity, Customer…).
> There is *also* a separate **`frappe_crm`** app with its own schema (`CRM Lead`, `CRM Deal`,
> `CRM Organization`…) — **not** the same tables. Check `frappe.get_installed_apps()` before
> querying. This file covers the **ERPNext built-in** module.

## DocTypes

| DocType | Submittable? | Purpose |
|---|---|---|
| Lead | No (status) | Unqualified prospect. `lead_name`, `company_name`, `email_id`, `status` (Lead/Open/Replied/Opportunity/Converted/Do Not Contact), `source`. |
| Opportunity | No (status) | Qualified chance. `opportunity_from` (Lead/Customer), `party_name`, child `items`, `expected_closing`, `probability`, `sales_stage`. |
| Prospect | No | v14+ company-level grouping of leads/contacts. |
| Customer | No (master) | The buyer. `customer_name`, `customer_group`, `territory`, `customer_type` (Company/Individual), `default_currency`, `default_price_list`, `tax_id`, `credit_limits` child. |
| Customer Group | No (tree master) | Segmentation tree; default credit limit/payment terms. |
| Territory | No (tree master) | Geographic tree; targets, pricing, tax rules. |
| Contact | No (master) | Person; linked to party via dynamic `links` child. Shared with Buying/CRM. |
| Address | No (master) | Postal address; dynamic `links`; `is_primary_address`, `is_shipping_address`. |
| Quotation | **Yes** | Price offer. `quotation_to` (Customer/Lead), `party_name`, `items`, `taxes`, `valid_till`. |
| Sales Order | **Yes** | Confirmed order. `delivery_date`, `items` (with `delivered_qty`, `billed_amt`), `per_delivered`, `per_billed`, `status`. |
| Delivery Note | **Yes** | Goods shipped out (stock voucher — see `stock.md`). Item `against_sales_order`. |
| Sales Invoice | **Yes** | Customer bill (see `accounting.md`). Item `sales_order`/`so_detail` links. |
| Price List | No (master) | Named price list; `selling`/`buying` flags, `currency`. |
| Item Price | No (master) | One item's rate in a list: `item_code`, `price_list`, `price_list_rate`, optional `customer`/qty/validity. |
| Pricing Rule | No (master) | Conditional discount/price/free-item. `apply_on`, `price_or_product_discount`, `min_qty`, `discount_percentage`, `margin_type`, `free_item`. |
| Promotional Scheme | No (master) | Multi-tier generator that creates Pricing Rules. |
| Sales Partner | No (master) | Channel partner/reseller; `commission_rate`. |
| Sales Person | No (tree master) | Sales team hierarchy. Referenced in voucher `sales_team` child with `allocated_percentage`. |
| Campaign | No (master) | Marketing campaign for attribution on Lead/Opportunity. |
| Customer Credit Limit | No (child) | Per-company limit on Customer; `bypass_credit_limit_check`. |
| Contract | **Yes** | Agreement with fulfilment terms + e-sign. |
| Selling Settings | No (single) | `cust_master_name`, `so_required`, `dn_required`, `maintain_same_sales_rate`, `allow_multiple_items`. |

## Transaction flow

```
Lead ─(qualify)─► Opportunity ─► Quotation ─► Sales Order ─┬─► Delivery Note ─► Sales Invoice ─► Payment Entry
                                                            └─► Sales Invoice (update_stock) ─► Payment
```

- Each step is created from the previous via "Create" / `make_*` mappers, copying items and
  stamping back-links (SO item `prevdoc_docname`, DN/SI item `sales_order`).
- `per_delivered` / `per_billed` on the Sales Order roll up as Delivery Notes / Invoices are
  submitted; status: "To Deliver and Bill" → "Completed".

## Key fields

- Price resolution: `default_price_list` → matching **Item Price** rows → **Pricing Rule**
  adjustments. Line rate = `price_list_rate` then `discount_percentage`/`margin` then `rate`.
- `selling_price_list`, `price_list_currency`, `plc_conversion_rate`, `conversion_rate` on
  every selling transaction.
- Customer `customer_group` + `territory` drive Tax Rules, Pricing Rules, defaults.

## Gotchas

1. **`so_required` / `dn_required`** (Selling Settings) can force the chain — e.g. block a
   Sales Invoice without a Sales Order. Check before creating documents out of order.
2. **Credit limit enforcement** — submitting an SO/SI over a customer's limit is blocked
   unless `bypass_credit_limit_check` or an override role.
3. **Lead is not a transaction party** beyond Quotation — convert to Customer before SO.
4. **Pricing Rule priority/conflicts** — multiple matches resolve by `priority`; unexpected
   discounts usually trace to an overlooked Pricing Rule or customer/qty-conditional Item Price.
5. **`maintain_same_sales_rate`** rejects a DN/Invoice whose rate differs from the SO.
6. **Quotation/Opportunity aren't ledger-submittable** — status workflows, no GL/stock impact
   until SO/DN/SI.

## Key reports

Sales Order Analysis · Sales Funnel · Lead Details · Opportunity Summary by Sales Stage ·
Sales Register · Item-wise Sales History · Sales Person-wise Transaction Summary ·
Quotation/Sales Order Trends · Customer Acquisition and Loyalty.
