import psycopg2
import psycopg2.extras
import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import os
import config

logger = logging.getLogger(__name__)


class DBClient:
    def __init__(self):
        """Initialize database client with PostgreSQL for GCP Cloud SQL"""
        self.connection_params = self._build_connection_params()
        self.init_database()

    def _build_connection_params(self) -> dict:
        """Build connection parameters for PostgreSQL"""
        params = {
            "host": config.DB_HOST,
            "port": config.DB_PORT,
            "database": config.DB_NAME,
            "user": config.DB_USER,
            "password": config.DB_PASSWORD,
        }

        # If running on GCP with Cloud SQL, use the connection name for socket connection
        if config.DB_CONNECTION_NAME:
            params["host"] = f"/cloudsql/{config.DB_CONNECTION_NAME}"
            params.pop("port", None)  # Remove port for socket connection

        return params

    def get_connection(self):
        """Get a database connection"""
        try:
            conn = psycopg2.connect(**self.connection_params)
            conn.autocommit = False
            return conn
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            raise

    def init_database(self):
        """Initialize database tables"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            # Create patients table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS patients (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    age INTEGER NOT NULL,
                    gender TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
            )

            # Create reports table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS reports (
                    id TEXT PRIMARY KEY,
                    patient_id TEXT NOT NULL,
                    summary TEXT,
                    health_status TEXT NOT NULL,
                    report_date DATE NOT NULL,
                    report_url TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (patient_id) REFERENCES patients (id)
                )
            """
            )

            conn.commit()
            logger.info("Database initialized successfully")

            # Add some sample data if tables are empty
            self._add_sample_data(cursor, conn)

            cursor.close()
            conn.close()

        except Exception as e:
            logger.error(f"Error initializing database: {e}")
            raise

    def _add_sample_data(self, cursor, conn):
        """Add sample data if tables are empty"""
        try:
            # Check if we already have data
            cursor.execute("SELECT COUNT(*) FROM patients")
            if cursor.fetchone()[0] > 0:
                return

            # Add sample patients
            sample_patients = [
                ("p001", "Alice Smith", 29, "Female"),
                ("p002", "Bob Johnson", 54, "Male"),
                ("p003", "Charlie Lee", 67, "Male"),
            ]

            cursor.executemany(
                "INSERT INTO patients (id, name, age, gender) VALUES (%s, %s, %s, %s)",
                sample_patients,
            )

            # Add sample reports
            sample_reports = [
                ("r101", "p001", None, "Normal", "2024-06-01", None),
                ("r102", "p002", None, "Follow-up", "2024-05-28", None),
                ("r103", "p003", None, "Critical", "2024-05-25", None),
                (
                    "r104",
                    "p002",
                    None,
                    "Normal",
                    "2024-04-15",
                    None,
                ),  # Older report for Bob
                (
                    "r105",
                    "p003",
                    None,
                    "Follow-up",
                    "2024-04-10",
                    None,
                ),  # Older report for Charlie
            ]

            cursor.executemany(
                "INSERT INTO reports (id, patient_id, summary, health_status, report_date, report_url) VALUES (%s, %s, %s, %s, %s, %s)",
                sample_reports,
            )

            conn.commit()
            logger.info("Sample data added to database")
        except Exception as e:
            logger.error(f"Error adding sample data: {e}")
            conn.rollback()

    def get_all_patients_with_latest_reports(self) -> List[Dict]:
        """Get all patients with their latest report for the table view"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

            query = """
                SELECT 
                    p.id as patient_id,
                    p.name,
                    p.age,
                    p.gender,
                    r.id as report_id,
                    r.summary,
                    r.health_status,
                    r.report_date,
                    r.report_url
                FROM patients p
                LEFT JOIN (
                    SELECT 
                        patient_id,
                        id,
                        summary,
                        health_status,
                        report_date,
                        report_url,
                        ROW_NUMBER() OVER (PARTITION BY patient_id ORDER BY report_date DESC) as rn
                    FROM reports
                ) r ON p.id = r.patient_id AND r.rn = 1
                ORDER BY r.report_date DESC NULLS LAST
            """

            cursor.execute(query)
            rows = cursor.fetchall()

            cursor.close()
            conn.close()

            return [dict(row) for row in rows]

        except Exception as e:
            logger.error(f"Error fetching patients with latest reports: {e}")
            return []

    def get_patient_by_id(self, patient_id: str) -> Optional[Dict]:
        """Get patient details by ID"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

            cursor.execute("SELECT * FROM patients WHERE id = %s", (patient_id,))

            row = cursor.fetchone()

            cursor.close()
            conn.close()

            return dict(row) if row else None

        except Exception as e:
            logger.error(f"Error fetching patient {patient_id}: {e}")
            return None

    def get_patient_reports_timeline(self, patient_id: str) -> List[Dict]:
        """Get all reports for a patient ordered by date (for timeline view)"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

            cursor.execute(
                """
                SELECT * FROM reports 
                WHERE patient_id = %s 
                ORDER BY report_date DESC
            """,
                (patient_id,),
            )

            rows = cursor.fetchall()

            cursor.close()
            conn.close()

            return [dict(row) for row in rows]

        except Exception as e:
            logger.error(f"Error fetching reports for patient {patient_id}: {e}")
            return []

    def get_report_by_id(self, report_id: str) -> Optional[Dict]:
        """Get specific report by ID"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

            cursor.execute("SELECT * FROM reports WHERE id = %s", (report_id,))

            row = cursor.fetchone()

            cursor.close()
            conn.close()

            return dict(row) if row else None

        except Exception as e:
            logger.error(f"Error fetching report {report_id}: {e}")
            return None

    def save_report(
        self,
        patient_id: str,
        report_id: str,
        health_status: str,
        report_date: str,
        report_url: str = None,
        summary: str = None,
    ) -> bool:
        """Save a new report for a patient"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO reports (id, patient_id, summary, health_status, report_date, report_url)
                VALUES (%s, %s, %s, %s, %s, %s)
            """,
                (
                    report_id,
                    patient_id,
                    summary,
                    health_status,
                    report_date,
                    report_url,
                ),
            )

            conn.commit()

            cursor.close()
            conn.close()

            logger.info(f"Report {report_id} saved for patient {patient_id}")
            return True

        except Exception as e:
            logger.error(f"Error saving report: {e}")
            return False

    def health_check(self) -> Dict:
        """Check database health"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) FROM patients")
            patient_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM reports")
            report_count = cursor.fetchone()[0]

            cursor.close()
            conn.close()

            return {
                "status": "healthy",
                "connected": True,
                "patients_count": patient_count,
                "reports_count": report_count,
                "database_type": "postgresql",
            }
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return {
                "status": "unhealthy",
                "connected": False,
                "error": str(e),
                "database_type": "postgresql",
            }
