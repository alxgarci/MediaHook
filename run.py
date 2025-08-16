#!/usr/bin/env python3
"""
MediaHook Main Entry Point

This is the main entry point for running the MediaHook application.
It starts the Flask server to listen for webhooks from Sonarr, Radarr, and Overseerr.
"""

import sys
import os

# Add the app directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    from app.flask_app import start_server
    start_server()