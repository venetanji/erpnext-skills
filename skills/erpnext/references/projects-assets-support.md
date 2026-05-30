# Projects, Assets, Support & Quality

> Targets ERPNext v14–v16. Four smaller modules grouped together.

---

# Projects

| DocType | Submittable? | Purpose |
|---|---|---|
| Project | No | Container for tasks/timesheets/costs; tracks % complete, billing, profitability. |
| Task | No | Unit of work; nestable (`parent_task` → tree), dependencies (`depends_on`). |
| Timesheet | **Yes** | Time logged against tasks/projects/activities; can be billable; feeds Sales Invoice & Salary. |
| Timesheet Detail | No (child) | One time-log row (from/to, hours, `activity_type`, billing rate). |
| Activity Type | No | Master kind of work (Development, Consulting). |
| Activity Cost | No | Per-employee per-activity costing + billing rate. |
| Project Type | No | Categorizes projects (Internal/External/Other). |
| Project Template / Template Task | No / child | Reusable task list to spawn a project. |

**Workflow**

```
Project Template (optional) → Project
   ├─► Task(s) (depends_on, parent_task, expected dates)
   ├─► Timesheet(s) (log hours) ─► Sales Invoice (bill billable hours)
   └─► roll-up: % complete, total costing/billing amount
```

- **Billing from timesheets:** mark Timesheet Detail rows `is_billable=1` with `billing_rate`;
  "Create Sales Invoice" from a submitted Timesheet pulls billable amounts (or add the
  Timesheet to a Sales Invoice `timesheets` table). `costing_rate` drives cost, `billing_rate`
  drives revenue.
- A Timesheet can flow into payroll when `salary_slip_based_on_timesheet=1` on the structure.

