# src/create_memory_table.py

from myapp.database import Base, engine
from myapp.memory_store import Memory  # triggers table registration

# Create the memory table (and others if missing)
Base.metadata.create_all(bind=engine)

print("✅ Memory table created successfully.")
