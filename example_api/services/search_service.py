"""
Search service for the data catalog API.
Provides search functionality across all data types.
"""

import logging
import json
import os
import re
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class SearchService:
    """Search service for the data catalog."""
    
    def __init__(self):
        self.index = {}
        self.stats = {
            'total_documents': 0,
            'total_tokens': 0,
            'last_updated': None,
            'documents_by_type': {}
        }
        self.data_dir = os.path.join(os.path.dirname(__file__), '..', '_data')
    
    def load_data_file(self, filename: str) -> List[Dict[str, Any]]:
        """Load data from a JSON file."""
        try:
            filepath = os.path.join(self.data_dir, filename)
            if os.path.exists(filepath):
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                    # Handle different data structures
                    if isinstance(data, list):
                        return data
                    elif isinstance(data, dict):
                        # Special handling for toolkit.json which has nested structure
                        if filename == 'toolkit.json' and 'toolkit' in data:
                            toolkit_data = data['toolkit']
                            all_items = []
                            # Combine functions, containers, and infrastructure
                            for category in ['functions', 'containers', 'infrastructure']:
                                if category in toolkit_data and isinstance(toolkit_data[category], list):
                                    # Add type field to each item for routing
                                    for item in toolkit_data[category]:
                                        item_with_type = item.copy()
                                        item_with_type['_toolkit_type'] = category
                                        all_items.append(item_with_type)
                            return all_items
                        
                        # Look for common array keys
                        for key in ['models', 'dataAgreements', 'domains', 'applications', 'reference', 'toolkit', 'policies', 'lexicon', 'agreements', 'terms']:
                            if key in data and isinstance(data[key], list):
                                return data[key]
                        # If no array found, return the dict as a single item
                        return [data]
                    else:
                        return []
            return []
        except Exception as e:
            logger.error(f"Error loading {filename}: {e}")
            return []
    
    def extract_searchable_text(self, item: Dict[str, Any]) -> str:
        """Extract searchable text from an item."""
        text_parts = []
        
        # For toolkit items (which have displayName), prioritize displayName over name
        # This ensures we index the display name (e.g., "Data Validation Utility") 
        # instead of the underscored name (e.g., "data_validation_utility")
        is_toolkit_item = 'displayName' in item or '_toolkit_type' in item
        
        if is_toolkit_item:
            # For toolkit items, use displayName instead of name
            if 'displayName' in item and item['displayName']:
                text_parts.append(str(item['displayName']))
            # Don't include the underscored 'name' field for toolkit items
        else:
            # For other items, use the standard 'name' field
            if 'name' in item and item['name']:
                text_parts.append(str(item['name']))
        
        # Common fields to search (excluding 'name' which we handled above)
        search_fields = ['title', 'description', 'extendedDescription', 'shortName', 'id', 'term', 'definition', 'category', 'owner']
        
        for field in search_fields:
            if field in item and item[field]:
                text_parts.append(str(item[field]))
        
        # Search in arrays
        if 'domain' in item and isinstance(item['domain'], list):
            text_parts.extend([str(d) for d in item['domain']])
        
        if 'changes' in item and isinstance(item['changes'], list):
            text_parts.extend([str(c) for c in item['changes']])
        
        # Glossary-specific fields
        if 'taggedModels' in item and isinstance(item['taggedModels'], list):
            text_parts.extend([str(m) for m in item['taggedModels']])
        
        return ' '.join(text_parts).lower()
    
    def build_index(self) -> bool:
        """Build the search index from all data sources."""
        try:
            logger.info("Building search index...")
            self.index = {}
            self.stats = {
                'total_documents': 0,
                'total_tokens': 0,
                'last_updated': datetime.now().isoformat(),
                'documents_by_type': {}
            }
            
            # Data files to index
            data_files = {
                'models': 'dataModels.json',
                'dataAgreements': 'dataAgreements.json',
                'domains': 'dataDomains.json',
                'applications': 'applications.json',
                'reference': 'reference.json',
                'toolkit': 'toolkit.json',
                'policies': 'dataPolicies.json',
                'lexicon': 'lexicon.json',
                'glossary': 'glossary.json'
            }
            
            total_documents = 0
            total_tokens = 0
            
            for doc_type, filename in data_files.items():
                logger.info(f"Indexing {doc_type} from {filename}")
                data = self.load_data_file(filename)
                
                if not data:
                    continue
                
                self.stats['documents_by_type'][doc_type] = 0
                
                for item in data:
                    # Create a unique ID for the document
                    # Handle different ID fields for different types
                    doc_id = str(item.get('id', item.get('shortName', item.get('name', item.get('term', '')))))
                    if not doc_id:
                        continue
                    
                    # Extract searchable text
                    searchable_text = self.extract_searchable_text(item)
                    if not searchable_text:
                        continue
                    
                    # Add to index
                    index_key = f"{doc_type}:{doc_id}"
                    self.index[index_key] = {
                        '_search_type': doc_type,
                        '_search_id': doc_id,
                        '_search_text': searchable_text,
                        **item
                    }
                    
                    total_documents += 1
                    total_tokens += len(searchable_text.split())
                    self.stats['documents_by_type'][doc_type] += 1
                
                logger.info(f"Indexed {self.stats['documents_by_type'][doc_type]} {doc_type} documents")
            
            self.stats['total_documents'] = total_documents
            self.stats['total_tokens'] = total_tokens
            
            logger.info(f"Search index built successfully with {total_documents} documents")
            return True
            
        except Exception as e:
            logger.error(f"Error building search index: {e}")
            return False
    
    def search(self, query: str, doc_types: Optional[List[str]] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Search across all indexed documents."""
        try:
            if not query or not query.strip():
                return []
            
            query_lower = query.lower().strip()
            results = []
            
            # Filter by document types if specified
            search_items = self.index.items()
            if doc_types:
                search_items = [(k, v) for k, v in search_items if v.get('_search_type') in doc_types]
            
            for index_key, item in search_items:
                search_text = item.get('_search_text', '')
                
                # Simple text matching
                if query_lower in search_text:
                    # Calculate a simple relevance score
                    score = search_text.count(query_lower) / len(search_text.split()) if search_text else 0
                    
                    # Extract matched terms
                    matched_terms = []
                    words = query_lower.split()
                    for word in words:
                        if word in search_text:
                            matched_terms.append(word)
                    
                    result = {
                        **item,
                        '_search_score': score,
                        '_matched_terms': matched_terms
                    }
                    results.append(result)
            
            # Sort by relevance score (highest first)
            results.sort(key=lambda x: x.get('_search_score', 0), reverse=True)
            
            # Limit results
            return results[:limit]
            
        except Exception as e:
            logger.error(f"Search error: {e}")
            return []
    
    def get_stats(self) -> Dict[str, Any]:
        """Get search index statistics."""
        return self.stats
    
    def rebuild_index(self) -> bool:
        """Rebuild the entire search index."""
        return self.build_index()
    
    def add_document(self, doc_type: str, doc_id: str, document: Dict[str, Any]) -> bool:
        """Add a document to the search index."""
        try:
            searchable_text = self.extract_searchable_text(document)
            if not searchable_text:
                return False
            
            index_key = f"{doc_type}:{doc_id}"
            self.index[index_key] = {
                '_search_type': doc_type,
                '_search_id': doc_id,
                '_search_text': searchable_text,
                **document
            }
            
            # Update stats
            self.stats['total_documents'] += 1
            self.stats['total_tokens'] += len(searchable_text.split())
            if doc_type not in self.stats['documents_by_type']:
                self.stats['documents_by_type'][doc_type] = 0
            self.stats['documents_by_type'][doc_type] += 1
            
            logger.info(f"Added document {doc_type}:{doc_id}")
            return True
        except Exception as e:
            logger.error(f"Error adding document: {e}")
            return False
    
    def update_document(self, doc_type: str, doc_id: str, document: Dict[str, Any]) -> bool:
        """Update a document in the search index."""
        try:
            searchable_text = self.extract_searchable_text(document)
            if not searchable_text:
                return False
            
            index_key = f"{doc_type}:{doc_id}"
            old_item = self.index.get(index_key, {})
            old_text = old_item.get('_search_text', '')
            
            self.index[index_key] = {
                '_search_type': doc_type,
                '_search_id': doc_id,
                '_search_text': searchable_text,
                **document
            }
            
            # Update token count
            old_tokens = len(old_text.split()) if old_text else 0
            new_tokens = len(searchable_text.split())
            self.stats['total_tokens'] = self.stats['total_tokens'] - old_tokens + new_tokens
            
            logger.info(f"Updated document {doc_type}:{doc_id}")
            return True
        except Exception as e:
            logger.error(f"Error updating document: {e}")
            return False
    
    def remove_document(self, doc_type: str, doc_id: str) -> bool:
        """Remove a document from the search index."""
        try:
            index_key = f"{doc_type}:{doc_id}"
            if index_key in self.index:
                item = self.index[index_key]
                searchable_text = item.get('_search_text', '')
                
                del self.index[index_key]
                
                # Update stats
                self.stats['total_documents'] -= 1
                self.stats['total_tokens'] -= len(searchable_text.split())
                if doc_type in self.stats['documents_by_type']:
                    self.stats['documents_by_type'][doc_type] -= 1
                
                logger.info(f"Removed document {doc_type}:{doc_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error removing document: {e}")
            return False

# Create a global instance
search_service = SearchService()