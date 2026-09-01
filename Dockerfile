FROM python:3.10-slim

WORKDIR /app

# Install system dependencies required for OpenCV, PyMuPDF, Tesseract, and ML libraries
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    tesseract-ocr \
    tesseract-ocr-eng \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (better layer caching)
COPY backend/requirements.txt ./backend_requirements.txt
COPY requirements_ml.txt ./ml_requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir -r backend_requirements.txt
RUN pip install --no-cache-dir -r ml_requirements.txt

# Copy the entire project
COPY . .

# Set environment variables
# /app/backend first so `from app.X import Y` resolves to /app/backend/app/
# /app second so `from ml_engine.X import Y` resolves to /app/ml_engine/
ENV PYTHONPATH=/app/backend:/app
ENV ENV=production

# Expose the port FastAPI runs on
EXPOSE 8000

# Start the application
# PYTHONPATH=/app/backend:/app so `app.main:app` finds /app/backend/app/main.py
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
