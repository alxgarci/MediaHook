import json
import requests
import langcodes
from collections import defaultdict
from app.logger import logger
from utils.utils import exit_with_error, bytes_to_gb, clean_title

class RadarrLogic:
    """
    Class for handling Radarr business logic.
    
    This class manages all interactions with Radarr instances, including
    movie downloads, disk space management, quality upgrades, and
    automated movie deletion for space management.
    """
    
    def __init__(self, app_config):
        """
        Initialize RadarrLogic with application configuration.
        
        Args:
            app_config: Application configuration containing Radarr instances
                       and other service configurations.
        """
        self.app_config = app_config
        self.radarr_instances = app_config.radarr_instances
        self.tmdb_api_key = app_config.tmdb.api_key
        self.tmdb_language = app_config.tmdb.language
        self.display_language = app_config.tmdb.display_language
        self.imdb_language = app_config.imdb.language
        
        # Use the first instance as default (can be expanded for multiple instances)
        if self.radarr_instances:
            self.primary_instance = self.radarr_instances[0]
        else:
            logger.error("No Radarr instances configured")
            exit_with_error("No Radarr instances configured")
    
    def get_disk_space(self, instance=None):
        """
        Get free disk space where Radarr movies are stored.
        
        Args:
            instance: Radarr instance to check. Uses primary instance if None.
            
        Returns:
            int: Free space in bytes.
            
        Raises:
            SystemExit: If the configured hard drive route is not found.
        """
        if instance is None:
            instance = self.primary_instance
            
        diskspace_url = f"{instance.api_url}/api/v3/diskspace"
        logger.debug(f"Obtaining disk space from GET {diskspace_url}")
        
        try:
            response = requests.get(diskspace_url, headers=instance.headers)
            response.raise_for_status()
            disk_data = response.json()
            
            logger.debug(f"Response from GET {json.dumps(disk_data, indent=4)}")
            
            for disk in disk_data:
                if instance.hard_drive_route == disk['path']:
                    logger.debug(f'{instance.hard_drive_route} has {bytes_to_gb(disk["freeSpace"])} GB'
                               f' out of {bytes_to_gb(disk["totalSpace"])} GB')
                    return disk['freeSpace']
            
            exit_with_error(f'{instance.hard_drive_route} route not found')
            
        except requests.RequestException as e:
            logger.error(f"Error getting disk space from Radarr: {e}")
            exit_with_error(f"Failed to get disk space from Radarr: {e}")
    
    def parse_language(self, language_list, is_subtitle=False):
        """
        Convert language codes to full language names in the configured language.
        
        Args:
            language_list (list): List of language codes to parse.
            is_subtitle (bool): Whether these languages are for subtitles.
            
        Returns:
            str: Comma-separated language names in configured display language.
        """
        if language_list:
            full_lang = []
            for lang_code in language_list:
                try:
                    full_lang.append(langcodes.Language.get(lang_code).display_name(self.display_language))
                except Exception as e:
                    logger.warning(f"Error parsing language code {lang_code}: {e}")
                    full_lang.append(lang_code)
            res = ', '.join(full_lang)
            return res.title()
        else:
            return "None" if is_subtitle else "Unknown"
    
    def get_spanish_title(self, tmdb_id, original):
        """
        Get the localized title of a movie from TMDb if available.
        
        Args:
            tmdb_id (int): TMDb ID of the movie.
            original (str): Original title to use as fallback.
            
        Returns:
            str: Localized title if available, otherwise original title.
        """
        if not tmdb_id or not self.tmdb_api_key:
            return original
        
        try:
            tmdb_url = f"https://api.themoviedb.org/3/movie/{tmdb_id}?api_key={self.tmdb_api_key}&language={self.tmdb_language}"
            response = requests.get(tmdb_url)
            response.raise_for_status()
            tmdb_data = response.json()
            
            return tmdb_data.get("title", original)  # Return localized title if available
        except requests.RequestException as e:
            logger.warning(f"Error getting localized title from TMDb: {e}")
            return original
    
    def get_no_delete_tag_id(self, instance=None):
        """
        Get the ID of the 'no_delete' tag in Radarr.
        
        Args:
            instance: Radarr instance to check. Uses primary instance if None.
            
        Returns:
            int: ID of the 'no_delete' tag.
            
        Raises:
            SystemExit: If the 'no_delete' tag is not found.
        """
        if instance is None:
            instance = self.primary_instance
            
        tag_url = f"{instance.api_url}/api/v3/tag"
        logger.debug(f"Obtaining ID tag from GET {tag_url}")
        
        try:
            response = requests.get(tag_url, headers=instance.headers)
            response.raise_for_status()
            tags = response.json()
            
            logger.debug(f"Response from GET {json.dumps(tags, indent=4)}")
            
            for tag in tags:
                if tag["label"].lower() == "no_delete":
                    logger.debug(f"no_delete tag id: {tag['id']}")
                    return tag["id"]
            
            exit_with_error(f'{tag_url} no_delete tag not found')
            
        except requests.RequestException as e:
            logger.error(f"Error getting tags from Radarr: {e}")
            exit_with_error(f"Failed to get tags from Radarr: {e}")
    
    def get_movies_without_no_delete_tag(self, instance=None):
        """
        Get all Radarr movies without the 'no_delete' tag.
        
        Args:
            instance: Radarr instance to check. Uses primary instance if None.
            
        Returns:
            list: List of movies that don't have the 'no_delete' tag.
        """
        if instance is None:
            instance = self.primary_instance
            
        movies_url = f"{instance.api_url}/api/v3/movie"
        logger.debug(f"Calling GET {movies_url}")
        
        try:
            response = requests.get(movies_url, headers=instance.headers)
            response.raise_for_status()
            movies = response.json()
            
            logger.debug(f"Response from GET {response.status_code}")
            
            tag_id = self.get_no_delete_tag_id(instance)
            # Filter movies without the 'no_delete' tag
            filtered_movies = [p for p in movies if tag_id not in p["tags"]]
            logger.debug(f"Found {len(filtered_movies)} movies without 'no_delete' tag")
            
            return filtered_movies
            
        except requests.RequestException as e:
            logger.error(f"Error getting movies from Radarr: {e}")
            exit_with_error(f"Failed to get movies from Radarr: {e}")
    
    def delete_movies(self, movies_to_delete):
        """
        Delete selected movies from Radarr.
        
        Args:
            movies_to_delete (list): List of movie IDs to delete.
        """
        from utils.delete_manual_import import DeleteManualImportManager
        from utils.telegram_notifier import res_actions_send
        
        instance = self.primary_instance
        res_actions_del = []
        res_actions_nodel = []
        
        # Check dry_run mode
        dry_run = self.app_config.general.get('dry_run', True)
        if dry_run:
            logger.info("🔍 DRY RUN MODE: Movies will not be actually deleted from Radarr")
        
        # Initialize the manual import manager
        manual_import_manager = DeleteManualImportManager(self.app_config)
        
        for movie_id in movies_to_delete:
            res_actions_del_add, res_actions_nodel_add = manual_import_manager.process_item('radarr', movie_id)
            res_actions_del.extend(res_actions_del_add)
            res_actions_nodel.extend(res_actions_nodel_add)
            
            if dry_run:
                logger.info(f"🔍 DRY RUN: Would delete movie id {movie_id} from Radarr")
            else:
                try:
                    response = requests.delete(
                        f"{instance.api_url}/api/v3/movie/{movie_id}?deleteFiles=true", 
                        headers=instance.headers
                    )
                    logger.info(f"Deleting movie id {movie_id}: "
                              f"{instance.api_url}/api/v3/movie/{movie_id}?deleteFiles=true: "
                              f"STATUS {response.status_code}")
                except requests.RequestException as e:
                    logger.error(f"Error deleting movie {movie_id}: {e}")
        
        logger.info(json.dumps(res_actions_del, indent=4))
        logger.info(json.dumps(res_actions_nodel, indent=4))
        res_actions_send(res_actions_del, res_actions_nodel)
    
    def get_poster(self, movie_images):
        """
        Extract the poster URL from a movie's images.
        
        Args:
            movie_images (list): List of image objects for the movie.
            
        Returns:
            str or None: URL of the poster image, or None if not found.
        """
        for image in movie_images:
            if image["coverType"] == "poster":
                return image["remoteUrl"]
        return None
    
    def process_event(self, event):
        """
        Process a Radarr webhook and manage movie deletion.
        
        Args:
            event (dict): Webhook event data from Radarr.
        """
        logger.debug(f"Processing radarr event [{event.get('eventType', '')}]")
        
        if event.get("eventType", "") != "Download":
            logger.warning(f"Event not Download/Upgrade, not processed : [{event.get('eventType', '')}]")
            return
        
        is_upgrade = event.get("isUpgrade", False)
        
        # Imported movie data
        movie_id = event["movie"]["id"]
        movie_year = event["movie"]["year"]
        movie_size = event["movieFile"]["size"]
        movie_imdb_id = event["movie"]["imdbId"]
        movie_quality = event["movieFile"]["quality"]
        movie_poster = self.get_poster(event["movie"]["images"])  # If no poster = None
        movie_title = self.get_spanish_title(event["movie"]["tmdbId"], event["movie"]["title"])
        
        # Get imported movie details (audio/subtitle languages)
        audio_tracks = self.parse_language(event["movieFile"]["mediaInfo"]["audioLanguages"])
        subtitles = self.parse_language(event["movieFile"]["mediaInfo"]["subtitles"], is_subtitle=True)
        
        # Notification structures
        added_movie = {
            "title": movie_title,
            "year": movie_year,
            "audio": audio_tracks,
            "subtitles": subtitles,
            "imdbUrl": f"https://www.imdb.com/{self.imdb_language}/title/{movie_imdb_id}",
            "quality": movie_quality,
            "poster": movie_poster
        }
        freed_space = 0
        deleted_movies = []
        
        available_space = self.get_disk_space()
        
        if available_space > self.primary_instance.hard_drive_threshold:
            logger.info(f"Sufficient disk space ({bytes_to_gb(available_space)} GB), "
                       f"no movies will be deleted.")
        else:
            available_movies = self.get_movies_without_no_delete_tag()
            available_movies = sorted(available_movies, key=lambda x: x["added"])
            
            movies_to_delete = []
            
            for movie in available_movies:
                if freed_space >= movie_size:
                    break
                
                movie_id_to_delete = movie["id"]
                movie_title_to_delete = self.get_spanish_title(movie["tmdbId"], movie["title"])
                movie_size_to_delete = movie.get("sizeOnDisk", 0)
                movie_imdbid = movie["imdbId"]
                movie_year_to_delete = movie["year"]
                
                freed_space += movie_size_to_delete
                movies_to_delete.append(movie_id_to_delete)
                
                deleted_movies.append({
                    "title": movie_title_to_delete,
                    "year": movie_year_to_delete,
                    "size": movie_size_to_delete,
                    "imdbUrl": f"https://www.imdb.com/{self.imdb_language}/title/{movie_imdbid}"
                })
                logger.debug(f"Marking for deletion: {movie_title_to_delete} "
                           f"({bytes_to_gb(movie_size_to_delete)} GB)")
            
            # Execute movie deletion
            self.delete_movies(movies_to_delete)
        
        # Final notification with added and deleted movies
        logger.info(f"Radarr message dict added movies: {json.dumps(added_movie, indent=4)}")
        logger.info(f"Radarr message dict deleted movies: {json.dumps(deleted_movies, indent=4)}")
        logger.info(f"Total space freed: {bytes_to_gb(freed_space)} GB")
        
        # Send notification to Telegram
        from utils.telegram_notifier import TelegramNotifier
        telegram_notifier = TelegramNotifier(self.app_config)
        telegram_notifier.send_radarr_message(added_movie, deleted_movies, freed_space, is_upgrade)
