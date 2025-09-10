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
        self.s3_service = S3Service()
        if not self.s3_service.is_available():
            raise RuntimeError("S3 service is not available. Please check your AWS credentials and S3 configuration.")
        
    def read_json_file(self, file_path: str) -> Optional[Dict[str, Any]]:
        """
        Read a JSON file from S3
        
        Args:
            file_path (str): Path to the JSON file
            
        Returns:
            Dict containing the JSON data or None if failed
        """
        logger.info(f"Reading from S3: {file_path}")
        return self._read_from_s3(file_path)
    
    def write_json_file(self, file_path: str, data: Dict[str, Any]) -> bool:
        """
        Write a JSON file to S3
        
        Args:
            file_path (str): Path to the JSON file
            data (Dict): Data to write
            
        Returns:
            bool: True if successful, False otherwise
        """
        logger.info(f"Writing to S3: {file_path}")
        return self.s3_service.write_json_file(file_path, data)
    
    def _read_from_s3(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Read JSON file from S3"""
        try:
            return self.s3_service.read_json_file(file_path)
        except Exception as e:
            logger.error(f"Error reading from S3: {e}")
            return None
    
    
    
    
    def file_exists(self, file_path: str) -> bool:
        """
        Check if a file exists in S3
        
        Args:
            file_path (str): Path to the file
            
        Returns:
            bool: True if file exists, False otherwise
        """
        return self.s3_service.file_exists(file_path)
    
    
    def get_file_size(self, file_path: str) -> Optional[int]:
        """
        Get the size of a file in S3
        
        Args:
            file_path (str): Path to the file
            
        Returns:
            File size in bytes or None if failed
        """
        return self.s3_service.get_file_size(file_path)
    
    
    def list_files(self, prefix: str = "") -> Optional[list]:
        """
        List files in S3 with optional prefix
        
        Args:
            prefix (str): Prefix to filter files
            
        Returns:
            List of file keys or None if failed
        """
        return self.s3_service.list_files(prefix)
    
