# Stage 1: Builder (Build and Compilation)
FROM python:3.12-slim AS builder

WORKDIR /app

# Prevent Python from writing .pyc files to the container
ENV PYTHONDONTWRITEBYTECODE=1
# Ensure Python logs are output in real-time to the console
ENV PYTHONUNBUFFERED=1

# Install system dependencies required only for compilation (e.g., ChromaDB)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Create a virtual environment to isolate dependencies
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy and install Python dependencies inside the venv
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Stage 2: Runner (Final production image)
FROM python:3.12-slim AS runner

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Copy ONLY the virtual environment from the builder stage
COPY --from=builder /opt/venv /opt/venv

# Ensure the container uses the virtual environment's Python and binaries
ENV PATH="/opt/venv/bin:$PATH"

# Copy the rest of the application code
COPY . .

EXPOSE 8000

# Command to run the Uvicorn ASGI server pointing to the FastAPI app
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]