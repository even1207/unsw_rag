"""SQLAlchemy database schema for staff data."""

from sqlalchemy import Column, String, Text, Integer, DateTime, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()


class StaffProfile(Base):
    """Staff profile table storing detailed information about UNSW staff members."""

    __tablename__ = 'staff_profiles'

    # Primary key - using profile_url as unique identifier (since not all staff have email)
    profile_url = Column(String(512), primary_key=True)

    # Basic information
    first_name = Column(String(100))
    last_name = Column(String(100))
    full_name = Column(String(255), nullable=False, index=True)
    role = Column(String(255))

    # Organizational structure
    faculty = Column(String(255), index=True)
    school = Column(String(255), index=True)

    # Contact information
    email = Column(String(255), index=True)
    phone = Column(String(50))
    photo_url = Column(String(512))

    # Profile content
    summary = Column(Text)
    biography = Column(Text)
    research_text = Column(Text)

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f"<StaffProfile(profile_url={self.profile_url}, name={self.full_name})>"


def create_tables(engine):
    """Create all tables in the database."""
    Base.metadata.create_all(engine)


def drop_tables(engine):
    """Drop all tables from the database."""
    Base.metadata.drop_all(engine)
