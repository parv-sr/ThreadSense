from backend.src.db.base import Base, import_all_models
from sqlalchemy.schema import CreateTable, CreateIndex
from sqlalchemy.dialects import postgresql

import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load all your ThreadSense models
import_all_models()

print("\n--- COPY EVERYTHING BELOW THIS LINE ---")
# Ensure Supabase has the vector extension enabled for your embeddings
print("CREATE EXTENSION IF NOT EXISTS vector;\n")

# Generate pure Postgres SQL for all tables and indexes
for table in Base.metadata.sorted_tables:
    table_sql = str(CreateTable(table).compile(dialect=postgresql.dialect())).strip()
    print(f"{table_sql};\n")
    for index in table.indexes:
        index_sql = str(CreateIndex(index).compile(dialect=postgresql.dialect())).strip()
        print(f"{index_sql};\n")

# Fake the successful Alembic migration so your API boots up happily
print("""CREATE TABLE IF NOT EXISTS alembic_version (
    version_num VARCHAR(32) NOT NULL,
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);
INSERT INTO alembic_version (version_num) VALUES ('e9d2fb0a4fe1');""")
print("--- COPY EVERYTHING ABOVE THIS LINE ---\n")