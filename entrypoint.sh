#!/bin/bash
set -e  # Stop script on error

LOG_DIR="/app/config/logs"
CONFIG_JSON="/app/config/config.json"
EXAMPLE_CONFIG_JSON="/app/config/config.example.json"

echo "VERSION v0.70-beta - JSON Config"

# Create necessary directories
mkdir -p "$LOG_DIR"

# Create example config.json file if it doesn't exist
if [ ! -f "$CONFIG_JSON" ]; then
    echo "Creating example config.json file at $CONFIG_JSON..."
    cp "$EXAMPLE_CONFIG_JSON" "$CONFIG_JSON"
else
    echo "config.json file already exists. Not overwriting."
fi

# Ensure permissions on /app/config
chmod -R 777 /app/config

# Start the application with 1 thread, tested OK with 20 queued requests (what I'm looking for)
exec gunicorn -w 1 -b 0.0.0.0:4343 app.flask_app:app
