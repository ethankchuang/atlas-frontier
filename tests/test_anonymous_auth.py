#!/usr/bin/env python3
"""
Test script for Supabase anonymous authentication
This script tests the anonymous sign-in flow without requiring a full frontend setup
"""

import asyncio
import json
import requests
from supabase import create_client, Client

# Configuration - replace with your actual values
SUPABASE_URL = "your_supabase_url_here"
SUPABASE_ANON_KEY = "your_supabase_anon_key_here"
API_URL = "http://localhost:8000"

def test_supabase_anonymous_auth():
    """Test Supabase anonymous authentication"""
    print("🧪 Testing Supabase Anonymous Authentication")
    print("=" * 50)
    
    try:
        # Initialize Supabase client
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
        print("✅ Supabase client initialized")
        
        # Test anonymous sign-in
        print("\n🔐 Testing anonymous sign-in...")
        response = supabase.auth.sign_in_anonymously()
        
        if response.user:
            print(f"✅ Anonymous user created: {response.user.id")
            print(f"   Email: {response.user.email}")
            print(f"   Is Anonymous: {response.user.is_anonymous}")
            
            # Test creating a guest player
            print("\n🎮 Testing guest player creation...")
            guest_data = {
                "anonymous_user_id": response.user.id
            }
            
            api_response = requests.post(
                f"{API_URL}/auth/guest",
                json=guest_data,
                headers={"Content-Type": "application/json"}
            )
            
            if api_response.status_code == 200:
                player_data = api_response.json()
                print(f"✅ Guest player created: {player_data['player']['name']}")
                print(f"   Player ID: {player_data['player']['id']}")
                print(f"   User ID: {player_data['player']['user_id']}")
            else:
                print(f"❌ Failed to create guest player: {api_response.status_code}")
                print(f"   Error: {api_response.text}")
                
        else:
            print("❌ Anonymous sign-in failed")
            print(f"   Error: {response}")
            
    except Exception as e:
        print(f"❌ Test failed: {str(e)}")
        return False
    
    return True

def test_conversion_flow():
    """Test the conversion flow"""
    print("\n🔄 Testing conversion flow...")
    print("=" * 50)
    
    try:
        # This would normally be done in the frontend
        # For testing, we'll simulate the conversion request
        conversion_data = {
            "email": "test@example.com",
            "password": "testpassword123",
            "username": "testuser",
            "guest_player_id": "guest_12345678",  # This would be the actual player ID
            "new_user_id": "new_user_id_here"     # This would be the new Supabase user ID
        }
        
        api_response = requests.post(
            f"{API_URL}/auth/guest-to-user",
            json=conversion_data,
            headers={"Content-Type": "application/json"}
        )
        
        if api_response.status_code == 200:
            print("✅ Conversion endpoint is working")
        else:
            print(f"❌ Conversion failed: {api_response.status_code}")
            print(f"   Error: {api_response.text}")
            
    except Exception as e:
        print(f"❌ Conversion test failed: {str(e)}")

if __name__ == "__main__":
    print("🚀 Supabase Anonymous Authentication Test")
    print("Make sure to update the configuration variables at the top of this file")
    print("and ensure your Supabase project has anonymous sign-ins enabled.")
    print()
    
    # Test the basic flow
    if test_supabase_anonymous_auth():
        print("\n✅ Basic anonymous authentication test passed!")
    else:
        print("\n❌ Basic anonymous authentication test failed!")
    
    # Test conversion (this will fail without proper setup, but shows the flow)
    test_conversion_flow()
    
    print("\n📝 Next steps:")
    print("1. Update SUPABASE_URL and SUPABASE_ANON_KEY in this script")
    print("2. Enable anonymous sign-ins in your Supabase dashboard")
    print("3. Run the test again")
    print("4. Test the full flow in the frontend application")
