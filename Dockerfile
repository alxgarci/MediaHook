# Use Python 3.11 base image
FROM python:3.11

# Set working directory inside container
WORKDIR /app

# Copy project content to container
COPY . .

# Create config and logs directories with proper permissions
RUN mkdir -p /app/config/logs && chmod -R 777 /app/config

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 4343

# Command to run the application
# CMD ["python", "run.py"]
ENTRYPOINT ["bash", "/app/entrypoint.sh"]