import os, httpx, jwt, asyncio
from dotenv import load_dotenv

load_dotenv()

async def f():
    res = await httpx.AsyncClient().post(
        os.environ['SUPABASE_URL']+'/auth/v1/token?grant_type=password',
        headers={'apikey': os.environ['SUPABASE_ANON_KEY']},
        json={'email':'demo@localhost','password':'ChangeMe123!'}
    )
    t = res.json()['access_token']
    print(jwt.get_unverified_header(t))

asyncio.run(f())
