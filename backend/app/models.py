import uuid

from sqlalchemy import TIMESTAMP, Column, Integer, Text, func
from sqlalchemy.dialects.postgresql import UUID

from app.db import Base


class Program(Base):
    __tablename__ = "programs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(Text, nullable=False)
    university = Column(Text, nullable=False)
    city = Column(Text, nullable=True)
    country = Column(Text, nullable=True)
    level = Column(Text, nullable=True)
    language = Column(Text, nullable=True)
    duration_years = Column(Integer, nullable=True)
    study_pace = Column(Text, nullable=True)
    field = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    career_paths = Column(Text, nullable=True)
    tuition_eu = Column(Text, nullable=True)
    tuition_non_eu = Column(Text, nullable=True)
    source_url = Column(Text, nullable=True)
    last_updated = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
