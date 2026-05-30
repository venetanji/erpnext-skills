# HR & Payroll Module (`hrms` app)

> HR was split out of ERPNext core into the standalone **`hrms`** (Frappe HR) app around v14.
> Install separately (`bench get-app hrms` → `bench --site <site> install-app hrms`). The
> DocTypes below live in `hrms`, not `erpnext` — the API path is the same
> (`/api/resource/Salary Slip`) but they won't exist if only `erpnext` is installed. Confirm
> with `frappe.get_installed_apps()`. Targets v14–v16.

## Organization & Employee

| DocType | Submittable? | Purpose |
|---|---|---|
| Employee | No | Master record of a person; central link target for all HR docs. |
| Department | No (tree) | Org unit; can carry leave/expense approvers. |
| Designation | No | Job title master. |
| Branch | No | Location/branch. |
| Employee Group | No | Grouping for bulk payroll/attendance. |
| Employee Grade | No | Pay grade; default salary structure + leave policy. |
| Employment Type | No | Full-time / contract etc. |

## Attendance & Shifts

| DocType | Submittable? | Purpose |
|---|---|---|
| Attendance | **Yes** | One day's presence/absence for one employee. |
| Attendance Request | **Yes** | Request to mark attendance (WFH, on-duty) for a date range. |
| Employee Checkin | No | Raw IN/OUT punch (biometric/API); processed into Attendance. |
| Shift Type | No | Start/end, grace, auto-attendance settings; links to checkins. |
| Shift Assignment | **Yes** | Assigns an employee to a Shift Type for a date range. |
| Shift Request | **Yes** | Employee request for a shift. |

## Leave

| DocType | Submittable? | Purpose |
|---|---|---|
| Leave Type | No | Defines a leave kind: paid, carry-forward, LWP, earned, max days, encashment. |
| Leave Allocation | **Yes** | Grants N leaves of a type to an employee for a period. |
| Leave Application | **Yes** | Request/record of leave taken; checks balance; needs approval. |
| Leave Policy | No | Bundle of (Leave Type → annual allocation) rows. |
| Leave Policy Assignment | **Yes** | Applies a Leave Policy to an employee (generates allocations). |
| Leave Period | No | Date range (year) for leave; basis for allocation. |
| Leave Control Panel | No (tool) | Bulk-allocate leave to many employees. |
| Leave Ledger Entry | Yes (auto) | Immutable balance ledger (created by allocation/application). |
| Leave Encashment | **Yes** | Pays out unused leave; can feed a Salary Slip. |
| Compensatory Leave Request | **Yes** | Earn comp-off for working holidays. |
| Holiday List | No | Calendar of holidays + weekly offs; attached to company/employee/shift. |

## Expenses & Advances

| DocType | Submittable? | Purpose |
|---|---|---|
| Expense Claim | **Yes** | Reimbursable expenses; posts GL on approval; settled via PE/JE. |
| Expense Claim Type | No | Category; default account. |
| Employee Advance | **Yes** | Cash advance; reconciled against claims/returns. |
| Travel Request | **Yes** | Request for travel (itinerary, funding, visa). |

## Payroll

| DocType | Submittable? | Purpose |
|---|---|---|
| Salary Component | No | An earning or deduction (Basic, HRA, PF, TDS); formula/condition, `abbr`. |
| Salary Structure | **Yes** | Template of earnings + deductions (with formulas) for a group. |
| Salary Structure Assignment | **Yes** | Binds a structure to one employee from a date; sets `base`, variable, `income_tax_slab`. |
| Salary Slip | **Yes** | Computed pay for one employee for one period; the payroll output. |
| Payroll Entry | **Yes** | Bulk run: generates many Salary Slips + accounting/bank entries. |
| Payroll Period | No | Fiscal payroll year; basis for tax-slab proration. |
| Income Tax Slab | **Yes** | Progressive tax brackets + standard deductions for a period. |
| Payroll Settings | No (Single) | `payroll_based_on` (Leave/Attendance), include holidays in working days, etc. |
| Additional Salary | **Yes** | One-off earning/deduction (bonus, ad-hoc) merged into next Salary Slip. |
| Salary Withholding | **Yes** (v15+) | Hold an employee's salary for N cycles. |

## Lifecycle, Recruitment, Performance

| DocType | Submittable? | Purpose |
|---|---|---|
| Employee Onboarding / Separation | **Yes** | Hire / exit checklists; can create tasks/Employee. |
| Employee Promotion / Transfer / Grievance | **Yes** | Lifecycle events; can update Employee on submit. |
| Job Opening / Job Applicant | No | A vacancy / a candidate. |
| Job Offer | **Yes** | Offer to an applicant with terms. |
| Appraisal | **Yes** | Performance review; KRA + goals scoring. |
| Appraisal Template / Appraisal Cycle | No / Yes | Define KRAs; run org-wide cycles (v14+). |

## Payroll workflow

```
Salary Component(s) (Basic, HRA, PF, Income Tax…)
   └─► Salary Structure (submit; earnings+deductions with formulas, e.g. HRA = 0.5*base)
         └─► Salary Structure Assignment (per employee: base, income_tax_slab, from_date)
               └─► Payroll Entry (company/branch/dept + period)
                     ├─► Create Salary Slips → one Salary Slip per employee (submit)
                     ├─► Submit Salary Slips
                     ├─► Make Accrual / Journal Entry → JE (Dr expense, Cr payable)
                     └─► Make Bank Entry / Payment → JE / Payment Entry (pay payable)
```

- **Income Tax Slab** is linked on the Salary Structure Assignment; tax is computed on the
  slip when a component has `variable_based_on_taxable_salary=1`.
- `payroll_based_on` (Payroll Settings) = Leave or Attendance decides how `payment_days`
  derive from `total_working_days` minus LWP.

## Gotchas

1. **`hrms` is a separate app** — DocTypes won't exist with only `erpnext` installed.
2. **Salary Slip recalculation is sticky** — a submitted slip is frozen. To fix base pay,
   cancel the slip, fix the **Salary Structure Assignment**, and regenerate. Editing the
   Salary Structure alone does nothing to existing slips.
3. **Leave balance is ledger-based** — balance = sum of **Leave Ledger Entry** rows (created
   by Allocation/Application/Encashment). Use Leave Policy Assignment, not manual allocations.
4. **Auto-attendance chain** — Biometric → **Employee Checkin** → (Shift Type with
   `enable_auto_attendance=1` + scheduled job) → **Attendance**. Without an active **Shift
   Assignment** mapping the employee to a shift, checkins won't convert.
5. **Salary Component formulas use abbreviations** — reference component `abbr` (e.g. `B`) and
   `base`/`gross_pay`. A duplicate abbr or typo'd `condition` silently yields zero.
6. **Payroll Entry double-posting** — re-running accrual JEs duplicates expense. Drive
   postings from the Payroll Entry buttons (it tracks `salary_slips_created`/`_submitted`),
   not manual JEs.

## Key reports

Salary Register · Monthly Attendance Sheet · Employee Leave Balance · Salary Payments Based
on Payment Mode · Income Tax Deductions · Employee Birthday · Recruitment Analytics.
