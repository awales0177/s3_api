import os
from datetime import timedelta

# Environment-based configuration
class Config:
    # Test mode - uses local _data files instead of GitHub
    TEST_MODE = os.getenv('TEST_MODE', 'false').lower() == 'true'
    
    # Passthrough mode - bypasses cache and fetches directly from GitHub
    PASSTHROUGH_MODE = os.getenv('PASSTHROUGH_MODE', 'false').lower() == 'true'
    
    # S3 mode - uses S3 bucket instead of GitHub or local files
    S3_MODE = os.getenv('S3_MODE', 'false').lower() == 'true'
    
    # GitHub configuration (only used when not in test mode or S3 mode)
    GITHUB_RAW_BASE_URL = os.getenv('GITHUB_RAW_BASE_URL', 'https://raw.githubusercontent.com/awales0177/test_data/main')
    
    # S3 configuration
    S3_BUCKET_NAME = os.getenv('S3_BUCKET_NAME')
    AWS_REGION = os.getenv('AWS_REGION', 'us-east-1')
    AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
    
    # Cache configuration
    CACHE_DURATION = timedelta(minutes=int(os.getenv('CACHE_DURATION_MINUTES', '15')))
    
    # Server configuration
    HOST = os.getenv('HOST', '0.0.0.0')
    PORT = int(os.getenv('PORT', '8000'))
    
    # Authentication
    ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', 'admin')
    ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'admin')
    
    # Logging
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    
    @classmethod
    def get_mode_description(cls):
        """Get a human-readable description of the current mode."""
        if cls.S3_MODE:
            return f"S3 MODE - Using S3 bucket: {cls.S3_BUCKET_NAME or 'Not configured'}"
        elif cls.TEST_MODE:
            return "TEST MODE - Using local _data files"
        elif cls.PASSTHROUGH_MODE:
            return "PASSTHROUGH MODE - Direct GitHub access (no cache)"
        else:
            return "CACHED MODE - GitHub with caching"
    
    @classmethod
    def get_data_source(cls):
        """Get the current data source."""
        if cls.S3_MODE:
            return "s3"
        elif cls.TEST_MODE:
            return "local"
        elif cls.PASSTHROUGH_MODE:
            return "github"
        else:
            return "cached_github"
    
    @classmethod
    def is_s3_configured(cls):
        """Check if S3 is properly configured."""
        return cls.S3_MODE and cls.S3_BUCKET_NAME is not None
