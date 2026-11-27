# Run3 ROOT v3.1 — operations and maintenance

This runbook documents the existing reconstruction and migration workflow. It is a source-code reference, **not an instruction to repeat commissioning or reactivate production**. The authoritative data-format guide is [`iq_root_v31.md`](iq_root_v31.md).

## Production checkout and runtime

- Official source tree: `/home/mazzitel/HFGW/analysis` on branch `main`.
- Runtime state: `/home/mazzitel/HFGW/analysis-runtime/autoreco/Run3`, separate from Git.
- The existing cron wrapper is `autoreco/run_autoreco_cron_configured.sh`; historically configured to invoke the Run3 cron path every five minutes.
- The runtime contains the validated ROOT 3.1 dependency package, worker receipts, logs and migration state. Do **not** replace it from Git or delete it during source consolidation.

The original Root31 commissioning procedure used validated job receipts and dependency SHA-256 checks, preserved the live configuration fields not explicitly changed, updated ROOT-only options atomically and retained the existing production lock. Do not rerun historical commissioning blindly on an already activated system.

## Inspection without changing jobs

```bash
repo=/home/mazzitel/HFGW/analysis
runtime=/home/mazzitel/HFGW/analysis-runtime/autoreco/Run3

git -C "$repo" status -sb
tail -n 100 "$runtime/logs/autoreco-$(date +%F).log"
condor_q -constraint 'FlashRun3Attempt isnt undefined' -af ClusterId JobStatus HoldReason FlashRun3Attempt

# Run read-only migration discovery only if its environment and inputs are configured:
"$repo/autoreco/run_autoreco_cron_configured.sh" --run3 --migrate-root --dry-run
```

The dry run distinguishes eligible, pending, already verified and potentially inconsistent files. Before running even read-only inspection, confirm the local runtime's configured paths and dependencies.

## Normal orchestration and migration semantics

The historic scheduling policy provided up to 20 normal reconstruction slots and up to 40 migration slots. The existing loop uses a common lock, distinct runtime counters, a bounded retry policy and evidence-based reconciliation of HTCondor job results. Submitted HDF5 jobs keep their original destinations until they finish. A ROOT result must be verified before the corresponding logbook version/path is changed, preserving `reco_done`.

Do **not** start a duplicate cron job or launch additional jobs merely to verify a Git merge. Handle held jobs only after checking the exact JobStatus, attempt identifier and receipt. Failed jobs may exhaust configured retry counts without being complete.

## Python analysis environment

The historical Python 3.9 runtime used CVMFS scientific packages and a persistent local `uproot-py39.tgz` archive. Use only the version/dependency path actually verified on the current host:

```bash
repo=/home/mazzitel/HFGW/analysis
runtime=/home/mazzitel/HFGW/analysis-runtime/autoreco/Run3
mkdir -p "$runtime/root31/python"
# Extract only if required and only if the archive has been previously verified.
# tar -xzf "$runtime/root31/uproot-py39.tgz" -C "$runtime/root31/python"
PYTHONPATH="$runtime/root31/python:/cvmfs/sft-flash.infn.it/package/python3.9/site-packages:examples" \
  python3.9 "$repo/examples/analyze_iq_run.py" /local/run01422_iq_v3.1.root /local/report-1422
```

## Storage reconciliation

A read-only audit script exists under `autoreco/root_storage_dry_run.py`. It requires real worker checksum evidence before declaring any HDF5 temporary or legacy product eligible for deletion. Without fresh remote evidence, **deletable bytes remain zero**. There is no automatic deletion of MIDAS raw or validated HDF5.

## Official-source consolidation (24 November 2026)

The ROOT v3.1 source modules and verified historical conventions are now tracked in `main`. The code integration does **not** establish that the live PSGE checkout has been updated nor that services and schedules should be restarted. Before pulling main into the production checkout, verify the deployed configuration, source/runtime dependency hashes, active jobs and rollback reference. The tracked disabled reference template is `config/autoreco_run3.example.json`. The operational `config/autoreco_run3.json` is Git-ignored and must be restored from the host's existing validated configuration before a production checkout update.

