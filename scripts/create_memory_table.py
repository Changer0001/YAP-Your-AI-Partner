#app/create_memory_table.py

from app.db.database import Base, engine
from app.db.memory_store import Memory  # triggers table registration

# Create the memory table (and others if missing)
Base.metadata.create_all(bind=engine)

print("✅ Memory table created successfully.")
