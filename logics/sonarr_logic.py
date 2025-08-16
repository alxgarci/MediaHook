import json
import requests
from collections import defaultdict
from app.logger import logger
from utils.utils import bytes_to_gb, exit_with_error

class SonarrLogic:
    """
    Class for handling Sonarr business logic.
    
    This class manages all interactions with Sonarr instances, including
    webhooks processing, series management, disk space monitoring,
    and automated quality upgrades.
    """
    
    def __init__(self, app_config):
        """
        Initialize SonarrLogic with application configuration.
        
        Args:
            app_config: Application configuration containing Sonarr instances
                       and other service configurations.
        """
        self.app_config = app_config
        self.sonarr_instances = app_config.sonarr_instances
        self.tmdb_api_key = app_config.tmdb.api_key
        self.tmdb_language = app_config.tmdb.language
        self.imdb_language = app_config.imdb.language
        
        # Use the first instance as default (can be expanded for multiple instances)
        if self.sonarr_instances:
            self.primary_instance = self.sonarr_instances[0]
        else:
            logger.error("No Sonarr instances configured")
            exit_with_error("No Sonarr instances configured")
    
    def get_disk_space(self, instance=None):
        """
        Get free disk space where Sonarr files are stored.
        
        Args:
            instance: Sonarr instance to check. Uses primary instance if None.
            
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
            logger.error(f"Error getting disk space from Sonarr: {e}")
            exit_with_error(f"Failed to get disk space from Sonarr: {e}")
    
    def get_no_delete_tag_id(self, instance=None):
        """
        Get the ID of the 'no_delete' tag in Sonarr.
        
        Args:
            instance: Sonarr instance to check. Uses primary instance if None.
            
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
            logger.error(f"Error getting tags from Sonarr: {e}")
            exit_with_error(f"Failed to get tags from Sonarr: {e}")
    
    def get_series_without_no_delete_tag(self, tag_id, instance=None):
        """
        Get all Sonarr series without the 'no_delete' tag.
        
        Args:
            tag_id (int): ID of the 'no_delete' tag to filter out.
            instance: Sonarr instance to check. Uses primary instance if None.
            
        Returns:
            list: List of series that don't have the 'no_delete' tag.
        """
        if instance is None:
            instance = self.primary_instance
            
        series_url = f"{instance.api_url}/api/v3/series?includeSeasonImages=False"
        logger.debug(f"Calling GET {series_url}")
        
        try:
            response = requests.get(series_url, headers=instance.headers)
            response.raise_for_status()
            series = response.json()
            
            logger.debug(f"Response from GET {response.status_code} {len(series)} series")
            
            filtered_series = [serie for serie in series if tag_id not in serie["tags"]]
            logger.debug(f"Filtered series {len(filtered_series)} series without 'no_delete' tag")
            
            return filtered_series
            
        except requests.RequestException as e:
            logger.error(f"Error getting series from Sonarr: {e}")
            exit_with_error(f"Failed to get series from Sonarr: {e}")
    
    def get_downloaded_episodes(self, series_id, instance=None):
        """
        Get downloaded episodes of a series and sort them by age.
        
        Args:
            series_id (int): ID of the series in Sonarr.
            instance: Sonarr instance to check. Uses primary instance if None.
            
        Returns:
            list: List of downloaded episodes sorted by date, season, and episode number.
        """
        if instance is None:
            instance = self.primary_instance
            
        episode_url = f"{instance.api_url}/api/v3/episode?seriesId={series_id}&includeEpisodeFile=true&includeSeries=false"
        logger.debug(f"Calling GET {episode_url}")
        
        try:
            response = requests.get(episode_url, headers=instance.headers)
            response.raise_for_status()
            episodes = response.json()
            
            logger.debug(f"Response from GET {response.url} {response.status_code}")
            
            # Only include episodes with file downloaded
            downloaded_episodes = [ep for ep in episodes if ep.get("hasFile", False)]
            
            # Grouping episodes by most recent date of an episode found in a season
            season_dates = defaultdict(lambda: None)
            for ep in downloaded_episodes:
                season = ep["seasonNumber"]
                date_added = ep["episodeFile"]["dateAdded"]
                
                # If no date is recorded for the season or we find a more recent one, update
                if season_dates[season] is None or date_added > season_dates[season]:
                    season_dates[season] = date_added
            
            # Each episode in a season will receive the most recent downloaded episode date
            for ep in downloaded_episodes:
                ep["episodeFile"]["dateAdded"] = season_dates[ep["seasonNumber"]]
            
            downloaded_episodes_sorted = sorted(
                downloaded_episodes, 
                key=lambda x: (x["episodeFile"]["dateAdded"], x["seasonNumber"], x["episodeNumber"])
            )
            
            logger.debug(f"Got episodes for seriesId {series_id} with file")
            return downloaded_episodes_sorted
            
        except requests.RequestException as e:
            logger.error(f"Error getting episodes for series {series_id}: {e}")
            return []
    
    def delete_episodes(self, episodes_to_delete):
        """
        Delete selected episodes from Sonarr.
        
        Args:
            episodes_to_delete (list): List of episodes to delete.
        """
        from utils.delete_manual_import import DeleteManualImportManager
        from utils.telegram_notifier import res_actions_send
        
        instance = self.primary_instance
        res_actions_del = []
        res_actions_nodel = []
        
        # Check dry_run mode
        dry_run = self.app_config.general.get('dry_run', True)
        if dry_run:
            logger.info("🔍 DRY RUN MODE: Episodes will not be actually deleted from Sonarr")
        
        # Initialize the manual import manager
        manual_import_manager = DeleteManualImportManager(self.app_config)
        
        for episode in episodes_to_delete:
            res_actions_del_add, res_actions_nodel_add = manual_import_manager.process_item('sonarr', episode['episodeId'])
            res_actions_del.extend(res_actions_del_add)
            res_actions_nodel.extend(res_actions_nodel_add)
            
            if dry_run:
                logger.info(f"🔍 DRY RUN: Would delete episode id {episode['episodeFileId']} from Sonarr")
            else:
                try:
                    response = requests.delete(
                        f"{instance.api_url}/api/v3/episodefile/{episode['episodeFileId']}", 
                        headers=instance.headers
                    )
                    logger.info(f"Deleting episode id {episode['episodeFileId']}: "
                              f"{instance.api_url}/api/v3/episodefile/{episode['episodeFileId']}: "
                              f"STATUS {response.status_code}")
                except requests.RequestException as e:
                    logger.error(f"Error deleting episode {episode['episodeFileId']}: {e}")
        
        logger.info(json.dumps(res_actions_del, indent=4))
        logger.info(json.dumps(res_actions_nodel, indent=4))
        res_actions_send(res_actions_del, res_actions_nodel)
    
    def get_spanish_title(self, tmdb_id, original):
        """
        Get the Spanish title of a series from TMDb if available.
        
        Args:
            tmdb_id (int): TMDb ID of the series.
            original (str): Original title to use as fallback.
            
        Returns:
            str: Spanish title if available, otherwise original title.
        """
        if not tmdb_id or not self.tmdb_api_key:
            return original
        
        try:
            tmdb_url = f"https://api.themoviedb.org/3/tv/{tmdb_id}?api_key={self.tmdb_api_key}&language={self.tmdb_language}"
            response = requests.get(tmdb_url)
            response.raise_for_status()
            tmdb_data = response.json()
            
            return tmdb_data.get("name", original)  # Return Spanish title if available
        except requests.RequestException as e:
            logger.warning(f"Error getting Spanish title from TMDb: {e}")
            return original
    
    def process_queue(self, events):
        """
        Process a queue of episodes added in Sonarr and manage batch deletion.
        
        Args:
            events (list): List of episode events to process.
        """
        logger.info(f"Processing batch of {len(events)} Sonarr episodes")
        
        # Filter invalid events
        valid_events = [
            event for event in events
            if event.get("eventType", "").lower() != "test" and "series" in event
        ]
        
        if not valid_events:
            logger.info("All received events are test events (eventType: 'Test') or invalid")
            return
        
        if not events:
            logger.warning("Sonarr episode queue is empty. Nothing to process.")
            return
        
        series_episodes_added = defaultdict(list)
        series_episodes_deleted = defaultdict(list)
        series_episodes_updated = defaultdict(list)
        freed_space = 0
        available_space = self.get_disk_space()
        
        if available_space > self.primary_instance.hard_drive_threshold:
            logger.info(f"Sufficient disk space ({bytes_to_gb(available_space)} GB), "
                       f"no episodes will be deleted.")
            
            for event in events:
                series = f'{self.get_spanish_title(event["series"].get("tmdbId", ""), event["series"]["title"])} ({event["series"]["year"]})'
                series_imdbid = event["series"].get("imdbId", "")
                season = event["episodes"][0]["seasonNumber"]
                episode_n = event["episodes"][0]["episodeNumber"]
                episode_tvdbid = event["episodes"][0]["tvdbId"]
                
                episode_data = {
                    "season": f"{season:02d}",
                    "episode": f"{episode_n:02d}",
                    "url": f"https://www.thetvdb.com/?tab=episode&id={episode_tvdbid}",
                    "imdbUrl": f"https://www.imdb.com/{self.imdb_language}/title/{series_imdbid}",
                }
                
                if event.get("isUpgrade", False):
                    series_episodes_updated[series].append(episode_data)
                else:
                    series_episodes_added[series].append(episode_data)
        
        else:
            logger.info(f"Insufficient disk space ({bytes_to_gb(available_space)} GB) "
                       f"from threshold {bytes_to_gb(self.primary_instance.hard_drive_threshold)}")
            
            for event in events:
                series = f'{self.get_spanish_title(event["series"].get("tmdbId", ""), event["series"]["title"])} ({event["series"]["year"]})'
                series_imdbid = event["series"].get("imdbId", "")
                season = event["episodes"][0]["seasonNumber"]
                episode_n = event["episodes"][0]["episodeNumber"]
                episode_tvdbid = event["episodes"][0]["tvdbId"]
                
                episode_data = {
                    "season": f"{season:02d}",
                    "episode": f"{episode_n:02d}",
                    "url": f"https://www.thetvdb.com/?tab=episode&id={episode_tvdbid}",
                    "imdbUrl": f"https://www.imdb.com/{self.imdb_language}/title/{series_imdbid}",
                }
                
                if event.get("isUpgrade", False):
                    series_episodes_updated[series].append(episode_data)
                else:
                    series_episodes_added[series].append(episode_data)
            
            # Calculate total space needed for all episodes in the queue
            total_size_to_add = sum(event["episodeFile"]["size"] for event in events)
            logger.info(f"Space required for new episodes: {bytes_to_gb(total_size_to_add)} GB")
            
            tag_no_delete_id = self.get_no_delete_tag_id()
            available_series = self.get_series_without_no_delete_tag(tag_no_delete_id)
            
            total_episodes = []
            series_dict = {
                series["id"]: {
                    "title": self.get_spanish_title(series["tmdbId"], series["title"]),
                    "year": series["year"],
                    "tmdbId": series.get("tmdbId", ""),
                    "imdbId": series.get("imdbId", "")
                }
                for series in available_series
            }
            logger.debug(f"Series ID - Title dictionary created: {json.dumps(series_dict, indent=4)}")
            
            for series_data in available_series:
                total_episodes.extend(self.get_downloaded_episodes(series_data["id"]))
            
            # Sort episodes by most recent season date, then by season and episode number
            total_episodes = sorted(
                total_episodes, 
                key=lambda x: (x["episodeFile"]["dateAdded"], x["seasonNumber"], x["episodeNumber"])
            )
            
            logger.info(f"Total episodes eligible for deletion: {len(total_episodes)}")
            
            # Structures for deleting episodes and logging notifications
            episodes_to_delete = []
            
            # Select episodes to delete until enough space is freed
            for episode in total_episodes:
                if freed_space >= total_size_to_add:
                    break
                
                episode_file_id = episode["episodeFileId"]
                series_title = f"{series_dict[episode['seriesId']]['title']} ({series_dict[episode['seriesId']]['year']})"
                season = episode["seasonNumber"]
                episode_num = episode["episodeNumber"]
                episode_file_size = episode["episodeFile"]["size"]  # In bytes
                episode_tvdbid = episode.get("tvdbId", "")
                
                freed_space += episode_file_size
                episodes_to_delete.append({
                    "episodeFileId": episode_file_id,
                    "seriesId": episode['seriesId'],
                    "episodeId": episode['id']
                })
                
                series_episodes_deleted[series_title].append({
                    "season": f"{season:02d}",
                    "episode": f"{episode_num:02d}",
                    "url": f"https://www.thetvdb.com/?tab=episode&id={episode_tvdbid}",
                    "imdbUrl": f"https://www.imdb.com/{self.imdb_language}/title/{series_dict[episode['seriesId']]['imdbId']}",
                })
                
                logger.debug(f"Marking for deletion: {series_title} S{season:02d}E{episode_num:02d} "
                           f"({bytes_to_gb(episode_file_size)} GB)")
            
            # Execute episode deletion
            self.delete_episodes(episodes_to_delete)
        
        # Final notification with added and deleted episodes
        logger.info(f"Sonarr message dict added episodes: {json.dumps(series_episodes_added, indent=4)}")
        logger.info(f"Sonarr message dict updated episodes: {json.dumps(series_episodes_updated, indent=4)}")
        logger.info(f"Sonarr message dict deleted episodes: {json.dumps(series_episodes_deleted, indent=4)}")
        logger.info(f"Total space freed: {bytes_to_gb(freed_space)} GB")
        
        # Send notification to Telegram
        from utils.telegram_notifier import TelegramNotifier
        telegram_notifier = TelegramNotifier(self.app_config)
        telegram_notifier.send_sonarr_message(
            series_episodes_added, 
            series_episodes_deleted, 
            series_episodes_updated, 
            freed_space
        )
