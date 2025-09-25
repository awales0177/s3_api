import boto3
import json
import logging
from typing import Dict, Any, Optional
from botocore.exceptions import ClientError, NoCredentialsError
import os
from dotenv import load_dotenv
from config import Config

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

class S3Service:
    """Service class for handling S3 operations"""
    
    def __init__(self):
        self.s3_client = None
        self.bucket_name = Config.S3_BUCKET_NAME
        self.folder_prefix = Config.S3_FOLDER_PREFIX
        self.region_name = Config.AWS_REGION
        self.access_key_id = Config.AWS_ACCESS_KEY_ID
        self.secret_access_key = Config.AWS_SECRET_ACCESS_KEY
        
        # Initialize S3 client
        self._initialize_s3_client()
    
    def _initialize_s3_client(self):
        """Initialize the S3 client with credentials"""
        try:
            # For IRSA (IAM Roles for Service Accounts), we don't need explicit credentials
            # The boto3 client will automatically use the IAM role assigned to the service account
            if self.access_key_id and self.secret_access_key:
                # Use explicit credentials (for local development or non-IRSA environments)
                self.s3_client = boto3.client(
                    's3',
                    aws_access_key_id=self.access_key_id,
                    aws_secret_access_key=self.secret_access_key,
                    region_name=self.region_name
                )
                logger.info("S3 client initialized with explicit credentials")
            else:
                # Use IAM role (IRSA) or default credentials
                self.s3_client = boto3.client('s3', region_name=self.region_name)
                logger.info("S3 client initialized with IAM role (IRSA) or default credentials")
                
        except NoCredentialsError:
            logger.error("AWS credentials not found - check IRSA configuration or provide explicit credentials")
            self.s3_client = None
        except Exception as e:
            logger.error(f"Failed to initialize S3 client: {e}")
            self.s3_client = None
    
    def is_available(self) -> bool:
        """Check if S3 service is available"""
        return self.s3_client is not None and self.bucket_name is not None
    
    def read_json_file(self, file_path: str) -> Optional[Dict[str, Any]]:
        """
        Read a JSON file from S3
        
        Args:
            file_path (str): Path to the JSON file in S3 (e.g., 'data/models.json')
            
        Returns:
            Dict containing the JSON data or None if failed
        """
        if not self.is_available():
            logger.error("S3 service not available")
            return None
        
        try:
            # Ensure file_path doesn't start with '_data/' for S3
            if file_path.startswith('_data/'):
                file_path = file_path[6:]  # Remove '_data/' prefix
            
            # Add .json extension if not present
            if not file_path.endswith('.json'):
                file_path = f"{file_path}.json"
            
            # Add folder prefix
            s3_key = f"{self.folder_prefix}/{file_path}"
            
            logger.info(f"Reading JSON file from S3: s3://{self.bucket_name}/{s3_key}")
            
            response = self.s3_client.get_object(
                Bucket=self.bucket_name,
                Key=s3_key
            )
            
            # Read and parse JSON content
            content = response['Body'].read().decode('utf-8')
            data = json.loads(content)
            
            logger.info(f"Successfully read JSON file from S3: {file_path}")
            return data
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'NoSuchKey':
                logger.error(f"File not found in S3: {file_path}")
            else:
                logger.error(f"S3 error reading {file_path}: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in S3 file {file_path}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error reading from S3 {file_path}: {e}")
            return None
    
    def write_json_file(self, file_path: str, data: Dict[str, Any]) -> bool:
        """
        Write a JSON file to S3
        
        Args:
            file_path (str): Path to the JSON file in S3
            data (Dict): Data to write
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.is_available():
            logger.error("S3 service not available")
            return False
        
        try:
            # Ensure file_path doesn't start with '_data/' for S3
            if file_path.startswith('_data/'):
                file_path = file_path[6:]  # Remove '_data/' prefix
            
            # Add .json extension if not present
            if not file_path.endswith('.json'):
                file_path = f"{file_path}.json"
            
            # Add folder prefix
            s3_key = f"{self.folder_prefix}/{file_path}"
            
            logger.info(f"Writing JSON file to S3: s3://{self.bucket_name}/{s3_key}")
            
            # Convert data to JSON string
            json_content = json.dumps(data, indent=2, ensure_ascii=False)
            
            # Upload to S3
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=json_content.encode('utf-8'),
                ContentType='application/json'
            )
            
            logger.info(f"Successfully wrote JSON file to S3: {file_path}")
            return True
            
        except ClientError as e:
            logger.error(f"S3 error writing {file_path}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error writing to S3 {file_path}: {e}")
            return False
    
    def list_files(self, prefix: str = "") -> Optional[list]:
        """
        List files in S3 bucket with optional prefix
        
        Args:
            prefix (str): Prefix to filter files
            
        Returns:
            List of file keys or None if failed
        """
        if not self.is_available():
            logger.error("S3 service not available")
            return None
        
        try:
            # Add folder prefix to the search prefix
            search_prefix = f"{self.folder_prefix}/{prefix}" if prefix else f"{self.folder_prefix}/"
            
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=search_prefix
            )
            
            if 'Contents' in response:
                files = [obj['Key'] for obj in response['Contents']]
                logger.info(f"Listed {len(files)} files with prefix '{prefix}'")
                return files
            else:
                logger.info(f"No files found with prefix '{prefix}'")
                return []
                
        except ClientError as e:
            logger.error(f"S3 error listing files with prefix '{prefix}': {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error listing S3 files: {e}")
            return None
    
    def file_exists(self, file_path: str) -> bool:
        """
        Check if a file exists in S3
        
        Args:
            file_path (str): Path to the file in S3
            
        Returns:
            bool: True if file exists, False otherwise
        """
        if not self.is_available():
            return False
        
        try:
            # Ensure file_path doesn't start with '_data/' for S3
            if file_path.startswith('_data/'):
                file_path = file_path[6:]  # Remove '_data/' prefix
            
            # Add .json extension if not present
            if not file_path.endswith('.json'):
                file_path = f"{file_path}.json"
            
            # Add folder prefix
            s3_key = f"{self.folder_prefix}/{file_path}"
            
            self.s3_client.head_object(Bucket=self.bucket_name, Key=s3_key)
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                return False
            else:
                logger.error(f"S3 error checking file existence {file_path}: {e}")
                return False
        except Exception as e:
            logger.error(f"Unexpected error checking S3 file existence: {e}")
            return False
    
    def get_file_size(self, file_path: str) -> Optional[int]:
        """
        Get the size of a file in S3
        
        Args:
            file_path (str): Path to the file in S3
            
        Returns:
            File size in bytes or None if failed
        """
        if not self.is_available():
            return None
        
        try:
            # Ensure file_path doesn't start with '_data/' for S3
            if file_path.startswith('_data/'):
                file_path = file_path[6:]  # Remove '_data/' prefix
            
            # Add .json extension if not present
            if not file_path.endswith('.json'):
                file_path = f"{file_path}.json"
            
            # Add folder prefix
            s3_key = f"{self.folder_prefix}/{file_path}"
            
            response = self.s3_client.head_object(Bucket=self.bucket_name, Key=s3_key)
            return response['ContentLength']
            
        except ClientError as e:
            logger.error(f"S3 error getting file size {file_path}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error getting S3 file size: {e}")
            return None
