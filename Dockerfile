FROM python:3.12-slim

# Install required packages, including netcat for wait-for-it
RUN apt-get update && apt-get install -y \
    gcc \
    default-libmysqlclient-dev \
    libmariadb-dev \
    build-essential \
    pkg-config \
    default-mysql-client \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code and wait-for-it.sh
COPY . .

# Make wait-for-it.sh executable
RUN chmod +x wait-for-it.sh

# Start with wait-for-it to ensure DB is ready
CMD ["./wait-for-it.sh", "db:3306", "gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "app:app"]

