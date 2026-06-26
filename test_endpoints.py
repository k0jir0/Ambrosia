import requests

base_url = "http://127.0.0.1:8001"

# Test /health
response = requests.get(f"{base_url}/health")
print(f"/health: {response.status_code}")

# Test /discovery/generate-thesis
response = requests.post(f"{base_url}/discovery/generate-thesis", json={"signal_data": "test"})
print(f"/discovery/generate-thesis: {response.status_code}")
if response.status_code != 200 and response.status_code != 201:
    print(f"  Response: {response.text[:200]}")

# Test /metrics
response = requests.get(f"{base_url}/metrics")
print(f"/metrics: {response.status_code}")
