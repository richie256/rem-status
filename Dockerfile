FROM python:3.11-slim

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml .
COPY README.md .
COPY src/ src/

# Install the application
RUN pip install --no-cache-dir .

# Command to run the application
CMD ["python", "-m", "rem_status.main"]
