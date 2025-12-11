#!/usr/bin/env python3
"""
Migration script to move local JSON files to S3 bucket
Usage: python migrate_to_s3.py
"""

import os
import json
import logging
from dotenv import load_dotenv
from services.s3_service import S3Service

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def migrate_local_to_s3():
    """Migrate all local JSON files to S3"""
    
    # Check if S3 is configured
    bucket_name = os.getenv('S3_BUCKET_NAME')
    if not bucket_name:
        logger.error("S3_BUCKET_NAME not set in environment variables")
        return False
    
    # Initialize S3 service
    s3_service = S3Service()
    if not s3_service.is_available():
        logger.error("S3 service not available. Check your AWS credentials.")
        return False
    
    # Local data directory
    local_data_dir = "_data"
    if not os.path.exists(local_data_dir):
        logger.error(f"Local data directory '{local_data_dir}' not found")
        return False
    
    # Get all JSON files
    json_files = []
    for root, dirs, files in os.walk(local_data_dir):
        for file in files:
            if file.endswith('.json'):
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, local_data_dir)
                json_files.append((file_path, rel_path))
    
    if not json_files:
        logger.warning("No JSON files found in local data directory")
        return True
    
    logger.info(f"Found {len(json_files)} JSON files to migrate")
    
    # Migrate each file
    success_count = 0
    error_count = 0
    
    for local_path, s3_key in json_files:
        try:
            logger.info(f"Migrating: {local_path} -> s3://{bucket_name}/{s3_key}")
            
            # Read local file
            with open(local_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Write to S3
            if s3_service.write_json_file(s3_key, data):
                success_count += 1
                logger.info(f"✓ Successfully migrated: {s3_key}")
            else:
                error_count += 1
                logger.error(f"✗ Failed to migrate: {s3_key}")
                
        except Exception as e:
            error_count += 1
            logger.error(f"✗ Error migrating {local_path}: {e}")
    
    # Summary
    logger.info(f"\nMigration Summary:")
    logger.info(f"✓ Successfully migrated: {success_count} files")
    if error_count > 0:
        logger.error(f"✗ Failed to migrate: {error_count} files")
    
    return error_count == 0

def verify_s3_migration():
    """Verify that files were migrated correctly to S3"""
    
    bucket_name = os.getenv('S3_BUCKET_NAME')
    if not bucket_name:
        logger.error("S3_BUCKET_NAME not set in environment variables")
        return False
    
    s3_service = S3Service()
    if not s3_service.is_available():
        logger.error("S3 service not available")
        return False
    
    # List files in S3
    files = s3_service.list_files()
    if files is None:
        logger.error("Failed to list S3 files")
        return False
    
    logger.info(f"Files in S3 bucket '{bucket_name}':")
    for file_key in sorted(files):
        size = s3_service.get_file_size(file_key)
        size_str = f" ({size} bytes)" if size else ""
        logger.info(f"  - {file_key}{size_str}")
    
    return True

def main():
    """Main migration function"""
    logger.info("Starting migration from local files to S3...")
    
    # Check environment
    if not os.getenv('S3_MODE'):
        logger.warning("S3_MODE not set to 'true'. Set this in your .env file to enable S3 mode.")
    
    # Perform migration
    if migrate_local_to_s3():
        logger.info("Migration completed successfully!")
        
        # Verify migration
        logger.info("\nVerifying migration...")
        verify_s3_migration()
        
        logger.info("\nNext steps:")
        logger.info("1. Set S3_MODE=true in your .env file")
        logger.info("2. Restart your API server")
        logger.info("3. Your API will now read from S3 instead of local files")
        
    else:
        logger.error("Migration failed!")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
