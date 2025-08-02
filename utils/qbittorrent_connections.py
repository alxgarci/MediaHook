"""
qBittorrent Connection Manager

This module provides comprehensive management for qBittorrent instances,
including authentication, torrent information retrieval, tag management,
and automated seed time verification.

Classes:
    QBittorrentManager: Centralized manager for multiple qBittorrent instances
    QBittorrentInstance: Individual qBittorrent instance handler

Functions:
    initialize_qbittorrent_manager: Initialize global manager instance
    set_to_delete_tag: Compatibility function for setting deletion tags

The module supports multiple qBittorrent instances and provides unified
access to torrent operations across different servers.
"""

import requests
import json
from datetime import datetime, timedelta
from app.logger import logger

class QBittorrentManager:
    """
    Centralized manager for qBittorrent instances
    
    This class manages multiple qBittorrent instances, providing unified access
    to torrent operations across different qBittorrent servers. It handles
    authentication, instance management, and provides high-level operations
    for torrent management.
    
    Attributes:
        app_config: Application configuration object
        instances: Dictionary mapping instance names to QBittorrentInstance objects
    """
    
    def __init__(self, app_config):
        """
        Initialize the manager with application configuration
        
        Args:
            app_config: Application configuration containing qBittorrent instances
        """
        self.app_config = app_config
        self.instances = {}
        
        # Initialize all qBittorrent instances
        for qbit_config in app_config.qbittorrent_instances:
            instance = QBittorrentInstance(qbit_config)
            self.instances[qbit_config.name] = instance
            logger.info(f"Initialized qBittorrent instance: {qbit_config.name}")
    
    def get_instance(self, name):
        """
        Get a specific instance by name
        
        Args:
            name: Name of the qBittorrent instance
            
        Returns:
            QBittorrentInstance object or None if not found
        """
        return self.instances.get(name)
    
    def get_all_instances(self):
        """
        Get all instances
        
        Returns:
            List of all QBittorrentInstance objects
        """
        return list(self.instances.values())
    
    def login_all(self):
        """Log in to all instances"""
        for instance in self.instances.values():
            instance.login()

