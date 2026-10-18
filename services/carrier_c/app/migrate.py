import os
from pymongo import MongoClient
def migrate():
 # Migración versionada para índices y colecciones de MongoDB.
 client=MongoClient(os.environ["MONGODB_URL"],serverSelectionTimeoutMS=10000)
 db=client[os.getenv("MONGODB_DATABASE","carrier_c_db")]
 db.command("ping")
 db["shipments"].create_index("tracking_number",unique=True)
 db["events"].create_index("event_key",unique=True)
 db["events"].create_index("tracking_number")
 db["generation_runs"].create_index("cycle_id",unique=True)
 client.close()
if __name__=="__main__": migrate()
