"""
Resource management utilities for ANPE GUI.

This module provides a centralized way to access resources relative to the application structure.
"""

from pathlib import Path
from PyQt6.QtGui import QIcon, QPixmap

class ResourceManager:
    """
    Manages access to application resources using file system paths.
    Assumes resources are located in a 'resources' directory relative to this module.
    """

    @classmethod
    def get_resource_path(cls, resource_name):
        """
        Get the full path to a resource file.
        
        Args:
            resource_name: Name of the resource file (e.g., 'app_icon.png')
            
        Returns:
            Path: Path object to the resource in the 'resources' directory.
        """
        # Resources are assumed to be in the 'resources' directory relative to this file
        resources_dir = Path(__file__).parent / "resources"
        return resources_dir / resource_name

    @classmethod
    def get_icon(cls, icon_name):
        """
        Get a QIcon for the specified resource file.
        
        Args:
            icon_name: Name of the icon file (e.g., 'app_icon.png')
            
        Returns:
            QIcon: The loaded icon
        """
        # Always use file system path
        icon_path = cls.get_resource_path(icon_name)
        return QIcon(str(icon_path)) # Ensure path is string

    @classmethod
    def get_pixmap(cls, image_name):
        """
        Get a QPixmap for the specified resource file.
        
        Args:
            image_name: Name of the image file (e.g., 'app_icon.png')
            
        Returns:
            QPixmap: The loaded image
        """
        # Always use file system path
        image_path = cls.get_resource_path(image_name)
        return QPixmap(str(image_path)) # Ensure path is string

    @classmethod
    def get_style_url(cls, resource_name):
        """
        Get the URL for a resource to be used in stylesheets.
        
        Args:
            resource_name: Name of the resource file (e.g., 'expand_open.svg')
            
        Returns:
            str: URL for the resource that works in Qt stylesheets
        """
        # Calculate path relative to the CWD, assuming CWD is the project root
        # and resources are in anpe_gui/resources/
        relative_path = Path("anpe_gui") / "resources" / resource_name
        # Convert to string and ensure forward slashes for CSS url()
        return str(relative_path).replace("\\", "/") 