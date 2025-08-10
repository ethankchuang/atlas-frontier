#!/usr/bin/env python3
"""
Setup script for Supabase configuration and testing.
Run this after you've created your Supabase project and run the schema.
"""

import os
import sys
from pathlib import Path

def check_env_file():
    """Check if .env file exists and has Supabase config"""
    env_file = Path(".env")
    
    if not env_file.exists():
        print("❌ .env file not found in server/")
        print("📝 Please create server/.env with your configuration")
        return False
    
    # Read env file and check for Supabase config
    with open(env_file, 'r') as f:
        content = f.read()
    
    required_vars = ['SUPABASE_URL', 'SUPABASE_ANON_KEY', 'SUPABASE_SERVICE_ROLE_KEY']
    missing_vars = []
    
    for var in required_vars:
        if var not in content or f'{var}=' not in content or f'{var}=""' in content:
            missing_vars.append(var)
    
    if missing_vars:
        print(f"❌ Missing or empty Supabase configuration: {', '.join(missing_vars)}")
        return False
    
    print("✅ .env file has Supabase configuration")
    return True

def test_supabase_connection():
    """Test the Supabase connection"""
    try:
        # Add the app directory to Python path
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))
        
        from app.supabase_client import test_supabase_connection
        
        if test_supabase_connection():
            print("✅ Supabase connection successful!")
            return True
        else:
            print("❌ Supabase connection failed")
            return False
            
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("💡 Make sure you've installed the supabase package: pip install supabase")
        return False
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False

def main():
    print("🚀 Supabase Setup for Game Database")
    print("=" * 40)
    
    print("\n📋 Setup Checklist:")
    print("1. Created Supabase project at https://supabase.com")
    print("2. Run the SQL schema in your Supabase SQL Editor")
    print("3. Added Supabase credentials to server/.env")
    print("4. Installed supabase package (pip install supabase)")
    
    print("\n🔍 Checking configuration...")
    
    # Check .env file
    if not check_env_file():
        print("\n❌ Setup incomplete. Please fix the issues above.")
        return
    
    # Test connection
    print("\n🔗 Testing Supabase connection...")
    if not test_supabase_connection():
        print("\n❌ Connection failed. Please check your credentials and try again.")
        return
    
    print("\n🎉 Setup complete!")
    print("\n📝 Next steps:")
    print("1. Your app will now use Supabase for persistent data")
    print("2. Redis is still used for transient data (chat, sessions, locks)")
    print("3. Start your server: python -m uvicorn app.main:app --reload")
    
    print("\n💡 Tips:")
    print("- Use Database.reset_world() to clear all data")
    print("- Check Supabase dashboard to see your data")
    print("- Redis still handles chat, sessions, and locks")

if __name__ == "__main__":
    main()
