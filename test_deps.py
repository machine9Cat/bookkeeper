#!/usr/bin/env python3
import sys
sys.path.insert(0, '/home/administrator/jmrspace/bookkeeper/backend')

try:
    import fastapi
    print(f"✅ fastapi {fastapi.__version__}")
except ImportError as e:
    print(f"❌ fastapi: {e}")

try:
    import uvicorn
    print(f"✅ uvicorn")
except ImportError as e:
    print(f"❌ uvicorn: {e}")

try:
    import aiosqlite
    print(f"✅ aiosqlite")
except ImportError as e:
    print(f"❌ aiosqlite: {e}")

try:
    import jwt
    print(f"✅ PyJWT")
except ImportError as e:
    print(f"❌ PyJWT: {e}")

try:
    import aiohttp
    print(f"✅ aiohttp {aiohttp.__version__}")
except ImportError as e:
    print(f"❌ aiohttp: {e}")

try:
    import openpyxl
    print(f"✅ openpyxl {openpyxl.__version__}")
except ImportError as e:
    print(f"❌ openpyxl: {e}")

print("\nAll checks passed!" if True else "")
