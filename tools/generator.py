import os
import time
from datetime import datetime, timezone

from tools.data_engine import cleanup_old_data, generate_cycle


def cycle_id_now() -> str:
    """Generate a stable 30-minute simulation cycle identifier."""
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    return now.replace(minute=0 if now.minute < 30 else 30).strftime("cycle-%Y%m%dT%H%MZ")


def main():
    """Main daemon loop generating synthetic carrier events and pruning expired cycles."""
    interval = int(os.getenv("GENERATOR_INTERVAL_SECONDS", "1800"))
    count = int(os.getenv("EVENTS_PER_CARRIER_PER_CYCLE", "10000"))
    retention_days = int(os.getenv("RETENTION_DAYS", "3"))

    print(
        f"[Generator] Starting periodic generation loop (interval={interval}s, "
        f"count_per_carrier={count}, retention_days={retention_days})",
        flush=True,
    )

    while True:
        cycle = cycle_id_now()
        for carrier in ("A", "B", "C", "D"):
            # 1. Clean up cycles older than retention window to prevent database bloat
            try:
                cleanup_res = cleanup_old_data(carrier, retention_days=retention_days)
                purged_events = cleanup_res.get("deleted_events", 0)
                if purged_events > 0:
                    print(
                        f"[Generator Cleanup] Carrier {carrier}: purged {purged_events} events "
                        f"prior to cutoff {cleanup_res.get('cutoff_cycle')}",
                        flush=True,
                    )
            except Exception as exc:
                print(f"[Generator Cleanup Warning] Carrier {carrier} cleanup failed: {exc}", flush=True)

            # 2. Generate current cycle events
            print(f"[Generator] Generating {count} events for carrier {carrier}, cycle {cycle}", flush=True)
            generate_cycle(carrier, count, cycle)

        time.sleep(interval)


if __name__ == "__main__":
    main()
