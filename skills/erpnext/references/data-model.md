# The Data Model — DocTypes & Fieldtypes

> Targets Frappe v14–v16. This is the foundation: understand it and the rest of ERPNext
> becomes navigable. Sources: docs.frappe.io/framework (DocTypes, Naming, Fieldtypes,
> Controllers).

## 1. What a DocType is

A **DocType** is the core building block of a Frappe app: a metadata-driven definition that
describes **both the data model and the form/list UI**. Creating a DocType (a JSON
definition + optional Python/JS controllers) generates a backing SQL table named
**`tab<DocType>`** (e.g. `Sales Order` → `tabSales Order`). DocTypes use **singular** names.
The UI is auto-generated: List View at `/app/<doctype>`, Form at `/app/<doctype>/<name>`.
The DocType definition is *itself* a DocType ("DocType is a DocType"), enabling runtime
metadata changes.

### Standard fields (on every document / `tab<DocType>` row)

| Column | Type | Meaning |
|---|---|---|
| `name` | varchar | Primary key (the document identifier) |
| `owner` | varchar | User who created the doc |
| `creation` | datetime | Created timestamp |
| `modified` | datetime | Last modified (used for optimistic-lock / conflict detection) |
| `modified_by` | varchar | User who last modified |
| `docstatus` | int | 0 Draft / 1 Submitted / 2 Cancelled |
| `idx` | int | Position/order index |
| `_user_tags`, `_comments`, `_assign`, `_liked_by` | text | System metadata (tags, comment cache, assignments, likes) |

**Child-table rows** additionally carry: `parent` (`name` of owning doc), `parentfield`
(the Table fieldname on the parent), `parenttype` (parent DocType), `idx` (row order).

## 2. Fieldtypes

Each field has a `fieldtype`. **(no column)** marks layout/virtual types that create no DB
column.

**Text / string**
- **Data** — single-line, ≤140 chars; supports validation (Email, Phone, URL, Name, IBAN).
- **Small Text** — multi-line, larger than Data. **Text** — general multi-line.
- **Long Text** — effectively unlimited. **Text Editor** — WYSIWYG rich text (HTML).
- **Code** — code input w/ syntax highlight. **HTML Editor** — HTML source.
- **Markdown Editor** — Markdown w/ preview. **JSON** — JSON column.
- **Password** — masked, encrypted-at-rest. **Phone** — number w/ country code.
- **Color** — color picker/hex. **Barcode** — stores code + renders barcode.
- **Signature** — captured signature image. **Autocomplete** — free text + static suggestions.

**Numeric**
- **Int** — integer. **Float** — up to 9 decimals. **Currency** — money, ≤6 decimals, shows symbol.
- **Percent** — percentage. **Check** — boolean (0/1). **Rating** — star rating (stored as fraction).
- **Duration** — time span in seconds (renders days/hrs/min/sec).

**Date & time** — **Date**, **Datetime** (system TZ), **Time**.

