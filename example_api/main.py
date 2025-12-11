from fastapi import FastAPI, HTTPException, Depends, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel, Field
import json
import os
from typing import Dict, Any, List, Optional
import secrets
import requests
from datetime import datetime, timedelta
import logging
import threading
import time
from time import perf_counter
import uuid

# Import authentication modules
from auth import get_current_user_optional, require_editor_or_admin, require_admin, UserRole
from endpoints.auth import router as auth_router
from services.search_service import search_service
from services.python_introspection_service import python_introspection_service

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Performance metrics
performance_metrics = {
    "requests": {
        "total": 0,
        "by_endpoint": {},
        "response_times": []
    },
    "github": {
        "requests": 0,
        "errors": 0,
        "response_times": []
    }
}

def log_performance(endpoint: str, start_time: float, github_request: bool = False):
    """Log performance metrics for an API request."""
    duration = perf_counter() - start_time
    performance_metrics["requests"]["total"] += 1
    performance_metrics["requests"]["by_endpoint"][endpoint] = performance_metrics["requests"]["by_endpoint"].get(endpoint, 0) + 1
    performance_metrics["requests"]["response_times"].append(duration)
    
    if github_request:
        performance_metrics["github"]["requests"] += 1
        performance_metrics["github"]["response_times"].append(duration)

def get_performance_stats():
    """Calculate performance statistics."""
    response_times = performance_metrics["requests"]["response_times"]
    github_times = performance_metrics["github"]["response_times"]
    
    stats = {
        "total_requests": performance_metrics["requests"]["total"],
        "requests_by_endpoint": performance_metrics["requests"]["by_endpoint"],
        "cache": {
            "status": "disabled",
            "message": "All data is read fresh from files"
        },
        "github": {
            "total_requests": performance_metrics["github"]["requests"],
            "errors": performance_metrics["github"]["errors"]
        }
    }
    
    if response_times:
        stats["response_times"] = {
            "avg": sum(response_times) / len(response_times),
            "min": min(response_times),
            "max": max(response_times),
            "p95": sorted(response_times)[int(len(response_times) * 0.95)]
        }
    
    if github_times:
        stats["github"]["response_times"] = {
            "avg": sum(github_times) / len(github_times),
            "min": min(github_times),
            "max": max(github_times),
            "p95": sorted(github_times)[int(len(github_times) * 0.95)]
        }
    
    return stats

