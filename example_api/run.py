#!/usr/bin/env python3
"""
Simple script to run the Data Catalog API in different modes.
"""

import os
import sys
import subprocess
from pathlib import Path

def print_banner():
    print("=" * 60)
    print("🚀 Data Catalog API Runner")
    print("=" * 60)

def print_modes():
    print("\nAvailable Modes:")
    print("1. 🧪 TEST MODE - Uses local _data files (fast, offline)")
    print("2. 🌐 PASSTHROUGH MODE - Direct GitHub access (no cache)")
    print("3. 💾 CACHED MODE - GitHub with caching (default)")
    print("4. 🔧 CUSTOM MODE - Set your own environment variables")

def run_api(mode, port=8000):
    """Run the API with the specified mode."""
    
    # Set environment variables based on mode
    env_vars = os.environ.copy()
    
    if mode == "test":
        env_vars["TEST_MODE"] = "true"
        env_vars["PASSTHROUGH_MODE"] = "false"
        print(f"\n🧪 Starting API in TEST MODE (port {port})")
        print("   - Using local _data files")
        print("   - No network requests to GitHub")
        print("   - Fast startup and response times")
        
    elif mode == "passthrough":
        env_vars["TEST_MODE"] = "false"
        env_vars["PASSTHROUGH_MODE"] = "true"
        print(f"\n🌐 Starting API in PASSTHROUGH MODE (port {port})")
        print("   - Direct GitHub access")
        print("   - No caching")
        print("   - Real-time data from GitHub")
        
    elif mode == "cached":
        env_vars["TEST_MODE"] = "false"
        env_vars["PASSTHROUGH_MODE"] = "false"
        print(f"\n💾 Starting API in CACHED MODE (port {port})")
        print("   - GitHub with 15-minute caching")
        print("   - Best performance for production")
        print("   - Automatic cache management")
        
    else:
        print(f"\n🔧 Starting API with custom configuration (port {port})")
        print("   - Using existing environment variables")
    
    # Set port
    env_vars["PORT"] = str(port)
    
    # Run the API
    try:
        subprocess.run([sys.executable, "main.py"], env=env_vars, check=True)
    except KeyboardInterrupt:
        print("\n\n🛑 API stopped by user")
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Error running API: {e}")
        return False
    
    return True

def main():
    print_banner()
    print_modes()
    
    while True:
        try:
            choice = input("\nSelect mode (1-4) or 'q' to quit: ").strip().lower()
            
            if choice == 'q':
                print("\n👋 Goodbye!")
                break
            elif choice == '1':
                port = input("Enter port number (default: 8000): ").strip()
                port = int(port) if port.isdigit() else 8000
                run_api("test", port)
                break
            elif choice == '2':
                port = input("Enter port number (default: 8000): ").strip()
                port = int(port) if port.isdigit() else 8000
                run_api("passthrough", port)
                break
            elif choice == '3':
                port = input("Enter port number (default: 8000): ").strip()
                port = int(port) if port.isdigit() else 8000
                run_api("cached", port)
                break
            elif choice == '4':
                port = input("Enter port number (default: 8000): ").strip()
                port = int(port) if port.isdigit() else 8000
                run_api("custom", port)
                break
            else:
                print("❌ Invalid choice. Please select 1-4 or 'q'.")
                
        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!")
            break
        except ValueError:
            print("❌ Invalid port number. Using default port 8000.")
            run_api("cached", 8000)
            break

if __name__ == "__main__":
    main()