The original commissioning documentation is preserved in the Git history of `autoreco-v3-lightweight` and `autoreco-run3-root31-release`; do not infer current operational status from historical statements in those branches.

## Backlog recovery mode

The live host configuration enables a one-shot recovery by setting
`max_active` to 60 and adding
`"backlog_recovery": {"threshold": 20, "normal_max_active": 20}`.
Keep `max_submit_per_cycle` at 20. The existing five-minute cron checks the
policy on each normal ROOT production cycle. The active limit counts local
attempts, including idle and held jobs. Matchmaking still depends on the
pool's CPU, memory, disk and slot policy. The HDF5 migration lane has its
own eligibility policy and concurrency limit.

The scheduler counts unique archived, released runs from the live logbook
using normal ROOT production eligibility. A canonical ROOT publication
requires the scheduler's validated receipt and an archive entry. The
report separates outstanding runs, exhausted or explicitly deferred runs,
job states, and archive entries or receipts awaiting reconciliation.
Exhausted and deferred runs are excluded from the threshold but remain
visible. Missing archive data, failed reconciliation, or a failed query
does not establish that recovery is complete.

At 20 actionable outstanding runs or fewer, with publication and logbook
reconciliation consistent, cron atomically sets `max_active` to 20 and
removes the policy under the production lock. Existing attempts drain
without cancellation. New runs remain eligible at the normal limit.
There is no time expiration or automatic rearming. The official
`--run3 --dry-run` reports the calculation without changing configuration.

For manual rollback, acquire the existing production `.autoreco.lock`,
remove `backlog_recovery` and set `max_active` to the desired rollback
value (20 for normal operation, or 40 to restore the pre-change cap).
Keep the per-cycle cap at 20 and let existing jobs drain. The saved
pre-change host configuration can also be restored under the same lock.

## Late Rucio raw publications

In the 25–26 November logbook snapshots, unreleased raw files had
`reco_done=-1` and Rucio status 2 or 4. When Rucio released 23 of
those files, `rucio_status` became zero and `reco_done` stayed at
minus one. The original eligibility rule therefore skipped them.

The opt-in host setting `late_rucio_recovery: true` enables a ROOT-only
path for exactly this shape of row: released Rucio status, minus-one
reconstruction status, empty reconstruction version and output path,
canonical filename, a blank or 3.1 requested version, and a nonempty
raw file visible on the mounted Tier-1 archive. A visible ROOT object
blocks a new submission and calls for reconciliation. The usual state,
retry and capacity checks continue to apply.

The scheduler records the recovery marker in the attempt state. The
logbook row retains minus one until a valid ROOT publication receipt
has been reconciled. The guarded success update changes it to one
only if the release and reconstruction fields still match expectations.
To suspend new late admissions, remove the opt-in under the production
lock. Existing tagged attempts can still reconcile normally.

## Discord operational notifications

Normal Run3 cron cycles use the private mode-0600 webhook file under
`~/.config/flash-autoreco/discord-webhook` at send time. The notifier
uses bounded HTTPS and suppresses mentions and response bodies.
Delivery and state failures are logged as fixed messages and do not
alter submissions, retries or reconciliation. Dry runs never send.

Authorization alerts use only one unambiguous HTTPS approval link
present in explicit Condor challenge output on the expected
`condor.psge.cloud.infn.it` origin and `/key/` path. The scheduler
preserves restricted local diagnostics. It does not echo submission
stdout or stderr to the cron log while the notifier is active.

Other categories cover submission failures, HOLD, repeated or
exhausted reconstruction failures, invalid or persistently missing
publication evidence, persistent Google logbook failures and scheduler
exceptions. Incident state is atomically replaced in
`analysis-runtime/autoreco/Run3/discord-notifications.json` under the
existing lock. The state stores only incident keys, counters and send
times. Set `discord_reminder_seconds` to a positive integer to opt in
to reminders. The default is disabled. After a delivery failure,
the next cycle can retry without adding multiple delays to the current
cycle.

Recovery requires an accepted Condor cluster, an observed exit from
HOLD, a validated ROOT receipt, or a successful logbook update, as
appropriate. A generic scheduler exception is not automatically
declared recovered by an otherwise successful cron cycle.

