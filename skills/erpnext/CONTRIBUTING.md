# Contributing to the `erpnext` skill

This skill is **knowledge-first by design**. It was distilled from the official docs to
give agents accurate, version-aware facts about ERPNext/Frappe. The intended second pass
is to harden it with **vetted Python scripts** and **operational knowledge** learned from a
*running* instance. This file tells a human or an agent how to do that without degrading
the skill.

> **Augmenting this skill requires a running ERPNext instance and access to an agent's
> accumulated memories/transcripts.** Knowledge added here should be *verified against a
> live system*, not invented. When in doubt, run it against the instance first.

## What belongs where

| Kind of content | Goes in | Format |
|---|---|---|
| Facts: DocTypes, fieldtypes, API endpoints, bench commands, module flows | `references/*.md` | Dense markdown, tables + short code blocks |
| Reusable automation: a script you'd run more than once | `scripts/<name>.py` (or `.sh`) | Standalone, documented header, idempotent |
| A multi-step *procedure* (a runbook) | A **new sibling skill** in `skills/`, not here | Its own `SKILL.md` |
| Hard-won gotchas / traps for one module | "Gotchas" section of that module's reference | Numbered list, each with the *symptom* |

Keep this skill **general and re-usable**. Anything site-specific (company name, account
abbreviations, container names, hostnames) must be a **placeholder**, never a real value —
follow the placeholder convention below. Real client data must never land here.

## Placeholder convention (mirror of the companion repo)

| Placeholder | Meaning |
|---|---|
| `<site>` | The Frappe site name (e.g. the value passed to `bench --site`) |
| `<backend-container>` | Docker container running the frappe backend (e.g. `frappe_docker-backend-1`) |
| `<host>` | Public hostname of the instance |
| `{COMPANY_NAME}` / `{ABBR}` | Company legal name / ERPNext company abbreviation (account suffix) |
| `<api_key>:<api_secret>` | A User's API credentials |
| `<DocType>`, `<name>`, `<field>` | Generic DocType / record name / fieldname slots |

## How to add a script (the second-pass workflow)

1. **Prove it on a live instance first.** Don't commit a script you haven't run. Use a
   throwaway/test site or read-only operations while developing.
2. **Make it standalone and self-describing.** Every script starts with a header block:
   ```python
   #!/usr/bin/env python3
   """<one-line purpose>.

   USAGE:   bench --site <site> execute path/to/script.fn --kwargs '{...}'
       OR:  docker exec -i <backend-container> bench --site <site> execute ...
   REQUIRES: <bench / frappe.init / external lib>
   READS:    <DocTypes it reads>
   WRITES:   <DocTypes it writes — or "read-only">
   IDEMPOTENT: yes/no — <how re-running behaves>
   VERSION:  tested on ERPNext v<x>
   """
   ```
3. **Prefer the `frappe.init` transactional pattern for writes** (see `references/bench.md`)
   so commits actually persist. End writes with an explicit `frappe.db.commit()`.
4. **Make writes idempotent** where possible: pre-check by business key before `insert`,
   so re-running doesn't duplicate documents (Universal Hard Rule #3).
5. **Dry-run by default** for anything destructive: accept a `dry_run=True` kwarg that logs
   the intended change without committing.
6. **No hardcoded site-specific values** — take them as kwargs or read from config.
7. **Register it** in `scripts/README.md` (one-line table row) and link it from the
   relevant `references/*.md` section so agents discover it.

### Script template

A ready-to-copy skeleton lives at **`scripts/_template.py`**. Copy it, fill the header,
implement, test against a live site, then register it.

## How to add / improve a reference fact

1. **Cite the source** when it's a documented fact — link the `docs.frappe.io` page in a
   comment or footnote so the next maintainer can re-verify.
2. **Mark version differences** explicitly (e.g. "v15+: …"). ERPNext changes across majors.
3. **Verify against the live instance** using the introspection commands in `SKILL.md`
   ("Introspect the live system"). If the live system disagrees with the docs, prefer the
   live behavior and note the discrepancy.
4. **Keep it dense.** These files are read by agents under context pressure — tables and
   tight code blocks beat prose. One screen of signal > three screens of narrative.

## Folding in agent memories / operational knowledge

The richest source for the second pass is what an agent *learned the hard way* on a real
instance (recurring traps, the exact kwargs that worked, the report filter that returns
the right shape). To harvest that:

1. Review the agent's transcripts/memories for ERPNext interactions.
2. For each recurring pattern, decide: is it a **fact** (→ reference), a **reusable
   action** (→ script), or a **procedure** (→ new runbook skill)?
3. Generalize: strip site-specifics to placeholders, confirm it's not a one-off.
4. Add the *symptom* alongside each gotcha so a future agent recognizes the situation, not
   just the fix.

## Quality bar

- ✅ Verified on a running instance (or clearly marked "from docs, unverified").
- ✅ Version-tagged where behavior differs across majors.
- ✅ No real client data; placeholders only.
- ✅ Scripts: documented header, idempotent or dry-run-able, registered in `scripts/README.md`.
- ✅ Dense, skimmable, cross-linked.
- ❌ No procedures/runbooks in this skill — those are sibling skills.
