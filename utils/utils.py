"""
Utility Functions

This module provides general utility functions used throughout the MediaHook
application. It includes functions for data conversion, error handling,
network utilities, date manipulation, and string processing.

Functions:
    bytes_to_gb: Convert bytes to gigabytes
    exit_with_error: Log critical error and exit application
    find_my_local_ip: Get local IP address
    truncate_date: Truncate datetime to hour precision
    clean_title: URL-encode title strings

These utilities support various operations including media file management,
network communication, and data processing across the application.
"""

import sys
import socket
import urllib.parse
from datetime import datetime
from app.logger import logger

def bytes_to_gb(bytes_value):
    """
    Convert bytes to gigabytes
    
    Args:
        bytes_value (int): Size in bytes to convert
        
    Returns:
        float: Size in gigabytes rounded to 2 decimal places
    """
    return round(bytes_value / (1024 ** 3), 2)  # 1 GB = 1024^3 bytes

def exit_with_error(message):
    """
    Print error message to logs and terminate execution
    
    Args:
        message (str): Critical error message to log before exiting
    """
    logger.critical(message)
    logger.critical('Critical error, exiting...')
    sys.exit(1)

def find_my_local_ip():
    """
    Find the local IP address of this machine
    
    Returns:
        str: Local IP address as a string
        
    Note:
        Uses a connection to Google's DNS server (8.8.8.8) to determine
        the local IP address that would be used for external connections.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    add = s.getsockname()[0]
    s.close()
    return add

def get_all_local_ips():
    """
    Get all local IP addresses available on this machine
    
    Returns:
        list: List of all local IP addresses as strings
        
    Note:
        Returns all network interfaces that have an assigned IP address,
        including localhost, local network interfaces, and external interfaces.
    """
    local_ips = []
    
    # Add localhost
    local_ips.append('127.0.0.1')
    
    # Get hostname and all associated IPs
    try:
        hostname = socket.gethostname()
        host_ips = socket.gethostbyname_ex(hostname)[2]
        for ip in host_ips:
            if ip not in local_ips and not ip.startswith('169.254'):  # Skip link-local addresses
                local_ips.append(ip)
    except Exception as e:
        logger.debug(f"Error getting hostname IPs: {e}")
    
    # Try to get the main external IP
    try:
        main_ip = find_my_local_ip()
        if main_ip and main_ip not in local_ips:
            local_ips.append(main_ip)
    except Exception as e:
        logger.debug(f"Error getting main external IP: {e}")
    
    # Remove any invalid IPs and sort
    valid_ips = []
    for ip in local_ips:
        try:
            socket.inet_aton(ip)  # Validate IP format
            if ip != '0.0.0.0':  # Skip invalid IP
                valid_ips.append(ip)
        except socket.error:
            continue
    
    return sorted(list(set(valid_ips)))  # Remove duplicates and sort

def truncate_date(date_str):
    """
    Truncate datetime to hour precision, ignoring minutes and seconds
    
    This function is used to avoid conflicts when bulk episodes are added
    with different seconds/minutes, ensuring consistent time comparison.
    
    Args:
        date_str (str): Date string in ISO format ("%Y-%m-%dT%H:%M:%SZ")
        
    Returns:
        datetime: Datetime object with minutes and seconds set to 0
    """
    return datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%SZ").replace(minute=0, second=0)

def clean_title(title):
    """
    URL-encode a title string for safe use in URLs
    
    Args:
        title (str): Title string to encode
        
    Returns:
        str: URL-encoded title string
    """
    return urllib.parse.quote(title, safe='')
