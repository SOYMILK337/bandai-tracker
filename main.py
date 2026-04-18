import os
import requests
import time
import re
from bs4 import BeautifulSoup
import urllib.parse
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

# 시작 시각 기록
start_time = time.time()
print("🚀 [System] 스텔스 병렬 탐색 엔진 가동!")

token = os.environ.get('TELEGRAM_TOKEN')
chat_id = os.environ.get('TELEGRAM_CHAT_ID')
github_pat = os.environ.get('MY_GITHUB_PAT')
repo_full_name = os.environ.get('GITHUB_REPOSITORY') 
GOOGLE_PROXY_URL = "https://script.google.com/macros/s/AKfycbwHH20V6XscVYYIek80dI0symQT3P3cnCZkqqCyGijhpjOkNNzbQsvUR5oNyU0ndUMR/exec"

# 데이터 저장소
known_in_stock_ids = set()
all_seen_names = {}
category_counts = {}

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
    if not github_pat or not repo_full_name: return
    url = f"https://api.telegram.org/repos/{repo_full_name}/dispatches"
    headers = {"Authorization": f"token {github_pat}", "Accept": "application/vnd.github.v3+json"}
    data = {"event_type": "restart_bot"}
    try: requests.post(url, headers=headers, json=data)
    except: pass

def clean_product_name(raw_name):
    clean = re.sub(r'좋아요|장바구니|\d{1,3}(,\d{3})*원', '', raw_name)
    return clean.strip()

def check_commands():
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
                    if cmd == "/상태": status_report_requested = True
                    elif cmd == "/추적상품확인": confirmation_requested = True
    except: pass

def scan_target_parallel(task):
    """병렬 실행용 함수: 결과 취합을 위해 라벨과 데이터를 함께 반환"""
    url = task['url']
    label = task['label']
    local_data = {}
    try:
        encoded_url = urllib.parse.quote(url, safe='')
        proxy_url = f"{GOOGLE_PROXY_URL}?url={encoded_url}"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
        response = requests.get(proxy_url, headers=headers, timeout=30)
        
        if len(response.text) < 1000: return label, {}
        
        soup = BeautifulSoup(response.text, 'html.parser')
        product_links = soup.find_all('a', href=re.compile(r'gno=\d+'))
        
        for link in product_links:
            p_id = link['href'].split('gno=')[-1].split('&')[0]
            raw_name = link.get_text(strip=True)
            if len(raw_name) < 10: continue
            local_data[p_id] = clean_product_name(raw_name)
        return label, local_data
    except: return label, {}

if __name__ == "__main__":
    if os.path.exists("list.txt"):
        tasks = []
        current_label = "기타"
        with open("list.txt", "r") as f:
            for line in f:
                line = line.strip()
                if line.startswith("#"): current_label = line.replace("#", "").strip()
                elif line: tasks.append({"url": line, "label": current_label})
        
        send_message("🛡️ 스텔스 병렬 감시 엔진 출격! (안전 휴식 모드 적용)")
        session = requests.Session()
        
        while True:
            # 6시간 주기 릴레이 체크
            if time.time() - start_time > 21000:
                restart_myself()
                break

            cycle_count += 1
            cycle_data = {} 
            category_counts = {} 
            
            # 1. 병렬 스캔 (5개 채널 동시 타격)
            with ThreadPoolExecutor(max_workers=5) as executor:
                results = list(executor.map(scan_target_parallel, tasks))
            
            # 2. 데이터 통합
            for label, data in results:
                cycle_data.update(data)
                category_counts[label] = category_counts.get(label, 0) + len(data)
                all_seen_names.update(data)
            
            last_check_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            current_ids = set(cycle_data.keys())
            
            # 3. 변화 감지 (2회차부터)
            if cycle_count > 1:
                new_restocked = [cycle_data[pid] for pid in (current_ids - known_in_stock_ids)]
                sold_out_items = [all_seen_names[pid] for pid in (known_in_stock_ids - current_ids)]
                
                if new_restocked:
                    for i in range(0, len(new_restocked), 30):
                        send_message(f"🚨 [재입고 포착]\n" + "\n".join([f"{idx+1}. {name}" for idx, name in enumerate(new_restocked[i:i+30])]))
                
                if sold_out_items:
                    for i in range(0, len(sold_out_items), 30):
