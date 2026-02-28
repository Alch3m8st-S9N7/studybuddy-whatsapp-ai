FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
# PyMuPDF might require some underlying libraries in some environments, though wheels usually cover it.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy local requirements
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the actual application
COPY ./app /app/app

# Command to run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
