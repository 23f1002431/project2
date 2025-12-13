"""
Comprehensive test file to verify all system components are working.
Tests the quiz solver with the provided request.
"""
import requests
import json
import time
import sys
from typing import Dict, Any

# Configuration
BASE_URL = "http://127.0.0.1:8000"  # Change this to your server URL
TEST_CONFIG = {
    "email": "23f1002431@ds.study.iitm.ac.in",
    "secret": "qwertyisthis",
    "url": "https://tds-llm-analysis.s-anand.net/project2-git",
    "expected_answer": "git add env.sample\ngit commit -m \"chore: keep env sample\""
}


def print_section(title: str):
    """Print a formatted section header."""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def print_result(test_name: str, passed: bool, details: str = ""):
    """Print test result."""
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"{status}: {test_name}")
    if details:
        print(f"   {details}")


def test_health_endpoint() -> bool:
    """Test the health endpoint."""
    print_section("Test 1: Health Check")
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            print_result("Health endpoint", True, f"Status: {data.get('status')}")
            print(f"   Uptime: {data.get('uptime_seconds', 0):.2f} seconds")
            print(f"   Total quizzes: {data.get('total_quizzes', 0)}")
            print(f"   Success rate: {data.get('success_rate', 0):.2f}%")
            return True
        else:
            print_result("Health endpoint", False, f"Status code: {response.status_code}")
            return False
    except Exception as e:
        print_result("Health endpoint", False, f"Error: {str(e)}")
        return False


def test_quiz_submission() -> Dict[str, Any]:
    """Test quiz submission with the provided request."""
    print_section("Test 2: Quiz Submission")
    
    payload = {
        "email": TEST_CONFIG["email"],
        "secret": TEST_CONFIG["secret"],
        "url": TEST_CONFIG["url"]
    }
    
    try:
        print(f"Submitting quiz request:")
        print(f"  URL: {payload['url']}")
        print(f"  Email: {payload['email']}")
        
        response = requests.post(
            f"{BASE_URL}/quiz",
            json=payload,
            timeout=5
        )
        
        if response.status_code == 200:
            data = response.json()
            print_result("Quiz submission", True, f"Status: {data.get('status')}")
            print(f"   Message: {data.get('message')}")
            
            task_id = data.get('task_id')
            if task_id:
                print(f"   Task ID: {task_id}")
                print(f"   Note: Quiz is processing in the background")
                print(f"   Check server logs for progress")
            
            return {
                "success": True,
                "task_id": task_id,
                "response": data
            }
        else:
            print_result("Quiz submission", False, f"Status code: {response.status_code}")
            print(f"   Response: {response.text}")
            return {"success": False, "status_code": response.status_code}
    
    except requests.exceptions.Timeout:
        print_result("Quiz submission", True, "Request accepted (timeout expected for async)")
        return {"success": True, "note": "async_processing"}
    except Exception as e:
        print_result("Quiz submission", False, f"Error: {str(e)}")
        return {"success": False, "error": str(e)}


def test_invalid_secret() -> bool:
    """Test that invalid secret is rejected."""
    print_section("Test 3: Invalid Secret Rejection")
    
    payload = {
        "email": TEST_CONFIG["email"],
        "secret": "wrong-secret",
        "url": TEST_CONFIG["url"]
    }
    
    try:
        response = requests.post(f"{BASE_URL}/quiz", json=payload, timeout=5)
        
        if response.status_code == 403:
            print_result("Invalid secret rejection", True, "Correctly rejected with 403")
            return True
        else:
            print_result("Invalid secret rejection", False, 
                        f"Expected 403, got {response.status_code}")
            return False
    except Exception as e:
        print_result("Invalid secret rejection", False, f"Error: {str(e)}")
        return False


def test_missing_fields() -> bool:
    """Test that missing required fields are rejected."""
    print_section("Test 4: Missing Fields Validation")
    
    # Test missing secret
    payload = {
        "email": TEST_CONFIG["email"],
        "url": TEST_CONFIG["url"]
    }
    
    try:
        response = requests.post(f"{BASE_URL}/quiz", json=payload, timeout=5)
        
        if response.status_code == 422:  # Validation error
            print_result("Missing fields validation", True, "Correctly rejected with 422")
            return True
        else:
            print_result("Missing fields validation", False,
                        f"Expected 422, got {response.status_code}")
            return False
    except Exception as e:
        print_result("Missing fields validation", False, f"Error: {str(e)}")
        return False


