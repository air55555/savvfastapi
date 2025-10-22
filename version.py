import subprocess
import json
from datetime import datetime
from typing import Dict, Any
import os


def get_git_commit_info() -> Dict[str, Any]:
    """
    Get the last git commit information including date, hash, and message.
    Returns a dictionary with version information.
    """
    try:
        # Get commit hash
        commit_hash = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], 
            stderr=subprocess.DEVNULL
        ).decode().strip()
        
        # Get commit date in ISO format
        commit_date = subprocess.check_output(
            ["git", "log", "-1", "--format=%cd", "--date=iso"], 
            stderr=subprocess.DEVNULL
        ).decode().strip()
        
        # Get commit message (first line only)
        commit_message = subprocess.check_output(
            ["git", "log", "-1", "--format=%s"], 
            stderr=subprocess.DEVNULL
        ).decode().strip()
        
        # Get short hash (7 characters)
        short_hash = commit_hash[:7]
        
        return {
            "commit_hash": commit_hash,
            "short_hash": short_hash,
            "commit_date": commit_date,
            "commit_message": commit_message,
            "is_dirty": is_git_dirty()
        }
        
    except (subprocess.CalledProcessError, FileNotFoundError):
        # Fallback if git is not available or not a git repository
        return {
            "commit_hash": "unknown",
            "short_hash": "unknown", 
            "commit_date": "unknown",
            "commit_message": "unknown",
            "is_dirty": False
        }


def is_git_dirty() -> bool:
    """
    Check if the working directory has uncommitted changes.
    """
    try:
        result = subprocess.check_output(
            ["git", "status", "--porcelain"], 
            stderr=subprocess.DEVNULL
        ).decode().strip()
        return len(result) > 0
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def get_version_info() -> Dict[str, Any]:
    """
    Get comprehensive version information for the API.
    """
    git_info = get_git_commit_info()
    
    return {
        "version": "1.0.0",
        "build_date": datetime.now().isoformat(),
        "git": git_info,
        "api_name": "FastAPI Palette Cheese API"
    }
