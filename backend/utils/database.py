import mysql.connector
from mysql.connector import Error
import logging
from config import DB_CONFIG

logger = logging.getLogger(__name__)

def test_db_connection():
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        print("✅ Database connected successfully!")
        connection.close()
        return True
    except Error as e:
        print(f"❌ Database connection failed: {e}")
        return False

# Add this before app.run()
test_db_connection()

def get_db_connection():
    """Get database connection"""
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        return connection
    except Error as e:
        logger.error(f"Database connection error: {e}")
        return None