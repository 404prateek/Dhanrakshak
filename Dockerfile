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
ENV ENV=production
ENV PYTHONPATH=/app

# Expose the port FastAPI runs on
EXPOSE 8000

# Start the application
# WORKDIR is /app, so Python path is /app/backend/app/main.py → module is backend.app.main
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
