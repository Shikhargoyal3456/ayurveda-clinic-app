import requests


response = requests.get("http://localhost:8000", timeout=10)
assert response.status_code == 200, f"Failed with {response.status_code}"
print("Template fix working!")
