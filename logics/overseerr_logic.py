import json
import re
import requests
from app.logger import logger

class OverseerrLogic:
    """
    Class for handling Overseerr business logic.
    
    This class manages webhook processing from Overseerr for media requests,
    approvals, denials, and other notifications.
    """
    
    def __init__(self, app_config):
        """
        Initialize OverseerrLogic with application configuration.
        
        Args:
            app_config: Application configuration containing TMDb settings.
        """
        self.app_config = app_config
        self.tmdb_api_key = app_config.tmdb.api_key
        self.tmdb_language = app_config.tmdb.language
    
    def clean_year(self, subject):
        """
        Extract year from a string that ends with (YYYY).
        
        Args:
            subject (str): String that may contain a year in parentheses.
            
        Returns:
            str: The year if found, empty string otherwise.
        """
        match = re.search(r"\((\d{4})\)$", subject)  # Search for year at end of string in parentheses
        return match.group(1) if match else ""  # Return year or ""
    
    def get_spanish_title(self, tmdb_id, original, media_type):
        """
        Get the localized title of a movie/series from TMDb if available.
        
        Args:
            tmdb_id (int): TMDb ID of the media.
            original (str): Original title to use as fallback.
            media_type (str): Type of media ('movie' or 'tv').
            
        Returns:
            str: Localized title with year if available, otherwise original title.
        """
        if not tmdb_id or not self.tmdb_api_key:
            return original
        
        try:
            tmdb_url = f"https://api.themoviedb.org/3/{media_type}/{tmdb_id}?api_key={self.tmdb_api_key}&language={self.tmdb_language}"
            response = requests.get(tmdb_url)
            response.raise_for_status()
            tmdb_data = response.json()
            
            logger.info(tmdb_data)
            
            if "name" in tmdb_data:
                return f'{tmdb_data["name"]} ({self.clean_year(original)})'
            elif "title" in tmdb_data:
                return f'{tmdb_data["title"]} ({self.clean_year(original)})'
            else:
                return original
        except requests.RequestException as e:
            logger.warning(f"Error getting localized title from TMDb: {e}")
            return original
    
    def process_webhook(self, event):
        """
        Process an Overseerr webhook.
        
        Args:
            event (dict): Webhook event data from Overseerr.
        """
        notification_type = event.get("notification_type", "")
        
        if notification_type == 'TEST_NOTIFICATION':
            logger.info("Received test webhook from Overseerr...")
        
        elif notification_type == 'MEDIA_AUTO_APPROVED':
            stat_4k = "4K - " if event["media"]["status4k"] == "PENDING" else ""
            self.format_message(event, f"✅  {stat_4k}Auto-approved request:")
        
        elif notification_type == 'MEDIA_APPROVED':
            stat_4k = "4K - " if event["media"]["status4k"] == "PENDING" else ""
            self.format_message(event, f"✅  {stat_4k}Request approved:")
        
        elif notification_type == 'MEDIA_DECLINED':
            stat_4k = "4K - " if event["media"]["status4k"] == "PENDING" else ""
            self.format_message(event, f"❌  {stat_4k}Request declined:")
        
        elif notification_type == 'MEDIA_PENDING':
            stat_4k = "4K - " if event["media"]["status4k"] == "PENDING" else ""
            self.format_message(event, f"🕘  {stat_4k}Request pending:")
        
        else:
            logger.error(f"Unknown overseerr webhook: {json.dumps(event, indent=4)}")
    
    def format_message(self, event, title):
        """
        Format and send notification message.
        
        Args:
            event (dict): Event data from Overseerr.
            title (str): Title for the notification message.
        """
        seasons = ""
        
        if event["media"]["media_type"] == 'movie':
            url = f"https://www.themoviedb.org/movie/{event['media']['tmdbId']}"
            res_title = self.get_spanish_title(event['media']['tmdbId'], event['subject'], "movie")
        else:
            url = f"https://www.themoviedb.org/tv/{event['media']['tmdbId']}"
            res_title = self.get_spanish_title(event['media']['tmdbId'], event['subject'], "tv")
            if len(event['extra']) > 0:
                seasons = event['extra'][0].get('value', "")
        
        res_message = (f"<b>{title}</b>\n"
                      f" <a href=\"{url}\">{res_title}</a>\n"
                      f"      <b>Requested by:</b> <i>{event['request']['requestedBy_username']}</i>")
        
        if seasons != "":
            res_message += f"\n      <b>Seasons:</b> {seasons}"
        
        from utils.telegram_notifier import TelegramNotifier
        telegram_notifier = TelegramNotifier(self.app_config)
        telegram_notifier.send_image_message(res_message, event['image'])
