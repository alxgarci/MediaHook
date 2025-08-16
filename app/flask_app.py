import json
import os
import sys
import threading
import time
from pathlib import Path

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, request, jsonify
from app.logger import logger

app = Flask(__name__)

# Path to configuration file
CONFIG_PATH = Path(os.path.dirname(os.path.abspath(__file__))) / '../config/config.json'

class ConfigManager:
    """
    Centralized configuration manager using Singleton pattern.
    
    This class manages the application configuration loaded from config.json.
    It ensures only one instance exists throughout the application lifecycle.
    """
    _instance = None
    _config = None
    
    def __new__(cls):
        """
        Create or return the singleton instance.
        
        Returns:
            ConfigManager: The singleton instance of ConfigManager.
        """
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize the ConfigManager and load configuration if not already loaded."""
        if self._config is None:
            self.load_config()
    
    def load_config(self):
        """
        Load configuration from the JSON file.
        
        Raises:
            SystemExit: If configuration file is not found or contains invalid JSON.
        """
        try:
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                self._config = json.load(f)
            logger.info("Configuration loaded successfully")
        except FileNotFoundError:
            logger.error(f"Configuration file not found: {CONFIG_PATH}")
            sys.exit(1)
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing configuration file: {e}")
            sys.exit(1)
    
    def get_config(self):
        """
        Return the complete configuration.
        
        Returns:
            dict: The complete configuration dictionary.
        """
        return self._config
    
    def get_section(self, section):
        """
        Return a specific configuration section.
        
        Args:
            section (str): The name of the configuration section.
            
        Returns:
            dict: The requested configuration section or empty dict if not found.
        """
        return self._config.get(section, {})

class SonarrInstance:
    """
    Represents a Sonarr instance configuration.
    
    This class encapsulates all the necessary information to connect to and
    interact with a Sonarr instance.
    """
    
    def __init__(self, name, host, port, api_key, hard_drive_route, hard_drive_threshold):
        """
        Initialize a Sonarr instance.
        
        Args:
            name (str): Human-readable name for the instance.
            host (str): IP address or hostname of the Sonarr server.
            port (int): Port number for the Sonarr API.
            api_key (str): API key for authentication.
            hard_drive_route (str): Path to the storage location.
            hard_drive_threshold (int): Minimum free space threshold in GB.
        """
        self.name = name
        self.host = host
        self.port = port
        self.api_key = api_key
        self.hard_drive_route = hard_drive_route
        self.hard_drive_threshold = int(hard_drive_threshold) * 1024 * 1024 * 1024  # Convert GB to bytes
        self.api_url = f"http://{host}:{port}"
        self.headers = {'X-Api-Key': api_key}
    
    def __str__(self):
        """
        Return string representation of the Sonarr instance.
        
        Returns:
            str: Human-readable string representation.
        """
        return f"Sonarr({self.name}@{self.host}:{self.port})"

class RadarrInstance:
    """
    Represents a Radarr instance configuration.
    
    This class encapsulates all the necessary information to connect to and
    interact with a Radarr instance.
    """
    
    def __init__(self, name, host, port, api_key, hard_drive_route, hard_drive_threshold):
        """
        Initialize a Radarr instance.
        
        Args:
            name (str): Human-readable name for the instance.
            host (str): IP address or hostname of the Radarr server.
            port (int): Port number for the Radarr API.
            api_key (str): API key for authentication.
            hard_drive_route (str): Path to the storage location.
            hard_drive_threshold (int): Minimum free space threshold in GB.
        """
        self.name = name
        self.host = host
        self.port = port
        self.api_key = api_key
        self.hard_drive_route = hard_drive_route
        self.hard_drive_threshold = int(hard_drive_threshold) * 1024 * 1024 * 1024  # Convert GB to bytes
        self.api_url = f"http://{host}:{port}"
        self.headers = {'X-Api-Key': api_key}
    
    def __str__(self):
        """
        Return string representation of the Radarr instance.
        
        Returns:
            str: Human-readable string representation.
        """
        return f"Radarr({self.name}@{self.host}:{self.port})"

class QBittorrentInstance:
    """
    Represents a qBittorrent instance configuration.
    
    This class encapsulates all the necessary information to connect to and
    interact with a qBittorrent instance.
    """
    
    def __init__(self, name, host, port, username, password, seed_limit):
        """
        Initialize a qBittorrent instance.
        
        Args:
            name (str): Human-readable name for the instance.
            host (str): IP address or hostname of the qBittorrent server.
            port (int): Port number for the qBittorrent Web UI.
            username (str): Username for authentication.
            password (str): Password for authentication.
            seed_limit (int): Maximum seeding time limit in minutes.
        """
        self.name = name
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.seed_limit = int(seed_limit)
        self.api_url = f"http://{host}:{port}"
        self.session = None
        self.authenticated = False
    
    def __str__(self):
        """
        Return string representation of the qBittorrent instance.
        
        Returns:
            str: Human-readable string representation.
        """
        return f"qBittorrent({self.name}@{self.host}:{self.port})"

class TelegramConfig:
    """
    Configuration class for Telegram notifications.
    
    This class holds all the necessary credentials and identifiers
    for sending notifications through Telegram API.
    """
    
    def __init__(self, token, chat_id, private_chat_id):
        """
        Initialize Telegram configuration.
        
        Args:
            token (str): Bot token for Telegram API authentication.
            chat_id (str): Public chat ID for general notifications.
            private_chat_id (str): Private chat ID for sensitive notifications.
        """
        self.token = token
        self.chat_id = chat_id
        self.private_chat_id = private_chat_id

class TMDbConfig:
    """
    Configuration class for The Movie Database (TMDb) API.
    
    This class holds the necessary configuration for interacting with
    TMDb API including language preferences.
    """
    
    def __init__(self, api_key, language="es-ES", display_language="es"):
        """
        Initialize TMDb configuration.
        
        Args:
            api_key (str): API key for TMDb authentication.
            language (str): Language code for TMDb API requests (e.g., 'es-ES', 'en-US').
            display_language (str): Language code for display purposes (e.g., 'es', 'en').
        """
        self.api_key = api_key
        self.language = language
        self.display_language = display_language

class IMDbConfig:
    """
    Configuration class for Internet Movie Database (IMDb) URLs.
    
    This class holds the language configuration for generating
    localized IMDb URLs.
    """
    
    def __init__(self, language="es-es"):
        """
        Initialize IMDb configuration.
        
        Args:
            language (str): Language code for IMDb URLs (e.g., 'es-es', 'en-us').
        """
        self.language = language

class ApplicationConfig:
    """
    Main application configuration class.
    
    This class orchestrates the entire application configuration by loading
    settings from config.json and creating appropriate service instances.
    It serves as the central point for accessing all configuration data.
    """
    
    def __init__(self):
        """
        Initialize the application configuration.
        
        Loads configuration from JSON file and creates instances for all
        configured services including Sonarr, Radarr, qBittorrent, etc.
        """
        self.config_manager = ConfigManager()
        config = self.config_manager.get_config()
        
        # Initialize service instances
        self.sonarr_instances = [
            SonarrInstance(**instance) 
            for instance in config.get('sonarr', [])
        ]
        
        self.radarr_instances = [
            RadarrInstance(**instance) 
            for instance in config.get('radarr', [])
        ]
        
        self.qbittorrent_instances = [
            QBittorrentInstance(**instance) 
            for instance in config.get('qbittorrent', [])
        ]
        
        # External service configurations
        telegram_config = config.get('telegram', {})
        self.telegram = TelegramConfig(
            telegram_config.get('token'),
            telegram_config.get('chat_id'),
            telegram_config.get('private_chat_id')
        )
        
        tmdb_config = config.get('tmdb', {})
        self.tmdb = TMDbConfig(
            tmdb_config.get('api_key'),
            tmdb_config.get('language', 'es-ES'),
            tmdb_config.get('display_language', 'es')
        )
        
        imdb_config = config.get('imdb', {})
        self.imdb = IMDbConfig(
            imdb_config.get('language', 'es-es')
        )
        
        self.general = config.get('general', {})
        
        # Easy access to commonly used general settings
        self.dry_run = self.general.get('dry_run', True)
        self.log_level = self.general.get('log_level', 'INFO')
        
        logger.info(f"Configuration initialized: {len(self.sonarr_instances)} Sonarr, "
                   f"{len(self.radarr_instances)} Radarr, {len(self.qbittorrent_instances)} qBittorrent")
        logger.info(f"DRY RUN mode: {'ENABLED' if self.dry_run else 'DISABLED'}")

# Global configuration instance
app_config = ApplicationConfig()

# Initialize qBittorrent manager
from utils.qbittorrent_connections import initialize_qbittorrent_manager
initialize_qbittorrent_manager(app_config)

# Shared list to accumulate incoming episodes
sonarr_episode_buffer = []
buffer_lock = threading.Lock()  # To prevent concurrency issues
radarr_lock = threading.Lock()  # To prevent Radarr from processing multiple movies simultaneously

secure_wait_seconds = 2
last_webhook_time = 0
TIMER_THRESHOLD = 20  # Seconds to wait before processing
sonarr_queue_thread = None

def delayed_process():
    """
    Wait TIMER_THRESHOLD seconds without receiving episodes before processing the queue.
    
    This function runs in a separate thread and monitors the episode buffer.
    When no new episodes are received for TIMER_THRESHOLD seconds, it processes
    all accumulated episodes in batch.
    """
    global last_webhook_time, sonarr_queue_thread
    # Import here to avoid circular imports
    from logics.sonarr_logic import SonarrLogic
    
    sonarr_logic = SonarrLogic(app_config)
    
    while sonarr_queue_thread is not None:
        time.sleep(5)  # Check every 5 seconds if inactivity time has passed
        logger.debug("Checking buffer...")
        with buffer_lock:
            if sonarr_episode_buffer and (time.time() - last_webhook_time > TIMER_THRESHOLD):
                logger.info(f"Processing {len(sonarr_episode_buffer)} accumulated episodes in buffer.")
                sonarr_logic.process_queue(sonarr_episode_buffer.copy())  # Copy list before clearing
                sonarr_episode_buffer.clear()  # Clear the buffer
                sonarr_queue_thread = None

@app.route('/webhook/sonarr', methods=['POST'])
def sonarr_webhook():
    """
    Handle Sonarr webhook requests.
    
    This endpoint receives webhook notifications from Sonarr and accumulates
    them in a buffer for batch processing. This prevents processing each
    episode individually when multiple episodes are imported simultaneously.
    
    Returns:
        tuple: JSON response and HTTP status code.
    """
    global last_webhook_time, sonarr_queue_thread
    data = request.json
    if not data:
        return jsonify({"error": "No JSON data received"}), 400

    with buffer_lock:
        if not sonarr_queue_thread:
            logger.debug("Listening for more Sonarr webhooks...")
            sonarr_queue_thread = 1
            threading.Thread(target=delayed_process, daemon=True).start()

        logger.debug("Appending received data to buffer...")
        sonarr_episode_buffer.append(data)
        last_webhook_time = time.time()  # Update last webhook received time

    logger.debug(f"Episode received in buffer: {data}")
    return jsonify({"message": "Sonarr webhook received"}), 200

@app.route('/webhook/radarr', methods=['POST'])
def radarr_webhook():
    """
    Handle Radarr webhook requests.
    
    This endpoint receives webhook notifications from Radarr and processes
    them immediately. Uses a lock to prevent concurrent processing of
    multiple movie imports.
    
    Returns:
        tuple: JSON response and HTTP status code.
    """
    global radarr_lock
    logger.debug('Radarr webhook received on /webhook/radarr')
    data = request.json
    if not data:
        logger.debug('No JSON data received reading Radarr webhook')
        return jsonify({"error": "No JSON data received"}), 400

    with radarr_lock:
        logger.debug("Processing Radarr webhook...")
        # Import here to avoid circular imports
        from logics.radarr_logic import RadarrLogic
        radarr_logic = RadarrLogic(app_config)
        radarr_logic.process_event(data)
        logger.debug(json.dumps(request.json, indent=4))
        time.sleep(secure_wait_seconds)

    return jsonify({"message": "Radarr webhook received"}), 200

@app.route('/webhook/overseerr', methods=['POST'])
def overseerr_webhook():
    """
    Handle Overseerr webhook requests.
    
    This endpoint receives webhook notifications from Overseerr for
    request approvals, denials, and other events.
    
    Returns:
        tuple: JSON response and HTTP status code.
    """
    logger.debug('Overseerr webhook received on /webhook/overseerr')
    data = request.json
    if not data:
        logger.debug('No JSON data received reading Overseerr webhook')
        return jsonify({"error": "No JSON data received"}), 400

    logger.debug("Processing Overseerr webhook...")
    logger.debug(json.dumps(request.json, indent=4))
    
    # Import here to avoid circular imports
    from logics.overseerr_logic import OverseerrLogic
    overseerr_logic = OverseerrLogic(app_config)
    overseerr_logic.process_webhook(data)

    return jsonify({"message": "Overseerr webhook received"}), 200

def start_server():
    """Start the Flask server to listen for webhooks."""    
    app.run(host='0.0.0.0', port=4343)

if __name__ == "__main__":
    start_server()
