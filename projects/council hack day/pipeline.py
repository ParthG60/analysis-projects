"""One-command refresh + build for Council Receipts.

Runs, in order:
  1. Registry prep   — the "*_all" builders that derive the master council registry
                       (scorecard_imd.csv) and every dataset keyed off it.
  2. Data fetchers   — the lighter per-run pulls (ombudsman, borrowing, elections,
                       QoL time series, contracts).
  3. Build + verify  — bake site/data.json, search indexes, preflight checks.

Designed to be the single entrypoint used by the scheduled GitHub Action
(see site/.github/workflows/refresh.yml).

    python pipeline.py                 # prep + fetch + build + verify
    python pipeline.py --skip-prep     # skip registry builders (use existing CSVs)
    python pipeline.py --skip-fetch    # rebuild from existing data_england/*.csv only
    python pipeline.py --skip-contracts  # skip the slow Contracts Finder fetch
    python pipeline.py --prep-only     # run the registry builders, then stop

Exit code is non-zero if any step fails or a preflight invariant breaks.
"""
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent

# Registry prep: order matters. scorecard_imd.py is the master registry; everything
# keyed on ons_code reads it, so it must run before population/control/qol/etc.
# england_profile.py must precede england_scorecard.py (which reads profile_all.csv).
PREP_STEPS = [
    ("Council name map", ["england_name_map.py"]),
    ("Registry (IMD scorecard)", ["scorecard_imd.py"]),
    ("Population", ["population_all.py"]),
    ("Council profiles", ["england_profile.py"]),
    ("Socio-economic scorecard", ["england_scorecard.py"]),
    ("Political control", ["control_all.py"]),
    ("Quality of life", ["data_england/qol_all.py"]),
    ("Ethnicity", ["data_england/ethnicity_all.py"]),
    ("Age bands", ["data_england/age_bands_all.py"]),
    ("Financial distress", ["data_england/financial_distress.py"]),
]


def run(label, args, timeout=None):
    print(f"\n=== {label} ===")
    t0 = time.time()
    proc = subprocess.run([sys.executable] + args, cwd=ROOT, timeout=timeout)
    dt = time.time() - t0
    if proc.returncode != 0:
        print(f"!!! {label} failed (exit {proc.returncode}) after {dt:.0f}s")
        sys.exit(proc.returncode)
    print(f"--- {label} done in {dt:.0f}s")


def main():
    skip_fetch = "--skip-fetch" in sys.argv
    skip_prep = "--skip-prep" in sys.argv
    skip_contracts = "--skip-contracts" in sys.argv
    prep_only = "--prep-only" in sys.argv

    if prep_only:
        skip_fetch = True

    # 1. Registry prep — only when we are allowed to hit the network. `--prep-only`
    # forces it even though it also skips the per-run fetchers below.
    run_prep = not skip_prep and (not skip_fetch or prep_only)
    if run_prep:
        for label, args in PREP_STEPS:
            run(label, args)
    else:
        reason = "skip-fetch" if skip_fetch else "skip-prep"
        print(f"(skipping registry prep — {reason})")

    if prep_only:
        print("\nPrep complete (--prep-only).")
        return

    # 2. Per-run fetchers.
    if not skip_fetch:
        run("Ombudsman complaints", ["england_ombudsman.py"])
        run("Borrowing & debt", ["england_borrowing.py"])
        run("Upcoming elections", ["elections.py"])
        run("QoL time series", ["data_england/qol_history.py"])
        if not skip_contracts:
            run("Contracts Finder suppliers", ["england_contracts.py"])
    else:
        print("(skipping fetchers — using existing data_england/*.csv)")

    # 3. Build + verify.
    run("Build site/data.json", ["site/build.py"])
    run("Build search indexes", ["site/build_search.py"])
    run("Preflight verification", ["site/verify.py"])

    print("\nPipeline complete.")


if __name__ == "__main__":
    main()
