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

The ROOT v3.1 source modules and verified historical conventions are now tracked in `main`. The code integration does **not** establish that the live PSGE checkout has been updated nor that services and schedules should be restarted. Before pulling main into the production checkout, verify the deployed configuration, source/runtime dependency hashes, active jobs and rollback reference. The file `config/autoreco_run3.json` in Git is a disabled reference template and may differ from the live local file.

The original commissioning documentation is preserved in the Git history of `autoreco-v3-lightweight` and `autoreco-run3-root31-release`; do not infer current operational status from historical statements in those branches.