# API Documentation
app = FastAPI(
    title="Catalog API",
    description="""
    API for serving and managing catalog JSON files. This API provides endpoints for:
    
    * Retrieving data models, contracts, domains, theme, and menu items
    * Managing data through an admin interface
    * Real-time updates to the catalog
    
    ## Authentication
    Admin endpoints require basic authentication with the following credentials:
    * Username: admin
    * Password: admin
    
    ## Data Structure
    The API serves the following data types:
    * Models: Data model definitions and metadata
    * Contracts: Product agreements and compliance
    * Domains: Data domains and their relationships
    * Theme: UI theme configuration
    * Menu: Navigation menu structure
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include authentication router
app.include_router(auth_router)

# GitHub configuration
GITHUB_RAW_BASE_URL = "https://raw.githubusercontent.com/awales0177/test_data/main"
CACHE_DURATION = timedelta(minutes=15)
PASSTHROUGH_MODE = False  # Can be toggled via environment variable
TEST_MODE = True  # Set to True to use local _data files instead of GitHub

# Log server configuration
logger.info("=" * 50)
logger.info("Server Configuration:")
logger.info(f"Mode: {'PASSTHROUGH' if PASSTHROUGH_MODE else 'DIRECT'}")
logger.info(f"Test Mode: {'ENABLED' if TEST_MODE else 'DISABLED'}")
logger.info(f"Caching: DISABLED - Always fresh data")
logger.info(f"GitHub Base URL: {GITHUB_RAW_BASE_URL}")
logger.info("=" * 50)

# Initialize search index
logger.info("Initializing search index...")
try:
    search_service.build_index()
    stats = search_service.get_stats()
    logger.info(f"Search index initialized with {stats['total_documents']} documents")
except Exception as e:
    logger.error(f"Failed to initialize search index: {e}")
    logger.info("Search functionality will be limited until index is rebuilt")

# Cache storage - Disabled
# cache = {
#     "data": {},
#     "last_updated": {}
# }

# Basic authentication
security = HTTPBasic()
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin"  # In production, use environment variables

def verify_credentials(credentials: HTTPBasicCredentials = Depends(security)):
    correct_username = secrets.compare_digest(credentials.username, ADMIN_USERNAME)
    correct_password = secrets.compare_digest(credentials.password, ADMIN_PASSWORD)
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials

# Data models
class JSONData(BaseModel):
    data: Dict[str, Any] = Field(..., description="The JSON data to be stored")

class CreateModelRequest(BaseModel):
    shortName: str = Field(..., description="Short name of the new model")
    name: str = Field(..., description="Name of the new model")
    description: str = Field(..., description="Description of the new model")
    version: str = Field(default="1.0.0", description="Version of the new model")
    extendedDescription: str = Field(default="", description="Extended description of the new model")
    owner: str = Field(default="", description="Owner of the new model")
    specMaintainer: str = Field(default="", description="Spec maintainer of the new model")
    maintainerEmail: str = Field(default="", description="Maintainer email of the new model")
    domain: List[str] = Field(default=[], description="Domains of the new model")
    referenceData: List[str] = Field(default=[], description="Reference data of the new model")
    meta: Dict[str, Any] = Field(default={"tier": "bronze", "verified": False}, description="Metadata of the new model")
    changelog: List[Dict[str, Any]] = Field(default=[], description="Changelog of the new model")
    resources: Dict[str, Any] = Field(default={}, description="Resources of the new model")
    users: List[str] = Field(default=[], description="Users of the new model")

class UpdateModelRequest(BaseModel):
    shortName: str = Field(..., description="Short name of the model to update")
    modelData: Dict[str, Any] = Field(..., description="Updated model data")
    updateAssociatedLinks: bool = Field(True, description="Whether to update agreements that reference this model")

class FileList(BaseModel):
    files: List[str] = Field(..., description="List of available file names")

class ItemCount(BaseModel):
    count: int = Field(..., description="Number of items in the data file")

class PaginationParams(BaseModel):
    page: int = Field(1, ge=1, description="Page number")
    page_size: int = Field(10, ge=1, le=100, description="Items per page")

# File paths mapping
JSON_FILES = {
    "dataAgreements": "dataAgreements.json",
    "domains": "dataDomains.json",
    "models": "dataModels.json",
    "specifications": "dataModels.json",  # Alias for specifications
    "theme": "theme.json",
    "applications": "applications.json",
    "lexicon": "lexicon.json",
    "reference": "reference.json",
    "toolkit": "toolkit.json",
    "policies": "dataPolicies.json",
    "zones": "zones.json",
    "glossary": "glossary.json",
    "statistics": "statistics.json",
    "rules": "rules.json",
    "countryRules": "countryRules.json"
}

# Data type to key mapping for counting items
DATA_TYPE_KEYS = {
    "dataAgreements": "agreements",
    "domains": "domains",
    "models": "models",
    "specifications": "models",  # Alias for specifications
    "applications": "applications",
    "lexicon": "terms",
    "reference": "items",
    "toolkit": "toolkit",
    "policies": "policies",
    "zones": "zones",
    "glossary": "terms"
}

def fetch_from_github(file_name: str) -> Dict:
    """Fetch data from GitHub raw content."""
    start_time = perf_counter()
    if file_name not in JSON_FILES:
        logger.error(f"File {file_name} not found in JSON_FILES mapping")
        raise HTTPException(status_code=404, detail="File not found")
    
    url = f"{GITHUB_RAW_BASE_URL}/{JSON_FILES[file_name]}"
    logger.info(f"Fetching data from GitHub: {url}")
    try:
        response = requests.get(url)
        logger.info(f"GitHub response status: {response.status_code}")
        if response.status_code == 404:
            logger.error(f"File not found on GitHub: {url}")
            raise HTTPException(status_code=404, detail="File not found on GitHub")
        if response.status_code != 200:
            performance_metrics["github"]["errors"] += 1
            logger.error(f"GitHub API error: {response.status_code} - {response.text}")
            raise HTTPException(status_code=500, detail=f"GitHub API error: {response.status_code}")
        
        data = response.json()
        logger.info(f"Successfully fetched and parsed JSON for {file_name}")
        log_performance("github_fetch", start_time, github_request=True)
        return data
    except requests.exceptions.RequestException as e:
        performance_metrics["github"]["errors"] += 1
        logger.error(f"Network error fetching from GitHub: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Network error: {str(e)}")
    except json.JSONDecodeError as e:
        performance_metrics["github"]["errors"] += 1
        logger.error(f"Invalid JSON response from GitHub: {str(e)}")
        raise HTTPException(status_code=500, detail="Invalid JSON response from GitHub")
    except Exception as e:
        performance_metrics["github"]["errors"] += 1
        logger.error(f"Unexpected error fetching from GitHub: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Cache cleanup disabled
# def cleanup_stale_cache():
#     """Remove cache entries that are older than CACHE_DURATION."""
#     current_time = datetime.now()
#     stale_files = [
#         file_name for file_name, last_updated in cache["last_updated"].items()
#         if current_time - last_updated > CACHE_DURATION
#     ]
#     
#     for file_name in stale_files:
#         logger.info(f"Removing stale cache for {file_name}")
#         del cache["data"][file_name]
#         del cache["last_updated"][file_name]

def get_cached_data(file_name: str) -> Dict:
    """Get data directly from local files (no caching)."""
    start_time = perf_counter()
    logger.info(f"Reading data directly from local files for {file_name}")
    
    if TEST_MODE:
        logger.info(f"Reading from local _data files for {file_name}")
        try:
            data = read_json_file(JSON_FILES[file_name])
            logger.info(f"Local file loaded successfully for {file_name}")
            log_performance("local_file_read", start_time)
            return data
        except Exception as e:
            logger.error(f"Error reading local file {file_name}: {str(e)}")
            # Fallback to GitHub if local file fails
            logger.info(f"Falling back to GitHub for {file_name}")
            data = fetch_from_github(file_name)
            logger.info(f"GitHub fallback loaded for {file_name}")
            log_performance("github_fallback", start_time)
            return data
    else:
        logger.info(f"Fetching from GitHub for {file_name}")
        data = fetch_from_github(file_name)
        logger.info(f"GitHub data loaded for {file_name}")
        log_performance("github_fetch", start_time)
        return data

# Search endpoints (must be before generic {file_name} route)
@app.get("/api/search")
def global_search(
    q: str = Query(..., description="Search query"),
    types: str = Query(None, description="Comma-separated list of data types to search"),
    limit: int = Query(50, ge=1, le=200, description="Maximum number of results")
):
    """Global search across all data types."""
    try:
        # Parse types parameter
        doc_types = None
        if types:
            doc_types = [t.strip() for t in types.split(',') if t.strip()]
        
        # Perform search
        results = search_service.search(q, doc_types, limit)
        
        return {
            "query": q,
            "results": results,
            "total": len(results),
            "types_searched": doc_types or "all"
        }
    except Exception as e:
        logger.error(f"Error in global search: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Search error: {str(e)}")

@app.post("/api/search/rebuild")
def rebuild_search_index(current_user: dict = Depends(require_admin)):
    """Rebuild the search index (admin only)."""
    try:
        success = search_service.rebuild_index()
        if success:
            stats = search_service.get_stats()
            return {
                "message": "Search index rebuilt successfully",
                "stats": stats
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to rebuild search index")
    except Exception as e:
        logger.error(f"Error rebuilding search index: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error rebuilding index: {str(e)}")

@app.get("/api/search/stats")
def get_search_stats():
    """Get search index statistics."""
    try:
        stats = search_service.get_stats()
        return stats
    except Exception as e:
        logger.error(f"Error getting search stats: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting stats: {str(e)}")

@app.get("/api/search/suggest")
def search_suggestions(
    q: str = Query(..., description="Partial search query"),
    limit: int = Query(10, ge=1, le=50, description="Maximum number of suggestions")
):
    """Get search suggestions based on partial query."""
    try:
        # Get search results for suggestions
        results = search_service.search(q, limit=limit)
        
        # Extract unique suggestions from results
        suggestions = set()
        for result in results:
            # Add name/title suggestions
            if 'name' in result:
                suggestions.add(result['name'])
            if 'shortName' in result:
                suggestions.add(result['shortName'])
            if 'title' in result:
                suggestions.add(result['title'])
            
            # Add domain suggestions
            if 'domain' in result and isinstance(result['domain'], list):
                suggestions.update(result['domain'])
        
        # Convert to list and limit
        suggestions_list = list(suggestions)[:limit]
        
        return {
            "query": q,
            "suggestions": suggestions_list
        }
    except Exception as e:
        logger.error(f"Error getting search suggestions: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting suggestions: {str(e)}")

@app.get("/api/zones")
def get_zones():
    """
    Get all zones with their associated domains.
    Zones are read from zones.json and domains are grouped by their zone field.
    """
    try:
        start_time = perf_counter()
        logger.info("Request for zones - reading from zones.json and grouping domains")
        
        # Get zones definitions from zones.json
        zones_data = get_cached_data("zones") if not PASSTHROUGH_MODE else fetch_from_github("zones")
        zones_definitions = zones_data.get("zones", [])
        
        # Get domains data
        domains_data = get_cached_data("domains") if not PASSTHROUGH_MODE else fetch_from_github("domains")
        domains = domains_data.get("domains", [])
        
        # Create a map of zone name to zone definition
        zones_map = {zone["name"]: zone.copy() for zone in zones_definitions}
        
        # Initialize domains array for each zone
        for zone_name in zones_map:
            zones_map[zone_name]["domains"] = []
        
        # Group domains by zone
        unzoned_domains = []
        
        for domain in domains:
            zone_name = domain.get("zone") or domain.get("zoneName")
            
            if not zone_name or zone_name == "Unzoned":
                unzoned_domains.append(domain)
            elif zone_name in zones_map:
                zones_map[zone_name]["domains"].append(domain)
            else:
                # Zone not found in definitions, add to unzoned
                logger.warning(f"Domain '{domain.get('name')}' references zone '{zone_name}' which is not defined in zones.json")
                unzoned_domains.append(domain)
        
        # Convert map to list - this includes ALL zones from zones.json, even if they have no domains
        zones = list(zones_map.values())
        
        # Log zone information for debugging
        logger.info(f"Loaded {len(zones_definitions)} zone definitions from zones.json")
        logger.info(f"Found {len(zones)} zones with definitions")
        logger.info(f"Unzoned domains: {len(unzoned_domains)}")
        
        # Add unzoned domains as a zone if there are any
        if unzoned_domains:
            zones.append({
                "id": "unzoned",
                "name": "Unzoned",
                "description": "Domains not assigned to a zone",
                "owner": "System",
                "lastUpdated": datetime.now().strftime("%Y-%m-%d"),
                "domains": unzoned_domains
            })
        
        # Sort zones by name
        zones.sort(key=lambda x: x["name"])
        
        log_performance("get_zones", start_time)
        
        return {
            "zones": zones,
            "total": len(zones)
        }
    except Exception as e:
        logger.error(f"Error getting zones: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting zones: {str(e)}")

# Country rules endpoints (must come before generic {file_name} route)
@app.get("/api/country-rules")
async def get_all_country_rules():
    """
    Get all country rules.
    
    Returns:
        dict: List of all country rules
    """
    try:
        try:
            rules_data = read_json_file(JSON_FILES['countryRules'])
        except HTTPException as e:
            logger.warning(f"Country rules file not found or can't be read: {str(e)}")
            return {"rules": []}
        except Exception as e:
            logger.warning(f"Error reading country rules file: {str(e)}, returning empty rules")
            return {"rules": []}
        
        # Ensure rules_data has the expected structure
        if not isinstance(rules_data, dict):
            logger.warning("Country rules file has invalid structure, returning empty rules")
            return {"rules": []}
        
        if 'rules' not in rules_data:
            logger.warning("Country rules file missing 'rules' key, returning empty rules")
            return {"rules": []}
        
        all_rules = rules_data.get('rules', [])
        logger.info(f"Returning all {len(all_rules)} country rules")
        return {
            "rules": all_rules,
            "count": len(all_rules)
        }
    except Exception as e:
        logger.error(f"Error getting all country rules: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting all country rules: {str(e)}")

@app.get("/api/country-rules/{country}")
async def get_rules_for_country(country: str):
    """
    Get all rules for a specific country.
    
    Args:
        country (str): The name of the country
        
    Returns:
        dict: List of rules for the country
    """
    try:
        try:
            rules_data = read_json_file(JSON_FILES['countryRules'])
        except HTTPException as e:
            logger.warning(f"Country rules file not found or can't be read: {str(e)}")
            return {"rules": []}
        except Exception as e:
            logger.warning(f"Error reading country rules file: {str(e)}, returning empty rules")
            return {"rules": []}
        
        # Ensure rules_data has the expected structure
        if not isinstance(rules_data, dict):
            logger.warning("Country rules file has invalid structure, returning empty rules")
            return {"rules": []}
        
        if 'rules' not in rules_data:
            logger.warning("Country rules file missing 'rules' key, returning empty rules")
            return {"rules": []}
        
        # Filter rules by country
        country_rules = [
            rule for rule in rules_data.get('rules', [])
            if rule.get('country', '').lower() == country.lower()
        ]
        
        logger.info(f"Found {len(country_rules)} rules for country {country}")
        return {
            "rules": country_rules,
            "count": len(country_rules)
        }
    except Exception as e:
        logger.error(f"Error getting country rules: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting country rules: {str(e)}")

@app.get("/api/country-rules/{country}/count")
async def get_country_rule_count(country: str):
    """
    Get the count of rules for a specific country.
    
    Args:
        country (str): The name of the country
        
    Returns:
        dict: Count of rules for the country
    """
    try:
        try:
            rules_data = read_json_file(JSON_FILES['countryRules'])
        except HTTPException as e:
            logger.warning(f"Country rules file not found or can't be read: {str(e)}")
            return {"count": 0}
        except Exception as e:
            logger.warning(f"Error reading country rules file: {str(e)}, returning count 0")
            return {"count": 0}
        
        if not isinstance(rules_data, dict):
            logger.warning("Country rules file has invalid structure, returning count 0")
            return {"count": 0}
        
        if 'rules' not in rules_data:
            logger.warning("Country rules file missing 'rules' key, returning count 0")
            return {"count": 0}
        
        # Filter rules by country and count
        country_rules = [
            rule for rule in rules_data.get('rules', [])
            if rule.get('country', '').lower() == country.lower()
        ]
        
        return {"count": len(country_rules)}
    except Exception as e:
        logger.error(f"Error getting country rule count: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting country rule count: {str(e)}")

@app.get("/api/country-rules/{country}/coverage")
async def get_country_rule_coverage(country: str):
    """
    Get rule coverage statistics for a country.
    
    Args:
        country (str): The name of the country
        
    Returns:
        dict: Coverage statistics showing rules per object/column
    """
    try:
        # Get country rules
        try:
            rules_data = read_json_file(JSON_FILES['countryRules'])
        except HTTPException:
            rules_data = {"rules": []}
        except Exception as e:
            logger.warning(f"Error reading country rules file: {str(e)}")
            rules_data = {"rules": []}
        
        if not isinstance(rules_data, dict):
            rules_data = {"rules": []}
        
        country_rules = [
            rule for rule in rules_data.get('rules', [])
            if rule.get('country', '').lower() == country.lower()
        ]
        
        # Calculate coverage
        tagged_objects = set()
        tagged_columns = set()
        tagged_functions = set()
        
        for rule in country_rules:
            if rule.get('taggedObjects') and isinstance(rule.get('taggedObjects'), list):
                tagged_objects.update(rule['taggedObjects'])
            if rule.get('taggedColumns') and isinstance(rule.get('taggedColumns'), list):
                tagged_columns.update(rule['taggedColumns'])
            if rule.get('taggedFunctions') and isinstance(rule.get('taggedFunctions'), list):
                tagged_functions.update(rule['taggedFunctions'])
        
        coverage = {
            "country": country,
            "totalRules": len(country_rules),
            "taggedObjects": list(tagged_objects),
            "taggedColumns": list(tagged_columns),
            "taggedFunctions": list(tagged_functions),
            "objectCoverage": len(tagged_objects),
            "columnCoverage": len(tagged_columns),
            "functionCoverage": len(tagged_functions),
            "rules": country_rules
        }
        
        return coverage
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting country rule coverage: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting country rule coverage: {str(e)}")

@app.get("/api/{file_name}")
def get_json_file(file_name: str):
    """Get JSON file content with direct file reading or passthrough mode."""
    start_time = perf_counter()
    logger.info(f"Request for {file_name} - Using {'passthrough' if PASSTHROUGH_MODE else 'direct'} mode")
    result = fetch_from_github(file_name) if PASSTHROUGH_MODE else get_cached_data(file_name)
    
    # Ensure clickCount is initialized for all toolkit components
    if file_name == 'toolkit' and isinstance(result, dict) and 'toolkit' in result:
        for component_type in ['functions', 'containers', 'infrastructure']:
            if component_type in result['toolkit'] and isinstance(result['toolkit'][component_type], list):
                for component in result['toolkit'][component_type]:
                    if 'clickCount' not in component or component['clickCount'] is None:
                        component['clickCount'] = 0
    
    log_performance("get_json_file", start_time)
    return result

@app.get("/api/{file_name}/paginated")
def get_paginated_json_file(
    file_name: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100)
):
    """Get paginated JSON file content."""
    logger.info(f"Paginated request for {file_name} - Using {'passthrough' if PASSTHROUGH_MODE else 'direct'} mode")
    data = get_cached_data(file_name) if not PASSTHROUGH_MODE else fetch_from_github(file_name)
    key = DATA_TYPE_KEYS.get(file_name)
    
    if not key or key not in data:
        raise HTTPException(status_code=500, detail=f"Invalid data structure for {file_name}")
    
    items = data[key]
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    
    return {
        "items": items[start_idx:end_idx],
        "total": len(items),
        "page": page,
        "page_size": page_size,
        "total_pages": (len(items) + page_size - 1) // page_size
    }

@app.get("/api/count/{file_name}")
def get_count(file_name: str):
    """Get the count of items in a specific data file."""
    logger.info(f"Count request for {file_name} - Using {'passthrough' if PASSTHROUGH_MODE else 'direct'} mode")
    data = get_cached_data(file_name) if not PASSTHROUGH_MODE else fetch_from_github(file_name)
    key = DATA_TYPE_KEYS.get(file_name)
    
    if not key or key not in data:
        raise HTTPException(status_code=500, detail=f"Invalid data structure for {file_name}")
    
    return {"count": len(data[key])}

@app.get("/api/agreements/by-model/{model_short_name}")
async def get_agreements_by_model(model_short_name: str):
    """
    Get all agreements associated with a specific data model by its short name.
    
    Args:
        model_short_name (str): The short name of the model (e.g., 'CUST', 'PROD')
        
    Returns:
        dict: A dictionary containing the model info and filtered agreements
        
    Raises:
        HTTPException: If the model is not found
    """
    try:
        agreements_data = read_json_file(JSON_FILES['dataAgreements'])
        model_data = read_json_file(JSON_FILES['models'])

        # Find the model by short name (case-insensitive)
        model = next((m for m in model_data['models'] if m['shortName'].lower() == model_short_name.lower()), None)
        if not model:
            raise HTTPException(
                status_code=404, 
                detail=f"Model with short name '{model_short_name}' not found"
            )

        # Filter agreements by model shortName
        filtered_agreements = [
            agreement for agreement in agreements_data['agreements']
            if agreement.get('modelShortName', '').lower() == model_short_name.lower()
        ]
        
        # Add debugging information
        logger.info(f"Agreements lookup for model '{model_short_name}':")
        logger.info(f"  Total agreements in file: {len(agreements_data['agreements'])}")
        logger.info(f"  Found agreements: {len(filtered_agreements)}")
        logger.info(f"  Agreement modelShortNames: {[a.get('modelShortName') for a in agreements_data['agreements']]}")
        logger.info(f"  Model shortName: {model['shortName']}")
        
        return {
            "model": {
                "id": model['id'],
                "shortName": model['shortName'],
                "name": model['name']
            },
            "agreements": filtered_agreements
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error processing request: {str(e)}"
        )

@app.post("/api/models")
async def create_model(request: CreateModelRequest, current_user: dict = Depends(require_editor_or_admin)):
    """
    Create a new data model.
    
    Args:
        request (CreateModelRequest): The new model data
        
    Returns:
        dict: Success message and created model info
        
    Raises:
        HTTPException: If creation fails
    """
    try:
        logger.info(f"Create request for new model")
        
        # Read current models data
        models_data = read_json_file(JSON_FILES['models'])
        
        # Check if the shortName already exists
        for existing_model in models_data['models']:
            if existing_model['shortName'] == request.shortName:
                raise HTTPException(
                    status_code=400,
                    detail=f"Model with shortName '{request.shortName}' already exists"
                )
        
        # Generate a new ID (max existing ID + 1)
        new_id = max([m['id'] for m in models_data['models']], default=0) + 1
        
        # Ensure meta has clickCount initialized to 0
        meta = request.meta.copy() if request.meta else {}
        if 'clickCount' not in meta:
            meta['clickCount'] = 0
        
        # Create the new model from the request
        new_model = {
            'id': new_id,
            'shortName': request.shortName,
            'name': request.name,
            'description': request.description,
            'version': request.version,
            'extendedDescription': request.extendedDescription,
            'owner': request.owner,
            'specMaintainer': request.specMaintainer,
            'maintainerEmail': request.maintainerEmail,
            'domain': request.domain,
            'referenceData': request.referenceData,
            'meta': meta,
            'changelog': request.changelog,
            'resources': request.resources,
            'users': request.users,
            'lastUpdated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # Add the new model to the array
        models_data['models'].append(new_model)
        
        # Save the updated data to local file
        local_file_path = JSON_FILES['models']
        write_json_file(local_file_path, models_data)
        logger.info(f"Created new model in local file {local_file_path}")
        
        # Update search index
        update_search_index("models", "add", new_model, str(new_id))
        
        logger.info(f"Model {request.shortName} created successfully with ID {new_id}")
        
        return {
            "message": "Model created successfully",
            "shortName": request.shortName,
            "id": new_id,
            "created": True
        }
        
    except Exception as e:
        logger.error(f"Error creating model: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error creating model: {str(e)}"
        )

@app.delete("/api/models/{short_name}")
async def delete_model(short_name: str, current_user: dict = Depends(require_editor_or_admin)):
    """
    Delete a data model by its short name.
    
    Args:
        short_name (str): The short name of the model to delete
        
    Returns:
        dict: Success message and deleted model info
        
    Raises:
        HTTPException: If the model is not found or deletion fails
    """
    try:
        logger.info(f"Delete request for model: {short_name}")
        
        # Read current models data
        models_data = read_json_file(JSON_FILES['models'])
        
        # Find the model to delete
        model_to_delete = None
        for model in models_data['models']:
            if model['shortName'].lower() == short_name.lower():
                model_to_delete = model
                break
        
        if not model_to_delete:
            raise HTTPException(
                status_code=404,
                detail=f"Model with shortName '{short_name}' not found"
            )
        
        # Remove the model from the array
        models_data['models'] = [m for m in models_data['models'] if m['shortName'].lower() != short_name.lower()]
        
        # Save the updated data to local file
        local_file_path = JSON_FILES['models']
        write_json_file(local_file_path, models_data)
        logger.info(f"Model deleted from local file {local_file_path}")
        
        # Update search index
        update_search_index("models", "delete", item_id=short_name)
        
        logger.info(f"Model {short_name} deleted successfully")
        
        return {
            "message": "Model deleted successfully",
            "shortName": short_name,
            "deleted": True
        }
        
    except Exception as e:
        logger.error(f"Error deleting model: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error deleting model: {str(e)}"
        )

@app.post("/api/models/{short_name}/click")
async def track_model_click(short_name: str):
    """
    Track a click on a data model card and increment the click counter.
    
    Args:
        short_name (str): The short name of the model to track
        
    Returns:
        dict: Success message and updated click count
        
    Raises:
        HTTPException: If the model is not found
    """
    try:
        logger.info(f"Click tracking request for model: {short_name}")
        
        # Read current models data
        models_data = read_json_file(JSON_FILES['models'])
        
        # Find the model to update
        model_index = None
        for i, model in enumerate(models_data['models']):
            if model['shortName'].lower() == short_name.lower():
                model_index = i
                break
        
        if model_index is None:
            raise HTTPException(
                status_code=404,
                detail=f"Model with short name '{short_name}' not found"
            )
        
        # Get the current model
        model = models_data['models'][model_index]
        
        # Initialize clickCount in meta if it doesn't exist
        if 'meta' not in model:
            model['meta'] = {}
        
        # Increment click count (initialize to 1 if not present)
        current_count = model['meta'].get('clickCount', 0)
        model['meta']['clickCount'] = current_count + 1
        
        # Update the model in the array
        models_data['models'][model_index] = model
        
        # Save the updated data to local file
        local_file_path = JSON_FILES['models']
        write_json_file(local_file_path, models_data)
        logger.info(f"Updated click count for model {short_name} to {model['meta']['clickCount']}")
        
        return {
            "message": "Click tracked successfully",
            "shortName": short_name,
            "clickCount": model['meta']['clickCount']
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error tracking click for model {short_name}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error tracking click: {str(e)}"
        )

@app.put("/api/models/{short_name}")
async def update_model(short_name: str, request: UpdateModelRequest, current_user: dict = Depends(require_editor_or_admin)):
    """
    Update a data model by its short name.
    
    Args:
        short_name (str): The short name of the model to update
        request (UpdateModelRequest): The updated model data
        
    Returns:
        dict: Success message and updated model info
        
    Raises:
        HTTPException: If the model is not found or update fails
    """
    try:
        logger.info(f"Update request for model: {short_name}")
        
        # Read current models data
        models_data = read_json_file(JSON_FILES['models'])
        
        # Find the model to update
        model_index = None
        for i, model in enumerate(models_data['models']):
            if model['shortName'].lower() == short_name.lower():
                model_index = i
                break
        
        if model_index is None:
            raise HTTPException(
                status_code=404,
                detail=f"Model with short name '{short_name}' not found"
            )
        
        # Update the model
        old_model = models_data['models'][model_index]
        updated_model = {**old_model, **request.modelData}
        
        # Preserve clickCount in meta if it exists in the old model
        if 'meta' in request.modelData and 'meta' in old_model:
            old_click_count = old_model['meta'].get('clickCount', 0)
            if 'clickCount' not in updated_model.get('meta', {}):
                if 'meta' not in updated_model:
                    updated_model['meta'] = {}
                updated_model['meta']['clickCount'] = old_click_count
        
        # Check if shortName is being changed
        old_short_name = old_model.get('shortName')
        new_short_name = updated_model.get('shortName')
        is_short_name_changing = old_short_name != new_short_name
        
        if is_short_name_changing:
            logger.info(f"ShortName is being changed from '{old_short_name}' to '{new_short_name}'")
            
            # Check if the new shortName conflicts with existing models
            for existing_model in models_data['models']:
                if existing_model['id'] != old_model['id'] and existing_model['shortName'] == new_short_name:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Model with shortName '{new_short_name}' already exists"
                    )
            
            # Update agreements that reference the old shortName (only if requested)
            if request.updateAssociatedLinks:
                try:
                    agreements_data = read_json_file(JSON_FILES['dataAgreements'])
                    agreements_updated = False
                    
                    for agreement in agreements_data['agreements']:
                        if agreement.get('modelShortName') == old_short_name:
                            agreement['modelShortName'] = new_short_name
                            agreements_updated = True
                            logger.info(f"Updated agreement {agreement['id']} modelShortName from '{old_short_name}' to '{new_short_name}'")
                    
                    if agreements_updated:
                        write_json_file(JSON_FILES['dataAgreements'], agreements_data)
                        logger.info(f"Updated agreements file with new modelShortName references")
                    
                except Exception as e:
                    logger.error(f"Error updating agreements: {str(e)}")
                    raise HTTPException(
                        status_code=500,
                        detail=f"Failed to update agreements: {str(e)}"
                    )
            else:
                logger.info(f"Not updating agreements - keeping old references to '{old_short_name}'")
        else:
            logger.info(f"ShortName unchanged: '{old_short_name}'")
        
        # Log the update details for debugging
        logger.info(f"Model update details:")
        logger.info(f"  Old shortName: {old_short_name}")
        logger.info(f"  New shortName: {new_short_name}")
        logger.info(f"  Request shortName: {short_name}")
        logger.info(f"  Model data keys: {list(request.modelData.keys())}")
        logger.info(f"  shortName in modelData: {request.modelData.get('shortName', 'NOT_PRESENT')}")
        logger.info(f"  shortName will be: {new_short_name}")
        logger.info(f"  updateAssociatedLinks: {request.updateAssociatedLinks}")
        
        # Update the lastUpdated field with full timestamp
        updated_model['lastUpdated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Replace the model in the array
        models_data['models'][model_index] = updated_model
        
        # Save the updated data to local file
        local_file_path = JSON_FILES['models']
        write_json_file(local_file_path, models_data)
        logger.info(f"Updated local file {local_file_path}")
        
        # Update search index
        update_search_index("models", "update", updated_model, short_name)
        
        # No cache to clear - always fresh data
        logger.info("No caching - data will be fresh on next request")
        
        logger.info(f"Model {short_name} updated successfully")
        
        return {
            "message": "Model updated successfully",
            "shortName": short_name,
            "updated": True,
            "lastUpdated": updated_model['lastUpdated']
        }
        
    except Exception as e:
        logger.error(f"Error updating model {short_name}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error updating model: {str(e)}"
        )

def get_paginated_data(data: Dict, key: str, page: int, page_size: int) -> Dict:
    """Get paginated data from a dictionary."""
    items = data.get(key, [])
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    return {
        "items": items[start_idx:end_idx],
        "total": len(items),
        "page": page,
        "page_size": page_size,
        "total_pages": (len(items) + page_size - 1) // page_size
    }

def update_json_path(data: Dict, path: str, value: Any) -> Dict:
    """Update a specific path in the JSON data."""
    # Simple path implementation - could be enhanced with proper JSON path parsing
    parts = path.split('.')
    current = data
    for part in parts[:-1]:
        if '[' in part:
            key, idx = part.split('[')
            idx = int(idx.rstrip(']'))
            current = current[key][idx]
        else:
            current = current[part]
    
    last_part = parts[-1]
    if '[' in last_part:
        key, idx = last_part.split('[')
        idx = int(idx.rstrip(']'))
        current[key][idx] = value
    else:
        current[last_part] = value
    
    return data

def read_json_file(file_path: str) -> Dict:
    try:
        # Handle both relative and absolute paths
        if file_path.startswith('_data/'):
            data_path = file_path
        else:
            data_path = os.path.join('_data', file_path)
        
        logger.info(f"Reading JSON file from: {data_path}")
        with open(data_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error(f"File not found: {data_path}")
        raise HTTPException(status_code=404, detail=f"File not found: {file_path}")
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON file: {data_path}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Invalid JSON in file {file_path}: {str(e)}")
    except Exception as e:
        logger.error(f"Error reading file {data_path}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error reading file {file_path}: {str(e)}")

def write_json_file(file_path: str, data: Dict):
    try:
        # Handle both relative and absolute paths
        if file_path.startswith('_data/'):
            data_path = file_path
        else:
            data_path = os.path.join('_data', file_path)
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(data_path), exist_ok=True)
        
        logger.info(f"Writing JSON file to: {data_path}")
        
        # Write to a temporary file first, then rename (atomic write)
        temp_path = f"{data_path}.tmp"
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        # Atomic rename
        if os.path.exists(data_path):
            os.replace(temp_path, data_path)
        else:
            os.rename(temp_path, data_path)
        
        logger.info(f"Successfully wrote to: {data_path}")
    except json.JSONEncodeError as e:
        logger.error(f"JSON encoding error writing file {data_path}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error encoding JSON for file {file_path}: {str(e)}")
    except Exception as e:
        logger.error(f"Error writing file {data_path}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error writing file {file_path}: {str(e)}")

def update_search_index(data_type: str, action: str, item: Dict[str, Any] = None, item_id: str = None):
    """Update search index after data changes"""
    try:
        if action == "add" and item:
            search_service.add_document(data_type, item_id or str(item.get('id', '')), item)
            logger.info(f"Added {data_type}:{item_id} to search index")
        elif action == "update" and item:
            search_service.update_document(data_type, item_id or str(item.get('id', '')), item)
            logger.info(f"Updated {data_type}:{item_id} in search index")
        elif action == "delete" and item_id:
            search_service.remove_document(data_type, item_id)
            logger.info(f"Removed {data_type}:{item_id} from search index")
        elif action == "rebuild":
            search_service.rebuild_index()
            logger.info(f"Rebuilt search index")
    except Exception as e:
        logger.error(f"Error updating search index: {str(e)}")
        # Don't raise exception here as it shouldn't break the main operation

# Agreement Management Endpoints
@app.post("/api/agreements")
async def create_agreement(request: Dict[str, Any], current_user: dict = Depends(require_editor_or_admin)):
    """
    Create a new agreement.
    
    Args:
        request (dict): The new agreement data
        
    Returns:
        dict: Success message and created agreement info
        
    Raises:
        HTTPException: If creation fails
    """
    try:
        logger.info(f"Create request for new agreement")
        agreements_data = read_json_file(JSON_FILES['dataAgreements'])
        
        # Generate automatic ID
        new_id = generate_next_agreement_id(agreements_data)
        
        # Add lastUpdated timestamp and assign the generated ID
        new_agreement = request.copy()
        new_agreement['id'] = new_id
        new_agreement['lastUpdated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        agreements_data['agreements'].append(new_agreement)
        local_file_path = JSON_FILES['dataAgreements']
        write_json_file(local_file_path, agreements_data)
        
        # Update search index
        update_search_index("dataAgreements", "add", new_agreement, new_id)
        
        logger.info(f"Created new agreement in local file {local_file_path}")
        logger.info(f"Agreement {new_id} created successfully")
        
        return {
            "message": "Agreement created successfully",
            "id": new_id,
            "created": True
        }
    except Exception as e:
        logger.error(f"Error creating agreement: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error creating agreement: {str(e)}")

@app.put("/api/agreements/{agreement_id}")
async def update_agreement(agreement_id: str, request: Dict[str, Any], current_user: dict = Depends(require_editor_or_admin)):
    """
    Update an existing agreement.
    
    Args:
        agreement_id (str): The ID of the agreement to update
        request (dict): The updated agreement data
        
    Returns:
        dict: Success message and updated agreement info
        
    Raises:
        HTTPException: If the agreement is not found or update fails
    """
    try:
        logger.info(f"Update request for agreement: {agreement_id}")
        agreements_data = read_json_file(JSON_FILES['dataAgreements'])
        
        # Find the agreement to update
        agreement_to_update = None
        for agreement in agreements_data['agreements']:
            if agreement['id'].lower() == agreement_id.lower():
                agreement_to_update = agreement
                break
        
        if not agreement_to_update:
            raise HTTPException(status_code=404, detail=f"Agreement with ID '{agreement_id}' not found")
        
        # Update the agreement
        updated_agreement = agreement_to_update.copy()
        updated_agreement.update(request)
        updated_agreement['lastUpdated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Replace the old agreement with the updated one
        agreements_data['agreements'] = [
            a for a in agreements_data['agreements'] 
            if a['id'].lower() != agreement_id.lower()
        ]
        agreements_data['agreements'].append(updated_agreement)
        
        local_file_path = JSON_FILES['dataAgreements']
        write_json_file(local_file_path, agreements_data)
        
        # Update search index
        update_search_index("dataAgreements", "update", updated_agreement, agreement_id)
        
        logger.info(f"Agreement updated in local file {local_file_path}")
        logger.info(f"Agreement {agreement_id} updated successfully")
        
        return {
            "message": "Agreement updated successfully",
            "id": agreement_id,
            "updated": True
        }
    except Exception as e:
        logger.error(f"Error updating agreement: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error updating agreement: {str(e)}")

@app.delete("/api/agreements/{agreement_id}")
async def delete_agreement(agreement_id: str, current_user: dict = Depends(require_editor_or_admin)):
    """
    Delete an agreement by its ID.
    
    Args:
        agreement_id (str): The ID of the agreement to delete
        
    Returns:
        dict: Success message and deleted agreement info
        
    Raises:
        HTTPException: If the agreement is not found or deletion fails
    """
    try:
        logger.info(f"Delete request for agreement: {agreement_id}")
        agreements_data = read_json_file(JSON_FILES['dataAgreements'])
        
        agreement_to_delete = None
        for agreement in agreements_data['agreements']:
            if agreement['id'].lower() == agreement_id.lower():
                agreement_to_delete = agreement
                break
        
        if not agreement_to_delete:
            raise HTTPException(status_code=404, detail=f"Agreement with ID '{agreement_id}' not found")
        
        agreements_data['agreements'] = [
            a for a in agreements_data['agreements'] 
            if a['id'].lower() != agreement_id.lower()
        ]
        
        local_file_path = JSON_FILES['dataAgreements']
        write_json_file(local_file_path, agreements_data)
        
        # Update search index
        update_search_index("dataAgreements", "delete", item_id=agreement_id)
        
        logger.info(f"Agreement deleted from local file {local_file_path}")
        logger.info(f"Agreement {agreement_id} deleted successfully")
        
        return {
            "message": "Agreement deleted successfully",
            "id": agreement_id,
            "deleted": True
        }
    except Exception as e:
        logger.error(f"Error deleting agreement: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error deleting agreement: {str(e)}")

def generate_next_reference_id(reference_data: Dict) -> str:
    """
    Generate the next available reference ID with format 'ref-XXX'.
    
    Args:
        reference_data (dict): The current reference data
        
    Returns:
        str: The next available ID
    """
    existing_ids = [item['id'] for item in reference_data['items']]
    max_number = 0
    
    for item_id in existing_ids:
        if item_id.startswith('ref-'):
            try:
                number = int(item_id[4:])  # Extract number after 'ref-'
                max_number = max(max_number, number)
            except ValueError:
                continue  # Skip if not a valid number
    
    next_number = max_number + 1
    return f"ref-{next_number:03d}"  # Format as ref-001, ref-002, etc.

def generate_next_agreement_id(agreements_data: Dict) -> str:
    """
    Generate the next available agreement ID with format 'agreement-XXX'.
    
    Args:
        agreements_data (dict): The current agreements data
        
    Returns:
        str: The next available ID
    """
    existing_ids = [agreement['id'] for agreement in agreements_data['agreements']]
    max_number = 0
    
    for item_id in existing_ids:
        if item_id.startswith('agreement-'):
            try:
                number = int(item_id[10:])  # Extract number after 'agreement-'
                max_number = max(max_number, number)
            except ValueError:
                continue  # Skip if not a valid number
    
    next_number = max_number + 1
    return f"agreement-{next_number:03d}"  # Format as agreement-001, agreement-002, etc.

# Reference Data Management Endpoints
@app.post("/api/reference")
async def create_reference_item(request: Dict[str, Any], current_user: dict = Depends(require_editor_or_admin)):
    """
    Create a new reference data item.
    
    Args:
        request (dict): The new reference data
        
    Returns:
        dict: Success message and created reference item info
        
    Raises:
        HTTPException: If creation fails
    """
    try:
        logger.info(f"Create request for new reference item")
        reference_data = read_json_file(JSON_FILES['reference'])
        
        # Generate automatic ID
        new_id = generate_next_reference_id(reference_data)
        
        # Add lastUpdated timestamp and assign the generated ID
        new_item = request.copy()
        new_item['id'] = new_id
        new_item['lastUpdated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        reference_data['items'].append(new_item)
        local_file_path = JSON_FILES['reference']
        write_json_file(local_file_path, reference_data)
        
        logger.info(f"Created new reference item in local file {local_file_path}")
        logger.info(f"Reference item {new_id} created successfully")
        
        return {
            "message": "Reference item created successfully",
            "id": new_id,
            "created": True
        }
    except Exception as e:
        logger.error(f"Error creating reference item: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error creating reference item: {str(e)}")

@app.put("/api/reference/{item_id}")
async def update_reference_item(item_id: str, request: Dict[str, Any], current_user: dict = Depends(require_editor_or_admin)):
    """
    Update an existing reference data item.
    
    Args:
        item_id (str): The ID of the reference item to update
        request (dict): The updated reference data
        
    Returns:
        dict: Success message and updated reference item info
        
    Raises:
        HTTPException: If the reference item is not found or update fails
    """
    try:
        logger.info(f"Update request for reference item: {item_id}")
        reference_data = read_json_file(JSON_FILES['reference'])
        
        # Find the reference item to update
        item_to_update = None
        for item in reference_data['items']:
            if item['id'].lower() == item_id.lower():
                item_to_update = item
                break
        
        if not item_to_update:
            raise HTTPException(status_code=404, detail=f"Reference item with ID '{item_id}' not found")
        
        # Update the reference item
        updated_item = item_to_update.copy()
        updated_item.update(request)
        updated_item['lastUpdated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Replace the old item with the updated one
        reference_data['items'] = [
            i for i in reference_data['items'] 
            if i['id'].lower() != item_id.lower()
        ]
        reference_data['items'].append(updated_item)
        
        local_file_path = JSON_FILES['reference']
        write_json_file(local_file_path, reference_data)
        
        logger.info(f"Reference item updated in local file {local_file_path}")
        logger.info(f"Reference item {item_id} updated successfully")
        
        return {
            "message": "Reference item updated successfully",
            "id": item_id,
            "updated": True
        }
    except Exception as e:
        logger.error(f"Error updating reference item: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error updating reference item: {str(e)}")

@app.delete("/api/reference/{item_id}")
async def delete_reference_item(item_id: str, current_user: dict = Depends(require_editor_or_admin)):
    """
    Delete a reference data item by its ID.
    
    Args:
        item_id (str): The ID of the reference item to delete
        
    Returns:
        dict: Success message and deleted reference item info
        
    Raises:
        HTTPException: If the reference item is not found or deletion fails
    """
    try:
        logger.info(f"Delete request for reference item: {item_id}")
        reference_data = read_json_file(JSON_FILES['reference'])
        
        item_to_delete = None
        for item in reference_data['items']:
            if item['id'].lower() == item_id.lower():
                item_to_delete = item
                break
        
        if not item_to_delete:
            raise HTTPException(status_code=404, detail=f"Reference item with ID '{item_id}' not found")
        
        reference_data['items'] = [
            i for i in reference_data['items'] 
            if i['id'].lower() != item_id.lower()
        ]
        
        local_file_path = JSON_FILES['reference']
        write_json_file(local_file_path, reference_data)
        
        logger.info(f"Reference item deleted from local file {local_file_path}")
        logger.info(f"Reference item {item_id} deleted successfully")
        
        return {
            "message": "Reference item deleted successfully",
            "id": item_id,
            "deleted": True
        }
    except Exception as e:
        logger.error(f"Error deleting reference item: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error deleting reference item: {str(e)}")

# Glossary Management Endpoints
@app.post("/api/glossary")
async def create_glossary_term(request: Dict[str, Any], current_user: dict = Depends(require_editor_or_admin)):
    """
    Create a new glossary term.
    
    Args:
        request (dict): The new glossary term data
        
    Returns:
        dict: Success message and created glossary term info
        
    Raises:
        HTTPException: If creation fails
    """
    try:
        logger.info(f"Create request for new glossary term")
        glossary_data = read_json_file(JSON_FILES['glossary'])
        
        # Generate automatic ID if not provided
        if not request.get('id'):
            max_number = 0
            for term in glossary_data.get('terms', []):
                if term.get('id', '').startswith('glossary-'):
                    try:
                        number = int(term['id'].split('-')[1])
                        max_number = max(max_number, number)
                    except (ValueError, IndexError):
                        continue
            new_id = f"glossary-{max_number + 1:03d}"
        else:
            new_id = request['id']
        
        # Check if ID already exists
        existing_term = next((t for t in glossary_data.get('terms', []) if t.get('id') == new_id), None)
        if existing_term:
            raise HTTPException(status_code=400, detail=f"Glossary term with ID '{new_id}' already exists")
        
        # Add lastUpdated timestamp and assign the generated ID
        new_term = request.copy()
        new_term['id'] = new_id
        if not new_term.get('lastUpdated'):
            new_term['lastUpdated'] = datetime.now().strftime('%Y-%m-%d')
        
        if 'terms' not in glossary_data:
            glossary_data['terms'] = []
        glossary_data['terms'].append(new_term)
        
        local_file_path = JSON_FILES['glossary']
        write_json_file(local_file_path, glossary_data)
        
        logger.info(f"Created new glossary term in local file {local_file_path}")
        logger.info(f"Glossary term {new_id} created successfully")
        
        return {
            "message": "Glossary term created successfully",
            "id": new_id,
            "created": True
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating glossary term: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error creating glossary term: {str(e)}")

@app.put("/api/glossary/{term_id}")
async def update_glossary_term(term_id: str, request: Dict[str, Any], current_user: dict = Depends(require_editor_or_admin)):
    """
    Update an existing glossary term.
    
    Args:
        term_id (str): The ID of the glossary term to update
        request (dict): The updated glossary term data
        
    Returns:
        dict: Success message and updated glossary term info
        
    Raises:
        HTTPException: If the glossary term is not found or update fails
    """
    try:
        logger.info(f"Update request for glossary term: {term_id}")
        glossary_data = read_json_file(JSON_FILES['glossary'])
        
        # Find the glossary term to update
        term_to_update = None
        for term in glossary_data.get('terms', []):
            if term.get('id', '').lower() == term_id.lower():
                term_to_update = term
                break
        
        if not term_to_update:
            raise HTTPException(status_code=404, detail=f"Glossary term with ID '{term_id}' not found")
        
        # Update the glossary term
        updated_term = term_to_update.copy()
        updated_term.update(request)
        updated_term['id'] = term_id  # Ensure ID doesn't change
        updated_term['lastUpdated'] = datetime.now().strftime('%Y-%m-%d')
        
        # Replace the old term with the updated one
        glossary_data['terms'] = [
            t for t in glossary_data.get('terms', []) 
            if t.get('id', '').lower() != term_id.lower()
        ]
        glossary_data['terms'].append(updated_term)
        
        local_file_path = JSON_FILES['glossary']
        write_json_file(local_file_path, glossary_data)
        
        logger.info(f"Glossary term updated in local file {local_file_path}")
        logger.info(f"Glossary term {term_id} updated successfully")
        
        return {
            "message": "Glossary term updated successfully",
            "id": term_id,
            "updated": True
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating glossary term: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error updating glossary term: {str(e)}")

@app.delete("/api/glossary/{term_id}")
async def delete_glossary_term(term_id: str, current_user: dict = Depends(require_editor_or_admin)):
    """
    Delete a glossary term by its ID.
    
    Args:
        term_id (str): The ID of the glossary term to delete
        
    Returns:
        dict: Success message and deleted glossary term info
        
    Raises:
        HTTPException: If the glossary term is not found or deletion fails
    """
    try:
        logger.info(f"Delete request for glossary term: {term_id}")
        glossary_data = read_json_file(JSON_FILES['glossary'])
        
        term_to_delete = None
        for term in glossary_data.get('terms', []):
            if term.get('id', '').lower() == term_id.lower():
                term_to_delete = term
                break
        
        if not term_to_delete:
            raise HTTPException(status_code=404, detail=f"Glossary term with ID '{term_id}' not found")
        
        glossary_data['terms'] = [
            t for t in glossary_data.get('terms', []) 
            if t.get('id', '').lower() != term_id.lower()
        ]
        
        local_file_path = JSON_FILES['glossary']
        write_json_file(local_file_path, glossary_data)
        
        logger.info(f"Glossary term deleted from local file {local_file_path}")
        logger.info(f"Glossary term {term_id} deleted successfully")
        
        return {
            "message": "Glossary term deleted successfully",
            "id": term_id,
            "deleted": True
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting glossary term: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error deleting glossary term: {str(e)}")

# Applications CRUD endpoints
@app.post("/api/applications")
async def create_application(application: Dict[str, Any], current_user: dict = Depends(require_editor_or_admin)):
    """
    Create a new application.
    
    Args:
        application (dict): The application data to create
        
    Returns:
        dict: Success message and created application info
        
    Raises:
        HTTPException: If creation fails
    """
    try:
        logger.info(f"Create request for application: {application.get('name', 'Unknown')}")
        applications_data = read_json_file(JSON_FILES['applications'])
        
        # Generate new ID
        max_id = max([app['id'] for app in applications_data['applications']]) if applications_data['applications'] else 0
        new_id = max_id + 1
        
        # Create new application with ID
        new_application = {
            "id": new_id,
            "name": application.get('name', ''),
            "description": application.get('description', ''),
            "domains": application.get('domains', []),
            "link": application.get('link', '')
        }
        
        applications_data['applications'].append(new_application)
        
        local_file_path = JSON_FILES['applications']
        write_json_file(local_file_path, applications_data)
        
        logger.info(f"Application created in local file {local_file_path}")
        logger.info(f"Application {new_id} created successfully")
        
        return {
            "message": "Application created successfully",
            "id": new_id,
            "application": new_application
        }
    except Exception as e:
        logger.error(f"Error creating application: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error creating application: {str(e)}")

@app.put("/api/applications/{application_id}")
async def update_application(application_id: int, application: Dict[str, Any], current_user: dict = Depends(require_editor_or_admin)):
    """
    Update an existing application by its ID.
    
    Args:
        application_id (int): The ID of the application to update
        application (dict): The updated application data
        
    Returns:
        dict: Success message and updated application info
        
    Raises:
        HTTPException: If the application is not found or update fails
    """
    try:
        logger.info(f"Update request for application: {application_id}")
        applications_data = read_json_file(JSON_FILES['applications'])
        
        # Find the application to update
        app_to_update = None
        for i, app in enumerate(applications_data['applications']):
            if app['id'] == application_id:
                app_to_update = i
                break
        
        if app_to_update is None:
            raise HTTPException(status_code=404, detail=f"Application with ID {application_id} not found")
        
        # Update the application
        applications_data['applications'][app_to_update] = {
            "id": application_id,
            "name": application.get('name', ''),
            "description": application.get('description', ''),
            "domains": application.get('domains', []),
            "link": application.get('link', '')
        }
        
        local_file_path = JSON_FILES['applications']
        write_json_file(local_file_path, applications_data)
        
        logger.info(f"Application updated in local file {local_file_path}")
        logger.info(f"Application {application_id} updated successfully")
        
        return {
            "message": "Application updated successfully",
            "id": application_id,
            "application": applications_data['applications'][app_to_update]
        }
    except Exception as e:
        logger.error(f"Error updating application: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error updating application: {str(e)}")

@app.delete("/api/applications/{application_id}")
async def delete_application(application_id: int, current_user: dict = Depends(require_editor_or_admin)):
    """
    Delete an application by its ID.
    
    Args:
        application_id (int): The ID of the application to delete
        
    Returns:
        dict: Success message and deleted application info
        
    Raises:
        HTTPException: If the application is not found or deletion fails
    """
    try:
        logger.info(f"Delete request for application: {application_id}")
        applications_data = read_json_file(JSON_FILES['applications'])
        
        app_to_delete = None
        for app in applications_data['applications']:
            if app['id'] == application_id:
                app_to_delete = app
                break
        
        if not app_to_delete:
            raise HTTPException(status_code=404, detail=f"Application with ID {application_id} not found")
        
        applications_data['applications'] = [
            app for app in applications_data['applications'] 
            if app['id'] != application_id
        ]
        
        local_file_path = JSON_FILES['applications']
        write_json_file(local_file_path, applications_data)
        
        logger.info(f"Application deleted from local file {local_file_path}")
        logger.info(f"Application {application_id} deleted successfully")
        
        return {
            "message": "Application deleted successfully",
            "id": application_id,
            "deleted": True
        }
    except Exception as e:
        logger.error(f"Error deleting application: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error deleting application: {str(e)}")

# Toolkit CRUD endpoints
@app.post("/api/toolkit")
async def create_toolkit_component(component: Dict[str, Any], current_user: dict = Depends(require_editor_or_admin)):
    """
    Create a new toolkit component.
    
    Args:
        component (dict): The component data to create
        
    Returns:
        dict: Success message and created component info
        
    Raises:
        HTTPException: If creation fails
    """
    try:
        logger.info(f"Create request for toolkit component: {component.get('name', 'Unknown')}")
        logger.debug(f"Component data received: {json.dumps(component, default=str)[:500]}")  # Log first 500 chars
        
        toolkit_data = read_json_file(JSON_FILES['toolkit'])
        
        # Ensure toolkit structure exists
        if 'toolkit' not in toolkit_data:
            toolkit_data['toolkit'] = {}
        
        # Determine component type and generate ID
        component_type = component.get('type', 'functions')
        if component_type not in ['functions', 'containers', 'terraform']:
            raise HTTPException(status_code=400, detail="Invalid component type")
        
        # Initialize component type array if it doesn't exist
        if component_type not in toolkit_data['toolkit']:
            toolkit_data['toolkit'][component_type] = []
        
        # For functions, generate a UUID as the ID
        if component_type == 'functions':
            function_name = component.get('name', '')
            if not function_name:
                raise HTTPException(status_code=400, detail="Function name is required")
            
            # Check if function name already exists (for display purposes, not ID)
            existing_names = [item.get('name', '') for item in toolkit_data['toolkit'][component_type] if item.get('name')]
            if function_name in existing_names:
                raise HTTPException(status_code=400, detail=f"Function with name '{function_name}' already exists")
            
            # Generate UUID for function ID
            new_id = str(uuid.uuid4())
        else:
            # Generate new ID based on type for other component types
            existing_ids = [item.get('id', '') for item in toolkit_data['toolkit'][component_type] if item.get('id')]
            if component_type == 'containers':
                prefix = 'cont_'
            else:
                prefix = 'tf_'
            
            max_num = 0
            for item_id in existing_ids:
                if item_id and item_id.startswith(prefix):
                    try:
                        num = int(item_id.split('_')[1])
                        max_num = max(max_num, num)
                    except (ValueError, IndexError):
                        pass
            
            new_id = f"{prefix}{max_num + 1:03d}"
        
        # Create new component with ID
        new_component = {
            "id": new_id,
            "name": component.get('name', ''),
            "displayName": component.get('displayName', component.get('name', '')),
            "description": component.get('description', ''),
            "type": component_type,
            "category": component.get('category', ''),
            "tags": component.get('tags', []),
            "author": component.get('author', ''),
            "version": component.get('version', '1.0.0'),
            "lastUpdated": datetime.now().isoformat(),
            "usage": component.get('usage', ''),
            "dependencies": component.get('dependencies', []),
            "examples": component.get('examples', []),
            "git": component.get('git', ''),
            "rating": component.get('rating', 5.0),
            "downloads": 0,
            "clickCount": 0
        }
        
        # Add type-specific fields
        if component_type == 'functions':
            new_component['language'] = component.get('language', 'python')
            # Safely handle code field - ensure it's a string
            code_value = component.get('code', '')
            new_component['code'] = str(code_value) if code_value is not None else ''
            # Safely handle parameters - ensure it's a list
            params = component.get('parameters', [])
            new_component['parameters'] = params if isinstance(params, list) else []
        elif component_type == 'containers':
            new_component['dockerfile'] = component.get('dockerfile', '')
            new_component['dockerCompose'] = component.get('dockerCompose', '')
        elif component_type == 'terraform':
            new_component['provider'] = component.get('provider', '')
            new_component['mainTf'] = component.get('mainTf', '')
            new_component['variablesTf'] = component.get('variablesTf', '')
            new_component['outputsTf'] = component.get('outputsTf', '')
        
        toolkit_data['toolkit'][component_type].append(new_component)
        
        logger.debug(f"About to write component with ID: {new_id}, name: {new_component.get('name')}")
        
        local_file_path = JSON_FILES['toolkit']
        write_json_file(local_file_path, toolkit_data)
        
        logger.info(f"Toolkit component created in local file {local_file_path}")
        logger.info(f"Component {new_id} created successfully")
        
        return {
            "message": "Toolkit component created successfully",
            "id": new_id,
            "component": new_component
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating toolkit component: {str(e)}", exc_info=True)
        error_detail = str(e) if str(e) else f"Unknown error: {type(e).__name__}"
        raise HTTPException(status_code=500, detail=f"Error creating toolkit component: {error_detail}")

@app.put("/api/toolkit/packages/{package_id}")
async def update_toolkit_package(
    package_id: str, 
    package_data: Dict[str, Any], 
    current_user: dict = Depends(require_editor_or_admin)
):
    """
    Update or create a toolkit package.
    
    Args:
        package_id: UUID of the package (or 'new' for creating a new package)
        package_data: Package metadata including description, version, maintainers, etc.
        
    Returns:
        dict: Success message and package info
    """
    try:
        logger.info(f"Update request for toolkit package: {package_id}")
        logger.info(f"Package data type: {type(package_data)}")
        logger.info(f"Package data received: {package_data}")
        
        # Validate package_data
        if package_data is None:
            raise HTTPException(status_code=400, detail="Package data is required")
        
        if not isinstance(package_data, dict):
            raise HTTPException(status_code=400, detail=f"Package data must be a dictionary, got {type(package_data)}")
        
        # Read toolkit data
        try:
            toolkit_data = read_json_file(JSON_FILES['toolkit'])
        except Exception as e:
            logger.error(f"Error reading toolkit file: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error reading toolkit data: {str(e)}")
        
        # Ensure toolkit structure exists
        if 'toolkit' not in toolkit_data:
            toolkit_data['toolkit'] = {}
        
        # Initialize packages array if it doesn't exist
        if 'packages' not in toolkit_data['toolkit']:
            toolkit_data['toolkit']['packages'] = []
        
        # Find existing package or create new one
        packages = toolkit_data['toolkit'].get('packages', [])
        package_index = None
        is_new_package = (package_id == 'new' or package_id not in [pkg.get('id') for pkg in packages])
        
        if not is_new_package:
            for i, pkg in enumerate(packages):
                if pkg.get('id') == package_id:
                    package_index = i
                    break
        
        # Safely extract and validate data
        try:
            # Ensure functionIds is a list
            function_ids = package_data.get('functionIds', [])
            if function_ids is None:
                function_ids = []
            elif not isinstance(function_ids, list):
                logger.warning(f"functionIds is not a list, converting: {function_ids}")
                function_ids = list(function_ids) if hasattr(function_ids, '__iter__') else []
            
            # Ensure maintainers is a list
            maintainers = package_data.get('maintainers', [])
            if maintainers is None:
                maintainers = []
            elif not isinstance(maintainers, list):
                logger.warning(f"maintainers is not a list, converting: {maintainers}")
                maintainers = list(maintainers) if hasattr(maintainers, '__iter__') else []
            
            # Safely get string fields
            description = str(package_data.get('description', '')) if package_data.get('description') is not None else ''
            version = str(package_data.get('version', '')) if package_data.get('version') is not None else ''
            latest_release_date = str(package_data.get('latestReleaseDate', '')) if package_data.get('latestReleaseDate') is not None else ''
            documentation = str(package_data.get('documentation', '')) if package_data.get('documentation') is not None else ''
            github_repo = str(package_data.get('githubRepo', '')) if package_data.get('githubRepo') is not None else ''
            package_name = package_data.get('name', '')
            if not package_name:
                raise HTTPException(status_code=400, detail="Package name is required")
            
            pip_install = str(package_data.get('pipInstall', f'pip install {package_name}')) if package_data.get('pipInstall') is not None else f'pip install {package_name}'
            
            # Generate UUID for new packages
            if is_new_package:
                package_uuid = str(uuid.uuid4())
            else:
                package_uuid = package_id
            
            package_metadata = {
                "id": package_uuid,
                "name": package_name,
                "description": description,
                "version": version,
                "latestReleaseDate": latest_release_date,
                "maintainers": maintainers,
                "documentation": documentation,
                "githubRepo": github_repo,
                "pipInstall": pip_install,
                "functionIds": function_ids,
            }
        except Exception as e:
            logger.error(f"Error processing package data: {str(e)}", exc_info=True)
            raise HTTPException(status_code=400, detail=f"Error processing package data: {str(e)}")
        
        # Update or create package
        try:
            if package_index is not None:
                toolkit_data['toolkit']['packages'][package_index] = package_metadata
                logger.info(f"Updated existing package: {package_name} (ID: {package_uuid})")
            else:
                toolkit_data['toolkit']['packages'].append(package_metadata)
                logger.info(f"Created new package: {package_name} (ID: {package_uuid})")
        except Exception as e:
            logger.error(f"Error updating package in memory: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Error updating package: {str(e)}")
        
        # Save the updated toolkit data
        try:
            local_file_path = JSON_FILES['toolkit']
            write_json_file(local_file_path, toolkit_data)
            logger.info(f"Package {package_name} (ID: {package_uuid}) saved successfully")
        except Exception as e:
            logger.error(f"Error writing toolkit file: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Error saving toolkit data: {str(e)}")
        
        return {
            "message": "Package saved successfully",
            "package": package_metadata
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving toolkit package: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error saving toolkit package: {str(e)}")

@app.put("/api/toolkit/{component_type}/{component_id}")
async def update_toolkit_component(component_type: str, component_id: str, component: Dict[str, Any], current_user: dict = Depends(require_editor_or_admin)):
    """
    Update an existing toolkit component by its ID.
    
    Args:
        component_type (str): The type of component (functions, containers, terraform)
        component_id (str): The ID of the component to update
        component (dict): The updated component data
        
    Returns:
        dict: Success message and updated component info
        
    Raises:
        HTTPException: If the component is not found or update fails
    """
    try:
        logger.info(f"Update request for toolkit component: {component_id}")
        
        if component_type not in ['functions', 'containers', 'terraform']:
            raise HTTPException(status_code=400, detail="Invalid component type")
        
        toolkit_data = read_json_file(JSON_FILES['toolkit'])
        
        # Find the component to update
        comp_to_update = None
        for i, comp in enumerate(toolkit_data['toolkit'][component_type]):
            if comp['id'] == component_id:
                comp_to_update = i
                break
        
        if comp_to_update is None:
            raise HTTPException(status_code=404, detail=f"Component with ID {component_id} not found")
        
        # Update the component
        existing_component = toolkit_data['toolkit'][component_type][comp_to_update]
        updated_component = {
            **existing_component,
            "name": component.get('name', ''),
            "displayName": component.get('displayName', component.get('name', '')),
            "description": component.get('description', ''),
            "category": component.get('category', ''),
            "tags": component.get('tags', []),
            "author": component.get('author', ''),
            "version": component.get('version', '1.0.0'),
            "lastUpdated": datetime.now().isoformat(),
            "usage": component.get('usage', ''),
            "dependencies": component.get('dependencies', []),
            "examples": component.get('examples', []),
            "git": component.get('git', ''),
            "rating": component.get('rating', 5.0)
        }
        # Preserve clickCount if it exists
        if 'clickCount' in existing_component:
            updated_component['clickCount'] = existing_component['clickCount']
        
        # Update type-specific fields
        if component_type == 'functions':
            updated_component['language'] = component.get('language', '')
            updated_component['code'] = component.get('code', '')
            updated_component['parameters'] = component.get('parameters', [])
        elif component_type == 'containers':
            updated_component['dockerfile'] = component.get('dockerfile', '')
            updated_component['dockerCompose'] = component.get('dockerCompose', '')
        elif component_type == 'terraform':
            updated_component['provider'] = component.get('provider', '')
            updated_component['mainTf'] = component.get('mainTf', '')
            updated_component['variablesTf'] = component.get('variablesTf', '')
            updated_component['outputsTf'] = component.get('outputsTf', '')
        
        toolkit_data['toolkit'][component_type][comp_to_update] = updated_component
        
        local_file_path = JSON_FILES['toolkit']
        write_json_file(local_file_path, toolkit_data)
        
        logger.info(f"Toolkit component updated in local file {local_file_path}")
        logger.info(f"Component {component_id} updated successfully")
        
        return {
            "message": "Toolkit component updated successfully",
            "id": component_id,
            "component": updated_component
        }
    except Exception as e:
        logger.error(f"Error updating toolkit component: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error updating toolkit component: {str(e)}")

@app.post("/api/toolkit/import-from-library")
async def import_functions_from_library(
    package_name: str = Query(..., description="Python package name to install and introspect"),
    module_path: Optional[str] = Query(None, description="Optional specific module path within the package"),
    pypi_url: Optional[str] = Query(None, description="Optional custom PyPI URL or index URL (e.g., 'https://pypi.org/simple' or 'https://custom-pypi.example.com/simple')"),
    bulk_mode: bool = Query(False, description="If true, import functions from all submodules"),
    current_user: dict = Depends(require_editor_or_admin)
):
    """
    Install a Python library and extract function documentation from docstrings.
    
    Args:
        package_name: Name of the Python package (e.g., 'pandas', 'numpy')
        module_path: Optional specific module to import (e.g., 'pandas.io')
        pypi_url: Optional custom PyPI URL or index URL for private repositories
        bulk_mode: If true, import functions from all submodules recursively
        
    Returns:
        dict: List of discovered functions with extracted metadata
    """
    try:
        logger.info(f"Import request for library: {package_name}, module: {module_path}, pypi_url: {pypi_url}, bulk_mode: {bulk_mode}")
        
        if bulk_mode:
            result = python_introspection_service.get_all_functions_from_package(package_name, module_path, pypi_url, include_submodules=True)
        else:
            result = python_introspection_service.get_functions_from_package(package_name, module_path, pypi_url)
        
        if not result["success"]:
            raise HTTPException(
                status_code=400,
                detail=result["message"]
            )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error importing from library: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error importing from library: {str(e)}"
        )

@app.delete("/api/toolkit/packages/{package_id}")
async def delete_toolkit_package(
    package_id: str,
    current_user: dict = Depends(require_editor_or_admin)
):
    """
    Delete a toolkit package.
    
    Args:
        package_id: UUID of the package to delete
        
    Returns:
        dict: Success message and deleted package info
        
    Raises:
        HTTPException: If the package is not found or deletion fails
    """
    try:
        logger.info(f"Delete request for toolkit package: {package_id}")
        
        # Read toolkit data
        toolkit_data = read_json_file(JSON_FILES['toolkit'])
        
        # Ensure toolkit structure exists
        if 'toolkit' not in toolkit_data:
            toolkit_data['toolkit'] = {}
        
        # Initialize packages array if it doesn't exist
        if 'packages' not in toolkit_data['toolkit']:
            toolkit_data['toolkit']['packages'] = []
        
        # Find the package to delete by ID (with fallback to name for backward compatibility)
        packages = toolkit_data['toolkit'].get('packages', [])
        package_to_delete = None
        actual_id = None
        actual_name = None
        
        for pkg in packages:
            # Check by ID first
            if pkg.get('id') == package_id:
                package_to_delete = pkg
                actual_id = pkg.get('id')
                actual_name = pkg.get('name')
                break
            # Fallback: check by name for backward compatibility
            if pkg.get('name') == package_id:
                package_to_delete = pkg
                actual_id = pkg.get('id')
                actual_name = pkg.get('name')
                break
        
        if not package_to_delete:
            # Check if package_id looks like a UUID (has dashes and is 36 chars) or is a name
            # If it's a name and no package found, it might not exist in packages array
            # Log more details for debugging
            logger.warning(f"Package not found. Searched for ID/name: '{package_id}'. Available packages: {[p.get('name') for p in packages]}")
            raise HTTPException(status_code=404, detail=f"Package with ID/name '{package_id}' not found in packages array")
        
        # Remove the package - use the actual ID or name from the found package
        toolkit_data['toolkit']['packages'] = [
            pkg for pkg in packages 
            if not (actual_id and pkg.get('id') == actual_id) and not (actual_name and pkg.get('name') == actual_name and not pkg.get('id'))
        ]
        
        # Save the updated toolkit data
        local_file_path = JSON_FILES['toolkit']
        write_json_file(local_file_path, toolkit_data)
        
        logger.info(f"Package {package_to_delete.get('name', 'Unknown')} (ID: {package_id}) deleted successfully")
        
        return {
            "message": "Package deleted successfully",
            "id": package_id,
            "name": package_to_delete.get('name', 'Unknown'),
            "deleted": True
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting toolkit package: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error deleting toolkit package: {str(e)}")

@app.delete("/api/toolkit/{component_type}/{component_id}")
async def delete_toolkit_component(component_type: str, component_id: str, current_user: dict = Depends(require_editor_or_admin)):
    """
    Delete a toolkit component by its ID.
    
    Args:
        component_type (str): The type of component (functions, containers, terraform)
        component_id (str): The ID of the component to delete
        
    Returns:
        dict: Success message and deleted component info
        
    Raises:
        HTTPException: If the component is not found or deletion fails
    """
    try:
        logger.info(f"Delete request for toolkit component: {component_id}")
        
        if component_type not in ['functions', 'containers', 'terraform']:
            raise HTTPException(status_code=400, detail="Invalid component type")
        
        toolkit_data = read_json_file(JSON_FILES['toolkit'])
        
        comp_to_delete = None
        for comp in toolkit_data['toolkit'][component_type]:
            if comp['id'] == component_id:
                comp_to_delete = comp
                break
        
        if not comp_to_delete:
            raise HTTPException(status_code=404, detail=f"Component with ID {component_id} not found")
        
        toolkit_data['toolkit'][component_type] = [
            comp for comp in toolkit_data['toolkit'][component_type] 
            if comp['id'] != component_id
        ]
        
        local_file_path = JSON_FILES['toolkit']
        write_json_file(local_file_path, toolkit_data)
        
        logger.info(f"Toolkit component deleted from local file {local_file_path}")
        logger.info(f"Component {component_id} deleted successfully")
        
        return {
            "message": "Toolkit component deleted successfully",
            "id": component_id,
            "deleted": True
        }
    except Exception as e:
        logger.error(f"Error deleting toolkit component: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error deleting toolkit component: {str(e)}")

@app.get("/api/policies")
def get_policies():
    """Get all data policies."""
    try:
        policies_data = read_json_file(JSON_FILES['policies'])
        return policies_data
    except Exception as e:
        logger.error(f"Error reading policies: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error reading policies: {str(e)}")

@app.post("/api/policies")
def create_policy(policy: Dict[str, Any], current_user: dict = Depends(require_editor_or_admin)):
    """Create a new data policy."""
    try:
        logger.info(f"Create request for new policy: {policy.get('name', 'Unknown')}")
        
        policies_data = read_json_file(JSON_FILES['policies'])
        
        # Generate new ID if not provided
        if not policy.get('id'):
            policy['id'] = f"{policy.get('type', 'policy')}_{policy.get('name', 'unknown').lower().replace(' ', '_')}_{int(time.time())}"
        
        # Add timestamp
        policy['lastUpdated'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Add to policies list
        policies_data['policies'].append(policy)
        
        # Write to file
        local_file_path = JSON_FILES['policies']
        write_json_file(local_file_path, policies_data)
        
        logger.info(f"Policy created successfully with ID: {policy['id']}")
        
        return {
            "message": "Policy created successfully",
            "id": policy['id'],
            "policy": policy
        }
    except Exception as e:
        logger.error(f"Error creating policy: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error creating policy: {str(e)}")

@app.put("/api/policies/{policy_id}")
def update_policy(policy_id: str, policy: Dict[str, Any], current_user: dict = Depends(require_editor_or_admin)):
    """Update an existing data policy."""
    try:
        logger.info(f"Update request for policy: {policy_id}")
        
        policies_data = read_json_file(JSON_FILES['policies'])
        
        # Find existing policy
        existing_policy = None
        for i, p in enumerate(policies_data['policies']):
            if p['id'] == policy_id:
                existing_policy = i
                break
        
        if existing_policy is None:
            raise HTTPException(status_code=404, detail=f"Policy with ID {policy_id} not found")
        
        # Update timestamp
        policy['lastUpdated'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Update the policy
        policies_data['policies'][existing_policy] = policy
        
        # Write to file
        local_file_path = JSON_FILES['policies']
        write_json_file(local_file_path, policies_data)
        
        logger.info(f"Policy {policy_id} updated successfully")
        
        return {
            "message": "Policy updated successfully",
            "id": policy_id,
            "policy": policy
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating policy: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error updating policy: {str(e)}")

@app.delete("/api/policies/{policy_id}")
def delete_policy(policy_id: str, current_user: dict = Depends(require_editor_or_admin)):
    """Delete a data policy."""
    try:
        logger.info(f"Delete request for policy: {policy_id}")
        
        policies_data = read_json_file(JSON_FILES['policies'])
        
        # Find and remove policy
        original_length = len(policies_data['policies'])
        policies_data['policies'] = [
            p for p in policies_data['policies'] 
            if p['id'] != policy_id
        ]
        
        if len(policies_data['policies']) == original_length:
            raise HTTPException(status_code=404, detail=f"Policy with ID {policy_id} not found")
        
        # Write to file
        local_file_path = JSON_FILES['policies']
        write_json_file(local_file_path, policies_data)
        
        logger.info(f"Policy {policy_id} deleted successfully")
        
        return {
            "message": "Policy deleted successfully",
            "id": policy_id,
            "deleted": True
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting policy: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error deleting policy: {str(e)}")

# Debug endpoints
@app.get("/api/debug/cache")
def get_cache_status():
    """Get the current status of the cache (disabled)."""
    return {
        "status": "Caching disabled",
        "message": "All data is read fresh from files on each request",
        "test_mode": TEST_MODE
    }

@app.get("/api/debug/performance")
def get_performance_metrics():
    """Get current performance metrics."""
    return get_performance_stats()

@app.get("/api/debug/model-relationships")
def get_model_relationships():
    """Debug endpoint to check model and agreement relationships."""
    try:
        models_data = read_json_file(JSON_FILES['models'])
        agreements_data = read_json_file(JSON_FILES['dataAgreements'])
        
        relationships = {}
        for model in models_data['models']:
            short_name = model['shortName']
            model_agreements = [
                agreement for agreement in agreements_data['agreements']
                if agreement.get('modelShortName', '').lower() == short_name.lower()
            ]
            
            relationships[short_name] = {
                "model": {
                    "id": model['id'],
                    "shortName": model['shortName'],
                    "name": model['name']
                },
                "agreements_count": len(model_agreements),
                "agreements": [a['id'] for a in model_agreements]
            }
        
        return {
            "total_models": len(models_data['models']),
            "total_agreements": len(agreements_data['agreements']),
            "relationships": relationships
        }
    except Exception as e:
        logger.error(f"Error in model relationships debug: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Statistics endpoints
@app.post("/api/statistics/page-view")
async def track_page_view(page: str = Query(..., description="Page path/name to track")):
    """
    Track a page view.
    
    Args:
        page (str): The page path/name (e.g., 'models', 'agreements', 'home')
        
    Returns:
        dict: Success message
    """
    try:
        # Get current date in YYYY-MM-DD format
        today = datetime.now().strftime('%Y-%m-%d')
        
        # Read or initialize statistics file
        try:
            stats_data = read_json_file(JSON_FILES['statistics'])
        except HTTPException:
            # File doesn't exist, create new structure
            stats_data = {
                "pageViews": {},
                "siteVisits": {
                    "daily": {},
                    "total": 0
                },
                "lastUpdated": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        
        # Initialize page if it doesn't exist
        if page not in stats_data['pageViews']:
            stats_data['pageViews'][page] = {
                "daily": {},
                "total": 0
            }
        
        # Increment daily count
        if today not in stats_data['pageViews'][page]['daily']:
            stats_data['pageViews'][page]['daily'][today] = 0
        
        stats_data['pageViews'][page]['daily'][today] += 1
        stats_data['pageViews'][page]['total'] += 1
        # Don't increment totalViews here - it's tracked separately as site visits
        stats_data['lastUpdated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Save updated statistics
        write_json_file(JSON_FILES['statistics'], stats_data)
        
        logger.info(f"Tracked page view for {page} on {today}")
        
        return {
            "message": "Page view tracked successfully",
            "page": page,
            "date": today,
            "dailyCount": stats_data['pageViews'][page]['daily'][today],
            "totalCount": stats_data['pageViews'][page]['total']
        }
        
    except Exception as e:
        logger.error(f"Error tracking page view: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error tracking page view: {str(e)}")

@app.post("/api/statistics/site-visit")
async def track_site_visit():
    """
    Track a site visit (unique session).
    This should only be called once per session.
    
    Returns:
        dict: Success message and updated site visit count
    """
    try:
        # Get current date in YYYY-MM-DD format
        today = datetime.now().strftime('%Y-%m-%d')
        
        # Read or initialize statistics file
        try:
            stats_data = read_json_file(JSON_FILES['statistics'])
        except HTTPException:
            # File doesn't exist, create new structure
            stats_data = {
                "pageViews": {},
                "siteVisits": {
                    "daily": {},
                    "total": 0
                },
                "lastUpdated": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        
        # Initialize siteVisits if it doesn't exist (for backward compatibility)
        if 'siteVisits' not in stats_data:
            stats_data['siteVisits'] = {
                "daily": {},
                "total": 0
            }
        
        # Increment daily site visit count
        if today not in stats_data['siteVisits']['daily']:
            stats_data['siteVisits']['daily'][today] = 0
        
        stats_data['siteVisits']['daily'][today] += 1
        stats_data['siteVisits']['total'] += 1
        stats_data['lastUpdated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Save updated statistics
        write_json_file(JSON_FILES['statistics'], stats_data)
        
        logger.info(f"Tracked site visit on {today}")
        
        return {
            "message": "Site visit tracked successfully",
            "date": today,
            "dailyCount": stats_data['siteVisits']['daily'][today],
            "totalCount": stats_data['siteVisits']['total']
        }
        
    except Exception as e:
        logger.error(f"Error tracking site visit: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error tracking site visit: {str(e)}")

@app.get("/api/statistics")
def get_statistics(current_user: dict = Depends(require_admin)):
    """
    Get page view statistics (admin only).
    
    Returns:
        dict: Statistics data with daily views per page and site visits
    """
    try:
        # Read statistics file
        try:
            stats_data = read_json_file(JSON_FILES['statistics'])
        except HTTPException:
            # File doesn't exist, return empty structure
            return {
                "pageViews": {},
                "siteVisits": {
                    "daily": {},
                    "total": 0
                },
                "lastUpdated": None
            }
        
        # Ensure siteVisits exists (for backward compatibility)
        if 'siteVisits' not in stats_data:
            stats_data['siteVisits'] = {
                "daily": {},
                "total": 0
            }
        
        return stats_data
        
    except Exception as e:
        logger.error(f"Error getting statistics: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting statistics: {str(e)}")

# Rules Management Endpoints
@app.get("/api/rules/{model_short_name}")
async def get_rules_for_model(model_short_name: str):
    """
    Get all rules for a specific model.
    
    Args:
        model_short_name (str): The short name of the model
        
    Returns:
        dict: List of rules for the model
    """
    try:
        try:
            rules_data = read_json_file(JSON_FILES['rules'])
        except HTTPException as e:
            # File doesn't exist or can't be read, return empty structure
            logger.warning(f"Rules file not found or can't be read: {str(e)}")
            return {"rules": []}
        except Exception as e:
            # Other errors reading file
            logger.warning(f"Error reading rules file: {str(e)}, returning empty rules")
            return {"rules": []}
        
        # Ensure rules_data has the expected structure
        if not isinstance(rules_data, dict):
            logger.warning("Rules file has invalid structure, returning empty rules")
            return {"rules": []}
        
        if 'rules' not in rules_data:
            logger.warning("Rules file missing 'rules' key, returning empty rules")
            return {"rules": []}
        
        # Filter rules by model
        model_rules = [
            rule for rule in rules_data.get('rules', [])
            if rule.get('modelShortName', '').lower() == model_short_name.lower()
        ]
        
        logger.info(f"Found {len(model_rules)} rules for model {model_short_name}")
        return {
            "rules": model_rules,
            "count": len(model_rules)
        }
    except Exception as e:
        logger.error(f"Error getting rules: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting rules: {str(e)}")

@app.get("/api/country-rules/{country}")
async def get_rules_for_country(country: str):
    """
    Get all rules for a specific country.
    
    Args:
        country (str): The name of the country
        
    Returns:
        dict: List of rules for the country
    """
    try:
        try:
            rules_data = read_json_file(JSON_FILES['countryRules'])
        except HTTPException as e:
            logger.warning(f"Country rules file not found or can't be read: {str(e)}")
            return {"rules": []}
        except Exception as e:
            logger.warning(f"Error reading country rules file: {str(e)}, returning empty rules")
            return {"rules": []}
        
        # Ensure rules_data has the expected structure
        if not isinstance(rules_data, dict):
            logger.warning("Country rules file has invalid structure, returning empty rules")
            return {"rules": []}
        
        if 'rules' not in rules_data:
            logger.warning("Country rules file missing 'rules' key, returning empty rules")
            return {"rules": []}
        
        # Filter rules by country
        country_rules = [
            rule for rule in rules_data.get('rules', [])
            if rule.get('country', '').lower() == country.lower()
        ]
        
        logger.info(f"Found {len(country_rules)} rules for country {country}")
        return {
            "rules": country_rules,
            "count": len(country_rules)
        }
    except Exception as e:
        logger.error(f"Error getting country rules: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting country rules: {str(e)}")

@app.get("/api/country-rules/{country}/count")
async def get_country_rule_count(country: str):
    """
    Get the count of rules for a specific country.
    
    Args:
        country (str): The name of the country
        
    Returns:
        dict: Count of rules for the country
    """
    try:
        try:
            rules_data = read_json_file(JSON_FILES['countryRules'])
        except HTTPException as e:
            logger.warning(f"Country rules file not found or can't be read: {str(e)}")
            return {"count": 0}
        except Exception as e:
            logger.warning(f"Error reading country rules file: {str(e)}, returning count 0")
            return {"count": 0}
        
        if not isinstance(rules_data, dict):
            logger.warning("Country rules file has invalid structure, returning count 0")
            return {"count": 0}
        
        if 'rules' not in rules_data:
            logger.warning("Country rules file missing 'rules' key, returning count 0")
            return {"count": 0}
        
        # Filter rules by country and count
        country_rules = [
            rule for rule in rules_data.get('rules', [])
            if rule.get('country', '').lower() == country.lower()
        ]
        
        return {"count": len(country_rules)}
    except Exception as e:
        logger.error(f"Error getting country rule count: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting country rule count: {str(e)}")

@app.get("/api/country-rules/{country}/coverage")
async def get_country_rule_coverage(country: str):
    """
    Get rule coverage statistics for a country.
    
    Args:
        country (str): The name of the country
        
    Returns:
        dict: Coverage statistics showing rules per object/column
    """
    try:
        # Get country rules
        try:
            rules_data = read_json_file(JSON_FILES['countryRules'])
        except HTTPException:
            rules_data = {"rules": []}
        except Exception as e:
            logger.warning(f"Error reading country rules file: {str(e)}")
            rules_data = {"rules": []}
        
        if not isinstance(rules_data, dict):
            rules_data = {"rules": []}
        
        country_rules = [
            rule for rule in rules_data.get('rules', [])
            if rule.get('country', '').lower() == country.lower()
        ]
        
        # Calculate coverage
        tagged_objects = set()
        tagged_columns = set()
        tagged_functions = set()
        
        for rule in country_rules:
            if rule.get('taggedObjects') and isinstance(rule.get('taggedObjects'), list):
                tagged_objects.update(rule['taggedObjects'])
            if rule.get('taggedColumns') and isinstance(rule.get('taggedColumns'), list):
                tagged_columns.update(rule['taggedColumns'])
            if rule.get('taggedFunctions') and isinstance(rule.get('taggedFunctions'), list):
                tagged_functions.update(rule['taggedFunctions'])
        
        coverage = {
            "country": country,
            "totalRules": len(country_rules),
            "taggedObjects": list(tagged_objects),
            "taggedColumns": list(tagged_columns),
            "taggedFunctions": list(tagged_functions),
            "objectCoverage": len(tagged_objects),
            "columnCoverage": len(tagged_columns),
            "functionCoverage": len(tagged_functions),
            "rules": country_rules
        }
        
        return coverage
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting country rule coverage: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting country rule coverage: {str(e)}")

@app.post("/api/rules")
async def create_rule(request: Dict[str, Any], current_user: dict = Depends(require_editor_or_admin)):
    """
    Create a new rule (model rule).
    
    Args:
        request (dict): The new rule data
        
    Returns:
        dict: Success message and created rule info
    """
    try:
        logger.info(f"Create request for new model rule")
        
        try:
            rules_data = read_json_file(JSON_FILES['rules'])
        except HTTPException:
            # File doesn't exist, create new structure
            rules_data = {"rules": []}
        
        # Generate UUID as ID
        new_id = str(uuid.uuid4())
        
        # Add lastUpdated timestamp and assign the generated ID
        # Remove form state fields that shouldn't be saved
        new_rule = {k: v for k, v in request.items() if k not in ['newObjectInput', 'newColumnInput', 'ruleTypeIdentifier']}
        new_rule['id'] = new_id
        new_rule['lastUpdated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        new_rule['createdBy'] = current_user.get('username', 'unknown')
        
        rules_data['rules'].append(new_rule)
        local_file_path = JSON_FILES['rules']
        write_json_file(local_file_path, rules_data)
        
        logger.info(f"Created new rule in local file {local_file_path}")
        logger.info(f"Rule {new_id} created successfully")
        
        return {
            "message": "Rule created successfully",
            "id": new_id,
            "created": True
        }
    except Exception as e:
        logger.error(f"Error creating rule: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error creating rule: {str(e)}")

@app.post("/api/country-rules")
async def create_country_rule(request: Dict[str, Any], current_user: dict = Depends(require_editor_or_admin)):
    """
    Create a new country rule.
    
    Args:
        request (dict): The new country rule data
        
    Returns:
        dict: Success message and created rule info
    """
    try:
        logger.info(f"Create request for new country rule")
        
        try:
            rules_data = read_json_file(JSON_FILES['countryRules'])
        except HTTPException:
            # File doesn't exist, create new structure
            rules_data = {"rules": []}
        
        # Generate UUID as ID
        new_id = str(uuid.uuid4())
        
        # Add lastUpdated timestamp and assign the generated ID
        # Remove form state fields that shouldn't be saved
        new_rule = {k: v for k, v in request.items() if k not in ['newObjectInput', 'newColumnInput', 'ruleTypeIdentifier']}
        new_rule['id'] = new_id
        new_rule['lastUpdated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        new_rule['createdBy'] = current_user.get('username', 'unknown')
        
        rules_data['rules'].append(new_rule)
        local_file_path = JSON_FILES['countryRules']
        write_json_file(local_file_path, rules_data)
        
        logger.info(f"Created new country rule in local file {local_file_path}")
        logger.info(f"Country rule {new_id} created successfully")
        
        return {
            "message": "Country rule created successfully",
            "id": new_id,
            "created": True
        }
    except Exception as e:
        logger.error(f"Error creating country rule: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error creating country rule: {str(e)}")

@app.put("/api/rules/{rule_id}")
async def update_rule(rule_id: str, request: Dict[str, Any], current_user: dict = Depends(require_editor_or_admin)):
    """
    Update an existing model rule.
    
    Args:
        rule_id (str): The ID of the rule to update
        request (dict): The updated rule data
        
    Returns:
        dict: Success message and updated rule info
    """
    try:
        logger.info(f"Update request for model rule: {rule_id}")
        
        rules_data = read_json_file(JSON_FILES['rules'])
        
        # Find the rule to update
        rule_to_update = None
        for i, rule in enumerate(rules_data.get('rules', [])):
            if rule.get('id', '').lower() == rule_id.lower():
                rule_to_update = i
                break
        
        if rule_to_update is None:
            raise HTTPException(status_code=404, detail=f"Rule with ID '{rule_id}' not found")
        
        # Update the rule
        updated_rule = rules_data['rules'][rule_to_update].copy()
        # Remove form state fields that shouldn't be saved
        cleaned_request = {k: v for k, v in request.items() if k not in ['newObjectInput', 'newColumnInput', 'ruleTypeIdentifier']}
        updated_rule.update(cleaned_request)
        updated_rule['id'] = rule_id  # Ensure ID doesn't change
        updated_rule['lastUpdated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        updated_rule['updatedBy'] = current_user.get('username', 'unknown')
        
        rules_data['rules'][rule_to_update] = updated_rule
        
        local_file_path = JSON_FILES['rules']
        write_json_file(local_file_path, rules_data)
        
        logger.info(f"Rule updated in local file {local_file_path}")
        logger.info(f"Rule {rule_id} updated successfully")
        
        return {
            "message": "Rule updated successfully",
            "id": rule_id,
            "updated": True
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating rule: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error updating rule: {str(e)}")

@app.put("/api/country-rules/{rule_id}")
async def update_country_rule(rule_id: str, request: Dict[str, Any], current_user: dict = Depends(require_editor_or_admin)):
    """
    Update an existing country rule.
    
    Args:
        rule_id (str): The ID of the country rule to update
        request (dict): The updated rule data
        
    Returns:
        dict: Success message and updated rule info
    """
    try:
        logger.info(f"Update request for country rule: {rule_id}")
        
        rules_data = read_json_file(JSON_FILES['countryRules'])
        
        # Find the rule to update
        rule_to_update = None
        for i, rule in enumerate(rules_data.get('rules', [])):
            if rule.get('id', '').lower() == rule_id.lower():
                rule_to_update = i
                break
        
        if rule_to_update is None:
            raise HTTPException(status_code=404, detail=f"Country rule with ID '{rule_id}' not found")
        
        # Update the rule
        updated_rule = rules_data['rules'][rule_to_update].copy()
        # Remove form state fields that shouldn't be saved
        cleaned_request = {k: v for k, v in request.items() if k not in ['newObjectInput', 'newColumnInput', 'ruleTypeIdentifier']}
        updated_rule.update(cleaned_request)
        updated_rule['id'] = rule_id  # Ensure ID doesn't change
        updated_rule['lastUpdated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        updated_rule['updatedBy'] = current_user.get('username', 'unknown')
        
        rules_data['rules'][rule_to_update] = updated_rule
        
        local_file_path = JSON_FILES['countryRules']
        write_json_file(local_file_path, rules_data)
        
        logger.info(f"Country rule updated in local file {local_file_path}")
        logger.info(f"Country rule {rule_id} updated successfully")
        
        return {
            "message": "Country rule updated successfully",
            "id": rule_id,
            "updated": True
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating country rule: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error updating country rule: {str(e)}")

@app.delete("/api/rules/{rule_id}")
async def delete_rule(rule_id: str, current_user: dict = Depends(require_editor_or_admin)):
    """
    Delete a model rule by its ID.
    
    Args:
        rule_id (str): The ID of the rule to delete
        
    Returns:
        dict: Success message and deleted rule info
    """
    try:
        logger.info(f"Delete request for model rule: {rule_id}")
        
        rules_data = read_json_file(JSON_FILES['rules'])
        
        rule_to_delete = None
        for rule in rules_data.get('rules', []):
            if rule.get('id', '').lower() == rule_id.lower():
                rule_to_delete = rule
                break
        
        if not rule_to_delete:
            raise HTTPException(status_code=404, detail=f"Rule with ID '{rule_id}' not found")
        
        rules_data['rules'] = [
            r for r in rules_data.get('rules', [])
            if r.get('id', '').lower() != rule_id.lower()
        ]
        
        local_file_path = JSON_FILES['rules']
        write_json_file(local_file_path, rules_data)
        
        logger.info(f"Rule deleted from local file {local_file_path}")
        logger.info(f"Rule {rule_id} deleted successfully")
        
        return {
            "message": "Rule deleted successfully",
            "id": rule_id,
            "deleted": True
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting rule: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error deleting rule: {str(e)}")

@app.get("/api/rules/{model_short_name}/count")
async def get_rule_count(model_short_name: str):
    """
    Get the count of rules for a specific model.
    
    Args:
        model_short_name (str): The short name of the model
        
    Returns:
        dict: Count of rules for the model
    """
    try:
        try:
            rules_data = read_json_file(JSON_FILES['rules'])
        except HTTPException as e:
            logger.warning(f"Rules file not found or can't be read: {str(e)}")
            return {"count": 0}
        except Exception as e:
            logger.warning(f"Error reading rules file: {str(e)}, returning count 0")
            return {"count": 0}
        
        # Ensure rules_data has the expected structure
        if not isinstance(rules_data, dict):
            logger.warning("Rules file has invalid structure, returning count 0")
            return {"count": 0}
        
        if 'rules' not in rules_data:
            logger.warning("Rules file missing 'rules' key, returning count 0")
            return {"count": 0}
        
        # Filter rules by model and count
        model_rules = [
            rule for rule in rules_data.get('rules', [])
            if rule.get('modelShortName', '').lower() == model_short_name.lower()
        ]
        
        return {"count": len(model_rules)}
    except Exception as e:
        logger.error(f"Error getting rule count: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting rule count: {str(e)}")

@app.get("/api/rules/{model_short_name}/coverage")
async def get_rule_coverage(model_short_name: str):
    """
    Get rule coverage statistics for a model.
    
    Args:
        model_short_name (str): The short name of the model
        
    Returns:
        dict: Coverage statistics showing rules per object/column
    """
    try:
        # Get model data to understand structure
        try:
            models_data = read_json_file(JSON_FILES['models'])
            model = next(
                (m for m in models_data.get('models', []) if m.get('shortName', '').lower() == model_short_name.lower()),
                None
            )
        except Exception as e:
            logger.warning(f"Error reading models file: {str(e)}")
            model = None
        
        if not model:
            logger.warning(f"Model with short name '{model_short_name}' not found")
            # Don't raise error, just return empty coverage
        
        # Get rules for this model
        try:
            rules_data = read_json_file(JSON_FILES['rules'])
        except HTTPException:
            rules_data = {"rules": []}
        except Exception as e:
            logger.warning(f"Error reading rules file: {str(e)}")
            rules_data = {"rules": []}
        
        if not isinstance(rules_data, dict):
            rules_data = {"rules": []}
        
        model_rules = [
            rule for rule in rules_data.get('rules', [])
            if rule.get('modelShortName', '').lower() == model_short_name.lower()
        ]
        
        # Calculate coverage
        tagged_objects = set()
        tagged_columns = set()
        tagged_functions = set()
        
        for rule in model_rules:
            if rule.get('taggedObjects') and isinstance(rule.get('taggedObjects'), list):
                tagged_objects.update(rule['taggedObjects'])
            if rule.get('taggedColumns') and isinstance(rule.get('taggedColumns'), list):
                tagged_columns.update(rule['taggedColumns'])
            if rule.get('taggedFunctions') and isinstance(rule.get('taggedFunctions'), list):
                tagged_functions.update(rule['taggedFunctions'])
        
        # Extract objects and columns from model (if available in resources or schema)
        # For now, we'll return what we have
        coverage = {
            "modelShortName": model_short_name,
            "totalRules": len(model_rules),
            "taggedObjects": list(tagged_objects),
            "taggedColumns": list(tagged_columns),
            "taggedFunctions": list(tagged_functions),
            "objectCoverage": len(tagged_objects),
            "columnCoverage": len(tagged_columns),
            "functionCoverage": len(tagged_functions),
            "rules": model_rules
        }
        
        return coverage
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting rule coverage: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting rule coverage: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 