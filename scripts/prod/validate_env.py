#!/usr/bin/env python3
import os
import sys
from dotenv import load_dotenv

def main():
    env_file = sys.argv[1] if len(sys.argv) > 1 else ".env.prod"
    if not os.path.exists(env_file):
        print(f"[ERROR] Environment file '{env_file}' not found.")
        sys.exit(1)
        
    load_dotenv(env_file)
    
    required = [
        "ENVIRONMENT", "SECRET_KEY", "DATABASE_URL", 
        "REDIS_URL", "QDRANT_URL"
    ]
    
    missing = []
    for req in required:
        if not os.environ.get(req):
            missing.append(req)
            
    if missing:
        print(f"[ERROR] Missing required variables in {env_file}: {', '.join(missing)}")
        sys.exit(1)
        
    if os.environ.get("ENVIRONMENT") != "production":
        print("[WARN] ENVIRONMENT is not set to 'production'.")
        
    print(f"[PASS] {env_file} validation passed.")
    sys.exit(0)

if __name__ == "__main__":
    main()
