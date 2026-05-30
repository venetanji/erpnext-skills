# The API — REST + RPC + Python ORM

> Targets Frappe v14–v16. Sources: docs.frappe.io/framework (REST API, Document API,
> Database API, Controllers, Naming).

## 1. REST API

The framework auto-generates a REST interface for **every** DocType at
`/api/resource/<DocType>`. The DocType name is used verbatim (URL-encode spaces, e.g.
`Sales%20Order`).

| Action | Method | Endpoint | Body |
|---|---|---|---|
| List | `GET` | `/api/resource/<DocType>` | — |
| Create | `POST` | `/api/resource/<DocType>` | JSON of field values |
| Read one | `GET` | `/api/resource/<DocType>/<name>` | — |
| Update | `PUT` | `/api/resource/<DocType>/<name>` | JSON of changed fields |
| Delete | `DELETE` | `/api/resource/<DocType>/<name>` | — |

Responses wrap data under `data`. Errors carry `exc` (traceback) + `exc_type`.

### Query parameters (list GET)

| Param | Purpose | Example |
|---|---|---|
| `fields` | JSON array of columns | `fields=["name","status"]` |
| `filters` | JSON list of `[field, op, value]`, ANDed. Short `{"status":"Open"}` also works | `filters=[["status","=","Open"]]` |
| `or_filters` | Same syntax, ORed | `or_filters=[["priority","=","High"]]` |
| `limit_start` | Pagination offset (0-based) | `limit_start=20` |
| `limit_page_length` (alias `limit`) | Page size (default 20; `0` = all) | `limit_page_length=50` |
| `order_by` | `field direction` | `order_by=creation desc` |
| `parent` | Parent DocType when querying child-table rows | `parent=Sales Order` |
| `debug` | Echo executed SQL | `debug=true` |

A bare list call (no `fields`) returns only `name` values.

### Filter operators

`=`, `!=`, `>`, `<`, `>=`, `<=`, `like`, `not like`, `in`, `not in`, `between`,
`is` (value `"set"`/`"not set"`), and tree ops `descendants of` / `ancestors of`.
- `like`: SQL `%` wildcards — `["subject","like","%urgent%"]`.
- `in`: list — `["status","in",["Open","Working"]]`.
- `between`: 2-element list — `["date","between",["2024-01-01","2024-12-31"]]`.
- `is set`: `["customer","is","set"]`.

### Example curl

```bash
# List with filters, fields, pagination, sort
curl -G 'https://<host>/api/resource/Task' \
  -H 'Authorization: token <api_key>:<api_secret>' \
  --data-urlencode 'fields=["name","subject","status"]' \
  --data-urlencode 'filters=[["status","=","Open"],["priority","=","High"]]' \
  --data-urlencode 'order_by=creation desc' \
  --data-urlencode 'limit_page_length=20'

# Create (child rows inline under the table fieldname)
curl -X POST 'https://<host>/api/resource/Sales Order' \
  -H 'Authorization: token <api_key>:<api_secret>' -H 'Content-Type: application/json' \
  -d '{"customer":"ACME","items":[{"item_code":"A","qty":2}]}'

# Read one / Update / Delete
curl  'https://<host>/api/resource/ToDo/abc123' -H 'Authorization: token <k>:<s>'
curl -X PUT    'https://<host>/api/resource/ToDo/abc123' -H 'Authorization: token <k>:<s>' \
  -H 'Content-Type: application/json' -d '{"status":"Closed"}'
curl -X DELETE 'https://<host>/api/resource/ToDo/abc123' -H 'Authorization: token <k>:<s>'
```

## 2. RPC / Method API

Any whitelisted Python function is callable at its dotted path:

```
GET|POST /api/method/<app>.<module>.<...>.<function>
```

- **GET** for read-only; **POST** for state-changing (auto-commits on success).
- Args via query string (GET) or form/JSON body (POST), matched to parameter names.
- Return value is JSON under `message`: `{"message": ...}`.

### `frappe.client.*` — generic document RPC (all respect permissions)

