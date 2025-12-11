from fastapi import HTTPException

@app.get("/api/contracts/by-model/{model_short_name}")
async def get_contracts_by_model(model_short_name: str):
    """
    Get all contracts associated with a specific data model by its short name.
    
    Args:
        model_short_name (str): The short name of the model (e.g., 'CUST', 'PROD')
        
    Returns:
        dict: A dictionary containing the filtered contracts
        
    Raises:
        HTTPException: If the model is not found
    """
    try:
        contracts_data = read_json_file(JSON_FILES['dataContracts'])
        model_data = read_json_file(JSON_FILES['models'])

        # Find the model by short name (case-insensitive)
        model = next((m for m in model_data['models'] if m['shortName'].lower() == model_short_name.lower()), None)
        if not model:
            raise HTTPException(
                status_code=404, 
                detail=f"Model with short name '{model_short_name}' not found"
            )

        # Filter contracts by model shortName
        filtered_contracts = [
            contract for contract in contracts_data['contracts']
            if contract.get('modelShortName', '').lower() == model_short_name.lower()
        ]
        
        return {
            "model": {
                "id": model['id'],
                "shortName": model['shortName'],
                "name": model['name']
            },
            "contracts": filtered_contracts
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error processing request: {str(e)}"
        ) 