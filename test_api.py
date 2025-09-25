#!/usr/bin/env python3
"""
Simple test script to verify the API is working correctly.
"""

import requests
import json
import sys

def test_api(base_url="http://localhost:8000"):
    """Test the API endpoints."""
    
    print("🧪 Testing S3 Data Catalog API...")
    print(f"Base URL: {base_url}")
    print("-" * 50)
    
    tests = [
        ("S3 Status", f"{base_url}/api/debug/s3"),
        ("Search Stats", f"{base_url}/api/search/stats"),
        ("Performance", f"{base_url}/api/debug/performance"),
        ("Models", f"{base_url}/api/models"),
        ("Search", f"{base_url}/api/search?q=test&limit=5"),
    ]
    
    results = []
    
    for test_name, url in tests:
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                print(f"✅ {test_name}: OK")
                
                # Show some useful info
                if test_name == "S3 Status":
                    print(f"   S3 Available: {data.get('s3_available', 'Unknown')}")
                    print(f"   Bucket: {data.get('bucket_name', 'Unknown')}")
                elif test_name == "Search Stats":
                    print(f"   Documents: {data.get('total_documents', 0)}")
                    print(f"   Last Updated: {data.get('last_updated', 'Unknown')}")
                elif test_name == "Models":
                    models = data.get('models', [])
                    print(f"   Models Count: {len(models)}")
                elif test_name == "Search":
                    results_count = len(data.get('results', []))
                    print(f"   Search Results: {results_count}")
                    
            else:
                print(f"❌ {test_name}: HTTP {response.status_code}")
                print(f"   Error: {response.text[:100]}...")
                
        except requests.exceptions.ConnectionError:
            print(f"❌ {test_name}: Connection failed (is the API running?)")
        except requests.exceptions.Timeout:
            print(f"❌ {test_name}: Timeout")
        except Exception as e:
            print(f"❌ {test_name}: {str(e)}")
        
        print()
    
    print("🏁 Test completed!")

if __name__ == "__main__":
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
    test_api(base_url)


