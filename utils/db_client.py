import mysql.connector
from mysql.connector import Error
import logging
from typing import List, Dict, Optional
import config

logger = logging.getLogger(__name__)


class DBClient:
    def __init__(self):
        """Initialize database client with MySQL for GCP Cloud SQL"""
        self.connection_params = self._build_connection_params()
        self.init_database()

    def _build_connection_params(self) -> dict:
        """Build connection parameters for MySQL"""
        params = {
            "host": config.DB_HOST,
            "port": config.DB_PORT,
            "database": config.DB_NAME,
            "user": config.DB_USER,
            "password": config.DB_PASSWORD,
            "autocommit": False,
            "use_unicode": True,
            "charset": "utf8mb4",
        }

        return params

    def get_connection(self):
        """Get a database connection"""
        try:
            conn = mysql.connector.connect(**self.connection_params)
            return conn
        except Error as e:
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
                    id VARCHAR(50) PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    age INT NOT NULL,
                    gender VARCHAR(20),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
            )

            # Create reports table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS reports (
                    id VARCHAR(50) PRIMARY KEY,
                    patient_id VARCHAR(50) NOT NULL,
                    summary TEXT,
                    health_status VARCHAR(50) NOT NULL,
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

        except Error as e:
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
        except Error as e:
            logger.error(f"Error adding sample data: {e}")
            conn.rollback()

    def get_all_patients_with_latest_reports(self) -> List[Dict]:
        """Get all patients with their latest report for the table view"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor(dictionary=True)

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
                ORDER BY r.report_date DESC
            """

            cursor.execute(query)
            rows = cursor.fetchall()

            cursor.close()
            conn.close()

            logger.info(f"Fetched {len(rows)} patients with latest reports")

            return rows

        except Error as e:
            logger.error(f"Error fetching patients with latest reports: {e}")
            return []

    def get_patient_by_id(self, patient_id: str) -> Optional[Dict]:
        """Get patient details by ID"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor(dictionary=True)

            cursor.execute("SELECT * FROM patients WHERE id = %s", (patient_id,))

            row = cursor.fetchone()

            cursor.close()
            conn.close()

            logger.info(f"Fetched patient {patient_id}")

            return row

        except Error as e:
            logger.error(f"Error fetching patient {patient_id}: {e}")
            return None

    def get_patient_reports_timeline(self, patient_id: str) -> List[Dict]:
        """Get all reports for a patient ordered by date (for timeline view)"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor(dictionary=True)

            cursor.execute(
                """
                SELECT * FROM reports 
                WHERE patient_id = %s 
                ORDER BY report_date DESC
            """,
                (patient_id,),
            )

            rows = cursor.fetchall()

            logger.info(f"Fetched {len(rows)} reports for patient {patient_id}")

            cursor.close()
            conn.close()

            return rows

        except Error as e:
            logger.error(f"Error fetching reports for patient {patient_id}: {e}")
            return []

    def get_report_by_id(self, report_id: str) -> Optional[Dict]:
        """Get specific report by ID"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor(dictionary=True)

            cursor.execute("SELECT * FROM reports WHERE id = %s", (report_id,))

            row = cursor.fetchone()

            logger.info(f"Fetched report {report_id}")

            cursor.close()
            conn.close()

            return row

        except Error as e:
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

            logger.info(f"Report {report_id} saved for patient {patient_id}")

            cursor.close()
            conn.close()

            return True

        except Error as e:
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

            logger.info(f"Database health check completed")
            cursor.close()
            conn.close()

            return {
                "status": "healthy",
                "connected": True,
                "patients_count": patient_count,
                "reports_count": report_count,
                "database_type": "mysql",
            }
        except Error as e:
            logger.error(f"Database health check failed: {e}")
            return {
                "status": "unhealthy",
                "connected": False,
                "error": str(e),
                "database_type": "mysql",
            }
