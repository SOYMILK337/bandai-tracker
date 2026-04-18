import os
import requests
import time
import re
from bs4 import BeautifulSoup
import urllib.parse
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

# 시작 시각 기록 (릴레이용)
start_time = time.time()

print("🚀 [System] 들여쓰기 오류 수정 및 스텔스 엔진 재출격!")

# 환경 변수 설정
token = os.environ.get('TELEGRAM_TOKEN')
chat_id = os.environ.get('TELEGRAM_CHAT_ID')
github_pat = os.environ.get('MY_GITHUB_PAT')
repo_full_name = os.environ.get('GITHUB_REPOSITORY') 

GOOGLE_PROXY_URL = "https://script.google.com/macros/s/AKfycbwHH20V6XscVYYIek80dI0symQT3P3cnCZkqqCyGijhpjOkNNzbQsvUR5oNyU0ndUMR/exec"

# 데이터 저장소
known_in_stock_ids = set()      # 현재 재고가 있는 것으로 파악된 ID들
all_seen_names = {}             # 품절 시 이름을 불러오기 위한 저장소 (ID: Name)
category_counts = {}            # 등급별 수치 요약용

cycle_count = 0
last_update_id = -1
last_check_time = "대기 중..."
status_report_requested = False
confirmation_requested = False

def send_message(text):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {'chat_id': chat_id, 'text': text}
    try:
        requests.post(url, data=payload)
    except:
        pass

def restart_myself():
    """6시간 종료 전 다음 봇 호출"""
    if not github_pat or not repo_full_name:
        return
    url = f"https://api.telegram.org/repos/{repo_full_name}/dispatches"
    headers = {"Authorization": f"token {github_pat}", "Accept": "application/vnd.github.v3+json"}
    data = {"event_type": "restart_bot"}
    try:
        requests.post(url, headers=headers, json=data)
    except:
        pass

def clean_product_name(raw_name):
    """노이즈 제거 및 상품명 정제"""
    clean = re.sub(r'좋아요|장바구니|\d{1,3}(,\d{3})*원', '', raw_name)
    return clean.strip()

def check_commands():
    """사용자 명령 확인"""
    global last_update_id, status_report_requested, confirmation_requested
    try:
        url = f"https://api.telegram.org/bot{token}/getUpdates"
        params = {'offset': last_update_id + 1, 'timeout': 1}
        response = requests.get(url, params=params).json()
        if response.get("ok") and response.get("result"):
            for update in response["result"]:
                last_update_id = update["update_id"]
                if "message" in update and "text" in update["message"]:
                    cmd = update["message"]["text"]
                    if cmd == "/상태":
                        status_report_requested = True
                    elif cmd == "/추적상품확인":
                        confirmation_requested = True
    except:
        pass

def scan_target_parallel(task):
    """병렬 스캔 함수"""
    url = task['url']
    label = task['label']
    local_data = {}
    try:
        encoded_url = urllib.parse.quote(url, safe='')
        proxy_url = f"{GOOGLE_PROXY_URL}?url={encoded_url}"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
        response = requests.get(proxy_url, headers=headers, timeout=30)
        
        if len(response.text) < 1000:
            return label, {}
        
        soup = BeautifulSoup(response.text, 'html.parser')
