"""
Module for managing automatic deletion of manually imported torrents.

This module handles:
1. Finding torrents that have been manually imported in Radarr/Sonarr
2. Verifying they have exceeded the minimum seeding threshold
3. Deleting torrents and associated files from qBittorrent
4. Sending process notifications via Telegram

Works with both history torrents (grabbed) and manual imports
identified by sourceTitle in manual_import categories.
"""

import json
import os
import re
from datetime import timedelta
from typing import List, Dict, Tuple, Optional

import requests
from app.logger import logger


class DeleteManualImportManager:
    """Manager for automatic deletion of manually imported torrents"""
    
    # Constants for action types and reasons
    KEY_ACT_DEL = "DEL"
    KEY_TYPE_HIST = "HIST"
    KEY_TYPE_MATCH = "MATCH"
    KEY_ACT_NODELETE = "NODELETE"
    KEY_REASON_SEEDTIME_UNCOMPLETE = "SEEDTIME_UNCOMPLETE"
    KEY_REASON_NO_MATCH = "NO_MATCH"
    KEY_REASON_NOT_FOUND = "NOT_FOUND"
    KEY_REASON_DRY_RUN = "DRY_RUN"
    
    # Seeding threshold in days
    SEED_THRESHOLD_DAYS = 30
    
    # Regex for video extensions
    VIDEO_EXT = re.compile(r'\.(mkv|mp4|avi|mov|wmv|m4a|flac)$', re.IGNORECASE)
    
    # Torrent categories to analyze
    MOVIE_CATEGORIES = [
        "manual_import_movies", "movies", "manual_import_prowlarr", 
        "movies.cross-seed", "manual_import_movies.cross-seed"
    ]
    
    TV_CATEGORIES = [
        "manual_import_tv", "tv", "manual_import_prowlarr", 
        "tv.cross-seed", "manual_import_tv.cross-seed"
    ]
    
    def __init__(self, app_config):
        """
        Initialize the manager with application configuration
        
        Args:
            app_config: Application configuration (ApplicationConfig)
        """
        self.app_config = app_config
        self.dry_run = app_config.general.get('dry_run', True)
        
        # Radarr configuration
        if app_config.radarr_instances:
            self.radarr_instance = app_config.radarr_instances[0]
            self.radarr_headers = {'X-Api-Key': self.radarr_instance.api_key}
        else:
            logger.error("No Radarr instances configured")
            self.radarr_instance = None
            self.radarr_headers = None
        
        # Sonarr configuration
        if app_config.sonarr_instances:
            self.sonarr_instance = app_config.sonarr_instances[0]
            self.sonarr_headers = {'X-Api-Key': self.sonarr_instance.api_key}
        else:
            logger.error("No Sonarr instances configured")
            self.sonarr_instance = None
            self.sonarr_headers = None
        
        # qBittorrent configuration
        self.qbittorrent_instances = app_config.qbittorrent_instances
        
        if self.dry_run:
            logger.info("🔍 DRY RUN MODE ACTIVATED - Torrents will not be actually deleted")
    
    @staticmethod
    def normalize(name: str) -> str:
        """
        Normalize a file/torrent name for comparison
        
        Args:
            name: Original file/torrent name
            
        Returns:
            Normalized name (no extension, spaces instead of dots/dashes, lowercase)
        """
        name = os.path.basename(name)
        base = DeleteManualImportManager.VIDEO_EXT.sub('', name)
        base = base.replace('.', ' ').replace('_', ' ')
        return base.casefold().strip()
    
    @staticmethod
    def create_action_dict(name: str, hash_value: str, action: str, type_value: str, reason: str = '') -> Dict:
        """
        Create a dictionary with information about an action performed
        
        Args:
            name: Torrent name
            hash_value: Torrent hash
            action: Action performed (DEL/NODELETE)
            type_value: Action type (HIST/MATCH)
            reason: Reason for the action
            
        Returns:
            Dictionary with action information
        """
        return {
            "action": action,
            "type": type_value,
            "name": name,
            "hash": hash_value,
            "reason": reason
        }
    
    def list_torrents_by_category(self, qbit_instance, category: str) -> List[Dict]:
        """
        Get the list of torrents in a specific category
        
        Args:
            qbit_instance: qBittorrent instance
            category: Category to filter
            
        Returns:
            List of torrents in the category
        """
        qbit_instance.login()
        url = f"{qbit_instance.api_url}/api/v2/torrents/info?filter=all&category={category}"
        response = qbit_instance.session.get(url)
        response.raise_for_status()
        return response.json()
    
    def list_files_for_torrent(self, qbit_instance, torrent_hash: str) -> List[Dict]:
        """
        Get the list of files in a specific torrent
        
        Args:
            qbit_instance: qBittorrent instance
            torrent_hash: Torrent hash
            
        Returns:
            List of files in the torrent
        """
        url = f"{qbit_instance.api_url}/api/v2/torrents/files?hash={torrent_hash}"
        response = qbit_instance.session.get(url)
        response.raise_for_status()
        return response.json()
    
    def get_radarr_history_hashes(self, movie_id: int) -> List[str]:
        """
        Get torrent hashes 'grabbed' from Radarr history
        
        Args:
            movie_id: Movie ID
            
        Returns:
            List of downloaded torrent hashes
        """
        if not self.radarr_instance:
            return []
            
        url = f"{self.radarr_instance.api_url}/api/v3/history/movie"
        params = {'movieId': movie_id, 'eventType': 'grabbed'}
        
        try:
            response = requests.get(url, headers=self.radarr_headers, params=params)
            response.raise_for_status()
            history_data = response.json()
            
            if len(history_data) > 20:
                logger.error(f"Too many records in Radarr history ({len(history_data)}), aborting")
                return []
            
            return [entry.get('downloadId') for entry in history_data if entry.get('downloadId')]
            
        except requests.RequestException as e:
            logger.error(f"Error getting Radarr history: {e}")
            return []
    
    def get_radarr_import_sources(self, movie_id: int) -> List[str]:
        """
        Get sourceTitles from Radarr manual imports
        
        Args:
            movie_id: Movie ID
            
        Returns:
            List of normalized titles of imported files
        """
        if not self.radarr_instance:
            return []
            
        url = f"{self.radarr_instance.api_url}/api/v3/history/movie"
        params = {'movieId': movie_id, 'eventType': 'downloadFolderImported'}
        
        try:
            response = requests.get(url, headers=self.radarr_headers, params=params)
            response.raise_for_status()
            history_data = response.json()
            
            if len(history_data) > 20:
                logger.error(f"Too many records in Radarr import ({len(history_data)}), aborting")
                return []
            
            return [self.normalize(entry.get('sourceTitle')) for entry in history_data if entry.get('sourceTitle')]
            
        except requests.RequestException as e:
            logger.error(f"Error getting Radarr imports: {e}")
            return []
    
    def get_sonarr_history_hashes(self, episode_id: int) -> List[str]:
        """
        Get torrent hashes 'grabbed' from Sonarr history
        
        Args:
            episode_id: Episode ID
            
        Returns:
            List of downloaded torrent hashes
        """
        if not self.sonarr_instance:
            return []
            
        url = f"{self.sonarr_instance.api_url}/api/v3/history?episodeId={episode_id}"
        
        try:
            response = requests.get(url, headers=self.sonarr_headers)
            response.raise_for_status()
            data = response.json()
            
            records = data.get('records', [])
            if int(data.get('totalRecords', 11)) > 10:
                logger.error(f"Too many records in Sonarr history ({len(records)}), aborting")
                return []
            
            return [entry['downloadId'] for entry in records if entry.get('downloadId')]
            
        except requests.RequestException as e:
            logger.error(f"Error getting Sonarr history: {e}")
            return []
    
    def get_sonarr_import_sources(self, episode_id: int) -> List[str]:
        """
        Get sourceTitles from Sonarr manual imports
        
        Args:
            episode_id: Episode ID
            
        Returns:
            List of normalized titles of imported files
        """
        if not self.sonarr_instance:
            return []
            
        url = f"{self.sonarr_instance.api_url}/api/v3/history?episodeId={episode_id}"
        
        try:
            response = requests.get(url, headers=self.sonarr_headers)
            response.raise_for_status()
            data = response.json()
            
            records = data.get('records', [])
            if int(data.get('totalRecords', 11)) > 10:
                logger.error(f"Too many records in Sonarr import ({len(records)}), aborting")
                return []
            
            return [self.normalize(entry['sourceTitle']) for entry in records if entry.get('sourceTitle')]
            
        except requests.RequestException as e:
            logger.error(f"Error getting Sonarr imports: {e}")
            return []
    
    def delete_torrent_from_qbittorrent(self, qbit_instance, torrent_hash: str, torrent_name: str) -> bool:
        """
        Delete a torrent from qBittorrent
        
        Args:
            qbit_instance: qBittorrent instance
            torrent_hash: Hash of the torrent to delete
            torrent_name: Torrent name (for logs)
            
        Returns:
            True if deleted successfully, False otherwise
        """
        if self.dry_run:
            logger.info(f"🔍 DRY RUN: Would delete torrent {torrent_name} ({torrent_hash}) from {qbit_instance.name}")
            return True
        
        try:
            response = qbit_instance.session.post(
                f"{qbit_instance.api_url}/api/v2/torrents/delete",
                data={"hashes": torrent_hash, "deleteFiles": True}
            )
            
            if response.ok:
                logger.info(f"✅ Torrent deleted: {torrent_name} ({torrent_hash}) from {qbit_instance.name}")
                return True
            else:
                logger.error(f"❌ Error deleting torrent {torrent_hash}: {response.status_code} {response.text}")
                return False
                
        except requests.RequestException as e:
            logger.error(f"❌ Connection error deleting torrent {torrent_hash}: {e}")
            return False
    
    def process_history_torrents(self, media: str, item_id: int, hashes: List[str], sources: List[str]) -> Tuple[List[Dict], List[Dict]]:
        """
        Process history torrents (grabbed) for deletion
        
        Args:
            media: Media type ('radarr' or 'sonarr')
            item_id: Item ID (movie_id or episode_id)
            hashes: List of hashes from history
            sources: List of sources for logging
            
        Returns:
            Tuple with (deleted_actions, non_deleted_actions)
        """
        res_actions_del = []
        res_actions_nodel = []
        
        if not hashes:
            return res_actions_del, res_actions_nodel
        
        logger.info(f"🔍 Processing {len(hashes)} history torrents for {media} {item_id}")
        
        # Remove duplicates
        unique_hashes = set(hashes)
        
        for qbit_instance in self.qbittorrent_instances:
            qbit_instance.login()
            
            # Get seeding information for all hashes
            info = qbit_instance.get_torrent_info(list(unique_hashes)) or {}
            
            for hash_value in unique_hashes:
                hash_lower = hash_value.lower()
                data = info.get(hash_lower, {})
                seed_days = data.get('seeding_time', 0) / 86400
                
                source_name = sources[0] if sources else f"Unknown-{item_id}"
                
                if seed_days >= self.SEED_THRESHOLD_DAYS:
                    if self.delete_torrent_from_qbittorrent(qbit_instance, hash_value, source_name):
                        reason = self.KEY_REASON_DRY_RUN if self.dry_run else ""
                        res_actions_del.append(
                            self.create_action_dict(source_name, hash_value, self.KEY_ACT_DEL, self.KEY_TYPE_HIST, reason)
                        )
                    else:
                        res_actions_nodel.append(
                            self.create_action_dict(source_name, hash_value, self.KEY_ACT_NODELETE, self.KEY_TYPE_HIST, "ERROR_DELETE")
                        )
                else:
                    logger.info(f"⏸️  Torrent {hash_value} seed={seed_days:.1f}d < {self.SEED_THRESHOLD_DAYS}d → skipped")
                    if seed_days > 1:
                        reason = self.KEY_REASON_SEEDTIME_UNCOMPLETE
                    else:
                        reason = f"{self.KEY_REASON_NOT_FOUND} {qbit_instance.name}"
                    
                    res_actions_nodel.append(
                        self.create_action_dict(source_name, hash_value, self.KEY_ACT_NODELETE, self.KEY_TYPE_HIST, reason)
                    )
        
        return res_actions_del, res_actions_nodel
    
    def find_manual_import_matches(self, sources: List[str], categories: List[str]) -> List[Tuple]:
        """
        Find ALL torrents that match manually imported files (including cross-seeds)
        
        Args:
            sources: List of normalized sources
            categories: List of categories to search
            
        Returns:
            List of tuples (instance, torrent, reason) for all matches found
        """
        if not sources:
            return []
        
        # Collect all candidate torrents
        candidates = []
        for qbit_instance in self.qbittorrent_instances:
            for category in categories:
                try:
                    torrents = self.list_torrents_by_category(qbit_instance, category)
                    for torrent in torrents:
                        candidates.append((qbit_instance, torrent))
                except Exception as e:
                    logger.warning(f"Error getting torrents from category {category} in {qbit_instance.name}: {e}")
        
        # Normalize sources for comparison
        normalized_sources = set(sources)
        logger.debug(f"🔍 Searching for matches for sources: {normalized_sources}")
        
        matches = []
        
        # Search for exact match by torrent name
        for qbit_instance, torrent in candidates:
            torrent_name_normalized = self.normalize(torrent['name'])
            if torrent_name_normalized in normalized_sources:
                matches.append((qbit_instance, torrent, f"name == {torrent_name_normalized!r}"))
        
        # Search for match in internal torrent files
        for qbit_instance, torrent in candidates:
            # Skip if already matched by name
            if any(match[1]['hash'] == torrent['hash'] for match in matches):
                continue
                
            try:
                files = self.list_files_for_torrent(qbit_instance, torrent['hash'])
                for file_info in files:
                    file_name_normalized = self.normalize(file_info['name'])
                    if file_name_normalized in normalized_sources:
                        matches.append((qbit_instance, torrent, f"file == {file_name_normalized!r}"))
                        break  # Don't add the same torrent multiple times for different files
            except Exception as e:
                logger.warning(f"Error getting files for torrent {torrent['hash']}: {e}")
                continue
        
        logger.info(f"🎯 Found {len(matches)} matching torrents (including cross-seeds)")
        return matches
    
    def process_manual_import_torrents(self, media: str, item_id: int, sources: List[str]) -> Tuple[List[Dict], List[Dict]]:
        """
        Process manual import torrents for deletion (including cross-seeds)
        
        Args:
            media: Media type ('radarr' or 'sonarr')
            item_id: Item ID
            sources: List of import sources
            
        Returns:
            Tuple with (deleted_actions, not_deleted_actions)
        """
        res_actions_del = []
        res_actions_nodel = []
        
        if not sources:
            logger.debug(f"No sources for {media} {item_id}")
            return res_actions_del, res_actions_nodel
        
        # Select categories based on media type
        categories = self.MOVIE_CATEGORIES if media == 'radarr' else self.TV_CATEGORIES
        
        # Search for ALL matches (including cross-seeds)
        matches = self.find_manual_import_matches(sources, categories)
        
        if not matches:
            logger.debug(f"❌ No manual torrent matches found for {media} {item_id}")
            res_actions_nodel.append(
                self.create_action_dict(sources[0], "", self.KEY_ACT_NODELETE, self.KEY_TYPE_MATCH, self.KEY_REASON_NO_MATCH)
            )
            return res_actions_del, res_actions_nodel
        
        # Process each matching torrent
        for match_index, (qbit_instance, torrent, reason) in enumerate(matches, 1):
            logger.info(f"🎯 Processing match {match_index}/{len(matches)}: {torrent['name']} ({torrent['hash']}) in {qbit_instance.name} by {reason}")
            
            # Check seeding time
            try:
                info = qbit_instance.get_torrent_info([torrent['hash']])
                seed_sec = info.get(torrent['hash'], {}).get('seeding_time', 0)
                seed_days = seed_sec / 86400
                
                logger.info(f"🎯 Match {match_index}: {torrent['name']} ({torrent['hash']}) in {qbit_instance.name} by {reason}; seed={seed_days:.1f}d")
                
                # Check seeding threshold
                if seed_days < self.SEED_THRESHOLD_DAYS:
                    logger.info(f"⏸️  Seed {seed_days:.1f}d < {self.SEED_THRESHOLD_DAYS}d → skipped")
                    res_actions_nodel.append(
                        self.create_action_dict(torrent['name'], torrent['hash'], self.KEY_ACT_NODELETE, self.KEY_TYPE_MATCH, self.KEY_REASON_SEEDTIME_UNCOMPLETE)
                    )
                    continue
                
                # Proceed with deletion
                if self.delete_torrent_from_qbittorrent(qbit_instance, torrent['hash'], torrent['name']):
                    reason_suffix = self.KEY_REASON_DRY_RUN if self.dry_run else ""
                    res_actions_del.append(
                        self.create_action_dict(torrent['name'], torrent['hash'], self.KEY_ACT_DEL, self.KEY_TYPE_MATCH, reason_suffix)
                    )
                else:
                    res_actions_nodel.append(
                        self.create_action_dict(torrent['name'], torrent['hash'], self.KEY_ACT_NODELETE, self.KEY_TYPE_MATCH, "ERROR_DELETE")
                    )
                    
            except Exception as e:
                logger.error(f"Error processing torrent {torrent['hash']}: {e}")
                res_actions_nodel.append(
                    self.create_action_dict(torrent['name'], torrent['hash'], self.KEY_ACT_NODELETE, self.KEY_TYPE_MATCH, f"ERROR: {str(e)}")
                )
        
        return res_actions_del, res_actions_nodel
    
    def process_item(self, media: str, item_id: int) -> Tuple[List[Dict], List[Dict]]:
        """
        Process an item (movie or episode) for torrent deletion
        
        Args:
            media: Media type ('radarr' or 'sonarr')
            item_id: Item ID (movie_id or episode_id)
            
        Returns:
            Tuple with (deleted_actions, not_deleted_actions)
        """
        logger.info(f"🔄 Processing {media} item {item_id}")
        
        # Get history and sources based on media type
        if media == 'radarr':
            hashes = self.get_radarr_history_hashes(item_id)
            sources = self.get_radarr_import_sources(item_id)
            logger.debug(f"📚 Radarr - Hashes: {len(hashes)}, Sources: {sources}")
        else:  # sonarr
            hashes = self.get_sonarr_history_hashes(item_id)
            sources = self.get_sonarr_import_sources(item_id)
            logger.debug(f"📺 Sonarr - Hashes: {len(hashes)}, Sources: {sources}")
        
        all_actions_del = []
        all_actions_nodel = []
        
        # Process history torrents if they exist
        if hashes:
            hist_del, hist_nodel = self.process_history_torrents(media, item_id, hashes, sources)
            all_actions_del.extend(hist_del)
            all_actions_nodel.extend(hist_nodel)
        
        # Process manual import torrents
        manual_del, manual_nodel = self.process_manual_import_torrents(media, item_id, sources)
        all_actions_del.extend(manual_del)
        all_actions_nodel.extend(manual_nodel)
        
        return all_actions_del, all_actions_nodel


