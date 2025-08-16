"""
Telegram Notification Manager

This module provides comprehensive Telegram notification functionality
for the MediaHook application. It handles sending formatted messages
for Sonarr and Radarr events, including media additions, deletions,
updates, and automated torrent management results.

Classes:
    TelegramNotifier: Main class for handling Telegram notifications

Functions:
    Compatibility functions for backward compatibility with existing code

The module supports rich HTML formatting, image attachments, and
different chat channels for different types of notifications.
"""

import requests
from app.logger import logger
from utils.utils import bytes_to_gb

class TelegramNotifier:
    """
    Class for handling Telegram notifications
    
    This class manages all Telegram communications for the MediaHook application,
    providing methods to send formatted notifications for various media events
    including series additions, movie updates, and torrent management results.
    
    Attributes:
        app_config: Application configuration object
        telegram_config: Telegram-specific configuration
        token: Telegram bot token
        chat_id: Main chat ID for notifications
        private_chat_id: Private chat ID for qBittorrent messages
        base_url: Base URL for Telegram API
        send_message_url: URL for sending text messages
        send_photo_url: URL for sending photo messages
    """
    
    def __init__(self, app_config):
        """
        Initialize the Telegram notifier
        
        Args:
            app_config: Application configuration containing Telegram settings
        """
        self.app_config = app_config
        self.telegram_config = app_config.telegram
        self.token = self.telegram_config.token
        self.chat_id = self.telegram_config.chat_id
        self.private_chat_id = self.telegram_config.private_chat_id
        
        # Base URLs for Telegram API
        self.base_url = f"https://api.telegram.org/bot{self.token}"
        self.send_message_url = f"{self.base_url}/sendMessage"
        self.send_photo_url = f"{self.base_url}/sendPhoto"
    
    def send_sonarr_message(self, added, deleted, updated, deleted_size):
        """
        Send Sonarr notification to Telegram
        
        Args:
            added: Dictionary of added series and episodes
            deleted: Dictionary of deleted episodes
            updated: Dictionary of updated episodes
            deleted_size: Total size of deleted content in bytes
        """
        res_message = ""
        
        if added:
            res_message += "📺 <b>Series added:</b>\n"
            for series, episodes in added.items():
                res_message += f"  🔸 <a href=\"{episodes[0]['imdbUrl']}\">{series}</a>\n"
                for episode in episodes:
                    res_message += f"    - <a href=\"{episode['url']}\">S{episode['season']}E{episode['episode']}</a>\n"
                res_message += "\n"
        
        if updated:
            res_message += "🔄 <b>Series updated:</b>\n"
            for series, episodes in updated.items():
                res_message += f"  🔸 <a href=\"{episodes[0]['imdbUrl']}\">{series}</a>\n"
                for episode in episodes:
                    res_message += f"    - <a href=\"{episode['url']}\">S{episode['season']}E{episode['episode']}</a>\n"
                res_message += "\n"
        
        if deleted:
            res_message += "🗑️ <b>Episodes deleted:</b>\n"
            for series, episodes in deleted.items():
                res_message += f"  🔹 <a href=\"{episodes[0]['imdbUrl']}\">{series}</a>\n"
                for episode in episodes:
                    res_message += f"    - <a href=\"{episode['url']}\">S{episode['season']}E{episode['episode']}</a>\n"
                res_message += "\n"
        
        if res_message:
            self.send_message(res_message, parse_mode=True)
    
    def send_radarr_message(self, added, deleted, deleted_size, is_upgrade):
        """
        Send Radarr notification to Telegram
        
        Args:
            added: Dictionary containing added movie information
            deleted: List of deleted movies
            deleted_size: Total size of deleted content in bytes
            is_upgrade: Boolean indicating if this is an upgrade operation
        """
        action = "🔄 updated" if is_upgrade else "🎬 added"
        
        res_message = f"🎭 <b>Movie {action}:</b>\n"
        res_message += f"  🔸 <a href=\"{added['imdbUrl']}\">{added['title']} ({added['year']})</a>\n"
        res_message += f"    - <b>Quality:</b> {added['quality']['quality']['name']}\n"
        res_message += f"    - <b>Audio:</b> {added['audio']}\n"
        res_message += f"    - <b>Subtitles:</b> {added['subtitles']}\n\n"
        
        if deleted:
            res_message += "🗑️ <b>Movies deleted:</b>\n"
            for movie in deleted:
                res_message += f"  🔹 <a href=\"{movie['imdbUrl']}\">{movie['title']} ({movie['year']})</a>\n"
                res_message += f"    - {bytes_to_gb(movie['size'])} GB\n"
        
        if added.get('poster'):
            self.send_image_message(res_message, added['poster'])
        else:
            self.send_message(res_message, parse_mode=True)
    
    def send_message(self, message, parse_mode=False):
        """
        Send a text message to Telegram
        
        Args:
            message: Text message to send
            parse_mode: Boolean indicating whether to use HTML parsing
        """
        try:
            params = {
                'chat_id': self.chat_id,
                'text': message,
                'disable_web_page_preview': True
            }
            
            if parse_mode:
                params['parse_mode'] = 'HTML'
            
            response = requests.get(self.send_message_url, params=params)
            response.raise_for_status()
            
            logger.debug(f"Message sent to Telegram: {message[:100]}...")
            
        except requests.RequestException as e:
            logger.error(f"Error sending message to Telegram: {e}")
    
    def send_image_message(self, message, image_url):
        """
        Send a message with image to Telegram
        
        Args:
            message: Caption text for the image
            image_url: URL of the image to send
        """
        try:
            params = {
                'chat_id': self.chat_id,
                'photo': image_url,
                'caption': message,
                'parse_mode': 'HTML'
            }
            
            response = requests.get(self.send_photo_url, params=params)
            response.raise_for_status()
            
            logger.debug(f"Message with image sent to Telegram: {message[:100]}...")
            
        except requests.RequestException as e:
            logger.error(f"Error sending message with image to Telegram: {e}")
            # Fallback: send text only
            self.send_message(message, parse_mode=True)
    
    def send_qbit_message(self, message):
        """
        Send a qBittorrent message to the private chat
        
        Args:
            message: Message text to send to the private chat
        """
        try:
            params = {
                'chat_id': self.private_chat_id,
                'text': message,
                'parse_mode': 'HTML',
                'disable_web_page_preview': True
            }
            
            response = requests.get(self.send_message_url, params=params)
            response.raise_for_status()
            
            logger.debug(f"qBittorrent message sent to Telegram: {message[:100]}...")
            
        except requests.RequestException as e:
            logger.error(f"Error sending qBittorrent message to Telegram: {e}")
    
    def send_action_results(self, del_actions, no_del_actions):
        """
        Send deletion action results
        
        Args:
            del_actions: List of successful deletion actions
            no_del_actions: List of failed or skipped deletion actions
        """
        from utils.delete_manual_import import DeleteManualImportManager
        
        # Use class constants
        KEY_ACT_DEL = DeleteManualImportManager.KEY_ACT_DEL
        KEY_ACT_NODELETE = DeleteManualImportManager.KEY_ACT_NODELETE
        
        if del_actions or no_del_actions:
            res_message = "🤖 <b>Automatic deletion results:</b>\n\n"
            
            if del_actions:
                res_message += "✅ <b>Deleted:</b>\n"
                for action in del_actions:
                    if action and action.get('action') == KEY_ACT_DEL:
                        res_message += f"  🔹 Torrent deleted\n"
                res_message += "\n"
            
            if no_del_actions:
                res_message += "❌ <b>Not deleted:</b>\n"
                for action in no_del_actions:
                    if action and action.get('action') == KEY_ACT_NODELETE:
                        reason = action.get('reason', 'Unknown reason')
                        res_message += f"  🔸 {reason}\n"
                res_message += "\n"
            
            self.send_qbit_message(res_message)

# Compatibility functions to maintain the previous interface
def res_actions_send(res_actions_del, res_actions_no_del):
    """
    Compatibility function for action results
    
    Args:
        res_actions_del: List of successful deletion actions
        res_actions_no_del: List of failed or skipped deletion actions
    """
    from app.flask_app import app_config
    notifier = TelegramNotifier(app_config)
    notifier.send_action_results(res_actions_del, res_actions_no_del)
