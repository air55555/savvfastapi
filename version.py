import subprocess
import json
from datetime import datetime
from typing import Dict, Any
import os
import re


def get_git_commit_count() -> int:
    """
    Get the total number of commits in the repository.
    This will be used for auto-incrementing version numbers.
    """
    try:
        result = subprocess.check_output(
            ["git", "rev-list", "--count", "HEAD"], 
            stderr=subprocess.DEVNULL
        ).decode().strip()
        return int(result)
    except (subprocess.CalledProcessError, FileNotFoundError, ValueError):
        return 0


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


def get_auto_increment_version() -> str:
    """
    Generate an auto-incrementing version based on git commit count.
    Format: MAJOR.MINOR.PATCH where PATCH = commit count
    """
    commit_count = get_git_commit_count()
    
    # Base version: 1.0.x where x = commit count
    major = 1
    minor = 0
    patch = commit_count
    
    return f"{major}.{minor}.{patch}"


def get_semantic_version() -> str:
    """
    Generate a semantic version with auto-increment based on git activity.
    Format: MAJOR.MINOR.PATCH-BUILD
    """
    commit_count = get_git_commit_count()
    git_info = get_git_commit_info()
    
    # Check if there are uncommitted changes
    is_dirty = git_info.get("is_dirty", False)
    
    # Base semantic version
    major = 1
    minor = 0
    patch = commit_count
    
    # Add build info if there are uncommitted changes
    build_suffix = ""
    if is_dirty:
        build_suffix = "-dirty"
    
    return f"{major}.{minor}.{patch}{build_suffix}"


def get_version_info() -> Dict[str, Any]:
    """
    Get comprehensive version information for the API with auto-incrementing version.
    """
    git_info = get_git_commit_info()
    commit_count = get_git_commit_count()
    
    return {
        "version": get_auto_increment_version(),
        "semantic_version": get_semantic_version(),
        "build_date": datetime.now().isoformat(),
        "commit_count": commit_count,
        "git": git_info,
        "api_name": "FastAPI Palette Cheese API"
    }
