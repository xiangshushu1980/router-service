import urllib.request
import urllib.error
import json

def test_router_server():
    url = "http://localhost:8000/v1/chat/completions"
    
    payload = {
        "model": "test-model",
        "messages": [
            {"role": "user", "content": "Hello, how are you?"}
        ],
        "temperature": 0.7
    }
    
    headers = {
        'Content-Type': 'application/json',
    }
    
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode('utf-8'),
            headers=headers,
            method='POST'
        )
        
        with urllib.request.urlopen(req) as response:
            response_data = response.read().decode('utf-8')
            response_json = json.loads(response_data)
            
            print("Response received:")
            print(json.dumps(response_json, indent=2))
            
            # 验证响应格式
            if "choices" in response_json:
                print("\n✓ Response format is correct")
                return True
            else:
                print("\n✗ Response format is incorrect")
                return False
                
    except urllib.error.HTTPError as e:
        print(f"HTTP Error: {e.code} - {e.reason}")
        return False
    except Exception as e:
        print(f"Error: {str(e)}")
        return False

if __name__ == "__main__":
    print("Testing Router server...")
    print("Make sure test_server.py and router_server.py are running")
    print("-" * 50)
    
    success = test_router_server()
    
    if success:
        print("\n✓ Test passed!")
    else:
        print("\n✗ Test failed!")