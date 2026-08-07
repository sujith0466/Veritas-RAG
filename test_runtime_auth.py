import asyncio
import httpx
import uuid
import jwt
import os
import time
from dotenv import load_dotenv

load_dotenv('.env')

API_URL = 'http://localhost:8000/api/v1'
TEST_EMAIL = f'test_{uuid.uuid4().hex[:8]}@raguard.ai'
TEST_PASSWORD = 'Password123!'

SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'dev_jwt_secret_key_change_in_production')
ALGORITHM = 'HS256'

async def verify_user(email: str):
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy import text
    url = os.getenv('DATABASE_URL')
    if url.startswith('postgres://'): url = url.replace('postgres://', 'postgresql+asyncpg://')
    engine = create_async_engine(url)
    async with engine.connect() as conn:
        await conn.execute(text("UPDATE users SET is_verified = true WHERE email = :email"), {"email": email})
        await conn.commit()
    await engine.dispose()

async def run_tests():
    async with httpx.AsyncClient() as client:
        print('6. Register new account...')
        res = await client.post(f'{API_URL}/auth/register', json={
            'email': TEST_EMAIL,
            'password': TEST_PASSWORD,
            'full_name': 'Test User',
            'accepted_terms': True
        })
        assert res.status_code in [201, 200, 202], f'Register failed: {res.status_code} {res.text}'
        print('Register OK')

        await verify_user(TEST_EMAIL)

        print('7. Login...')
        res = await client.post(f'{API_URL}/auth/login', json={
            'email': TEST_EMAIL,
            'password': TEST_PASSWORD
        })
        assert res.status_code == 200, f'Login failed: {res.status_code} {res.text}'
        tokens = res.json()['data']
        access_token = tokens['access_token']
        # The API v1 uses http only cookies for refresh token if not returned in JSON. Let's see if it's there.
        refresh_token = tokens.get('refresh_token') or res.cookies.get('refresh_token')
        print('Login OK')

        print('8. GET /api/v1/auth/me...')
        res = await client.get(f'{API_URL}/auth/me', headers={'Authorization': f'Bearer {access_token}'})
        assert res.status_code == 200, f'/auth/me failed: {res.status_code} {res.text}'
        me_data = res.json()['data']['user']
        assert me_data['role'] == 'viewer', f'Role is not viewer: {me_data.get("role")}'
        print('GET /auth/me OK, Role is viewer')

        if refresh_token:
            print('9. Refresh token...')
            res = await client.post(f'{API_URL}/auth/refresh', json={'refresh_token': refresh_token})
            assert res.status_code == 200, f'Refresh failed: {res.status_code} {res.text}'
            access_token = res.json()['data']['access_token']
            print('Refresh OK')
        else:
            print('9. Skipping refresh token test (no token returned in body or cookie)')

        print('11. Testing Legacy JWT fallback...')
        legacy_payload = {
            'sub': me_data['id'],
            'email': TEST_EMAIL,
            'role': 'user',
            'iat': int(time.time()),
            'exp': int(time.time()) + 3600
        }
        legacy_token = jwt.encode(legacy_payload, SECRET_KEY, algorithm=ALGORITHM)
        res = await client.get(f'{API_URL}/auth/me', headers={'Authorization': f'Bearer {legacy_token}'})
        assert res.status_code == 200, f'Legacy token failed: {res.status_code} {res.text}'
        legacy_me = res.json()['data']['user']
        assert legacy_me['role'] == 'viewer', f'Legacy token did not map to viewer: {legacy_me.get("role")}'
        print('Legacy JWT mapped successfully to viewer!')

        print('10. Logout...')
        res = await client.post(f'{API_URL}/auth/logout', headers={'Authorization': f'Bearer {access_token}'})
        assert res.status_code == 200, f'Logout failed: {res.status_code} {res.text}'
        print('Logout OK')

        print('All API tests passed!')

asyncio.run(run_tests())
