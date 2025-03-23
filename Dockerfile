FROM python:3.8-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    wget \
    git \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Clone GFPGAN
RUN git clone https://github.com/TencentARC/GFPGAN.git /app/GFPGAN

# Copy our application
COPY app /app/app
COPY requirements.txt /app/

# Install Python dependencies
RUN pip install -r requirements.txt
RUN pip install -r GFPGAN/requirements.txt

# Download pre-trained model
RUN mkdir -p experiments/pretrained_models \
    && wget https://github.com/TencentARC/GFPGAN/releases/download/v1.3.0/GFPGANv1.4.pth \
    -P experiments/pretrained_models

# Create static directory for FastAPI
RUN mkdir -p /app/static

CMD ["python", "app/main.py"]