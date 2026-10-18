import os
import time
from datetime import datetime, timezone
from tools.data_engine import generate_cycle

def cycle_id_now():
    # La ejecución queda asociada a una ventana fija de 30 minutos.
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    return now.replace(minute=0 if now.minute < 30 else 30).strftime("cycle-%Y%m%dT%H%MZ")

def main():
    interval = int(os.getenv("GENERATOR_INTERVAL_SECONDS", "1800"))
    count = int(os.getenv("EVENTS_PER_CARRIER_PER_CYCLE", "10000"))
    while True:
        cycle = cycle_id_now()
        for carrier in ("A", "B", "C", "D"):
            print(f"Generating {count} events for carrier {carrier}, cycle {cycle}", flush=True)
            generate_cycle(carrier, count, cycle)
        time.sleep(interval)

if __name__ == "__main__":
    main()
