import os
from tools.data_engine import seed_relational, seed_mongo

def main():
    # La semilla usa IDs deterministas y operaciones insert-if-absent.
    count = int(os.getenv("SEED_EVENTS_PER_CARRIER", "50000"))
    cycle_id = f"seed-v1-{os.getenv('SEED', '42')}"
    for carrier in ("A", "B", "C", "D"):
        print(f"Seeding carrier {carrier}: {count} events", flush=True)
        if carrier == "C":
            seed_mongo(count, cycle_id)
        else:
            seed_relational(carrier, count, cycle_id)
    print("Seed completed.", flush=True)

if __name__ == "__main__":
    main()
