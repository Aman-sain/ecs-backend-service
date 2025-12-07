from sqlalchemy import inspect
from db.database import engine, Base
from db.models import Employee
import logging

logger = logging.getLogger(__name__)

def init_database():
    """Initialize database and handle migrations"""
    try:
        inspector = inspect(engine)

        # Check if employees table exists
        if 'employees' in inspector.get_table_names():
            # Check if new columns exist
            columns = [col['name'] for col in inspector.get_columns('employees')]

            missing_columns = []
            if 'performance_rating' not in columns:
                missing_columns.append('performance_rating')
            if 'skills' not in columns:
                missing_columns.append('skills')

            if missing_columns:
                logger.info(f"Adding missing columns: {missing_columns}")
                # Drop and recreate table (simple migration for SQLite)
                Base.metadata.drop_all(bind=engine)
                Base.metadata.create_all(bind=engine)
                logger.info("Database schema updated successfully")
        else:
            # Create all tables
            Base.metadata.create_all(bind=engine)
            logger.info("Database tables created successfully")

    except Exception as e:
        logger.error(f"Database initialization error: {e}")
        # Force recreate on error
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        logger.info("Database recreated after error")
