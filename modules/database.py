import logging
import os
import psycopg2
from openai import timeout
from psycopg2 import sql

class PostgresDB:
    def __init__(self):
        # Load environment variables
        self.db_name = os.getenv('DB_NAME')
        self.db_user = os.getenv('DB_USER')
        self.db_password = os.getenv('DB_PASSWORD')
        self.db_host = os.getenv('DB_HOST', 'localhost')
        self.db_port = os.getenv('DB_PORT', '5432')

        self.conn = None

    def connect(self):
        """Establish a connection to the PostgreSQL database."""
        try:
            self.conn = psycopg2.connect(
                dbname=self.db_name,
                user=self.db_user,
                password=self.db_password,
                host=self.db_host,
                port=self.db_port

            )
            logging.info("Connected to the database.")
        except psycopg2.DatabaseError as e:
            logging.error(f"Error connecting to the database: {e}")
            self.conn = None

    def close(self):
        """Close the connection to the database."""
        if self.conn is not None:
            self.conn.close()
            logging.info("Database connection closed.")

    def insert_serialized(self, key, bytes): # pragma: no cover
        """Insert a serialized object into the database."""
        self.connect()

        if self.conn is None:
            return

        with self.conn.cursor() as cur:
            query = sql.SQL("INSERT INTO serialized (key, bytes) VALUES (%s, %s) ON CONFLICT (key) DO UPDATE SET bytes = EXCLUDED.bytes")
            cur.execute(query, (key, bytes))

        self.conn.commit()
        self.close()

    def get_serialized(self, key): # pragma: no cover
        """Retrieve a serialized object from the database."""

        self.connect()

        if self.conn is None:
            return

        with self.conn.cursor() as cur:
            query = sql.SQL("SELECT bytes FROM serialized WHERE key = %s")
            cur.execute(query, (key,))
            self.close()
            return cur.fetchone()

