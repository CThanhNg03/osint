FROM python:3.10-slim

WORKDIR /app

# Install system dependencies for OpenCV and other tools
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "api_gateway:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
