import os
from datetime import timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Environment-based configuration
class Config:
    # S3 mode - uses S3 bucket as the only data source
    S3_MODE = os.getenv('S3_MODE', 'true').lower() == 'true'
    
    # S3 configuration
    S3_BUCKET_NAME = os.getenv('S3_BUCKET_NAME')
    S3_FOLDER_PREFIX = os.getenv('S3_FOLDER_PREFIX', 'dh-api')  # Folder prefix in S3 bucket
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
        else:
            return "S3 MODE DISABLED - S3 is required"
    
    @classmethod
    def get_data_source(cls):
        """Get the current data source."""
        return "s3"
    
    @classmethod
    def is_s3_configured(cls):
        """Check if S3 is properly configured."""
        return cls.S3_BUCKET_NAME is not None
