# -*- coding: utf-8 -*-
"""Migrate database: add agent tables.

Run: python migrate_agent.py
"""
import os
import sys

backend_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(backend_dir)
sys.path.insert(0, backend_dir)

from app.database import engine, Base
from app.models import AgentSession, TaskState, AgentMessage

def migrate():
    """Create new agent tables."""
    print("Creating agent tables...")
    
    # Create only the new tables (won't affect existing ones)
    tables_to_create = [AgentSession.__tablename__, TaskState.__tablename__, AgentMessage.__tablename__]
    print(f"Tables to create: {tables_to_create}")
    
    # Use create_all with checkfirst=True (only creates if not exists)
    Base.metadata.create_all(engine, tables=[
        AgentSession.__table__,
        TaskState.__table__,
        AgentMessage.__table__
    ], checkfirst=True)
    
    print("Done! Agent tables created (or already existed).")
    
    # Verify
    from app.database import SessionLocal
    db = SessionLocal()
    session_count = db.query(AgentSession).count()
    task_count = db.query(TaskState).count()
    msg_count = db.query(AgentMessage).count()
    print(f"Current data: sessions={session_count}, tasks={task_count}, messages={msg_count}")
    db.close()

if __name__ == "__main__":
    migrate()
