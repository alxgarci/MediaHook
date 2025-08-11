# MediaHook

[![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?style=for-the-badge&logo=docker&logoColor=white)](https://github.com/alxgarci/MediaHook/pkgs/container/mediahook)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/flask-%23000.svg?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com/)

MediaHook is an automated webhook system that integrates **Sonarr**, **Radarr**, **Overseerr**, and **qBittorrent** to automatically manage media downloads and hard drive available space with Telegram notifications.

## Features

- Set a space threshold, and if reached or over it will delete content to get over it after importing or upgrading any movie/episode.
- Will remove episodes or movies in the instances provided and delete any torrent hash present in qBittorrent clients (if present) to avoid hardlinks from not freeing space and fulfilling the harddrive.
- Will check for manual imported names for content imported manually but from qBittorrent, matching by title of files or torrent, with secure matching guaranteen that nothing gets removed if it does not match.
- If the seed_limit has not been reached, will set the seed_time specified on the qBittorrent client and will only remove the content from Sonarr/Radarr.
- Can exclude any full shows or movies by adding the tag `no_delete` inside Sonarr/Radarr.

## Table of Contents

- [MediaHook](#mediahook)
  - [Features](#features)
  - [Table of Contents](#table-of-contents)
  - [Requirements](#requirements)
  - [Installation](#installation)
    - [Option 1: Using GitHub Container Registry image (Recommended)](#option-1-using-github-container-registry-image-recommended)
    - [Option 2: Local build](#option-2-local-build)
  - [Configuration](#configuration)
    - [Modify the default configuration file](#modify-the-default-configuration-file)
    - [Configuration file parameters](#configuration-file-parameters)
    - [TMDB Locales](#tmdb-locales)
    - [Multiple qBittorrent instances](#multiple-qbittorrent-instances)
  - [Webhook Configuration](#webhook-configuration)
    - [Sonarr](#sonarr)
    - [Radarr](#radarr)
    - [Overseerr](#overseerr)
  - [Available Endpoints](#available-endpoints)
  - [DRY RUN Mode](#dry-run-mode)
    - [What does DRY RUN mode do?](#what-does-dry-run-mode-do)
  - [More Features](#more-features)
    - [Torrent Management](#torrent-management)
    - [Sonarr/Radarr Integration](#sonarrradarr-integration)
    - [Telegram Notifications](#telegram-notifications)
  - [Project Structure](#project-structure)
  - [Development and Contributing](#development-and-contributing)
    - [Local setup](#local-setup)
    - [Local Docker build](#local-docker-build)
  - [Logs and Monitoring](#logs-and-monitoring)
    - [Log levels:](#log-levels)
    - [Real-time monitoring:](#real-time-monitoring)
  - [Troubleshooting](#troubleshooting)
    - [Issue: Connection error to Sonarr/Radarr](#issue-connection-error-to-sonarrradarr)
    - [Issue: Telegram not sending messages](#issue-telegram-not-sending-messages)
    - [Issue: Docker permissions](#issue-docker-permissions)
  - [Security](#security)
  - [Roadmap](#roadmap)
  - [License](#license)
  - [Contributing](#contributing)
  - [Support](#support)


## Requirements

- Docker and Docker Compose
- Sonarr/Radarr configured with webhooks
- qBittorrent with Web API enabled
- Telegram bot token
- TMDB API key

## Installation

### Option 1: Using GitHub Container Registry image (Recommended)

```yaml
# docker-compose.yml
version: '3.8'

services:
  mediahook:
    image: ghcr.io/alxgarci/mediahook:latest
    container_name: mediahook
    ports:
      - "4343:4343"
    volumes:
      - ./config:/app/config
    restart: unless-stopped
```

### Option 2: Local build

```bash
# Clone repository
git clone https://github.com/alxgarci/MediaHook.git
cd MediaHook

# Run with Docker Compose
docker-compose up -d
```

## Configuration

### Modify the default configuration file

When you start the Docker container for the first time, a sample `config.json` file will be created in the mounted configuration directory. The container will then exit automatically. You must edit this file to match your environment and requirements before restarting the container. See the next section for detailed configuration instructions.

### Configuration file parameters

If having more than one instance of qBittorrent, refer to [this section](#multiple-qbittorrent-instances)

Edit `config/config.json` with your data:

> [!WARNING]
> Remember to use the example config file, do not copy and paste from this .json as .jsons cannot have comments and will fail reading it. It is just showing the meaning of every field available.

```json
{
  "sonarr": [
    {
      "name": "sonarr_main",              // Identifier name
      "host": "192.168.1.100",            // Sonarr server IP
      "port": 8989,                       // Sonarr port
      "api_key": "your_sonarr_api_key",   // Sonarr API Key
      "hard_drive_route": "/media/data",   // Hard drive path AS SHOWN INSIDE SONARR
      "hard_drive_threshold": 500          // Threshold in GB for alerts
    }
  ],
  "radarr": [
    {
      "name": "radarr_main",              // Identifier name
      "host": "192.168.1.100",            // Radarr server IP
      "port": 7878,                       // Radarr port
      "api_key": "your_radarr_api_key",   // Radarr API Key
      "hard_drive_route": "/media/data",   // Hard drive path AS SHOWN INSIDE RADARR
      "hard_drive_threshold": 500          // Threshold in GB for alerts
    }
  ],
  "qbittorrent": [
    {
      "name": "qbittorrent_vpn",          // Identifier name
      "host": "192.168.1.101",            // qBittorrent server IP
      "port": 8081,                       // Web UI port
      "username": "admin",                // qBittorrent username
      "password": "your_password",        // qBittorrent password
      "seed_limit": 23040                 // Seeding limit in minutes (16 days)
    }
  ],
  "tmdb": {
    "api_key": "your_tmdb_api_key",      // TMDB API Key
    "language": "es-ES",                 // Preferred language for movie/show titles. See the TMDB Locales section below for supported values.
    "display_language": "es"             // Language for displaying subtitles and audio (in movies). Can use any of the present in https://www.iana.org/assignments/language-subtag-registry/language-subtag-registry
  },
  "telegram": {
    "token": "your_telegram_bot_token",  // Telegram bot token
    "chat_id": "your_chat_id",          // Chat ID for notifications
    "private_chat_id": "your_private_id" // Private chat ID
  },
  "general": {
    "log_level": "INFO",                 // Log level (DEBUG, INFO, WARNING, ERROR)
    "dry_run": true                      // Safe mode (doesn't execute deletions)
  }
}
```

### TMDB Locales

As of 2025, TMDB locales that can be used are:

```json
"af-ZA", "ar-AE", "ar-BH", "ar-EG", "ar-IQ", "ar-JO", "ar-LY", "ar-MA", "ar-QA", "ar-SA", 
"ar-TD", "ar-YE", "be-BY", "bg-BG", "bn-BD", "br-FR", "ca-AD", "ca-ES", "ch-GU", "cs-CZ", 
"cy-GB", "da-DK", "de-AT", "de-CH", "de-DE", "el-CY", "el-GR", "en-AG", "en-AU", "en-BB", 
"en-BZ", "en-CA", "en-CM", "en-GB", "en-GG", "en-GH", "en-GI", "en-GY", "en-IE", "en-JM", 
"en-KE", "en-LC", "en-MW", "en-NZ", "en-PG", "en-TC", "en-US", "en-ZM", "en-ZW", "eo-EO", 
"es-AR", "es-CL", "es-DO", "es-EC", "es-ES", "es-GQ", "es-GT", "es-HN", "es-MX", "es-NI", 
"es-PA", "es-PE", "es-PY", "es-SV", "es-UY", "et-EE", "eu-ES", "fa-IR", "fi-FI", "fr-BF", 
"fr-CA", "fr-CD", "fr-CI", "fr-FR", "fr-GF", "fr-GP", "fr-MC", "fr-ML", "fr-MU", "fr-PF", 
"ga-IE", "gd-GB", "gl-ES", "he-IL", "hi-IN", "hr-HR", "hu-HU", "id-ID", "it-IT", "it-VA", 
"ja-JP", "ka-GE", "kk-KZ", "kn-IN", "ko-KR", "ku-TR", "ky-KG", "lt-LT", "lv-LV", "ml-IN", 
"mr-IN", "ms-MY", "ms-SG", "nb-NO", "nl-BE", "nl-NL", "no-NO", "pa-IN", "pl-PL", "pt-AO", 
"pt-BR", "pt-MZ", "pt-PT", "ro-MD", "ro-RO", "ru-RU", "si-LK", "sk-SK", "sl-SI", "so-SO", 
"sq-AL", "sq-XK", "sr-ME", "sr-RS", "sv-SE", "sw-TZ", "ta-IN", "te-IN", "th-TH", "tl-PH", 
"tr-TR", "uk-UA", "ur-PK", "uz-UZ", "vi-VN", "zh-CN", "zh-HK", "zh-SG", "zh-TW", "zu-ZA"
```

If a translation is available for the TMDB ID you are requesting, you will get the title in that locale. If no translation is available on that locale, will use en-US. If not even the en-US is available, will use the original language title for that media content.
Can get the updated list of locales available in https://developer.themoviedb.org/reference/configuration-primary-translations

### Multiple qBittorrent instances

If you do have multiple qBittorrent instances, just specify those as a list inside the qBittorrent settings section. A sample could be:

```json
  "qbittorrent": [
    {
      "name": "qbittorrent_a",
      "host": "localhost",
      "port": 8081,
      "username": "admin",
      "password": "admin",
      "seed_limit": 23040
    },
    {
      "name": "qbittorrent_b",
      "host": "localhost",
      "port": 8080,
      "username": "admin",
      "password": "admin",
      "seed_limit": 23040
    }
  ],
```

## Webhook Configuration

### Sonarr
```
URL: http://your-ip:4343/webhook/sonarr
Method: POST
Triggers: On File Import, On File Upgrade
```

### Radarr
```
URL: http://your-ip:4343/webhook/radarr
Method: POST
Triggers: On File Import, On File Upgrade
```

### Overseerr
```
Enable Agent: ✓
URL: http://your-ip:4343/webhook/overseerr
Payload: Do not modify anything unless you know what you are doing
Triggers: Select all
```

## Available Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/webhook/sonarr` | POST | Receives webhooks from Sonarr |
| `/webhook/radarr` | POST | Receives webhooks from Radarr |
| `/webhook/overseerr` | POST | Receives webhooks from Overseerr |

## DRY RUN Mode

DRY RUN mode is a safety feature that allows testing the configuration without executing destructive actions:

```json
{
  "general": {
    "dry_run": true
  }
}
```

### What does DRY RUN mode do?

- ✅ **Executes all processing logic**
- ✅ **Sends Telegram notifications**
- ✅ **Logs all actions** it would perform
- ❌ **Does NOT delete torrents** from qBittorrent
- ❌ **Does NOT delete files** from disk
- ❌ **Does NOT modify** Sonarr/Radarr

## More Features

### Torrent Management
- **Manual import detection**: Identifies torrents imported manually through qBittorrent
- **Cross-seed handling**: Processes multiple torrents with similar names (cross-seeds)
- **Seeding time verification**: Checks if torrents have met minimum seeding requirements
- **Multi-instance support**: Searches across all configured qBittorrent instances

### Sonarr/Radarr Integration
- **Webhook processing**: Handles import and upgrade events from Sonarr/Radarr
- **Space threshold monitoring**: Monitors disk space against configured thresholds
- **Content deletion**: Removes episodes/movies when space threshold is exceeded (older first)
- **Manual import cleanup**: Deletes torrents associated with manually imported content

### Telegram Notifications
- **Space monitoring alerts**: Notifications when any movie/show is downloaded into the Sonarr/Radarr library
- **Multi-language support**: Delivers notifications and media titles in your preferred language, not just English
- **Grouped import notifications**: Sends a single notification summarizing all imported shows when multiple episodes are added at once (within 20 seconds)
- **Clear notifications**: Provides chat updates on submitted requests, including acceptance, import, removal, or update of media content
- **Content removal reports**: Details of episodes/movies deleted to free space on your Private Chat
- **Manual import summaries**: Reports of processed manual imports and torrent deletions on your Private Chat
- **System status updates**: Operational status and error notifications on your Private Chat

## Project Structure

```
MediaHook/
├── app/                    # Flask application
│   ├── flask_app.py       # Main server
│   └── logger.py          # Logging system
├── config/                # Configuration
│   ├── config.example.json # Configuration template
│   └── logs/              # Log files
├── logics/                # Business logic
│   ├── overseerr_logic.py # Overseerr processing
│   ├── radarr_logic.py    # Radarr processing
│   └── sonarr_logic.py    # Sonarr processing
├── utils/                 # Utilities
│   ├── delete_manual_import.py # Torrent management
│   ├── qbittorrent_connections.py # qBittorrent connections
│   ├── telegram_notifier.py # Telegram notifications
│   └── utils.py           # Helper functions
├── docker-compose.yml     # Docker Compose configuration
├── Dockerfile            # Optimized Docker image
├── requirements.txt      # Python dependencies
└── run.py               # Entry point
```

## Development and Contributing

### Local setup

```bash
# Clone repository
git clone https://github.com/alxgarci/MediaHook.git
cd MediaHook

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# or
.venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt

# Copy configuration
cp config/config.example.json config/config.json

# Run in development mode
python run.py
```

### Local Docker build

```bash
# Build image
docker build -t mediahook:local .

# Run container
docker run -d \
  --name mediahook \
  -p 4343:4343 \
  -v ./config:/app/config \
  mediahook:local
```

## Logs and Monitoring

Logs are stored in:
- **Container**: `/app/config/logs/app.log`
- **Host**: `./config/logs/app.log`

### Log levels:
- `DEBUG`: Detailed information for debugging
- `INFO`: General operation information
- `WARNING`: Warnings about potential issues
- `ERROR`: Errors that require attention

### Real-time monitoring:
```bash
# View logs in real-time
docker logs -f mediahook

# View logs from file
tail -f config/logs/app.log
```

## Troubleshooting

### Issue: Connection error to Sonarr/Radarr
```bash
# Verify connectivity
curl http://your-ip:8989/api/v3/system/status?apikey=your_api_key
```

### Issue: Telegram not sending messages
```bash
# Verify bot token
curl https://api.telegram.org/bot<TOKEN>/getMe

# Get chat id (need to send a message to the bot for your id to appear here)
curl https://api.telegram.org/bot<TOKEN>/getUpdates
```

### Issue: Docker permissions
```bash
# Verify config directory permissions
chmod -R 777 ./config
```

## Security

- **API Keys**: Never expose API keys in logs or public repositories.
- **Dry Run**: Always use DRY RUN mode to test configurations. 
  
> [!TIP]
> If `dry_run` is missing or incorrectly set in the configuration file, it will default to `true`.

## Roadmap

- [ ] Integrate more notification clients or Apprise?
- [ ] Allow multiple Sonarr/Radarr instances.

## License

This project is licensed under the MIT License. See the `LICENSE` file for more details.

## Contributing

Contributions are welcome. Please:

1. Fork the project
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## Support

- **Issues**: [GitHub Issues](https://github.com/alxgarci/MediaHook/issues)

---

⭐ **If you like MediaHook, give it a star on GitHub!** ⭐
