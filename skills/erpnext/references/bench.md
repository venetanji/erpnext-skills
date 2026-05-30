# Bench & Site Operations Reference

> **Version notes:** Targets **Frappe / ERPNext v14, v15, v16**. Command syntax is stable
> across these; differences are minor (`bench execute` gained native `--arg/--kwarg`-by-name
> style, `bench update` takes a backup by default). Confirm with `bench version`. The
> `bench` CLI is [frappe/bench](https://github.com/frappe/bench); the *site* subcommands
> (`migrate`, `console`, `execute`, …) are dispatched by `frappe` itself.

## 0. Mental model

- **bench** = a directory (e.g. `/home/frappe/frappe-bench`) holding the Python env, apps,
  sites, and process config. Also the name of the CLI that operates on it.
- A **bench** hosts one or more **sites**. A site = a database + a config + file storage.
  Multi-tenant: one set of app code serves many sites.
- Commands that touch a database/site need `--site <site>` (placed **before** the
  subcommand). Bench-wide commands (start, build, get-app, update) do not.
- The default site (`sites/currentsite.txt`, set by `bench use <site>`) is used when
  `--site` is omitted for site-scoped commands. `--site all` runs against every site.

```
bench [--site <site>] <command> [args] [--flags]
```

---

## 1. bench CLI — operator command reference

### Process / lifecycle (bench-scoped — no `--site`)

| Command | Purpose |
|---|---|
| `bench start` | Start all dev processes from the `Procfile` (web, socketio, redis x3, watch, schedule, workers) in foreground. Dev only. |
| `bench restart` | Restart web + workers. In prod restarts supervisor/systemd units (`--web`, `--supervisor`, `--systemd` to scope). **Run after Python code changes.** |
| `bench version` | Print every installed app + version. `--format json`. |
| `bench doctor` | Diagnostic on the **scheduler** and workers (pending jobs per queue, scheduler status). |
| `bench pip <args>` | Run pip inside the bench's Python env. |

### Site lifecycle

```bash
# Create a site (bench-scoped; site name positional)
bench new-site <site> \
  --db-name <db> --admin-password <pw> \
  --mariadb-root-password <root-pw> \   # v15+ also accepts --db-root-password
  --install-app erpnext                 # optional, repeatable

bench --site <site> install-app erpnext           # install app on existing site
bench --site <site> install-app hrms payments     # multiple allowed

bench --site <site> reinstall          # WIPE DB + reinstall all apps (DESTRUCTIVE)

bench drop-site <site> \                # delete a site completely (DESTRUCTIVE)
  --root-login root --root-password <root-pw> \
  --archived-sites-path <path>          # optional: move instead of purge
bench drop-site <site> --force

bench use <site>                        # set bench default site
bench list-sites
bench --site <site> list-apps           # apps installed on this site
```

> `new-site`, `drop-site`, `reinstall <site>`, `use` take the site as a **positional** arg.
> `install-app`, `list-apps` need `--site`.

### Migrate / build / update

```bash
# Apply pending DB patches, sync DocType schema, rebuild search/indexes/translations.
# RUN AFTER: app install, code update, pulling new app versions.
bench --site <site> migrate
bench --site all migrate
bench --site <site> migrate --skip-failing          # continue past failing patches
bench --site <site> migrate --skip-search-index

# Rebuild front-end assets (JS/CSS). Bench-scoped. RUN AFTER JS/CSS changes.
bench build
bench build --app erpnext
bench build --production            # minified
bench build --hard-link             # for containers/NFS

# Full update: backup + git pull all apps + dep install + build + migrate + restart.
bench update
bench update --pull          # only git pull apps
bench update --patch         # only run migrations/patches
bench update --build         # only rebuild assets
bench update --requirements  # only reinstall deps
bench update --bench         # also update bench tool
bench update --no-backup     # skip pre-update backup
bench update --reset         # git reset --hard before pull (DISCARDS local changes)
```

### Apps (bench-scoped)

```bash
bench get-app <name>                              # from frappe registry
bench get-app https://github.com/org/repo.git     # from git URL
bench get-app <url> --branch version-15           # pin a branch
bench get-app /path/to/local/app                  # from filesystem
bench remove-app <app>                            # (uninstall from sites first)
bench exclude-app <app> / bench include-app <app> # skip/include during bench update
```

> Add an app to a running instance: `bench get-app <url> --branch <ver>` →
> `bench --site <site> install-app <app>` → `bench --site <site> migrate`.

### Backup & restore

```bash
bench --site <site> backup                  # DB only (gzip SQL) -> sites/<site>/private/backups/
bench --site <site> backup --with-files     # DB + public AND private files (full DR backup)
bench --site <site> backup --backup-path <dir>
bench backup-all-sites [--with-files]

# Restore (DESTRUCTIVE: overwrites current DB)
bench --site <site> restore /path/to/database.sql.gz
bench --site <site> restore <db_file> \
  --with-public-files /path/to/files.tar \
  --with-private-files /path/to/private-files.tar \
  --db-root-password <root-pw> \            # needed to (re)create the DB
  --admin-password <pw>
```

### Site config & secrets

```bash
bench --site <site> set-config key value              # -> sites/<site>/site_config.json
bench --site <site> set-config maintenance_mode 1
bench --site <site> set-config -g key value           # -g/--global -> common_site_config.json
bench --site <site> set-config --parse key '{"a":1}'  # value parsed as JSON
bench --site <site> show-config                       # EFFECTIVE merged config

bench config set-common-config -c <key> <value>       # common_site_config.json
bench config remove-common-config <key>

bench --site <site> set-admin-password <newpassword>  # reset Administrator pw
bench --site <site> set-admin-password                # prompts
bench --site <site> add-to-hosts                      # add hostname to /etc/hosts (dev, sudo)
```

### Cache (run after changing fixtures / custom fields / metadata-affecting code)

```bash
bench --site <site> clear-cache           # redis + DocType cache + defaults
bench --site <site> clear-website-cache   # web page / portal cache only
bench --site all clear-cache
```

### Interactive / introspection

```bash
bench --site <site> console               # IPython REPL, frappe initialised + connected
bench --site <site> console --autoreload  # reload edited modules in REPL
bench --site <site> mariadb               # SQL shell on the site DB (uses site creds)

bench --site <site> execute <dotted.path> ...   # see §2
bench --site <site> run-tests
bench --site <site> run-tests --app erpnext
bench --site <site> run-tests --doctype "Sales Order"
bench --site <site> run-tests --module erpnext.selling.doctype.sales_order.test_sales_order
```

### Maintenance mode & scheduler

```bash
bench --site <site> set-maintenance-mode on|off   # 503 to users; auto-set during migrate

bench --site <site> scheduler status|enable|disable|pause|resume
bench --site <site> enable-scheduler              # legacy aliases, still present
bench --site <site> disable-scheduler
bench --site <site> trigger-scheduler-event daily # fire an event immediately
```

### Data import / export

```bash
bench --site <site> data-import --doctype "Customer" --file customers.csv --type Insert  # or Update
bench --site <site> data-import --doctype Item --file items.csv --submit-after-import

bench --site <site> export-json "Sales Order" out.json
bench --site <site> export-json "Sales Order" out.json --name SO-0001   # single record

bench --site <site> export-fixtures                # from each app hooks.py `fixtures`
bench --site <site> export-fixtures --app erpnext
```

### Setup (production provisioning — bench-scoped)

```bash
bench setup requirements [--python|--node]   # (re)install deps
bench setup supervisor                        # config/supervisor.conf
bench setup nginx                             # config/nginx.conf
bench setup redis                             # the 3 redis configs
bench setup procfile                          # regenerate dev Procfile
bench setup production <user>                 # full production setup
bench setup env                               # (re)create virtualenv
```

### Workers / scheduler processes (usually supervisor-managed; run manually to debug)

```bash
bench worker --queue short
bench worker --queue default,short,long       # one worker draining multiple queues
bench schedule [--site <site>]                # scheduler tick loop (enqueues due events)
bench purge-jobs                              # purge pending periodic tasks from redis
```

---

## 2. `bench execute` — calling python by dotted path

`bench execute` imports and calls a Python function (any importable path — whitelisting is
for HTTP/API, not `execute`) inside a fully-initialised, **connected** site context.

```bash
bench --site <site> execute <module.path.to.function>
```

### Passing arguments

**Native named style (v14+):** flags after the path map to kwargs; bare flags become `True`.

```bash
bench --site <site> execute frappe.get_doc User Administrator              # positional args
bench --site <site> execute frappe.db.get_value \
  --doctype User --filters '{"name":"Administrator"}' --fieldname email
bench --site <site> execute frappe.get_list User --ignore_permissions      # bare flag -> True
```

**JSON `--args` / `--kwargs` style (all versions):**

```bash
bench --site <site> execute frappe.db.get_value --args "['User','Administrator','email']"
bench --site <site> execute frappe.db.set_value \
  --kwargs "{'doctype':'User','name':'Administrator','fieldname':'enabled','value':1}"
```

**Inline python expression:**

```bash
bench --site <site> execute "frappe.db.count('User')"
```

### `execute` vs `console` — the auto-commit gotcha

| | `bench execute` | `bench console` |
|---|---|---|
| Form | one function call from the shell | interactive IPython REPL |
| Good for | scripted/repeatable one-shots, cron, CI | exploration, debugging |
| **DB commit** | **auto-commits** on success | **does NOT auto-commit** |

> **Critical:** `bench console` does **not** commit automatically — `set_value`, `doc.save()`,
> `delete_doc` are rolled back on exit unless you call `frappe.db.commit()`. `bench execute`
> commits for you when the function returns without error. The #1 "my change didn't save"
> cause is a missing `frappe.db.commit()`.

---

## 3. `frappe.init` pattern — standalone transactional scripts

To run a Python script through the bench virtualenv (not via `execute`/`console`), bootstrap
Frappe yourself: pick a site, open a DB connection, do work, then **commit**. This is the
preferred pattern for any multi-step / transactional write (see `CONTRIBUTING.md`).

```python
import frappe

frappe.init(site="<site>")    # load site_config + common_site_config, set frappe.local
frappe.connect()              # open the DB connection for the site

try:
    doc = frappe.get_doc("Item", "ITEM-0001")
    doc.description = "Updated via script"
    doc.save()
    frappe.db.set_value("Stock Settings", None, "allow_negative_stock", 1)
    frappe.db.commit()        # REQUIRED — nothing persists without this
except Exception:
    frappe.db.rollback()
    raise
finally:
    frappe.destroy()          # tear down connection / local context
```

Run with the bench interpreter so env + apps resolve:

```bash
cd /home/frappe/frappe-bench && ./env/bin/python myscript.py
```

Or as a one-liner via heredoc (common in dockerized installs — see companion repo's
`/bookkeeper` skill):

```bash
docker exec -i <backend-container> bash -c '/home/frappe/frappe-bench/env/bin/python <<PY
import frappe; frappe.init(site="<site>"); frappe.connect()
# ... work ...
frappe.db.commit()
PY'
```

> **Why commit is needed:** Frappe wraps DB work in a transaction tied to the request/job.
> Standalone scripts and `bench console` have no framework boundary that commits for you;
> writes are discarded at process exit unless you `frappe.db.commit()`. `frappe.init(site=)`
> must precede `frappe.connect()`.

---

## 4. Docker (frappe_docker)

In the official [frappe/frappe_docker](https://github.com/frappe/frappe_docker) Compose
stack the bench lives **inside the `backend` service container** at
`/home/frappe/frappe-bench`. Run bench by exec-ing into that container.

```bash
docker compose -p <project> exec backend bench --site <site> <command> ...
docker compose -p <project> exec backend bash          # shell in /home/frappe/frappe-bench
docker exec -it <project>-backend-1 bench --site <site> clear-cache   # plain docker exec
```

Common operations:

```bash
docker compose -p frappe exec backend bench new-site <site> \
  --db-root-password <db-pw> --admin-password <admin-pw> --install-app erpnext
docker compose -p frappe exec backend bench --site <site> install-app erpnext
docker compose -p frappe exec backend bench --site <site> migrate
docker compose -p frappe exec backend bench --site <site> backup --with-files
```

**Caveat:** wait for `db` to be healthy and the `configurator` container to exit before
creating a site, else `new-site` can't connect.

Config/data live on a shared `sites` volume mounted into backend, frontend, and
worker/scheduler containers:

```
/home/frappe/frappe-bench/sites/
├── common_site_config.json   # shared: db_host, redis_*, scheduler_tick_interval (configurator-injected)
├── apps.txt
└── <site>/site_config.json   # per-site: db_name, db_password, encryption_key
```

Separate containers run the long-lived processes — `backend` (gunicorn), `frontend` (nginx
+ assets + proxy), `websocket` (socketio), `queue-short`/`queue-long` (workers), `scheduler`.
After installing/updating code: `migrate`, then
`docker compose restart backend queue-short queue-long scheduler`.

---

## 5. frappe-bench directory layout

```
frappe-bench/
├── apps/                       # source of each app (git repos): frappe/, erpnext/, hrms/ ...
├── config/                     # generated infra config
│   ├── redis_cache.conf        # redis for cache
│   ├── redis_queue.conf        # redis for job queue (RQ)
│   ├── supervisor.conf         # (prod) process supervision
│   └── nginx.conf              # (prod) reverse proxy + static assets
├── env/                        # Python virtualenv; all apps + deps installed here
├── logs/                       # per-process logs (web.log, worker.log, schedule.log, …)
├── Procfile                    # dev process definitions (used by `bench start`)
└── sites/
    ├── apps.txt                # ordered list of apps in this bench
    ├── assets/                 # built JS/CSS bundles (output of `bench build`)
    ├── common_site_config.json # config SHARED by all sites
    └── <site>/
        ├── site_config.json    # per-site: db_name, db_password, encryption_key, maintenance_mode, developer_mode
        ├── private/            # private files; includes private/backups/ (where `bench backup` writes)
        └── public/             # publicly served files (/files/<name>)
```

- **Config precedence:** `site_config.json` overrides `common_site_config.json`.
  `bench --site <site> show-config` prints the merged result.
- **Secrets:** `encryption_key` and `db_password` live in `site_config.json` — back it up;
  losing `encryption_key` makes stored passwords/OAuth tokens unrecoverable.

---

## 6. Scheduler, background jobs & workers

### Queues (Redis + RQ)

| Queue | Default timeout | Use for |
|---|---|---|
| `short` | 300s | quick tasks |
| `default` | 300s | general |
| `long` | 1500s | heavy/slow tasks |

### `frappe.enqueue`

```python
frappe.enqueue(
    method,                     # callable OR "dotted.module.path"
    queue="default",            # short | default | long
    timeout=None,               # override queue default (seconds)
    now=False,                  # True -> run inline (no worker)
    job_name=None,
    enqueue_after_commit=False, # only enqueue once current DB txn commits
    at_front=False,
    **kwargs,                   # forwarded to method
)

frappe.enqueue_doc(doctype, name, "controller_method", queue="long", timeout=4000, param="x")
```

> Use `enqueue_after_commit=True` when the job depends on data written in the current
> request — else the worker may run before your txn commits and read stale/missing rows.

### Scheduler events (in each app's `hooks.py`)

```python
scheduler_events = {
    "all":     ["app.tasks.frequent_task"],        # every tick (default 60s)
    "hourly":  ["app.tasks.update_database"],
    "daily":   ["app.tasks.manage_recurring_invoices"],
    "weekly":  ["app.tasks.weekly_task"],
    "monthly": ["app.tasks.monthly_task"],
    "daily_long": ["app.tasks.take_backups_daily"],# *_long variants run on the long queue
    "cron": {"15 18 * * *": ["app.tasks.delete_barcodes"]},
}
```

- Tick interval = `scheduler_tick_interval` in `common_site_config.json` (default 60s).
- Scheduler must be **enabled per site** (`bench --site <site> scheduler enable`) and not
  paused. `bench doctor` shows status + pending counts.
- **After editing `scheduler_events`, run `bench --site <site> migrate`** to register.

---

## 7. Operational gotchas (read before acting on a live instance)

1. **`migrate` auto-enables maintenance mode** (503s while patches/schema sync run). Don't
   run casually on busy production; schedule a window; `backup --with-files` first.
2. **Clear cache after metadata/code changes.** Custom fields, property setters, fixtures,
   DocType JSON often won't show until `clear-cache`; portal pages also need `clear-website-cache`.
3. **`bench build` after any JS/CSS change**, then hard refresh.
4. **Restart workers after Python code changes.** Workers/gunicorn import code once at boot;
   new logic (incl. enqueued jobs + scheduler tasks) needs `bench restart` (or restart the
   worker/scheduler supervisor units / docker containers).
5. **`developer_mode`** (`set-config developer_mode 1`) enables creating/exporting DocTypes
   to disk + full tracebacks. **Never leave on in production.**
6. **Console doesn't commit; `execute` does** (§2). Forgetting `frappe.db.commit()` is the
   most common silent-failure.
7. **`reinstall`, `drop-site`, `restore`, `update --reset` are destructive.** Backup first.
8. **`--site` placement** must be **before** the subcommand: `bench --site x migrate`.
9. **Run from the bench root** (`cd /home/frappe/frappe-bench`).
10. **`--site all` fans out to every tenant** — double-check before `migrate`/`clear-cache --site all`.

---

### Sources
- [Bench Commands](https://docs.frappe.io/framework/user/en/bench/bench-commands), [Frappe Commands](https://docs.frappe.io/framework/user/en/bench/frappe-commands)
- [bench execute](https://docs.frappe.io/framework/user/en/bench/reference/execute), [Cheatsheet](https://docs.frappe.io/framework/user/en/bench/resources/bench-commands-cheatsheet)
- [Directory structure](https://docs.frappe.io/framework/user/en/basics/directory-structure), [Background Jobs](https://docs.frappe.io/framework/user/en/api/background_jobs)
- [frappe/frappe_docker](https://github.com/frappe/frappe_docker), [frappe/bench](https://github.com/frappe/bench)
