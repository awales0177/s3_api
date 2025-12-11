#!/usr/bin/env python3
"""
Test script for the edit mode API endpoint.
Run this to test the model update functionality.
"""

import requests
import json
import time

def test_edit_mode():
    """Test the edit mode API endpoint."""
    
    base_url = "http://localhost:8000"
    
    print("🧪 Testing Edit Mode API")
    print("=" * 40)
    
    # Test 1: Check API mode
    print("\n1. Checking API mode...")
    try:
        response = requests.get(f"{base_url}/api/debug/mode")
        if response.status_code == 200:
            mode_info = response.json()
            print(f"✅ API Mode: {mode_info.get('mode_description', 'Unknown')}")
            print(f"   Test Mode: {mode_info.get('test_mode', False)}")
            print(f"   Data Source: {mode_info.get('data_source', 'Unknown')}")
        else:
            print(f"❌ Failed to get API mode: {response.status_code}")
            return
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to API. Make sure it's running on localhost:8000")
        return
    
    # Test 2: Get current model data
    print("\n2. Fetching current model data...")
    try:
        response = requests.get(f"{base_url}/api/models")
        if response.status_code == 200:
            models_data = response.json()
            if models_data.get('models'):
                test_model = models_data['models'][0]  # Use first model
                print(f"✅ Found model: {test_model.get('name', 'Unknown')}")
                print(f"   Short Name: {test_model.get('shortName', 'Unknown')}")
                print(f"   Current Description: {test_model.get('description', 'No description')[:50]}...")
            else:
                print("❌ No models found in response")
                return
        else:
            print(f"❌ Failed to fetch models: {response.status_code}")
            return
    except Exception as e:
        print(f"❌ Error fetching models: {e}")
        return
    
    # Test 3: Update model
    print("\n3. Testing model update...")
    try:
        # Create updated data
        updated_data = {
            "description": f"Updated description - Test run at {time.strftime('%H:%M:%S')}",
            "meta": {
                "verified": True,
                "tier": "gold"
            }
        }
        
        update_payload = {
            "shortName": test_model['shortName'],
            "modelData": updated_data
        }
        
        print(f"   Updating model: {test_model['shortName']}")
        print(f"   New description: {updated_data['description']}")
        
        response = requests.put(
            f"{base_url}/api/models/{test_model['shortName']}",
            json=update_payload,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Model updated successfully!")
            print(f"   Message: {result.get('message', 'No message')}")
            print(f"   Last Updated: {result.get('lastUpdated', 'Unknown')}")
        else:
            error_data = response.json()
            print(f"❌ Failed to update model: {response.status_code}")
            print(f"   Error: {error_data.get('detail', 'Unknown error')}")
            return
            
    except Exception as e:
        print(f"❌ Error updating model: {e}")
        return
    
    # Test 4: Verify update
    print("\n4. Verifying update...")
    try:
        time.sleep(1)  # Wait a moment for the update to process
        
        response = requests.get(f"{base_url}/api/models")
        if response.status_code == 200:
            models_data = response.json()
            updated_model = next(
                (m for m in models_data['models'] if m['shortName'] == test_model['shortName']), 
                None
            )
            
            if updated_model:
                print(f"✅ Update verified!")
                print(f"   New Description: {updated_model.get('description', 'No description')[:50]}...")
                print(f"   Verified: {updated_model.get('meta', {}).get('verified', False)}")
                print(f"   Tier: {updated_model.get('meta', {}).get('tier', 'Unknown')}")
            else:
                print("❌ Could not find updated model")
        else:
            print(f"❌ Failed to verify update: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error verifying update: {e}")
    
    print("\n" + "=" * 40)
    print("🎉 Edit mode test completed!")

if __name__ == "__main__":
    test_edit_mode()