class QBittorrentInstance:
    """
    Class to represent and manage a qBittorrent instance
    
    This class handles all interactions with a single qBittorrent instance,
    including authentication, torrent information retrieval, tag management,
    and seed time verification.
    
    Attributes:
        name: Instance name for identification
        api_url: qBittorrent Web API URL
        username: Authentication username
        password: Authentication password
        seed_limit: Minimum seed time in seconds before deletion
        session: Persistent HTTP session for API calls
        authenticated: Current authentication status
    """
    
    def __init__(self, config):
        """
        Initialize the qBittorrent instance
        
        Args:
            config: Configuration object containing instance details
        """
        self.name = config.name
        self.api_url = config.api_url
        self.username = config.username
        self.password = config.password
        self.seed_limit = config.seed_limit
        self.session = requests.Session()
        self.authenticated = False
        
        logger.info(f"Configured qBittorrent instance: {self}")
    
    def __str__(self):
        """String representation of the instance"""
        return f"qBittorrent({self.name}@{self.api_url})"
    
    def login(self):
        """
        Log in to the qBittorrent instance
        
        Authenticates with the qBittorrent Web API using configured credentials.
        Updates the authenticated status based on the result.
        """
        try:
            login_data = {
                'username': self.username,
                'password': self.password
            }
            
            response = self.session.post(f"{self.api_url}/api/v2/auth/login", data=login_data)
            response.raise_for_status()
            
            if response.text == "Ok.":
                self.authenticated = True
                logger.info(f"Successful login to {self.name}")
            else:
                logger.error(f"Authentication error on {self.name}: {response.text}")
                self.authenticated = False
                
        except requests.RequestException as e:
            logger.error(f"Error connecting to {self.name}: {e}")
            self.authenticated = False
    
    def get_torrent_info(self, hashes):
        """
        Get torrent information by their hashes
        
        Args:
            hashes: List of torrent hash strings
            
        Returns:
            List of torrent information dictionaries, empty list on error
        """
        if not self.authenticated:
            self.login()
            
        if not self.authenticated:
            logger.error(f"Could not authenticate to {self.name}")
            return []
        
        try:
            params = {'hashes': '|'.join(hashes)}
            response = self.session.get(f"{self.api_url}/api/v2/torrents/info", params=params)
            response.raise_for_status()
            
            torrents = response.json()
            logger.debug(f"Retrieved information for {len(torrents)} torrents from {self.name}")
            
            return torrents
            
        except requests.RequestException as e:
            logger.error(f"Error getting torrent info from {self.name}: {e}")
            return []
    
    def add_tag_to_delete(self, hashes):
        """
        Add the 'to_delete' tag to specified torrents
        
        Args:
            hashes: List of torrent hash strings to tag
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.authenticated:
            self.login()
            
        if not self.authenticated:
            logger.error(f"Could not authenticate to {self.name}")
            return False
        
        try:
            data = {
                'hashes': '|'.join(hashes),
                'tags': 'to_delete'
            }
            
            response = self.session.post(f"{self.api_url}/api/v2/torrents/addTags", data=data)
            response.raise_for_status()
            
            logger.info(f"Tag 'to_delete' added to {len(hashes)} torrents in {self.name}")
            return True
            
        except requests.RequestException as e:
            logger.error(f"Error adding tag in {self.name}: {e}")
            return False
    
    def verify_torrents(self, hashes):
        """
        Verify if torrents exist in this instance
        
        Args:
            hashes: List of torrent hash strings to verify
            
        Returns:
            List of hashes that were found in this instance
        """
        torrents = self.get_torrent_info(hashes)
        found_hashes = [torrent['hash'] for torrent in torrents]
        
        logger.debug(f"Verified {len(found_hashes)} of {len(hashes)} torrents in {self.name}")
        return found_hashes
    
    def add_to_delete_respecting_seedtime(self, hashes):
        """
        Add to_delete tag respecting seed time
        
        Analyzes each torrent's seed time and only tags for deletion those
        that have exceeded the configured seed limit.
        
        Args:
            hashes: List of torrent hash strings to process
            
        Returns:
            List of dictionaries with action results for each torrent
        """
        if not hashes:
            return []
        
        torrents = self.get_torrent_info(hashes)
        if not torrents:
            return []
        
        results = []
        
        for torrent in torrents:
            try:
                # Calculate seed time
                completed_time = datetime.fromtimestamp(torrent.get('completion_on', 0))
                current_time = datetime.now()
                seed_time = current_time - completed_time
                
                # Check if it has exceeded the seed limit
                if seed_time.total_seconds() >= self.seed_limit:
                    if self.add_tag_to_delete([torrent['hash']]):
                        results.append({
                            'hash': torrent['hash'],
                            'name': torrent['name'],
                            'action': 'tagged_for_deletion',
                            'seed_time_hours': seed_time.total_seconds() / 3600
                        })
                else:
                    results.append({
                        'hash': torrent['hash'],
                        'name': torrent['name'],
                        'action': 'seed_time_not_reached',
                        'seed_time_hours': seed_time.total_seconds() / 3600,
                        'required_hours': self.seed_limit / 3600
                    })
                    
            except Exception as e:
                logger.error(f"Error processing torrent {torrent.get('hash', 'unknown')}: {e}")
        
        return results

# Global variables for compatibility
qbit_manager = None

def initialize_qbittorrent_manager(app_config):
    """
    Initialize the qBittorrent manager with application configuration
    
    Creates a global QBittorrentManager instance and authenticates
    to all configured qBittorrent instances.
    
    Args:
        app_config: Application configuration containing qBittorrent instances
    """
    global qbit_manager
    qbit_manager = QBittorrentManager(app_config)
    qbit_manager.login_all()

def set_to_delete_tag(hash_list):
    """
    Compatibility function to set deletion tags
    
    Processes a list of torrent hashes and tags them for deletion
    if they meet the seed time requirements. Searches across all
    configured qBittorrent instances.
    
    Args:
        hash_list: List of torrent hash strings to process
    """
    global qbit_manager
    
    if not qbit_manager:
        logger.error("QBittorrent manager not initialized")
        return
    
    if not hash_list:
        return
    
    logger.info(f"Processing {len(hash_list)} hashes for deletion tagging")
    
    # Try with all instances until finding the torrents
    for instance in qbit_manager.get_all_instances():
        found_hashes = instance.verify_torrents(hash_list)
        if found_hashes:
            logger.info(f"Found {len(found_hashes)} torrents in {instance.name}")
            instance.add_to_delete_respecting_seedtime(found_hashes)
            
            # Remove found hashes from list to avoid duplication
            hash_list = [h for h in hash_list if h not in found_hashes]
            
            if not hash_list:
                break
    
    if hash_list:
        logger.warning(f"Could not find {len(hash_list)} hashes in any qBittorrent instance")
