import logging
import os
import json
from pathlib import Path
from logging.handlers import TimedRotatingFileHandler

# Create logs directory if it doesn't exist
LOG_DIR = "config/logs"
os.makedirs(LOG_DIR, exist_ok=True)

def get_log_level():
    """
    Gets the logging level directly from config.json file.
    
    Returns:
        int: The logging level constant from the logging module.
        Returns logging.INFO as default if any error occurs.
    """
    try:
        config_path = Path(os.path.dirname(os.path.abspath(__file__))) / '../config/config.json'
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        log_level = config.get('general', {}).get('log_level', 'INFO').upper()
        
        # Validate log level
        levels = {
            "DEBUG": logging.DEBUG, 
            "INFO": logging.INFO, 
            "WARNING": logging.WARNING, 
            "ERROR": logging.ERROR, 
            "CRITICAL": logging.CRITICAL
        }
        return levels.get(log_level, logging.DEBUG)
        
    except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
        # If any error occurs, use DEBUG as default level
        return logging.DEBUG

# Get log level from config.json
LOG_LEVEL = get_log_level()

# Main log file with daily rotation and 2 backup copies
LOG_FILE = os.path.join(LOG_DIR, "app.log")
file_handler = TimedRotatingFileHandler(
    LOG_FILE, when="D", interval=1, backupCount=2, encoding="utf-8", utc=True
)
file_handler.setLevel(LOG_LEVEL)
file_handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))

# Configure console output
console_handler = logging.StreamHandler()
console_handler.setLevel(LOG_LEVEL)
console_handler.setFormatter(logging.Formatter("%(levelname)s - %(message)s"))

# Configure global logger
logger = logging.getLogger("Webhooks")
logger.setLevel(LOG_LEVEL)
logger.addHandler(file_handler)
logger.addHandler(console_handler)

logger.info(f"Logging file created in {os.getcwd()} {LOG_FILE}")
logger.info(f"Logger initialized with level: {LOG_LEVEL}")
