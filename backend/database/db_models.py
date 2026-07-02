"""DB Models"""

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.sql import func

from backend.database.db import Base


class NetworkDevice(Base):
    __tablename__ = "network_devices"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ne_name = Column(String(100), unique=True, nullable=False, index=True)
    lte_ip = Column(String(100), nullable=True)
    gsm_ip = Column(String(100), nullable=True)
    gnodeb_ip = Column(String(100), nullable=True)
    loop_ip = Column(String(100), nullable=True)
    ike_peer = Column(String(100), nullable=True)
    enodeb_id = Column(Integer, nullable=True)
    gnodeb_id = Column(Integer, nullable=True)


class TicketData(Base):
    __tablename__ = "ticket_data"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticket_number = Column(String(100), unique=True, nullable=False, index=True)
    status = Column(String(50), nullable=False)
    creator_area = Column(String(100), nullable=False)
    use_case = Column(String(100), nullable=True)
    subject = Column(String(255), nullable=True)
    priority = Column(Integer, nullable=True)
    description = Column(Text, nullable=True)
    start = Column(String(50), nullable=True)
    sla_ticket = Column(String(50), nullable=True)
    network_element_identifier = Column(String(100), nullable=True)
    loc_identifier = Column(String(100), nullable=True)
    assignee_area = Column(String(100), nullable=True)
    response_subject = Column(String(255), nullable=True)
    response_description = Column(Text, nullable=True)



class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
