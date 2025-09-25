from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Dict, Any, List
from datetime import datetime
import logging
from time import perf_counter

# Import authentication modules
from auth import get_current_user_optional, require_editor_or_admin, require_admin, UserRole
from endpoints.auth import router as auth_router
from services.search_service import search_service
from services.data_service import DataService
from config import Config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Performance metrics
performance_metrics = {
    "requests": {
        "total": 0,
        "by_endpoint": {},
        "response_times": []
    }
}

def log_performance(endpoint: str, start_time: float):
    """Log performance metrics for an API request."""
    duration = perf_counter() - start_time
    performance_metrics["requests"]["total"] += 1
    performance_metrics["requests"]["by_endpoint"][endpoint] = performance_metrics["requests"]["by_endpoint"].get(endpoint, 0) + 1
    performance_metrics["requests"]["response_times"].append(duration)

def get_performance_stats():
    """Calculate performance statistics."""
    response_times = performance_metrics["requests"]["response_times"]
    
    stats = {
        "total_requests": performance_metrics["requests"]["total"],
        "requests_by_endpoint": performance_metrics["requests"]["by_endpoint"],
        "cache": {
            "status": "disabled",
            "message": "All data is read fresh from files"
        }
    }
    
    if response_times:
        stats["response_times"] = {
            "avg": sum(response_times) / len(response_times),
            "min": min(response_times),
            "max": max(response_times),
            "p95": sorted(response_times)[int(len(response_times) * 0.95)]
        }
    
    return stats

def trigger_reindex(file_name: str = None):
    """Trigger search index reindexing for a specific file or all files."""
    try:
        if file_name:
            logger.info(f"Triggering reindex for file: {file_name}")
            success = search_service.reindex_file(file_name)
        else:
            logger.info("Triggering full search reindex")
            success = search_service.reindex()
        
        if success:
            logger.info("Search reindex completed successfully")
        else:
            logger.error("Search reindex failed")
        
        return success
    except Exception as e:
        logger.error(f"Error triggering reindex: {e}")
        return False

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

# Initialize data service
data_service = DataService()

# Log server configuration
logger.info("=" * 50)
logger.info("Server Configuration:")
logger.info(f"Data Source: {Config.get_mode_description()}")
logger.info(f"S3 Mode: {'ENABLED' if Config.S3_MODE else 'DISABLED'}")
logger.info(f"Caching: DISABLED - Always fresh data")
logger.info(f"S3 Bucket: {Config.S3_BUCKET_NAME}")
logger.info(f"AWS Region: {Config.AWS_REGION}")
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



# Data models
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
    "dataProducts": "dataProducts.json"
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
    "dataProducts": "dataProducts"
}



def get_cached_data(file_name: str) -> Dict:
    """Get data from the configured data source (no caching)."""
    start_time = perf_counter()
    logger.info(f"Reading data from {Config.get_data_source()} for {file_name}")
    
    try:
        data = data_service.read_json_file(JSON_FILES[file_name])
        if data is not None:
            logger.info(f"Data loaded successfully for {file_name}")
            log_performance(f"{Config.get_data_source()}_read", start_time)
            return data
        else:
            logger.error(f"Failed to load data for {file_name}")
            raise HTTPException(status_code=500, detail=f"Failed to load data for {file_name}")
    except Exception as e:
        logger.error(f"Error reading data for {file_name}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error loading data: {str(e)}")

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

@app.get("/api/{file_name}")
def get_json_file(file_name: str):
    """Get JSON file content from configured data source."""
    start_time = perf_counter()
    logger.info(f"Request for {file_name} - Using {Config.get_data_source()} mode")
    result = get_cached_data(file_name)
    log_performance("get_json_file", start_time)
    return result

@app.get("/api/{file_name}/paginated")
def get_paginated_json_file(
    file_name: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100)
):
    """Get paginated JSON file content."""
    logger.info(f"Paginated request for {file_name} - Using {Config.get_data_source()} mode")
    data = get_cached_data(file_name)
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
    logger.info(f"Count request for {file_name} - Using {Config.get_data_source()} mode")
    data = get_cached_data(file_name)
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
            'meta': request.meta,
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
        models_data = data_service.read_json_file('dataModels.json')
        
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
        
        # Save the updated data to S3
        data_service.write_json_file('dataModels.json', models_data)
        logger.info(f"Model deleted from S3")
        
        # Trigger search reindex for models
        trigger_reindex('dataModels.json')
        
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
        models_data = data_service.read_json_file('dataModels.json')
        
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
                    agreements_data = data_service.read_json_file('dataAgreements.json')
                    agreements_updated = False
                    
                    for agreement in agreements_data['agreements']:
                        if agreement.get('modelShortName') == old_short_name:
                            agreement['modelShortName'] = new_short_name
                            agreements_updated = True
                            logger.info(f"Updated agreement {agreement['id']} modelShortName from '{old_short_name}' to '{new_short_name}'")
                    
                    if agreements_updated:
                        data_service.write_json_file('dataAgreements.json', agreements_data)
                        logger.info(f"Updated agreements file with new modelShortName references")
                        # Trigger reindex for agreements
                        trigger_reindex('dataAgreements.json')
                    
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
        
        # Save the updated data to S3
        data_service.write_json_file('dataModels.json', models_data)
        logger.info(f"Updated S3 file")
        
        # Trigger search reindex for models
        trigger_reindex('dataModels.json')
        
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