## Persistent recovery and operator exclusions

The `auto_reco` column is operator-owned. Blank or zero enables
automatic admission and `-2` excludes a run. Unknown values fail
closed. The scheduler checks the flag in the snapshot and rereads
the exact row immediately before submitting. Exclusion does not
cancel a job or stop safe reconciliation. Existing attempt
diagnostics remain intact while excluded.

For the normal ROOT lane, the opt-in host setting
`"persistent_recovery": {}` scans all logbook runs above 680 with
at least 1,000 acquired events. The Rucio release, canonical raw
object and requested profile must pass validation. Old reconstruction
counters alone do not determine admission. Existing canonical ROOT
objects suppress submission. A ROOT claim with a missing object
requires review. The scheduler preserves explicit requested-version
conflicts, and checks both lanes for duplicate work. The worker
still validates the actual raw and ROOT data.

The defaults are two scientific attempts per episode, 24 hours
between exhausted episodes and three episodes total, including the
initial episode. Set positive integer `cooldown_seconds` and
`max_episodes` inside the policy to override those defaults. A new
episode requires an exact unsuccessful terminal Condor history record.
Recognized, nonzero-exit authorization failures without a matching
queue or history record are retried separately with a one-hour
`submission_cooldown_seconds` and a cap of three consecutive
`max_submission_failures`. A failed authorization submission does
not consume a scientific attempt. Unknown submit outcomes and generic
failures require review instead of assuming safe re-admission.

The original attempt records and monotonic attempt numbers survive
new episodes. Observed dispositions are written atomically to
`persistent-recovery.json` under the Run3 runtime. Disappearing
logbook rows remain marked unresolved. Discord incident keys separate
episodes and explain the manual exclusion flag. Recovery publication
uses the existing verified receipt and checks the original logbook
metadata again before updating. Positive existing completion counts
are retained; a new validated completion for a nonpositive or missing
counter records one. The scheduler never writes the operator flag.

Use an official dry run with `--recovery-report /path/to/new-file.json`
and a temporary config to inspect the entire candidate set before
activating the policy. Review conflicting historical profile requests
and anomalous raw inputs first. The existing five-minute cron is the
only production entry point.

### Google logbook operator view

The scheduler-owned fields are `auto_reco_status`, `auto_reco_error`
and `auto_reco_next_retry`. They show pending, running, cooling-down,
authentication-blocked, manually excluded, completed or other blocked
dispositions. Retry timestamps are UTC and are blank when there is
no scheduled retry. The error cell contains a short categorized
reason. It never contains diagnostic output or approval links.
Observed job changes appear on the next reconciliation cycle.

Install the three status headers and the operator-owned
`auto_reco_release` header as new columns to the right of `auto_reco`
with all data cells blank. Do this only after reviewing
`--dry-run --status-preview /path/to/new-file.json` and the optional
`--recovery-report`. The preview specifies exact header coordinates,
old and new cell values, skipped conflicts and the first bounded batch.
It does not change the sheet. After the schema and deployment are
approved, set `"recovery_logbook_status": true` together with the
persistent recovery policy to permit writes on regular cron cycles.
Only changed scheduler-owned cells are sent in one sparse RAW batch,
with at most 120 rows per cycle and intervention statuses prioritized.
Rows whose identity, control, reconstruction or status cells changed
between snapshots are deferred. Google Sheets has no atomic
compare-and-set for these cells; avoid moving rows or columns during
a scheduler write. Monitoring write failures do not stop reconstruction.

To release a temporary historical hold, review that run's input and
profile first. In that run's row, leave `auto_reco` blank or zero and
enter `root31:01143` for Run 1143 or `root31:01144` for Run 1144 in
`auto_reco_release`. The token is scoped to that run, and it is
rechecked immediately before submitting. Clear the token to reinstate
the hold for future attempts. A manual `auto_reco=-2` takes precedence.
Release does not override a conflicting requested version, a host
deferral, an existing ROOT product, an active attempt or an exhausted
recovery budget. An explicit historical version request can be changed
only by an authorized operator after reviewing that profile. The
scheduler writes neither control column and never assigns `-2`.
