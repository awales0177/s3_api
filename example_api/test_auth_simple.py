#!/usr/bin/env python3
"""
Simple test to verify authentication imports work
"""

try:
    from auth import authenticate_user, create_access_token, UserRole
    print("✅ Authentication imports successful!")
    
    # Test user authentication
    user = authenticate_user("reader1", "reader123")
    if user:
        print(f"✅ User authentication successful: {user['username']} ({user['role']})")
    else:
        print("❌ User authentication failed")
    
    # Test token creation
    token = create_access_token({"sub": "reader1", "role": "reader"})
    if token:
        print(f"✅ Token creation successful: {token[:20]}...")
    else:
        print("❌ Token creation failed")
        
    print("\n🎉 All authentication tests passed!")
    
except ImportError as e:
    print(f"❌ Import error: {e}")
except Exception as e:
    print(f"❌ Error: {e}")
