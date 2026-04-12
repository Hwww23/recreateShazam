import os
from sqlalchemy import create_engine, text

# Update password to whatever you set during PostgreSQL installation
# DATABASE_URL = "postgresql://postgres:123456@localhost:5432/soundmatch"

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:YOUR_PASSWORD@localhost:5432/soundmatch"
)

engine = create_engine(DATABASE_URL)

def get_connection():
    return engine.connect()

def test_connection():
    with get_connection() as conn:
        result = conn.execute(text("SELECT version()"))
        print(f"Connected to: {result.fetchone()[0]}")

if __name__ == "__main__":
    test_connection()