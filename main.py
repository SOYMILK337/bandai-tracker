import os
import requests
import time
import re
from bs4 import BeautifulSoup

# [진단용] 시작하자마자 바로 출력
print("🚀 [진단] 봇이 이제 막 엔진을 켰습니다!")

token = os.environ.get('TELEGRAM_TOKEN')
chat_id = os.environ.get('TELEGRAM_CHAT_ID')
GOOGLE_PROXY_URL = "https://script.google.com/macros/s/AKfycbwHH20V6XscVYYIek80dI0symQT3P3cnCZkqqCyGijhpjOkNNzbQsvUR5oNyU0ndUMR/exec"

if not token or not chat_id:
    print("❌ [에러] 텔레그램 토큰이나 ID 설정이 안 되어 있습니다!")
    exit()

tracked_products = {}
cycle_count = 0
last_update_id = -1

# ... (중간 함수들은 동일)

if __name__ == "__main__":
    print("🔍 [진단] 메인 함수 진입 완료")
    
    if os.path.exists("list.txt"):
        print("✅ [진단] list.txt 파일을 찾았습니다!")
        with open("list.txt", "r") as f:
            urls = [line.strip() for line in f.readlines() if line.strip()]
        
        if not urls:
            print("⚠️ [진단] list.txt 파일은 있는데 내용이 텅 비어있습니다!")
            exit()
            
        print(f"📡 감시 시작! 대상 페이지: {len(urls)}개")
        # ... (이후 while True 루프 동일)
    else:
        # 이 메시지가 로그에 찍힌다면 파일 위치가 잘못된 겁니다!
        print("❌ [진단 에러] list.txt 파일을 찾을 수 없습니다. 파일명을 확인하세요!")
