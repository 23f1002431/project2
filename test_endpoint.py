"""
Test script for the quiz solver endpoint.
"""
import requests
import json
import sys
from config import STUDENT_EMAIL, STUDENT_SECRET, API_HOST, API_PORT

def test_endpoint(base_url: str = None):
    """Test the quiz endpoint with demo URL."""
    if base_url is None:
        # Use config values for default
        base_url = f"http://{API_HOST}:{API_PORT}" if API_HOST != "0.0.0.0" else f"http://127.0.0.1:{API_PORT}"
    
    # Test health endpoint
    print("Testing health endpoint...")
    try:
        response = requests.get(f"{base_url}/health")
        print(f"✓ Health check: {response.status_code} - {response.json()}")
    except Exception as e:
        print(f"✗ Health check failed: {e}")
        return
    
    # Test quiz endpoint with demo
    print("\nTesting quiz endpoint with demo URL...")
    payload = {
        "email": STUDENT_EMAIL,
        "secret": STUDENT_SECRET,
        "url": "https://tds-llm-analysis.s-anand.net/demo"
    }
    
    try:
        response = requests.post(
            f"{base_url}/quiz",
            json=payload,
            timeout=5
        )
        print(f"✓ Quiz endpoint: {response.status_code}")
        print(f"  Response: {json.dumps(response.json(), indent=2)}")
    except requests.exceptions.Timeout:
        print("✓ Quiz endpoint accepted request (timeout expected for async processing)")
    except Exception as e:
        print(f"✗ Quiz endpoint failed: {e}")
    
    # Test invalid secret
    print("\nTesting invalid secret (should return 403)...")
    payload["secret"] = "wrong-secret"
    try:
        response = requests.post(f"{base_url}/quiz", json=payload)
        if response.status_code == 403:
            print("✓ Invalid secret correctly rejected")
        else:
            print(f"✗ Expected 403, got {response.status_code}")
    except Exception as e:
        print(f"✗ Error: {e}")
    
    # Test invalid JSON
    print("\nTesting invalid JSON (should return 400)...")
    try:
        response = requests.post(
            f"{base_url}/quiz",
            data="invalid json",
            headers={"Content-Type": "application/json"}
        )
        if response.status_code == 400:
            print("✓ Invalid JSON correctly rejected")
        else:
            print(f"✗ Expected 400, got {response.status_code}")
    except Exception as e:
        print(f"✗ Error: {e}")

if __name__ == "__main__":
    # Allow override via command line, otherwise use config defaults
    if len(sys.argv) > 1:
        base_url = sys.argv[1]
    else:
        base_url = None  # Will use config defaults
    test_endpoint(base_url)

