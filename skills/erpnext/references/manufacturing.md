# Manufacturing Module

> Targets ERPNext v14–v16. Production consumes raw materials and produces finished goods via
> Stock Entries; the manufacturing `Stock Entry` (`stock_entry_type = Manufacture`) is what
> actually moves inventory and posts cost of goods manufactured.

## DocTypes

| DocType | Submittable? | Purpose |
|---|---|---|
| BOM (Bill of Materials) | **Yes** | Recipe: items + operations + scrap to produce one item. Tree/nested (sub-assembly BOMs). |
| BOM Item / BOM Operation / BOM Scrap Item | No (child) | Raw-material / operation / expected-scrap lines. |
| BOM Update Tool | No (Single) | Bulk replace a component across BOMs, or rebuild cost. |
| BOM Update Log | Yes (status) | Tracks async BOM-replace / cost-update jobs. |
| BOM Creator | **Yes** (v15+) | Multi-level BOM authoring tool; publish to real BOMs. |
| Work Order | **Yes** | Order to manufacture qty of an item against a BOM; drives material + operation tracking. |
| Work Order Item / Work Order Operation | No (child) | Required-items / operations tables. |
| Job Card | **Yes** | Execution of one operation at a workstation; logs time + completed qty. |
| Job Card Time Log | No (child) | Start/stop entries within a Job Card. |
| Workstation | No | A machine/station with hourly costs + working hours. |
| Workstation Type | No (v14+) | Group of identical workstations for capacity. |
| Operation | No | Master operation (links default workstation). |
| Routing | No | Reusable ordered set of operations; pulled into a BOM. |
| Production Plan | **Yes** | Aggregates demand (SO/MR/forecast); generates Work Orders + Material Requests. |
| Production Plan Item / Sub Assembly Item | No (child) | Planned items / sub-assemblies to produce. |
| Downtime Entry | No | Workstation downtime + reason (OEE). |
| Manufacturing Settings | No (Single) | `backflush_raw_materials_based_on`, over-production %, WIP/FG warehouses, capacity planning. |
| Plant Floor | No (v15+) | Shop-floor dashboard of workstations/job cards. |

### Subcontracting (v14+ dedicated DocTypes — replaces the old PO-only flow)

| DocType | Submittable? | Purpose |
|---|---|---|
| Subcontracting BOM | No (v15+) | Master mapping Service Item ↔ Finished Good Item + conversion; auto-fills POs. |
| Subcontracting Order (SCO) | **Yes** | The subcontract job; auto-populates supplied raw materials from BOM. Created from a subcontracted PO. |
| Subcontracting Order Item / Supplied Item | No (child) | FG to receive / RM to supply. |
| Subcontracting Receipt (SCR) | **Yes** | Receives FG, backflushes supplied RM, records scrap. Posts SLE + GL. |
| Subcontracting Receipt Item / Supplied Item | No (child) | Received FG / consumed RM. |

## Workflow

**Standard make-to-stock / make-to-order:**

```
Item (Default BOM) ─► BOM (submitted, is_active=1, is_default=1)
   └─► Production Plan (pull SOs / MRs / forecast)
         ├─► Material Request(s)   (raw-material shortage)
         └─► Work Order(s)         (one per FG item / sub-assembly)
               ├─► Stock Entry (Material Transfer for Manufacture) → RM into WIP warehouse
               ├─► Job Card(s)     (one per operation; only "with operations")
               │     └─► logs time + completed qty
               └─► Stock Entry (Manufacture) → consumes RM from WIP, produces FG, posts scrap
```

- **Work Order** states: Draft → Not Started → In Process → Completed → Stopped/Closed
  (derived from produced qty + transfer, not a Workflow doc).
- **Job Card** is mandatory only when the Work Order is created "with operations".
- The **Manufacture Stock Entry** references `work_order` and books cost of goods manufactured.

**Subcontracting (modern v15+):**

```
Purchase Order (is_subcontracted=1, Service Item rows)
   └─► Subcontracting Order   (button on PO; pulls RM via BOM / Subcontracting BOM)
         ├─► Stock Entry (Send to Subcontractor) → RM to supplier warehouse
         └─► Subcontracting Receipt (receive FG; backflush RM; record scrap) → SLE + GL
```

## Gotchas

1. **BOM cost is not auto-recalculated.** `rm_cost_as_per` = Valuation Rate / Last Purchase
   Rate / Price List / Manual. After price changes, run **BOM Update Tool → Update Cost**
   (async; watch *BOM Update Log*). A submitted BOM's cost is frozen until updated.
2. **Backflush method** (`backflush_raw_materials_based_on`): `BOM` (per BOM qty) vs
   `Material Transferred for Manufacture` (consume exactly what was transferred). The latter
   prevents negative-stock errors but needs accurate transfer Stock Entries. #1 cause of
   "manufacture stock entry won't balance".
3. **WIP warehouse vs `skip_transfer`** — mismatch between WIP setup and backflush method
   causes consumption errors.
4. **Over-production** — `overproduction_percentage_for_work_order` / `..._for_sales_order`;
   exceeding blocks the Stock Entry. Scrap is BOM-defined, produced at scrap warehouse,
   reduces FG cost.
5. **Tree BOM explosion** — a BOM referencing sub-assembly items shows `exploded_items`. If a
   sub-assembly has no active default BOM, plan generation silently skips it.
6. **Subcontracting v13→v15 trap** — in v13 the whole subcontract lived on PO + PR. From
   v14/v15 the **Subcontracting Order/Receipt** carry stock + supplied-items logic; the PO
   only carries the service item + price. Create the SCO, not just a PR, or RM tracking won't
   happen.

## Key reports

Production Planning Report · BOM Stock Report · Work Order Summary · Job Card Summary ·
Production Analytics · Downtime Analysis · BOM Operations Time · Cost of Poor Quality.
