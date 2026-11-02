"""Standalone database cleanup utility for Type B carrier simulators."""

import argparse
import os
import sys

from tools.data_engine import cleanup_old_data


def main():
    """Execute manual database pruning across all or specific carriers."""
    parser = argparse.ArgumentParser(description="Prune old simulation cycles across carrier databases.")
    parser.add_argument(
        "--days",
        type=int,
        default=int(os.getenv("RETENTION_DAYS", "3")),
        help="Retention period in days (default: 3)",
    )
    parser.add_argument(
        "--carrier",
        choices=["A", "B", "C", "D", "ALL"],
        default="ALL",
        help="Target carrier or ALL (default: ALL)",
    )
    parser.add_argument(
        "--purge-seed",
        action="store_true",
        default=False,
        help="Also remove baseline seed dataset",
    )
    args = parser.parse_args()

    carriers = ["A", "B", "C", "D"] if args.carrier == "ALL" else [args.carrier]
    print(
        f"[Cleanup CLI] Starting cleanup for carriers {carriers} "
        f"(retention={args.days} days, purge_seed={args.purge_seed})...",
        flush=True,
    )

    total_purged = 0
    for carrier in carriers:
        try:
            res = cleanup_old_data(carrier, retention_days=args.days, keep_seed=not args.purge_seed)
            purged = res.get("deleted_events", 0)
            total_purged += purged
            print(
                f"[Cleanup CLI] Carrier {carrier}: {purged} events, "
                f"{res.get('deleted_runs', 0)} runs, "
                f"{res.get('deleted_shipments', 0)} shipments purged "
                f"(cutoff: {res.get('cutoff_cycle')})",
                flush=True,
            )
        except Exception as exc:
            print(f"[Cleanup CLI Error] Carrier {carrier} failed: {exc}", file=sys.stderr)

    print(f"[Cleanup CLI] Completed. Total events purged: {total_purged}", flush=True)


if __name__ == "__main__":
    main()