| Method | Key params | Purpose |
|---|---|---|
| `frappe.client.get` | `doctype`, `name`, `filters` | Full document (dict, incl. children) |
| `frappe.client.get_list` | `doctype`, `filters`, `fields`, `order_by`, `limit_*`, `parent` | List query (respects perms) |
| `frappe.client.get_value` | `doctype`, `fieldname`, `filters` | One/several field values |
| `frappe.client.get_count` | `doctype`, `filters` | Row count |
| `frappe.client.set_value` | `doctype`, `name`, `fieldname`, `value` | Update field(s); runs validation |
| `frappe.client.insert` | `doc` (dict) | Insert a new document |
| `frappe.client.insert_many` | `docs` (list) | Bulk insert |
| `frappe.client.save` | `doc` (dict) | Save an existing document |
| `frappe.client.submit` | `doc` (dict) | Submit (docstatus 0→1) |
| `frappe.client.cancel` | `doctype`, `name` | Cancel (docstatus 1→2) |
| `frappe.client.delete` | `doctype`, `name` | Delete |
| `frappe.client.rename_doc` | `doctype`, `old_name`, `new_name`, `merge` | Rename PK |

```bash
curl -G 'https://<host>/api/method/frappe.client.get_value' \
  -H 'Authorization: token <k>:<s>' \
  --data-urlencode 'doctype=Customer' \
  --data-urlencode 'filters={"customer_name":"ACME"}' \
  --data-urlencode 'fieldname=["name","territory"]'
```

These are also the workhorses for `bench execute` (see `references/bench.md`):
```bash
$EB bench --site <site> execute frappe.client.get_list \
  --kwargs '{"doctype":"Sales Invoice","filters":{"docstatus":1},"fields":["name","grand_total"]}'
```

### Reports

```
GET /api/method/frappe.desk.query_report.run?report_name=<Report Name>&filters=<JSON>
```
Returns `{"message": {"result": [...], "columns": [...]}}`. Via bench:
```bash
$EB bench --site <site> execute frappe.desk.query_report.run \
  --kwargs '{"report_name":"General Ledger","filters":{"company":"{COMPANY_NAME}","from_date":"2026-01-01","to_date":"2026-03-31"}}'
```

### File upload

```bash
curl -X POST 'https://<host>/api/method/upload_file' -H 'Authorization: token <k>:<s>' \
  -F 'file=@/path/to/file.png' -F 'doctype=ToDo' -F 'docname=abc123' -F 'is_private=1'
```

## 3. Authentication

**Token-based (recommended).** Header `Authorization: token <api_key>:<api_secret>`.
Generate on a User: User record → Settings → API Access → "Generate Keys". The **API Secret**
is shown only once. Programmatically: `frappe.core.doctype.user.user.generate_keys(user)`.

**Password / session.** POST `/api/method/login` with `{"usr":..., "pwd":...}` → sets an
`sid` cookie. Logout `/api/method/logout`.

**OAuth2.** Bearer tokens via `Authorization: Bearer <access_token>`.

Verify creds with `/api/method/frappe.auth.get_logged_user`.

## 4. Python server-side API

### Fetching
```python
doc = frappe.get_doc("Task", "TASK00002")                     # load existing
doc = frappe.get_doc({"doctype": "Task", "subject": "X"})     # build new (in-memory)
doc = frappe.new_doc("Task")                                   # blank new doc
doc = frappe.get_last_doc("Task", filters={"status":"Open"})
doc = frappe.get_cached_doc("System Settings")                 # cache-first
```
`get_doc` raises `frappe.DoesNotExistError` if missing. For a Single, `name` == DocType name.

### Querying
```python
# Ignores permissions — use in trusted server code / jobs:
rows = frappe.get_all("Task", filters={"status":"Open"},
    fields=["name","subject"], order_by="creation desc",
    limit_start=0, limit_page_length=20, pluck="name")   # pluck -> flat list

# Respects user permissions:
rows = frappe.get_list("Task", filters=..., fields=...)
```
**Key distinction:** `frappe.get_all` / `frappe.db.get_all` **bypass** permission checks;
`frappe.get_list` / `frappe.db.get_list` **apply** the session user's permissions.
`frappe.get_all` ≡ `frappe.get_list(..., ignore_permissions=True)`.

