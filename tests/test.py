import requests
import json

# app = FastAPI()

OPENAI_API_KEY = "sk-sp-iP9d7tGzkcMhgjkDVhhZ7XIhhZuTfZEGORVw0TlltsALWQq7"

# 建议尝试这个更完整的地址
TARGET_URL = "https://api.lkeap.cloud.tencent.com/coding/v3/chat/completions"
MODEL_NAME = "glm-5"

def test_api():
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "user", "content": "你好，请回复‘收到’"}
        ],
        "stream": False
    }
    
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }

    print(f"--- 正在发起测试 ---")
    print(f"目标地址: {TARGET_URL}")
    
    try:
        response = requests.post(TARGET_URL, headers=headers, json=payload, timeout=10)
        
        print(f"状态码: {response.status_code}")
        print(f"原始返回内容: {response.text}")
        
        if response.status_code == 200:
            print("✅ 恭喜！接口调用成功。")
            print(f"模型回复: {response.json()['choices'][0]['message']['content']}")
        elif response.status_code == 404:
            print("❌ 依然返回 404：请确认 URL。如果加上 /chat/completions 还报错，请登录腾讯云控制台确认该模型对应的 API Endpoint。")
        elif response.status_code == 401:
            print("❌ 返回 401：API Key 无效或已过期。")
            
    except Exception as e:
        print(f"❌ 请求发生异常: {e}")

if __name__ == "__main__":
    test_api()