# Use Python 3.11 slim image for better performance
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements first (for better caching)
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy all application files
COPY . .

# Expose port 8080 (Cloud Run default)
EXPOSE 8080

# Run the application with Gunicorn (production WSGI server)
# --workers 2: Use 2 worker processes for better concurrency
# --threads 4: 4 threads per worker
# --timeout 300: Match Cloud Run timeout
# --preload: Load application code before worker processes are forked (better memory usage)
# --worker-class gthread: Use threaded workers for I/O bound operations
CMD ["gunicorn", "--workers=2", "--threads=4", "--timeout=300", "--preload", "--worker-class=gthread", "--bind=0.0.0.0:8080", "app:app"]