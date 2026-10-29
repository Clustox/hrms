# Clustox HRMS — Environments, CI/CD & Observability

**Last updated:** 2026-10-29

This documents the deploy architecture, the dev environment, the CI/CD pipeline,
and error logging (GlitchTip/Sentry) for the Clustox Frappe HR system. It is the
reference for how changes get from a laptop to production safely.

> Secrets (GlitchTip admin password, API keys) are **not** in this file. See the
> team's secret store / the ops owner. Sentry **DSN public keys** below are
> client-side keys (not secret) and are safe to keep here.

---

## 1. Environments

Host: a single Linux box (`69.30.247.141`, 72 cores / 251 GB RAM). Everything
runs in Docker. Stack: **Frappe/ERPNext v17, HRMS, Helpdesk, Telephony**;
**Python 3.14**; **MariaDB 10.8.8**; **Redis**.

| | **Production** | **Dev / staging** |
|---|---|---|
| URL | https://frappe.theclustox.com | https://frappe-dev.theclustox.com |
| App checkout (host) | `/opt/app/hrms` | `/opt/app/hrms-dev` |
| Git branch | `develop` | `dev` |
| Compose file | `/opt/app/hrms/docker/docker-compose.yml` | `/opt/app/hrms-dev-stack/docker-compose.yml` |
| Compose project | `docker` | `dev` |
| Containers | `docker-frappe-1` / `docker-mariadb-1` / `docker-redis-1` | `dev-frappe-1` / `dev-mariadb-1` / `dev-redis-1` |
| App port | 8000 | 8001 |
| Jenkinsfile | `Jenkinsfile` | `Jenkinsfile.dev` |
| Site | `hrms.localhost` | `hrms.localhost` (separate DB) |

The app code is **bind-mounted** into the container, so the host checkout *is*
the running app. Data lives in the named volumes `mariadb-data` and
`frappe-bench` — these **survive `docker compose down`**. **Never `down -v`** (it
deletes the data).

### Promotion flow

```
work on `dev`  ──push──▶  dev pipeline deploys frappe-dev   (test here)
                              │
                          merge dev → develop
                              │
                     prod pipeline deploys frappe (production)
```

---

## 2. CI/CD pipeline

Jenkins runs natively on the host (`:8080`, auth-gated) and **auto-triggers on
push** via a GitHub webhook. Each branch has its own pipeline.

### Stages (both `Jenkinsfile` and `Jenkinsfile.dev`)

1. **Checkout** (+ SonarQube analysis / quality gate on prod only — non-blocking).
2. **Sync deploy checkout** — `git reset --hard origin/<branch>` on the host
   app checkout, so the deployed tree always matches the branch.
3. **Redeploy & migrate** — the important one:
   ```
   compose down
   compose up -d mariadb redis          # data services only
   wait for mariadb
   compose run --rm --no-deps -w /home/frappe/frappe-bench frappe \
       bench --site hrms.localhost migrate
       bench build --app hrms
       bench --site hrms.localhost clear-cache
   compose up -d                        # start the app
   ```
4. **Health check** — polls the site until it returns 200.

### Why migrate runs in a throwaway container while the app is down

Running `bench migrate` against a **live** stack deadlocks: a migration's
`ALTER TABLE` waits on metadata locks held by the running workers/scheduler and
fails with `Lock wait timeout exceeded (1205)`. Migrating with **no app
processes running** (DB up, app down, migrate in a disposable `compose run`
container) is the only reliable way. This is why the deploy brings the app down
first, migrates, then starts it.

**Result:** a push to `dev` (or a merge to `develop`) is now a complete,
hands-off deploy — schema migrated, assets rebuilt, caches cleared. No manual
`bench migrate` / `build` / `clear-cache` afterwards.

### Gotchas learned
- `bench` must run with `-w /home/frappe/frappe-bench` (the container's workdir
  is `/home/frappe`), otherwise it errors `No such option: --site`.
- Deploying through the app container with `compose exec` **does not work** for
  migrate — it hits the lock above. Use the throwaway `compose run` instead.
- To clear a stuck dev migrate manually: kill idle-in-transaction connections on
  `dev-mariadb-1` (`information_schema.innodb_trx` → `KILL <tid>`, root pw `123`),
  then `down → up -d mariadb redis → compose run --rm --no-deps frappe bench …
  migrate → up -d`.

### Manual deploy (if ever needed, mirrors the pipeline)
```bash
CF=/opt/app/hrms-dev-stack/docker-compose.yml; P=dev      # or /opt/app/hrms/docker/..., P=docker
sudo docker compose -f $CF -p $P down
sudo docker compose -f $CF -p $P up -d mariadb redis
RUN="sudo docker compose -f $CF -p $P run --rm --no-deps -w /home/frappe/frappe-bench frappe"
$RUN bench --site hrms.localhost migrate
$RUN bench build --app hrms
$RUN bench --site hrms.localhost clear-cache
sudo docker compose -f $CF -p $P up -d
```

---

## 3. Dev environment: clone from prod + anonymize

The dev site is a **full clone of the prod database, with all PII anonymized and
email disabled**, so testing and deploys happen here first.

### Refresh dev from prod (one command)

```bash
bash /opt/app/hrms-dev/scripts/dev/refresh_dev.sh
```