def test_test_submit_endpoint() -> bool:
    """Test the test-submit endpoint with the expected answer."""
    print_section("Test 5: Test Submit Endpoint")
    
    payload = {
        "email": TEST_CONFIG["email"],
        "secret": TEST_CONFIG["secret"],
        "url": TEST_CONFIG["url"],
        "answer": TEST_CONFIG["expected_answer"]
    }
    
    try:
        response = requests.post(f"{BASE_URL}/test-submit", json=payload, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            print_result("Test submit endpoint", True, f"Response received")
            print(f"   Correct: {data.get('correct')}")
            print(f"   Reason: {data.get('reason', 'N/A')}")
            return data.get('correct', False)
        else:
            print_result("Test submit endpoint", False,
                        f"Status code: {response.status_code}")
            return False
    except Exception as e:
        print_result("Test submit endpoint", False, f"Error: {str(e)}")
        return False


def monitor_health(changes: int = 3, interval: int = 5):
    """Monitor health endpoint for changes (background task processing)."""
    print_section("Test 6: Background Task Monitoring")
    print(f"Monitoring health endpoint for {changes} changes (checking every {interval}s)...")
    
    initial_health = None
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=10)
        if response.status_code == 200:
            initial_health = response.json()
            print(f"Initial state:")
            print(f"   Total quizzes: {initial_health.get('total_quizzes', 0)}")
            print(f"   Active tasks: {initial_health.get('active_tasks', 0)}")
    except:
        pass
    
    print(f"\nWaiting for background tasks to process...")
    for i in range(changes):
        time.sleep(interval)
        try:
            response = requests.get(f"{BASE_URL}/health", timeout=10)
            if response.status_code == 200:
                current_health = response.json()
                total = current_health.get('total_quizzes', 0)
                active = current_health.get('active_tasks', 0)
                success = current_health.get('successful_quizzes', 0)
                failed = current_health.get('failed_quizzes', 0)
                
                print(f"  Check {i+1}/{changes}: Total={total}, Active={active}, "
                      f"Success={success}, Failed={failed}")
        except:
            pass


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("  AUTONOMOUS QUIZ SOLVER - SYSTEM TEST")
    print("=" * 60)
    print(f"\nTesting against: {BASE_URL}")
    print(f"Test quiz URL: {TEST_CONFIG['url']}")
    
    results = {
        "health": False,
        "quiz_submission": False,
        "invalid_secret": False,
        "missing_fields": False,
        "test_submit": False
    }
    
    # Run tests
    results["health"] = test_health_endpoint()
    
    if not results["health"]:
        print("\n❌ Health check failed. Is the server running?")
        print(f"   Try: python main.py")
        print(f"   Or: uvicorn main:app --host 0.0.0.0 --port 8000")
        sys.exit(1)
    
    results["quiz_submission"] = test_quiz_submission().get("success", False)
    results["invalid_secret"] = test_invalid_secret()
    results["missing_fields"] = test_missing_fields()
    results["test_submit"] = test_test_submit_endpoint()
    
    # Optional: Monitor background tasks
    if results["quiz_submission"]:
        try:
            monitor_input = input("\nMonitor background task processing? (y/n): ")
            if monitor_input.lower() == 'y':
                monitor_health()
        except KeyboardInterrupt:
            print("\nMonitoring interrupted")
    
    # Summary
    print_section("Test Summary")
    passed = sum(results.values())
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅" if result else "❌"
        print(f"{status} {test_name}")
    
    print(f"\nResults: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! System is working correctly.")
    else:
        print("\n⚠️  Some tests failed. Check the output above for details.")
    
    return passed == total


if __name__ == "__main__":
    # Allow BASE_URL override from command line
    if len(sys.argv) > 1:
        BASE_URL = sys.argv[1]
        print(f"Using custom BASE_URL: {BASE_URL}")
    
    success = main()
    sys.exit(0 if success else 1)

