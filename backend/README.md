# DhanRakshak Backend

Enterprise-grade backend for the DhanRakshak fraud investigation platform.

## Setup Instructions

1. **Create a virtual environment (optional but recommended):**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Database Configuration:**
   - Ensure PostgreSQL is running.
   - Create a database named `dhanrakshak` (or update `DATABASE_URL`).
   - Copy `.env.example` to `.env` and adjust the `DATABASE_URL` if necessary.

4. **Initialize Database and Seed Data:**
   - Run Alembic migrations to create tables:
     ```bash
     alembic upgrade head
     ```
   - Seed the database with mock data:
     ```bash
     python seed.py
     ```

5. **Start the Server:**
   ```bash
   uvicorn app.main:app --reload
   ```

6. **API Documentation:**
   - Swagger UI: `http://localhost:8000/docs`
   - ReDoc: `http://localhost:8000/redoc`