This: backs up the prod DB (read-only on prod) → sets `mute_emails=1` in the dev
site config → restores the backup into dev → disables all email accounts +
flushes the queue → runs the anonymizer → prints a verification line
(`clean=true` means **zero** real emails/domains remain).

- `scripts/dev/refresh_dev.sh` — the orchestration (host).
- `scripts/dev/anonymize_dev.py` — the anonymizer (deterministic, idempotent,
  self-verifying; **guarded to the dev site + `mute_emails` only**, so it can
  never run against prod).

### What the anonymizer does
- Replaces names, all emails (→ `@example.com`), phones, DOB, addresses; zeroes
  salary; blanks bank/passport.
- **Renames User login emails** via `frappe.rename_doc` (User PK = email). Note:
  this Frappe's `rename_doc` has **no `ignore_permissions` kwarg**, and
  `User.username`/`mobile_no` are **UNIQUE** → set to `NULL`, not `""`.
- Sweeps DB-wide: `owner`/`modified_by` → `Administrator`; `_assign`/`_liked_by`/
  `_comments` regex-scrubbed; free-text bodies (Comment/Communication) regex-
  scrubbed; company domains replaced; logs/cache truncated
  (`__UserSettings`, `__global_search`, Activity/View/Error/Version/Notification
  Log); email-keyed PKs renamed (Job Applicant, HD Agent).
- **Verifies** by scanning **all ~12,762 text columns** for `@clustox.com`,
  `theclustox.com`, `@yopmail.com` → target is 0.

### Email safety (why dev can never email real people)
Triple-locked: `mute_emails=1` in the site config (file, survives restore) **+**
every Email Account disabled **+** the Email Queue flushed. Private files
(CVs/IDs — PII) are **not** copied to dev at all.

---

## 4. Error logging — GlitchTip (self-hosted, Sentry-compatible)

GlitchTip speaks the Sentry DSN/ingest protocol, so Frappe's **native** Sentry
integration works against it. ~4 light containers.

- Compose: `/opt/app/glitchtip/docker-compose.yml` (project `glitchtip`):
  `gt-postgres` / `gt-redis` / `gt-web` (`8100:8080`) / `gt-worker` / `gt-migrate`.
  Image pinned by digest.
- **UI** (internal-only): SSH tunnel then open the local port:
  ```bash
  ssh -L 8100:127.0.0.1:8100 hamad@69.30.247.141   # then http://localhost:8100
  ```
  Admin user: `admin@example.com` (password in the secret store). Org: **Clustox**.
- **Projects / DSN public keys** (public keys, safe to keep):
  - `hrms-prod` → id **1**, key `594700bf-c8d1-484a-ae22-ff155bcb5fe0`
  - `hrms-dev` → id **2**, key `8744ff63-1d32-47d3-a387-85e48c459b48`
  - DSN form: `http://<key>@69.30.247.141:8100/<id>` (Frappe containers reach
    GlitchTip via the host IP on `:8100`).

### How Frappe is wired to send errors (THREE requirements)
1. `sentry-sdk` installed in the bench env
   (`/home/frappe/frappe-bench/env/bin/pip install sentry-sdk`). **Install it
   before step 2** — `app.py` imports `sentry_sdk` only inside
   `if FRAPPE_SENTRY_DSN:`, so setting the env without the package crashes app
   import.
2. Env vars on the frappe service (`environment:` in the compose):
   - `FRAPPE_SENTRY_DSN=http://<key>@69.30.247.141:8100/<id>`
   - `SENTRY_TRACING_SAMPLE_RATE=0.1` (enables the WSGI middleware + light tracing)
3. **System Settings `enable_telemetry = 1`** — the real gate:
   `frappe/utils/sentry.capture_exception` (called from `log_error`) early-returns
   unless telemetry is on. (Side effect: `enable_telemetry` also sends anonymized
   usage stats to Frappe's own telemetry. Accepted for this project.)

Capture path is `log_error → capture_exception` (Frappe catches request
exceptions itself, so the WSGI middleware alone is not enough).

**Status:** dev is fully wired and proven (a web 500 is captured and grouped in
the `hrms-dev` project). Prod is staged — see below.

---

## 5. Prod cutover runbook (pending a maintenance window)

Promoting the pipeline fix **and** wiring prod Sentry is **one ~2–3 min prod
restart** (the app is down only during migrate/build). Steps:

1. `sudo docker exec docker-frappe-1 /home/frappe/frappe-bench/env/bin/pip install sentry-sdk`
2. Set prod System Settings `enable_telemetry = 1`.
3. Add to `docker/docker-compose.yml` (frappe service `environment:`), commit:
   ```
   - FRAPPE_SENTRY_DSN=http://594700bf-c8d1-484a-ae22-ff155bcb5fe0@69.30.247.141:8100/1
   - SENTRY_TRACING_SAMPLE_RATE=0.1
   ```
4. **Merge `dev` → `develop`.** The prod pipeline then deploys: applies the
   pipeline fix, prod's pending migrations, and the Sentry env — in the
   down→migrate→up flow.
5. Verify: trigger a prod test 500 and confirm it appears in GlitchTip `hrms-prod`.

### Open follow-ups (optional)
- Expose the GlitchTip UI via an nginx `sentry.theclustox.com` subdomain (needs a
  DNS record + TLS cert) instead of the SSH tunnel.
- Make the `sentry-sdk` install reproducible (add to app deps / init.sh) so a
  from-scratch bench has it without the manual pip step.
