import os
import requests
import time
import re
from bs4 import BeautifulSoup
import urllib.parse
from datetime import datetime

# 시작 시각 기록
start_time = time.time()

print("🚀 [System] 0초 공백 릴레이 감시 엔진 가동!")

token = os.environ.get('TELEGRAM_TOKEN')
chat_id = os.environ.get('TELEGRAM_CHAT_ID')
# 릴레이를 위한 토큰과 정보
github_pat = os.environ.get('MY_GITHUB_PAT')
repo_full_name = os.environ.get('GITHUB_REPOSITORY') # 예: username/repo_name

GOOGLE_PROXY_URL = "https://script.google.com/macros/s/AKfycbwHH20V6XscVYYIek80dI0symQT3P3cnCZkqqCyGijhpjOkNNzbQsvUR5oNyU0ndUMR/exec"

tracked_products = set() 
cycle_count = 0
last_update_id = -1
last_check_time = "대기 중..."
status_report_requested = False
confirmation_requested = False

def send_message(text):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {'chat_id': chat_id, 'text': text}
    try: requests.post(url, data=payload)
    except: pass

def restart_myself():
    """자신이 종료되기 전 다음 봇을 강제로 출격시킵니다."""
    if not github_pat or not repo_full_name:
        print("⚠️ [Relay] 토큰 정보가 없어 릴레이를 포기합니다.")
        return
    
    url = f"https://api.telegram.org/repos/{repo_full_name}/dispatches"
    headers = {
        "Authorization": f"token {github_pat}",
        "Accept": "application/vnd.github.v3+json"
    }
    data = {"event_type": "restart_bot"}
    
    try:
        r = requests.post(url, headers=headers, json=data)
        if r.status_code == 204:
            send_message("🔄 [Relay] 6시간 도달 전 다음 봇에게 바통을 터치했습니다!")
        else:
            print(f"❌ 릴레이 실패: {r.status_code}")
    except Exception as e:
        print(f"❌ 릴레이 에러: {e}")

# ... (기존 clean_product_name, check_commands, scan_target 함수 동일)

if __name__ == "__main__":
    if os.path.exists("list.txt"):
        with open("list.txt", "r") as f:
            tasks = []
            current_label = "기타"
            for line in f:
                line = line.strip()
                if line.startswith("#"): current_label = line.replace("#", "").strip()
                elif line: tasks.append({"url": line, "label": current_label})
        
        send_message(f"🤖 정밀 감시 시작! (0초 공백 릴레이 모드)")
        session = requests.Session()
        
        while True:
            # [핵심] 실행 시간이 5시간 50분(21000초)을 넘으면 릴레이 시작
            if time.time() - start_time > 21000:
                restart_myself()
                break # 현재 봇은 종료
            
            cycle_count += 1
            # ... (기존 감시 및 알림 로직 동일)
            
            for task in tasks:
                check_commands()
                scan_target(session, task["url"], task["label"], {}) # 중복 제거 로직 포함된 스캔
                time.sleep(2)
            
            # (생략: 기존 알림 및 보고 로직)
            
            print(f"⏳ {cycle_count}회차 완료.")
            for _ in range(10): # 쉬는 시간 단축
                check_commands()
                time.sleep(1)
