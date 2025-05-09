"""
Version information for the ANPE Studio package.

This module is separated to avoid circular import issues.
It should not import any other modules from the package.
"""

# Version of the ANPE Studio package
__version__ = "1.0.0"

# Function to get version information
def get_version():
    """Return the version string."""
    return __version__ 