import os
import requests
import time
import re
from bs4 import BeautifulSoup
import urllib.parse
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

# 시작 시각 기록 (릴레이 구동용)
start_time = time.time()

print("🚀 [System] 구문 오류 수정 완료. 정밀 감시 엔진 재출격!")

# 환경 변수 로드
token = os.environ.get('TELEGRAM_TOKEN')
chat_id = os.environ.get('TELEGRAM_CHAT_ID')
github_pat = os.environ.get('MY_GITHUB_PAT')
repo_full_name = os.environ.get('GITHUB_REPOSITORY') 

GOOGLE_PROXY_URL = "https://script.google.com/macros/s/AKfycbwHH20V6XscVYYIek80dI0symQT3P3cnCZkqqCyGijhpjOkNNzbQsvUR5oNyU0ndUMR/exec"

# 데이터 저장소 초기화
known_in_stock_ids = set()
all_seen_names = {}
category_counts = {}

cycle_count = 0
last_update_id = -1
last_check_time = "대기 중..."
status_report_requested = False
confirmation_requested = False

def send_message(text):
    """텔레그램 메시지 전송"""
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {'chat_id': chat_id, 'text': text}
    try:
        requests.post(url, data=payload, timeout=10)
    except:
        pass

def restart_myself():
    """6시간 제한 전 바통 터치"""
    if not github_pat or not repo_full_name:
        return
    url = f"https://api.telegram.org/repos/{repo_full_name}/dispatches"
    headers = {"Authorization": f"token {github_pat}", "Accept": "application/vnd.github.v3+json"}
    data = {"event_type": "restart_bot"}
    try:
        requests.post(url, headers=headers, json=data, timeout=10)
    except:
        pass

def clean_product_name(raw_name):
    """상품명 노이즈 제거"""
    clean = re.sub(r'좋아요|장바구니|\d{1,3}(,\d{3})*원', '', raw_name)
    return clean.strip()

def check_commands():
    """사용자 명령어 확인"""
    global last_update_id, status_report_requested, confirmation_requested
    try:
        url = f"https://api.telegram.org/bot{token}/getUpdates"
        params = {'offset': last_update_id + 1, 'timeout': 1}
        response = requests.get(url, params=params, timeout=10).json()
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
    """병렬 스캔 핵심 로직"""
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
        product_links = soup.find_all('a', href=re.compile(r'gno=\d+'))
        
        for link in product_links:
            p_id = link['href'].split('gno=')[-1].split('&')[0]
            raw_name = link.get_text(strip=True)
            if len(raw_name) < 10:
                continue
            
            clean_name = clean_product_name(raw_name)
            local_data[p_id] = clean_name
            
        return label, local_data
    except:
        return label, {}

if __name__ == "__main__":
    if os.path.exists("list.txt"):
        tasks = []
        current_label = "기타"
        with open("list.txt", "r") as f:
            for line in f:
                line = line.strip()
                if line.startswith("#"):
                    current_label = line.replace("#", "").strip()
                elif line:
                    tasks.append({"url": line, "label": current_label})
        
        send_message("🤖 정밀 병렬 감시 시스템 재가동합니다.")
        session = requests.Session()
        
        while True:
            # 6시간 자동 릴레이
            if time.time() - start_time > 21000:
                restart_myself()
                break

            cycle_count += 1
            cycle_data = {} 
            category_counts = {} 
            
            # 병렬 스캔 (5개 동시 처리)
            with ThreadPoolExecutor(max_workers=5) as executor:
                results = list(executor.map(scan_target_parallel, tasks))
            
            # 결과 병합
            for label, data in results:
                cycle_data.update(data)
                category_counts[label] = category_counts.get(label, 0) + len(data)
                all_seen_names.update(data)
            
            last_check_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            current_ids = set(cycle_data.keys())
            
            # 2회차부터 실시간 변화 보고
            if cycle_count > 1:
                # 1. 재입고 체크
                new_ids = current_ids - known_in_stock_ids
                if new_ids:
                    new_list = [cycle_data[pid] for pid in new_ids]
                    for i in range(0, len(new_list), 30):
                        msg = "\n".join([f"{idx+1}. {name}" for idx, name in enumerate(new_list[i:i+30])])
                        send_message(f"🚨 [재입고 포착]\n{msg}")
                
                # 2. 품절 체크
                gone_ids = known_in_stock_ids - current_ids
                if gone_ids:
                    gone_list = [all_seen_names[pid] for pid in gone_ids]
                    for i in range(0, len(gone_list), 30):
                        msg = "\n".join([f"{idx+1}. {name}" for idx, name in enumerate(gone_list[i:i+30])])
                        send_message(f"🗑️ [품절 포착]\n{msg}")

            known_in_stock_ids = current_ids
            
            # 명령어 응답 처리
            if status_report_requested:
                sum_text = [f"📍 {l}: {c}개" for l, c in category_counts.items()]
                report = (f"📊 [감시 완료 보고]\n🔄 {cycle_count}회차\n" + "\n".join(sum_text) + 
                         f"\n\n📦 총합: {len(known_in_stock_ids)}개\n⏱️ 시각: {last_check_time}")
                send_message(report)
                status_report_requested = False
            
            if confirmation_requested:
                names = sorted(cycle_data.values())
                send_message(f"📂 현재 전체 목록 (총 {len(names)}개)")
                for i in range(0, len(names), 30):
                    msg = "\n".join([f"{i+idx+1}. {name}" for idx, name in enumerate(names[i:i+30])])
                    send_message(f"📋 [목록 {i//30 + 1}]\n{msg}")
                confirmation_requested = False
            
            # 스텔스 휴식 (7초)
            print(f"⏳ {cycle_count}회차 완료. 7초간
