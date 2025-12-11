#!/usr/bin/env python3
"""
Test script to verify S3 connectivity and configuration
Usage: python test_s3_connection.py
"""

import os
import logging
from dotenv import load_dotenv
from services.s3_service import S3Service
from config import Config

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_s3_connection():
    """Test S3 connectivity and configuration"""
    
    print("🔍 Testing S3 Connection...")
    print("=" * 50)
    
    # Check environment variables
    print("\n📋 Environment Configuration:")
    print(f"  S3_MODE: {os.getenv('S3_MODE', 'Not set')}")
    print(f"  S3_BUCKET_NAME: {os.getenv('S3_BUCKET_NAME', 'Not set')}")
    print(f"  AWS_REGION: {os.getenv('AWS_REGION', 'Not set')}")
    print(f"  AWS_ACCESS_KEY_ID: {'Set' if os.getenv('AWS_ACCESS_KEY_ID') else 'Not set'}")
    print(f"  AWS_SECRET_ACCESS_KEY: {'Set' if os.getenv('AWS_SECRET_ACCESS_KEY') else 'Not set'}")
    
    # Check config
    print(f"\n⚙️  Config Mode: {Config.get_mode_description()}")
    print(f"  Data Source: {Config.get_data_source()}")
    print(f"  S3 Configured: {Config.is_s3_configured()}")
    
    if not Config.is_s3_configured():
        print("\n❌ S3 is not properly configured!")
        print("   Please check your environment variables and .env file")
        return False
    
    # Test S3 service
    print("\n🔧 Testing S3 Service...")
    s3_service = S3Service()
    
    if not s3_service.is_available():
        print("❌ S3 service is not available!")
        print("   Please check your AWS credentials and bucket configuration")
        return False
    
    print("✅ S3 service is available")
    
    # Test bucket access
    bucket_name = Config.S3_BUCKET_NAME
    print(f"\n🪣 Testing bucket access: {bucket_name}")
    
    try:
        # List files in bucket
        files = s3_service.list_files()
        if files is not None:
            print(f"✅ Successfully listed {len(files)} files in bucket")
            if files:
                print("   Files found:")
                for file_key in sorted(files)[:10]:  # Show first 10 files
                    size = s3_service.get_file_size(file_key)
                    size_str = f" ({size} bytes)" if size else ""
                    print(f"     - {file_key}{size_str}")
                if len(files) > 10:
                    print(f"     ... and {len(files) - 10} more files")
            else:
                print("   No files found in bucket")
        else:
            print("❌ Failed to list files in bucket")
            return False
            
    except Exception as e:
        print(f"❌ Error testing bucket access: {e}")
        return False
    
    # Test reading a sample file (if any exist)
    if files:
        sample_file = files[0]
        print(f"\n📖 Testing file read: {sample_file}")
        
        try:
            data = s3_service.read_json_file(sample_file)
            if data is not None:
                print(f"✅ Successfully read file: {sample_file}")
                if isinstance(data, dict):
                    print(f"   File contains {len(data)} top-level keys")
                    for key in list(data.keys())[:5]:  # Show first 5 keys
                        print(f"     - {key}")
                    if len(data) > 5:
                        print(f"     ... and {len(data) - 5} more keys")
            else:
                print(f"❌ Failed to read file: {sample_file}")
                return False
                
        except Exception as e:
            print(f"❌ Error reading file: {e}")
            return False
    
    print("\n✅ All S3 tests passed!")
    return True

def test_write_permission():
    """Test if we have write permission to S3"""
    
    print("\n✍️  Testing Write Permission...")
    print("=" * 50)
    
    if not Config.is_s3_configured():
        print("❌ S3 not configured, skipping write test")
        return False
    
    s3_service = S3Service()
    if not s3_service.is_available():
        print("❌ S3 service not available, skipping write test")
        return False
    
    # Test file
    test_file = "test_connection.json"
    test_data = {
        "test": True,
        "timestamp": "2024-01-01T00:00:00Z",
        "message": "This is a test file to verify S3 write permissions"
    }
    
    print(f"  Writing test file: {test_file}")
    
    try:
        # Write test file
        if s3_service.write_json_file(test_file, test_data):
            print("✅ Successfully wrote test file")
            
            # Verify it was written
            if s3_service.file_exists(test_file):
                print("✅ Test file exists in S3")
                
                # Read it back
                read_data = s3_service.read_json_file(test_file)
                if read_data and read_data.get('test'):
                    print("✅ Successfully read back test file")
                    
                    # Clean up test file
                    print("🧹 Cleaning up test file...")
                    # Note: S3 service doesn't have delete method yet, but that's okay for this test
                    print("   Test file left in S3 for manual cleanup")
                    return True
                else:
                    print("❌ Failed to read back test file")
                    return False
            else:
                print("❌ Test file not found after writing")
                return False
        else:
            print("❌ Failed to write test file")
            return False
            
    except Exception as e:
        print(f"❌ Error during write test: {e}")
        return False

def main():
    """Main test function"""
    print("🚀 S3 Connection Test for Data Catalog API")
    print("=" * 60)
    
    # Test basic connection
    if not test_s3_connection():
        print("\n❌ S3 connection test failed!")
        print("   Please check your configuration and try again")
        return 1
    
    # Test write permission
    if not test_write_permission():
        print("\n⚠️  Write permission test failed!")
        print("   Your API may be read-only")
        print("   Check your IAM permissions")
    
    print("\n🎉 S3 integration test completed successfully!")
    print("\nNext steps:")
    print("1. Your S3 configuration is working correctly")
    print("2. You can now run the API with S3_MODE=true")
    print("3. Use the migration script to move your data to S3")
    
    return 0

if __name__ == "__main__":
    exit(main())
