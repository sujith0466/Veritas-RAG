import asyncio
import os

from dotenv import load_dotenv

load_dotenv()
os.environ["ENABLE_DEMO_USER"] = "true"

from backend.core.auth.seed import seed_demo_user


async def main():
    await seed_demo_user()
    print("Seeding complete.")

if __name__ == "__main__":
    asyncio.run(main())
