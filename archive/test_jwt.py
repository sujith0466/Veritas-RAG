import jwt

anon_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inlwem50dmtmd2lkcXJmY2lrdXdxIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODQ1ODYwOTMsImV4cCI6MjEwMDE2MjA5M30.FoFwTmgpvWG9cvDLEtofMpeVwPOs6Vp7BTJFZJpeX-0"
secret = "a3495afb-fdc7-4f58-8498-185c3168368f"

try:
    decoded = jwt.decode(anon_key, secret, algorithms=["HS256"], options={"verify_exp": False, "verify_aud": False})
    print("SUCCESS: Secret matches!")
    print(decoded)
except Exception as e:
    print(f"FAILED: {e}")