### Direct DB access (`frappe.db`)
```python
frappe.db.get_value("Task", "T1", "subject")                    # one value
frappe.db.get_value("Task", "T1", ["subject","status"], as_dict=1)
frappe.db.get_value("Task", {"status":"Open"}, "subject")       # filter form
frappe.db.set_value("Task", "T1", "subject", "New")             # NO validation, NO hooks
frappe.db.set_value("Task", "T1", {"subject":"X","status":"Open"})
frappe.db.get_single_value("System Settings", "time_zone")
frappe.db.exists("User", "jane@example.com")                    # name or None
frappe.db.count("Task", {"status":"Open"})
frappe.db.delete("Error Log", {"creation": ("<", cutoff)})      # bulk DML delete
frappe.db.sql("""SELECT name FROM `tabTask` WHERE status=%(s)s""",
              {"s":"Open"}, as_dict=True)                        # raw SQL, parametrized
```
`frappe.db.set_value` writes straight to the DB — skips controller hooks/validation. Always
parametrize `frappe.db.sql` (`%(name)s`/`%s`); backtick-quote tables as `` `tab<DocType>` ``.

### Mutating (with hooks/validation)
```python
doc.insert(ignore_permissions=False, ignore_mandatory=False, ignore_if_duplicate=False)
doc.save()
doc.submit()        # docstatus=1, runs before_submit/on_submit
doc.cancel()        # docstatus=2, runs before_cancel/on_cancel
doc.delete()        # runs on_trash/after_delete
doc.reload()
doc.db_set("price", 2300, update_modified=True)   # write one field directly + update in-memory
doc.append("items", {"item_code":"A","qty":2})    # add child row
frappe.rename_doc("Task", "OLD", "NEW", merge=False)
frappe.delete_doc("Task", "TASK00002", force=False)
```

### Transactions
```python
frappe.db.commit()      # web requests/jobs auto-commit on success; needed in console/scripts
frappe.db.rollback()    # or rollback(save_point="sp")
frappe.db.savepoint("sp")
```
Each HTTP request / background job is one transaction (commit on success, rollback on
uncaught exception). In `bench console` and standalone `frappe.init` scripts you **must**
call `frappe.db.commit()` yourself — see `references/bench.md` §2–3.

### `frappe.call`
```python
frappe.call("frappe.client.get_value", doctype="User", filters={...}, fieldname="name")
```

## 5. Whitelisting

```python
@frappe.whitelist()                      # requires authenticated session/token
def my_method(arg1, arg2=None): ...

@frappe.whitelist(allow_guest=True)      # callable without login (webhooks, public forms)
def public_method(): ...

@frappe.whitelist(methods=["POST"])      # restrict HTTP verbs
def change_state(...): ...
```
Without the decorator, HTTP calls raise `PermissionError`. All HTTP-supplied args arrive as
**strings** — cast explicitly (`int(...)`, `frappe.parse_json(...)`).

## 6. Document lifecycle & docstatus

| Value | State | Meaning |
|---|---|---|
| `0` | Draft | Editable; default for new docs |
| `1` | Submitted | Locked; only post-submit-allowed fields editable |
| `2` | Cancelled | Reversed; immutable |

Only DocTypes flagged **`is_submittable`** participate in submit/cancel. A cancelled doc can
be **amended** — a copy with `amended_from` set and name suffix `-1`, `-2`, …

### Controller hook order (methods on the DocType's Python controller)

- **Insert:** `before_naming` → `autoname` → `before_insert` → `before_validate` → `validate`
  → `before_save` → *(db insert)* → `after_insert` → `on_update` → `on_change`
- **Save existing:** `before_validate` → `validate` → `before_save` → *(db update)* →
  `on_update` → `on_change`
- **Submit:** `before_validate` → `validate` → `before_submit` → *(docstatus=1)* →
  `on_submit` → `on_change`
- **Cancel:** `before_cancel` → *(docstatus=2)* → `on_cancel` → `on_change`
- **Update after submit:** `before_update_after_submit` → *(db update)* →
  `on_update_after_submit` → `on_change`
- **Delete:** `on_trash` → *(db delete)* → `after_delete`

`validate` is the standard place to `frappe.throw(...)` to abort a save. `on_submit`/
`on_cancel` are where ledger postings + side effects belong. App-level `hooks.py`
`doc_events` can attach the same events to any DocType externally.
