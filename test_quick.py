"""
Quick test script for the specific quiz request.
Run this to quickly test your system.
"""
import requests
import json
import sys

# Your test configuration
BASE_URL = "http://127.0.0.1:8000"
QUIZ_REQUEST = {
    "email": "23f1002431@ds.study.iitm.ac.in",
    "secret": "qwertyisthis",
    "url": "https://tds-llm-analysis.s-anand.net/project2"
}

EXPECTED_ANSWER = "git add env.sample\ngit commit -m \"chore: keep env sample\""


def main():
    print("🚀 Quick Test - Quiz Solver System")
    print("-" * 50)
    
    # Override BASE_URL if provided
    if len(sys.argv) > 1:
        global BASE_URL
        BASE_URL = sys.argv[1]
    
    print(f"Server: {BASE_URL}")
    print(f"Quiz URL: {QUIZ_REQUEST['url']}\n")
    
    # 1. Health check
    print("1. Checking health...")
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Server is healthy")
            print(f"   📊 Uptime: {data.get('uptime_seconds', 0):.1f}s")
            print(f"   📈 Quizzes processed: {data.get('total_quizzes', 0)}")
        else:
            print(f"   ❌ Health check failed: {response.status_code}")
            return
    except Exception as e:
        print(f"   ❌ Cannot connect to server: {e}")
        print(f"   💡 Make sure the server is running:")
        print(f"      python main.py")
        return
    
    # 2. Submit quiz
    print("\n2. Submitting quiz...")
    try:
        response = requests.post(
            f"{BASE_URL}/quiz",
            json=QUIZ_REQUEST,
            timeout=5
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Quiz accepted!")
            print(f"   📝 Status: {data.get('status')}")
            print(f"   💬 Message: {data.get('message')}")
            
            task_id = data.get('task_id')
            if task_id:
                print(f"   🆔 Task ID: {task_id}")
            
            print(f"\n   ⏳ Quiz is processing in the background...")
            print(f"   📋 Check server logs to see progress")
            print(f"   🔍 Monitor with: python test_system.py")
            
        else:
            print(f"   ❌ Submission failed: {response.status_code}")
            print(f"   Response: {response.text}")
            
    except requests.exceptions.Timeout:
        print(f"   ✅ Request accepted (timeout expected for async processing)")
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return
    
    # 3. Test with expected answer (optional)
    print("\n3. Testing with expected answer...")
    test_payload = {
        **QUIZ_REQUEST,
        "answer": EXPECTED_ANSWER
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/test-submit",
            json=test_payload,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            is_correct = data.get('correct', False)
            if is_correct:
                print(f"   ✅ Answer is correct!")
            else:
                print(f"   ❌ Answer marked as incorrect")
                print(f"   Reason: {data.get('reason', 'N/A')}")
        else:
            print(f"   ⚠️  Test endpoint returned: {response.status_code}")
            
    except Exception as e:
        print(f"   ⚠️  Could not test answer: {e}")
    
    print("\n" + "-" * 50)
    print("✨ Test complete!")
    print("\n💡 Tips:")
    print("   - Watch server logs for quiz solving progress")
    print("   - Use test_system.py for comprehensive testing")
    print("   - Check /health endpoint for statistics")


if __name__ == "__main__":
    main()