def read_json_file(file_path: str) -> Dict:
    """Read JSON file using DataService"""
    data = data_service.read_json_file(file_path)
    if data is None:
        raise HTTPException(status_code=404, detail=f"File not found: {file_path}")
    return data

def write_json_file(file_path: str, data: Dict):
    """Write JSON file using DataService"""
    success = data_service.write_json_file(file_path, data)
    if not success:
        raise HTTPException(status_code=500, detail=f"Failed to write file: {file_path}")

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
        toolkit_data = read_json_file(JSON_FILES['toolkit'])
        
        # Determine component type and generate ID
        component_type = component.get('type', 'functions')
        if component_type not in ['functions', 'containers', 'terraform']:
            raise HTTPException(status_code=400, detail="Invalid component type")
        
        # For functions, use the function name as the ID
        if component_type == 'functions':
            function_name = component.get('name', '')
            if not function_name:
                raise HTTPException(status_code=400, detail="Function name is required")
            
            # Check if function name already exists
            existing_names = [item['name'] for item in toolkit_data['toolkit'][component_type]]
            if function_name in existing_names:
                raise HTTPException(status_code=400, detail=f"Function with name '{function_name}' already exists")
            
            new_id = function_name
        else:
            # Generate new ID based on type for other component types
            existing_ids = [item['id'] for item in toolkit_data['toolkit'][component_type]]
            if component_type == 'containers':
                prefix = 'cont_'
            else:
                prefix = 'tf_'
            
            max_num = 0
            for item_id in existing_ids:
                if item_id.startswith(prefix):
                    try:
                        num = int(item_id.split('_')[1])
                        max_num = max(max_num, num)
                    except:
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
            "downloads": 0
        }
        
        # Add type-specific fields
        if component_type == 'functions':
            new_component['language'] = component.get('language', '')
            new_component['code'] = component.get('code', '')
            new_component['parameters'] = component.get('parameters', [])
        elif component_type == 'containers':
            new_component['dockerfile'] = component.get('dockerfile', '')
            new_component['dockerCompose'] = component.get('dockerCompose', '')
        elif component_type == 'terraform':
            new_component['provider'] = component.get('provider', '')
            new_component['mainTf'] = component.get('mainTf', '')
            new_component['variablesTf'] = component.get('variablesTf', '')
            new_component['outputsTf'] = component.get('outputsTf', '')
        
        toolkit_data['toolkit'][component_type].append(new_component)
        
        local_file_path = JSON_FILES['toolkit']
        write_json_file(local_file_path, toolkit_data)
        
        logger.info(f"Toolkit component created in local file {local_file_path}")
        logger.info(f"Component {new_id} created successfully")
        
        return {
            "message": "Toolkit component created successfully",
            "id": new_id,
            "component": new_component
        }
    except Exception as e:
        logger.error(f"Error creating toolkit component: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error creating toolkit component: {str(e)}")

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
        updated_component = {
            **toolkit_data['toolkit'][component_type][comp_to_update],
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
        "message": "All data is read fresh from S3 on each request",
        "data_source": Config.get_data_source(),
        "s3_mode": Config.S3_MODE,
        "s3_bucket": Config.S3_BUCKET_NAME
    }

@app.get("/api/debug/s3")
def get_s3_status():
    """Get S3 connection status and configuration."""
    if not Config.S3_MODE:
        return {
            "s3_mode": False,
            "message": "S3 mode is not enabled"
        }
    
    s3_available = data_service.s3_service.is_available() if data_service.s3_service else False
    
    return {
        "s3_mode": True,
        "s3_available": s3_available,
        "bucket_name": Config.S3_BUCKET_NAME,
        "aws_region": Config.AWS_REGION,
        "message": "S3 is available" if s3_available else "S3 is not available - check credentials"
    }

@app.get("/api/debug/performance")
def get_performance_metrics():
    """Get current performance metrics."""
    return get_performance_stats()

@app.post("/api/admin/reindex")
async def manual_reindex(file_name: str = None, current_user: dict = Depends(require_admin)):
    """
    Manually trigger search index reindexing.
    
    Args:
        file_name (str, optional): Specific file to reindex. If not provided, reindexes all files.
        
    Returns:
        dict: Reindex status and statistics
    """
    try:
        logger.info(f"Manual reindex triggered by {current_user.get('username', 'unknown')} for file: {file_name or 'all'}")
        
        # Trigger reindex
        success = trigger_reindex(file_name)
        
        if success:
            stats = search_service.get_stats()
            return {
                "message": "Reindex completed successfully",
                "success": True,
                "file_name": file_name,
                "stats": stats
            }
        else:
            return {
                "message": "Reindex failed",
                "success": False,
                "file_name": file_name
            }
            
    except Exception as e:
        logger.error(f"Manual reindex error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Reindex failed: {str(e)}"
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 