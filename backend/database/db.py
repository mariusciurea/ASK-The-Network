"""Database

Requirements
------------
    pip install sqlalchemy
    pip install mysql-connector-python

db URL general template:
<dialect>+<driver>://<username>:<password>@<host>:<port>/<database>
------------------
    MySql
    mysql_db_url = "mysql://<username>:<password>@<hostname>:<port>/<database>"
    mysql_db_url = "mysql+mysqlconnector://<username>:<password>@<hostname>:<port>/<database>"

    PostgreSQL
    postgresql_db_url = "postgresql://<username>:<password>@<hostname>:<port>/<database>"
    "postgresql+psycopg2://<username>:<password>@<hostname>:<port>/<database>"

Get username and port from SQL server
--------------------
    CREATE DATABASE test_docker;
    USE test_docker;

    SHOW VARIABLES WHERE Variable_name = 'port';
    SELECT user();

"""

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base

from backend.core.settings import settings


engine = create_engine(settings.DB_URL)

Base = declarative_base()




