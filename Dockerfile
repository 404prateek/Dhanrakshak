FROM python:3.10-slim

WORKDIR /app

# Install system dependencies required for OpenCV, PyMuPDF, and ML libraries
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY backend/requirements.txt ./backend_requirements.txt
COPY requirements_ml.txt ./ml_requirements.txt

# Install dependencies (ignoring versions to ensure compatibility on linux)
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
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
