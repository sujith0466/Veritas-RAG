import asyncio
import httpx
import uuid

API_URL = 'http://localhost:8000/api/v1'

async def run_tests():
    async with httpx.AsyncClient() as client:
        res = await client.post(f'{API_URL}/auth/login', json={'email': 'test_user@raguard.ai', 'password': 'Password123!'})
        if res.status_code != 200:
            print("Login failed, outputting to see if we can use existing test users")
        
        # Or I can just register one quickly
        email = f'test_{uuid.uuid4().hex[:8]}@raguard.ai'
        await client.post(f'{API_URL}/auth/register', json={'email': email, 'password': 'Password123!', 'full_name': 'Test User'})
        
        # Verify
        from sqlalchemy.ext.asyncio import create_async_engine
        from sqlalchemy import text
        import os
        url = os.getenv('DATABASE_URL')
        if url and url.startswith('postgres://'): url = url.replace('postgres://', 'postgresql+asyncpg://')
        engine = create_async_engine(url)
        async with engine.connect() as conn:
            await conn.execute(text("UPDATE users SET is_verified = true WHERE email = :email"), {"email": email})
            await conn.commit()
        await engine.dispose()
        
        # Login
        res = await client.post(f'{API_URL}/auth/login', json={'email': email, 'password': 'Password123!'})
        access_token = res.json()['data']['access_token']
        
        res = await client.get(f'{API_URL}/auth/me', headers={'Authorization': f'Bearer {access_token}'})
        print(res.json())

asyncio.run(run_tests())
