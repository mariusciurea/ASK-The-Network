"""Script to read data from mockup file and populate the db"""

import csv

from sqlalchemy.orm import sessionmaker
from backend.database.db import engine

from backend.database.db_models import Base, NetworkDevice
from backend.core.settings import settings

SessionLocal = sessionmaker(bind=engine)

def init_db() -> None:
    """Reads data from csv file and populates the db"""

    Base.metadata.create_all(engine)

    session = SessionLocal()
    try:
        if session.query(NetworkDevice).count() == 0:
            data_path = settings.DATA_DIR / "MOCK_DATA.csv"
            with open(data_path, "r") as csv_file:
                reader = csv.DictReader(csv_file)
                for row in reader:
                    session.add(NetworkDevice(
                        ne_name=row.get("ne_name"),
                        lte_ip=row.get("lte_ip"),
                        gsm_ip=row.get("gsm_ip"),
                        gnodeb_ip=row.get("5g_ip"),
                        loop_ip=row.get("loop_ip"),
                        ike_peer=row.get("ike_peer"),
                        enodeb_id=int(row.get("enodeb_id")),
                        gnodeb_id=int(row.get("gnodeb_id")),
                    ))
            session.commit()
    finally:
        session.close()


if __name__ == "__main__":
    init_db()