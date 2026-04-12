# Start from an official Python image
FROM python:3.11-slim

# Install ffmpeg (needed for webm conversion)
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

# Set working directory inside the container
WORKDIR /app

# Copy and install Python dependencies first
# (Docker caches this layer — if requirements.txt hasn't changed,
#  it won't reinstall packages on every rebuild. Much faster.)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the backend code
COPY . .

# Start the FastAPI server
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]