**Gotchas**
1. **% completion method** (`percent_complete_method`): `Task Completion` (count), `Task
   Progress` (avg of each task's `progress`), or `Task Weight` (weighted by `task_weight`).
2. **Dependencies don't block** — `depends_on` is informational/Gantt scheduling; ERPNext
   doesn't prevent starting a task whose dependency is open. Closing a parent doesn't
   auto-close children.
3. **Timesheet rate is captured at log time** — changing Activity Cost later doesn't retro-update.
4. **Project costing is derived, not GL** — `total_costing_amount`, `total_billed_amount`,
   `gross_margin` are summaries from linked docs; accuracy depends on setting `project` on
   every cost doc.
5. **Group vs leaf tasks** — log time on leaf tasks (`is_group=0`).

---

# Assets

| DocType | Submittable? | Purpose |
|---|---|---|
| Asset | **Yes** | A capitalized fixed asset; gross value, depreciation, status, location. |
| Asset Category | No | Groups assets; default method, accounts, useful life. |
| Asset Category Account | No (child) | Per-company fixed-asset / accumulated-depr / expense accounts. |
| Finance Book | No | Parallel depreciation books (accounting vs tax). |
| Asset Finance Book | No (child) | Per-asset depreciation params per book (method, life, rate). |
| Asset Depreciation Schedule | **Yes** (v14+) | Standalone schedule generated per Asset + Finance Book. |
| Asset Movement | **Yes** | Transfer asset between locations/employees/warehouses. |
| Asset Maintenance / Maintenance Log | No / Yes | Plan / record of maintenance tasks. |
| Asset Repair | **Yes** | Repair event with cost; can capitalize cost / consume stock. |
| Asset Value Adjustment | **Yes** | Manually revalue (impairment/appreciation); adjusts depreciation. |
| Asset Capitalization | **Yes** (v14+) | Build a composite asset from consumed stock/assets + service; or decapitalize. |
| Asset Shift Factor | No (v14+) | Multiplier for shift-based (WDV) depreciation. |

**Workflow**

```
Asset Category (defaults: method, life, accounts)
Purchase Invoice / Receipt (item is_fixed_asset=1, or "Create Asset")
   └─► Asset (Draft) → set purchase value, available_for_use_date, depreciation params
         ├─► Submit → generates Asset Depreciation Schedule(s); posts capitalization GL
         ├─► scheduled job posts each Depreciation Entry (JE) on schedule dates
         ├─► Asset Movement / Repair / Value Adjustment (during life)
         └─► Disposal: "Sell Asset" → Sales Invoice (books gain/loss)
                       "Scrap Asset" → JE writing off WDV; status = Scrapped
```

- **CWIP:** if `enable_cwip_accounting`, purchase posts to Capital Work In Progress until
  `available_for_use_date`, then capitalization moves it to the fixed-asset account.

**Gotchas**
1. **Methods** (`depreciation_method`): `Straight Line`, `Written Down Value`/`Double
   Declining Balance` (rate on book value), `Manual`, `Manufacturing`.
2. **Booked rows lock; future rows recompute** — editing useful life mid-life only changes
   future rows. Use **Asset Value Adjustment** for impairments, not editing gross value.
3. **Multiple Finance Books** — each gets its own schedule + JEs (IFRS vs tax). Disposal must
   consider all books.
4. **Disposal needs a gain/loss account** — `disposal_account` in Company/Accounts Settings;
   missing it blocks disposal.
5. **`available_for_use_date` drives everything** — back-dated assets may post catch-up
   depreciation immediately on submit.
6. **Migrating mid-life / historical assets** — set `is_existing_asset=1` (so submit does **not**
   re-post the purchase cost — it's already in the GL), plus `opening_accumulated_depreciation`
   and `opening_number_of_booked_depreciations` (Asset-level) and
   `total_number_of_booked_depreciations` (per Finance Book row). `net_purchase_amount` is a
   **mandatory** field even when `gross_purchase_amount` is set. A Finance Book row (method /
   `frequency_of_depreciation` / `total_number_of_depreciations` / `depreciation_start_date`)
   must exist on the Asset or be inherited from the Asset Category.
7. **Submitting builds the schedule but doesn't post past rows in console/scripted creation** —
   to book depreciation whose `schedule_date` is already in the past (a catch-up reconstruction),
   call `erpnext.assets.doctype.asset.depreciation.post_depreciation_entries("<date>")` once;
   it posts every due row up to `<date>` across all assets (one Depreciation Entry JE each).
   First-year amounts are pro-rated from `available_for_use_date` (matches straight-line
   schedules with a partial first period).

---

# Support

| DocType | Submittable? | Purpose |
|---|---|---|
| Issue | No | Support ticket; status, priority, SLA timers, agreement fulfilment. |
| Issue Type / Issue Priority | No | Categorization; priority feeds SLA targets. |
| Service Level Agreement (SLA) | No | Response/resolution time per priority, support hours, holiday list, conditions. |
| Service Day | No (child) | Working-hours rows inside an SLA. |
| Warranty Claim | No | Customer claim under warranty/AMC; can spawn a Maintenance Visit. |
| Maintenance Schedule | **Yes** | Plan of preventive visits for sold items (generates a schedule). |
| Maintenance Visit | **Yes** | Record of a service visit (Scheduled / Unscheduled / Breakdown). |
| Support Settings | No (Single) | Default SLA behavior, email integration, allow resetting SLA. |

**Workflow**

```
SLA (priorities → response/resolution mins, support hours, holiday list)
   └─► Issue (priority + customer) → SLA timers (response_by, resolution_by)
         ├─► agent replies → first_responded_on
         └─► resolve/close → agreement_status = Fulfilled / Failed
Maintenance Schedule (from Sales Order / serial items)
   └─► scheduled dates → Maintenance Visit(s)   (also from Warranty Claim)
```

**Gotchas**
1. **SLA timer pausing** — `response_by`/`resolution_by` pause during configured "hold"
   statuses and outside support hours / on the Holiday List. No Holiday List/hours → timers
   run 24×7 and "fail" unexpectedly.
2. **Maintenance Schedule only plans** — actual service is logged as a **Maintenance Visit**;
   serial-numbered items schedule per serial.

---

# Quality

| DocType | Submittable? | Purpose |
|---|---|---|
| Quality Inspection | **Yes** | Inspect an item vs parameters at receipt/transfer/delivery/manufacture. |
| Quality Inspection Template | No | Reusable parameter set. |
| Quality Inspection Parameter | No | Master parameter (numeric/formula criteria). |
| Quality Inspection Reading | No (child) | Actual reading vs spec. |
| Quality Goal | No | Measurable objective with target + frequency. |
| Quality Procedure | No (tree) | Documented process steps (nested). |
| Quality Action / Resolution | No / child | Corrective/preventive action. |
| Quality Meeting / Agenda / Minutes | No / child | Review meetings. |
| Quality Feedback / Template | No | Stakeholder feedback. |
| Quality Review | No | Periodic review of a Quality Goal. |
| Non Conformance | No | A deviation from a Quality Procedure → drives Quality Action. |

**Workflow**

```
Quality Inspection Template (parameters + acceptance criteria)
   └─► Quality Inspection (reference_type = Purchase Receipt / Stock Entry / Delivery Note / Job Card)
         → readings vs spec → status Accepted/Rejected → can block submission of the referenced stock doc
```

**Gotchas**
1. **Inspection enforcement** is controlled by the **Item** master
   (`inspection_required_before_purchase` / `..._before_delivery`) + Stock Settings; without
   those flags, inspections are optional and block nothing.
2. **Most of Quality posts no ledgers** — Goal/Procedure/Review/Action form a CAPA loop
   (Non Conformance → Quality Action → Quality Review); only **Quality Inspection** has real
   transactional effect (blocking stock docs).
