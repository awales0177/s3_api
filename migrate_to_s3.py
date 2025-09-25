#!/usr/bin/env python3
"""
Migration script to upload local JSON files to S3.
Run this script once to migrate your data from local files to S3.
"""

import os
import json
import logging
from services.s3_service import S3Service
from config import Config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate_files_to_s3():
    """Migrate all JSON files from local _data directory to S3."""
    
    # Initialize S3 service
    s3_service = S3Service()
    
    if not s3_service.is_available():
        logger.error("S3 service is not available. Please check your AWS credentials and S3 configuration.")
        return False
    
    # List of files to migrate
    files_to_migrate = [
        'dataModels.json',
        'dataAgreements.json', 
        'dataDomains.json',
        'applications.json',
        'dataPolicies.json',
        'lexicon.json',
        'reference.json',
        'toolkit.json'
    ]
    
    # Check if _data directory exists
    data_dir = '_data'
    if not os.path.exists(data_dir):
        logger.warning(f"Local data directory '{data_dir}' not found. Creating sample files...")
        os.makedirs(data_dir, exist_ok=True)
        
        # Create sample files
        for filename in files_to_migrate:
            sample_data = {
                'models' if 'Models' in filename else 
                'agreements' if 'Agreements' in filename else
                'domains' if 'Domains' in filename else
                'applications' if 'applications' in filename else
                'policies' if 'Policies' in filename else
                'terms' if 'lexicon' in filename else
                'items' if 'reference' in filename else
                'toolkit': []
            }
            
            filepath = os.path.join(data_dir, filename)
            with open(filepath, 'w') as f:
                json.dump(sample_data, f, indent=2)
            logger.info(f"Created sample file: {filename}")
    
    # Migrate each file
    success_count = 0
    for filename in files_to_migrate:
        local_filepath = os.path.join(data_dir, filename)
        
        if os.path.exists(local_filepath):
            try:
                # Read local file
                with open(local_filepath, 'r') as f:
                    data = json.load(f)
                
                # Upload to S3
                success = s3_service.write_json_file(filename, data)
                
                if success:
                    logger.info(f"✅ Successfully migrated {filename}")
                    success_count += 1
                else:
                    logger.error(f"❌ Failed to migrate {filename}")
                    
            except Exception as e:
                logger.error(f"❌ Error migrating {filename}: {e}")
        else:
            logger.warning(f"⚠️  File not found: {local_filepath}")
    
    logger.info(f"Migration completed: {success_count}/{len(files_to_migrate)} files migrated successfully")
    
    # Verify migration
    logger.info("Verifying migration...")
    for filename in files_to_migrate:
        exists = s3_service.file_exists(filename)
        status = "✅" if exists else "❌"
        logger.info(f"{status} {filename}: {'Found' if exists else 'Not found'}")
    
    return success_count == len(files_to_migrate)

if __name__ == "__main__":
    print("🚀 Starting S3 migration...")
    print(f"Bucket: {Config.S3_BUCKET_NAME}")
    print(f"Folder Prefix: {Config.S3_FOLDER_PREFIX}")
    print(f"Region: {Config.AWS_REGION}")
    print("-" * 50)
    
    success = migrate_files_to_s3()
    
    if success:
        print("🎉 Migration completed successfully!")
        print("Your data is now available in S3 and ready to use with the API.")
    else:
        print("❌ Migration failed. Please check the logs above for details.")
        exit(1)


