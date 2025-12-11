import json
import os
import logging
from typing import Dict, Any, Optional
from .s3_service import S3Service
from config import Config

logger = logging.getLogger(__name__)

class DataService:
    """Service class for handling data operations from different sources"""
    
    def __init__(self):
        self.s3_service = S3Service() if Config.S3_MODE else None
        self.data_directory = "_data"
        
    def read_json_file(self, file_path: str) -> Optional[Dict[str, Any]]:
        """
        Read a JSON file from the configured data source
        
        Args:
            file_path (str): Path to the JSON file
            
        Returns:
            Dict containing the JSON data or None if failed
        """
        # Priority: S3 > Local > GitHub
        if Config.S3_MODE and self.s3_service and self.s3_service.is_available():
            logger.info(f"Reading from S3: {file_path}")
            return self._read_from_s3(file_path)
        elif Config.TEST_MODE:
            logger.info(f"Reading from local files: {file_path}")
            return self._read_from_local(file_path)
        else:
            logger.info(f"Reading from GitHub: {file_path}")
            return self._read_from_github(file_path)
    
    def write_json_file(self, file_path: str, data: Dict[str, Any]) -> bool:
        """
        Write a JSON file to the configured data source
        
        Args:
            file_path (str): Path to the JSON file
            data (Dict): Data to write
            
        Returns:
            bool: True if successful, False otherwise
        """
        if Config.S3_MODE and self.s3_service and self.s3_service.is_available():
            logger.info(f"Writing to S3: {file_path}")
            return self.s3_service.write_json_file(file_path, data)
        elif Config.TEST_MODE:
            logger.info(f"Writing to local files: {file_path}")
            return self._write_to_local(file_path, data)
        else:
            logger.warning("Write operations not supported for GitHub mode")
            return False
    
    def _read_from_s3(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Read JSON file from S3"""
        try:
            return self.s3_service.read_json_file(file_path)
        except Exception as e:
            logger.error(f"Error reading from S3: {e}")
            return None
    
    def _read_from_local(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Read JSON file from local filesystem"""
        try:
            # Ensure file_path starts with _data/
            if not file_path.startswith(self.data_directory):
                file_path = os.path.join(self.data_directory, file_path)
            
            # Add .json extension if not present
            if not file_path.endswith('.json'):
                file_path = f"{file_path}.json"
            
            # Check if file exists
            if not os.path.exists(file_path):
                logger.error(f"Local file not found: {file_path}")
                return None
            
            with open(file_path, 'r', encoding='utf-8') as file:
                data = json.load(file)
                logger.info(f"Successfully read local file: {file_path}")
                return data
                
        except FileNotFoundError:
            logger.error(f"Local file not found: {file_path}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in local file {file_path}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error reading local file {file_path}: {e}")
            return None
    
    def _read_from_github(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Read JSON file from GitHub (placeholder for existing functionality)"""
        # This would integrate with your existing GitHub fetching logic
        # For now, we'll return None to indicate GitHub mode needs implementation
        logger.warning("GitHub mode not yet implemented in DataService")
        return None
    
    def _write_to_local(self, file_path: str, data: Dict[str, Any]) -> bool:
        """Write JSON file to local filesystem"""
        try:
            # Ensure file_path starts with _data/
            if not file_path.startswith(self.data_directory):
                file_path = os.path.join(self.data_directory, file_path)
            
            # Add .json extension if not present
            if not file_path.endswith('.json'):
                file_path = f"{file_path}.json"
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            with open(file_path, 'w', encoding='utf-8') as file:
                json.dump(data, file, indent=2, ensure_ascii=False)
                logger.info(f"Successfully wrote local file: {file_path}")
                return True
                
        except Exception as e:
            logger.error(f"Error writing local file {file_path}: {e}")
            return False
    
    def file_exists(self, file_path: str) -> bool:
        """
        Check if a file exists in the configured data source
        
        Args:
            file_path (str): Path to the file
            
        Returns:
            bool: True if file exists, False otherwise
        """
        if Config.S3_MODE and self.s3_service and self.s3_service.is_available():
            return self.s3_service.file_exists(file_path)
        elif Config.TEST_MODE:
            return self._local_file_exists(file_path)
        else:
            logger.warning("File existence check not supported for GitHub mode")
            return False
    
    def _local_file_exists(self, file_path: str) -> bool:
        """Check if file exists locally"""
        try:
            if not file_path.startswith(self.data_directory):
                file_path = os.path.join(self.data_directory, file_path)
            
            if not file_path.endswith('.json'):
                file_path = f"{file_path}.json"
            
            return os.path.exists(file_path)
        except Exception as e:
            logger.error(f"Error checking local file existence: {e}")
            return False
    
    def get_file_size(self, file_path: str) -> Optional[int]:
        """
        Get the size of a file in the configured data source
        
        Args:
            file_path (str): Path to the file
            
        Returns:
            File size in bytes or None if failed
        """
        if Config.S3_MODE and self.s3_service and self.s3_service.is_available():
            return self.s3_service.get_file_size(file_path)
        elif Config.TEST_MODE:
            return self._get_local_file_size(file_path)
        else:
            logger.warning("File size check not supported for GitHub mode")
            return None
    
    def _get_local_file_size(self, file_path: str) -> Optional[int]:
        """Get local file size"""
        try:
            if not file_path.startswith(self.data_directory):
                file_path = os.path.join(self.data_directory, file_path)
            
            if not file_path.endswith('.json'):
                file_path = f"{file_path}.json"
            
            if os.path.exists(file_path):
                return os.path.getsize(file_path)
            return None
        except Exception as e:
            logger.error(f"Error getting local file size: {e}")
            return None
    
    def list_files(self, prefix: str = "") -> Optional[list]:
        """
        List files in the configured data source with optional prefix
        
        Args:
            prefix (str): Prefix to filter files
            
        Returns:
            List of file keys or None if failed
        """
        if Config.S3_MODE and self.s3_service and self.s3_service.is_available():
            return self.s3_service.list_files(prefix)
        elif Config.TEST_MODE:
            return self._list_local_files(prefix)
        else:
            logger.warning("File listing not supported for GitHub mode")
            return None
    
    def _list_local_files(self, prefix: str = "") -> Optional[list]:
        """List local files with optional prefix"""
        try:
            base_path = self.data_directory
            if prefix:
                base_path = os.path.join(base_path, prefix)
            
            if not os.path.exists(base_path):
                return []
            
            files = []
            for root, dirs, filenames in os.walk(base_path):
                for filename in filenames:
                    if filename.endswith('.json'):
                        rel_path = os.path.relpath(os.path.join(root, filename), self.data_directory)
                        files.append(rel_path)
            
            return files
        except Exception as e:
            logger.error(f"Error listing local files: {e}")
            return None
