# Use Python 3.11 slim image (90% smaller)
FROM python:3.11-slim

# Set working directory inside container
WORKDIR /app

# Copy requirements first for better Docker layer caching
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy Python source code
COPY app/ ./app/
COPY logics/ ./logics/
COPY utils/ ./utils/
COPY run.py .
COPY entrypoint.sh .

# Copy config files to a template directory (not /app/config)
COPY config/*.json ./config-templates/

# Create the actual config directory for volume mounting
RUN mkdir -p /app/config/logs && chmod -R 777 /app/config

# Make entrypoint script executable
RUN chmod +x /app/entrypoint.sh

# Set default port
ENV MEDIAHOOK_PORT=4343
ENV MEDIAHOOK_HOST=0.0.0.0

EXPOSE ${MEDIAHOOK_PORT}

# Command to run the application
# CMD ["python", "run.py"]
ENTRYPOINT ["bash", "/app/entrypoint.sh"]