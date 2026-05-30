# Customization & Administration (Frappe Framework level)

> Targets Frappe v14–v16. These are the most important DocTypes for an agent that *modifies*
> a live instance. They live in the `frappe` app, not `erpnext`. Most require System Manager /
> Administrator. **After changing DocType/meta, run `bench migrate`** (and `clear-cache`) or
> the change persists only in the DB and may be lost on update.

## Schema & field customization

| DocType | Purpose |
|---|---|
| DocType | The definition of a data type itself (fields, permissions, naming). Editing a *standard* DocType requires developer mode (writes to JSON); otherwise blocked. |
| DocField | A field definition row (child of DocType). |
| Custom Field | Adds a field to an existing DocType **without** touching its core definition. The safe way to extend standard DocTypes; survives `bench update`. |
| Property Setter | Overrides a single property of an existing field/DocType (mandatory, label, hidden, options, default). Created automatically by Customize Form. |
| Customize Form | UI tool (`/app/customize-form`) to bulk-create Custom Fields + Property Setters on any DocType. |
| Custom DocType | A user-created DocType (`custom=1`), stored in DB, safe across updates. |
| DocType Link / Action / State | Connections tab, custom buttons, Workflow-state styling. |
| Module Def | Defines a module namespace for grouping custom DocTypes. |

## Scripting & automation

| DocType | Purpose |
|---|---|
| Client Script | JS in the browser form/list (`frm` API); per DocType, Form or List. Replaces old "Custom Script". |
| Server Script | Python run server-side (sandboxed `frappe.safe_exec`): types = DocType Event (hooks), API (whitelisted endpoint), Scheduler Event, Permission Query. |
| Workflow | State machine over a DocType: states + transitions gated by roles/conditions. |
| Workflow State | Master of a state name + style; each maps to a `doc_status` (0/1/2). |
| Workflow Action (+ Master) | A transition action name ("Approve"); per-user action items at runtime. |
| Workflow Transition | child | state + action + next_state + allowed role + condition. |
| Notification | Event-/schedule-/value-triggered alert (email/system/Slack); condition + recipients + template. |
| Email Template | Reusable Jinja subject/body for notifications + comms. |
| Webhook | Outbound HTTP POST on doc events (after_insert/on_submit…); headers, secret, payload mapping. |
| Scheduled Job Type | Registered cron-like jobs; trigger/inspect; logs in Scheduled Job Log. |
| Auto Repeat | Recurring-document generator (subscriptions). |

## Presentation & reporting

| DocType | Purpose |
|---|---|
| Print Format | Print/PDF layout; Standard, Jinja/HTML, or Print Format Builder (drag-drop). |
| Print Settings | Single — global print/PDF options (page size, footer, PDF engine). |
| Letter Head | Header/footer HTML + image for documents. |
| Report | Query Report (raw SQL), Script Report (Python `execute()` → columns+data), or Report Builder (saved filters/columns on a DocType). |
| Dashboard / Dashboard Chart / Number Card | A KPI dashboard, a chart, a single-KPI tile. |
| Workspace | Left-nav page composition (shortcuts, cards, charts) — replaces old Desk Pages (v13+). |
| Web Form | Public/portal form that creates/edits a DocType from the website. |

## Access control & identity

| DocType | Purpose |
|---|---|
| User | Login identity; roles via child table. |
| Role | A named permission bundle; attached to DocPerm rows. |
| Role Profile | A reusable set of roles applied to users. |
| Module Profile | Hides modules for a class of users. |
| User Permission | Row-level restriction: user X sees only records where a link field = value Y. |
| DocPerm / Custom DocPerm | child | Permission rules per role per DocType (read/write/create/submit/cancel/amend + permlevel). |
| User Type / User Group | Portal vs system users; grouping. |

## System configuration (Singles)

| DocType | Purpose |
|---|---|
| System Settings | Global: timezone, date/number format, session expiry, password policy, language. |
| Naming Series | Tool — manage `naming_series` prefixes + current counters (`tabSeries`). |
| Email Account / Email Domain | Inbound (IMAP/POP) + outbound (SMTP) mail config. |
| Global Defaults / Stock / Accounts / Buying / Selling Settings | Module-level Singles controlling validation behavior. |

## Making customizations without code (UI)

- **Add a field:** Customize Form → pick DocType → add row → Save (creates a **Custom
  Field**). To override a *standard* field's property, it creates a **Property Setter**.
  Neither touches the core DocType JSON, so both survive `bench update`.
- **No-code automation:** **Server Script** (DocType Event) for server rules; **Client
  Script** for in-form UX; **Notification** for alerts; **Workflow** for approval routing;
  **Auto Repeat** for recurring docs.
- **No-code reports:** Report Builder (saved view) or Query Report (read-only SQL, requires
  System Manager). Dashboards = Number Cards + Dashboard Charts on a Workspace.

## Fixtures & migration (how customizations move dev→prod)

- **Fixtures:** in a custom app's `hooks.py`, list
  `fixtures = ["Custom Field", "Property Setter", {"dt":"Client Script","filters":[["module","=","X"]]}]`.
  `bench export-fixtures` writes them to JSON in the app; `bench migrate` re-imports.
- **Export Customizations:** Customize Form → menu → Export Customizations writes Custom
  Fields + Property Setters to a target app/module as JSON, auto-imported on migrate.
- **`bench migrate`** runs DB schema sync (from DocType changes), patches, and fixture import.
  Safe prod sequence: `bench backup --with-files` → `bench update` → (auto `bench migrate`) →
  `bench restart`.

## Gotchas

1. **Custom Field vs editing DocType** — never edit a *standard* DocType's fields directly
   (needs developer mode, breaks on update). Use **Custom Field** / **Property Setter** via
   Customize Form. Custom DocTypes (`custom=1`) are DB-stored and safe.
2. **Server Script is sandboxed** — `frappe.safe_exec`: no arbitrary imports, restricted
   builtins, limited API. Code needing full Python (external libs, file IO) must live in a
   real app. Server Scripts can be globally disabled (`server_script_enabled`).
3. **Workflow vs docstatus** — each Workflow State maps to `doc_status` (0/1/2). A "submit"
   transition must land on a state with `doc_status=1`, else users "approve" without actually
   submitting (no GL entries). Once a Workflow exists, the normal Submit button is replaced by
   workflow actions.
4. **User Permission is restrictive AND can leak** — with `apply_to_all_doctypes=1` it
   cascades to every DocType with that link field. The "Strict User Permissions" system
   setting controls whether records with no link value are visible.
5. **Naming Series counter drift** — editing the current value below the existing max causes
   duplicate-name collisions; series prefixes in `naming_series` options must match exactly.
6. **Bulk ops skip hooks** — `frappe.db.set_value` and direct SQL bypass the ORM `save`, so
   they do **not** fire doc events / Server Scripts / Webhooks / Notifications. Use
   `doc.save()` / `.submit()` in automation when you need side effects; use `db.set_value`
   only to silently patch.
7. **`bench migrate` is mandatory after meta changes** — UI field changes hit the DB
   immediately, but adding a Custom DocType or importing fixtures into another site requires
   migrate (+ `clear-cache`).
