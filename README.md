# erpnext-skills

Claude Code / Agent SDK **skills** that give an agent core operating knowledge of
[Frappe Framework](https://docs.frappe.io/framework/) and
[ERPNext](https://docs.frappe.io/erpnext/) — the data model, the bench CLI, the REST/RPC API,
and a module-by-module map of the business domain.

These are **knowledge** skills: they teach an agent *which DocTypes exist, how they relate,
and how to drive a running instance correctly*. They are meant to underpin task-specific
runbooks (like the back-office skills in
[`shicheng-agents/claude-skills`](https://github.com/shicheng-agents/claude-skills)) by
supplying the ERPNext facts those runbooks assume.

## Skills

| Skill | What it covers |
|---|---|
| [`erpnext`](skills/erpnext/SKILL.md) | The metadata/DocType data model, bench + site operations, REST/RPC/Python API, and references for every module: Accounting, Selling/CRM, Buying, Stock, Manufacturing, HR/Payroll, Projects/Assets/Support/Quality, and Customization/Admin. |

### Layout

```
skills/erpnext/
├── SKILL.md                 # entry point: mental model, routing, universal hard rules, introspection
├── CONTRIBUTING.md          # how to augment the skill with scripts + operational knowledge (second pass)
├── references/              # dense, version-aware reference files (progressive disclosure)
│   ├── data-model.md        # DocTypes, fieldtypes, naming, child/single doctypes, customization
│   ├── bench.md             # bench CLI, sites, backup/migrate, docker, scheduler, frappe.init
│   ├── api.md               # REST + RPC + Python ORM, auth, reports, docstatus lifecycle
│   ├── accounting.md        # GL Entry, JE, Payment Entry, invoices, multi-currency
│   ├── selling-crm.md       # Lead→Opportunity→Quotation→SO→DN→SI, pricing
│   ├── buying.md            # MR→RFQ→SQ→PO→PR→PI, SRBNB
│   ├── stock.md             # Item, Warehouse, Stock Entry, SLE, Bin, valuation, batches
│   ├── manufacturing.md     # BOM, Work Order, Job Card, Production Plan, subcontracting
│   ├── hr-payroll.md        # hrms app: Employee, Attendance, Leave, Salary, Payroll Entry
│   ├── projects-assets-support.md
│   └── customization.md     # Custom Field, Client/Server Script, Workflow, Roles, Reports, fixtures
└── scripts/                 # reusable Python/shell helpers (sparse; filled in the second pass)
    ├── _template.py         # skeleton: header, dry-run guard, idempotency, frappe.init runner
    └── README.md            # how to run + the script registry
```

## Installation

These are [Claude Code skills](https://docs.claude.com/en/docs/claude-code/skills). The
harness auto-loads skills under `~/.claude/skills/` or a project's `.claude/skills/`. Clone
this repo into one of those, or symlink the skill:

```bash
git clone https://github.com/venetanji/erpnext-skills.git ~/.claude/skills-source
ln -s ~/.claude/skills-source/skills/erpnext ~/.claude/skills/erpnext
```

## Scope & versioning

- Targets **Frappe/ERPNext v14–v16**; version-specific behavior (HR/CRM as separate apps,
  v15 subcontracting rework, Serial and Batch Bundle) is called out inline.
- Distilled from the official docs at <https://docs.frappe.io/>. **Every site can be
  customized** — the skill teaches agents to introspect the live system (`frappe.get_meta`,
  Custom Field queries) and trust it over the docs when they disagree.
- Contains **no client-specific data**; placeholders (`<site>`, `<backend-container>`,
  `{COMPANY_NAME}`, `{ABBR}`) follow the same convention as the companion repo.

## Augmenting the skill

The second pass adds vetted Python scripts and hard-won operational knowledge harvested from
agents running against a live instance. See
[`skills/erpnext/CONTRIBUTING.md`](skills/erpnext/CONTRIBUTING.md) for what goes where, the
script template + quality bar, and how to fold in agent memories.

## License

MIT (to be added).