**Selection & relationships**
- **Select** — dropdown from newline-separated static options.
- **Link** — reference to another DocType's document (stores target `name`); enables fetch.
- **Dynamic Link** — reference whose target DocType is named by a sibling field (polymorphic).
- **Table** — embedded child table (rows of a child DocType; stored in the child's table).
- **Table MultiSelect** — Link+Table hybrid: pick multiple, stored as child rows.

**Files & media**
- **Attach** / **Attach Image** — file attachment (stores file URL).
- **Image** *(no column)* — display-only; renders from another Attach field via Options.
- **Geolocation** — points/lines/polygons as GeoJSON.

**Display / layout (no column)**
- **Section Break**, **Column Break**, **Tab Break** — form layout.
- **Heading** — section heading. **HTML** — renders raw HTML from Options.
- **Button** — triggers a client/server action. **Fold** — collapse point (deprecated).
- **Read Only** — display-only (still backed by a column; typically fetched/computed).

> The meta layer maintains `no_value_fields` (Section/Column/Tab Break, HTML, Button,
> Heading, Image, Fold) which never produce a scalar column, and `table_fields` (Table,
> Table MultiSelect) which store data in the child DocType's table.

## 3. DocType configuration (key flags)

- **autoname / naming** — how `name` is generated (§7).
- **is_submittable** — enables Draft/Submitted/Cancelled (docstatus) + Submit/Cancel.
- **istable** (`is_child_table`) — child table DocType; gets `parent`/`parentfield`/`parenttype`.
- **issingle** — Single DocType: exactly one record, stored as key-value rows in `tabSingles`.
- **is_tree** — nested-set tree; adds `lft`, `rgt`, `old_parent`, a parent link; enables
  `descendants of` filters.
- **track_changes** — records a Version doc per change (field-level audit trail).
- **module** — owning module. **custom** — `1` for user-created DocTypes (DB + fixtures),
  `0` for standard (app source `.json` + Python controller).
- UI toggles: **quick_entry**, **editable_grid**, **allow_rename**, **allow_import**,
  **read_only**, **in_create**, **hide_toolbar**, **max_attachments**.

## 4. Child tables

A **Table**/**Table MultiSelect** field embeds rows of a child DocType (`istable=1`). Rows
live in the **child's** `tab<Child DocType>` table, each storing `parent`, `parentfield`,
`parenttype`, `idx`.

```python
so = frappe.get_doc("Sales Order", "SO-0001")
for row in so.items:                                # 'items' is the Table fieldname
    print(row.item_code, row.qty, row.idx, row.parent)
so.append("items", {"item_code": "A", "qty": 5})    # add a row
so.save()                                            # children persisted with parent
```

Children are inserted/updated/deleted automatically with the parent. You normally never
`insert()` a child doc directly.

## 5. Single DocTypes

`issingle=1` → exactly one logical record, used for settings (**System Settings**, **Stock
Settings**, **Accounts Settings**, **Selling/Buying Settings**, **Website Settings**). No
`tab<DocType>` data table; values live as `(doctype, field, value)` rows in **`tabSingles`**.

```python
settings = frappe.get_single("System Settings")                   # full doc
tz = frappe.db.get_single_value("System Settings", "time_zone")   # one field, fast
settings.time_zone = "UTC"; settings.save()
```

## 6. Links & relationships

- **Link** stores the target `name`; `options` names the target DocType.
- **fetch_from** — `fetch_from = "<link_field>.<source_field>"` auto-copies a value from the
  linked doc (e.g. `customer_name` ← `customer.customer_name`). Read-only mirror by default.
- **Dynamic Link** — a Link/Select field naming the DocType + the Dynamic Link field holding
  the record name (e.g. Contact → any party).
- Link integrity: on delete, Frappe checks for documents linking to the record unless
  `ignore_links` is set.

## 7. Naming series

| Strategy | `autoname` value | Result |
|---|---|---|
| By field | `field:<fieldname>` | `name` = that field's value (must be unique) |
| Naming series | `naming_series:` | uses the doc's `naming_series` Select field, e.g. `SINV-.YYYY.-.#####` |
| Pattern / format | `format:` / `INV-.YYYY.-.#####` | static text + variables |
| Hash | `hash` | random hash |
| Prompt | `prompt` | user types the name |
| Autoincrement | `autoincrement` | sequential integer PK (v13+) |
| Script | (controller `autoname()`) | controller sets `self.name` |

**Pattern variables:** `.#####` (zero-padded counter; digit count = number of `#`), date
tokens `.YYYY.` `.MM.` `.DD.` `.WW.`, `.timestamp.`, field refs `.{fieldname}.`. Example
`ACC-SINV-.YYYY.-.#####` → `ACC-SINV-2026-00001`.

**Counter table — `tabSeries`:** each distinct prefix has a row storing its `current`
integer, incremented on each new name.

> **Gotcha — counters never roll back.** Deleting a document does **not** decrement
> `tabSeries`; a rolled-back transaction can still leave the counter advanced. Sequence
> numbers have gaps and are not a reliable contiguous count. Never set `naming_series`
> counters by hand; to reset, use the **Naming Series** tool or update `tabSeries.current`
> carefully.

Precedence: a controller `autoname()` overrides the DocType setting; **Document Naming Rule**
records (conditional, prioritized) override per-condition. Child DocTypes get hash names.

## 8. Customization (extend without forking app source)

- **Custom Field** — add a field to any DocType (adds a column to `tab<DocType>`); survives updates.
- **Property Setter** — override one property of a field/DocType (mandatory, label, hidden)
  without editing the standard definition. Created by Customize Form.
- **Customize Form** (`/app/customize-form`) — UI to add Custom Fields + Property Setters.
- **Client Script** — JS in the Desk form/list (form events, field behavior).
- **Server Script** — sandboxed Python server-side: DocType Event, Scheduler Event, API
  (whitelisted endpoint), Permission Query. No deploy needed.
- **Custom DocType** — user-created (`custom=1`), defined entirely in DB/UI.
- **hooks.py `doc_events`** (app code) — attach `validate`/`on_submit`/etc. to any DocType.

See `references/customization.md` for full detail.

## 9. Meta — introspecting a DocType

```python
meta = frappe.get_meta("Sales Order")
meta.fields                      # list of DocField objects
meta.get_field("customer")       # one DocField (fieldtype, options, reqd, ...)
meta.get_table_fields()          # all Table/child-table fields
meta.get_link_fields()           # all Link fields
meta.get_valid_columns()         # actual DB columns (excludes layout fields)
meta.is_submittable
meta.issingle; meta.istable; meta.is_tree
meta.autoname
```

`frappe.get_meta` returns a cached `Meta` built from the DocType + Custom Fields + Property
Setters, so it reflects customizations. Use it to discover fields/types/options
programmatically — the reliable way to "ask the live system" what exists (see SKILL.md
"Introspect the live system").
