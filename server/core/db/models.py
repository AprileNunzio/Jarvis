from sqlalchemy import Column, Integer, String, JSON, DateTime
from sqlalchemy.sql import func
from .database import Base

class AgentConfig(Base):
    __tablename__ = "agent_configs"
    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(String, unique=True, index=True)
    llm_order = Column(String)  # Comma separated models
    fallback_strategy = Column(String, default="first_available")
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class ProjectTask(Base):
    __tablename__ = "project_tasks"
    id = Column(String, primary_key=True, index=True)  # task_id
    name = Column(String)
    status = Column(String)
    progress = Column(Integer, default=0)
    state_data = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
