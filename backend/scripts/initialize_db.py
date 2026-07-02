"""Script to read data from mockup file and populate the db"""

import csv

from gitdb.utils.encoding import force_text
from sqlalchemy.orm import sessionmaker
from backend.database.db import engine

from backend.database.db_models import Base, NetworkDevice, TicketData
from backend.core.settings import settings

SessionLocal = sessionmaker(bind=engine)


def init_db(force_reload: bool = False) -> None:
    """Reads data from csv file and populates the db.

    Args:
        force_reload: If True, deletes existing ticket data and reloads from CSV.
    """

    Base.metadata.create_all(engine)

    session = SessionLocal()
    try:
        # Network devices - only load if empty
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
            print(f"Loaded network devices from {data_path}")

        # Tickets - reload if force_reload or empty
        if force_reload:
            deleted = session.query(TicketData).delete()
            session.commit()
            print(f"Deleted {deleted} existing tickets.")

        if force_reload or session.query(TicketData).count() == 0:
            tickets_path = settings.DATA_DIR / "network_tickets_diverse_resolution.csv"
            count = 0
            with tickets_path.open("r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    session.add(TicketData(
                        ticket_number=row.get("Ticket Number"),
                        status=row.get("Status"),
                        creator_area=row.get("Creator Area"),
                        use_case=row.get("Use Case"),
                        subject=row.get("Subject"),
                        priority=int(row["Priority"]) if row.get("Priority") else None,
                        description=row.get("Description"),
                        start=row.get("Start"),
                        sla_ticket=row.get("SLA Ticket"),
                        network_element_identifier=row.get("Network Element Identifier"),
                        loc_identifier=row.get("Loc Identifier"),
                        assignee_area=row.get("Assignee Area"),
                        response_subject=row.get("Response Subject"),
                        response_description=row.get("Response Description"),
                    ))
                    count += 1
            session.commit()
            print(f"Loaded {count} tickets from {tickets_path}")
        else:
            print(f"Tickets already exist ({session.query(TicketData).count()} rows). Use --force to reload.")
    finally:
        session.close()


if __name__ == "__main__":
    force=True
    init_db(force_reload=force)