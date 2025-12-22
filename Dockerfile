# Daily Brief Agent - Google Cloud Run Jobs
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY config.py .
COPY coordinator.py .
COPY agents/ ./agents/
COPY integrations/ ./integrations/
COPY utils/ ./utils/

# Create data directory for mention tracking
RUN mkdir -p /app/data

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV TZ=America/Phoenix

# Run the daily brief coordinator
CMD ["python", "coordinator.py"]
