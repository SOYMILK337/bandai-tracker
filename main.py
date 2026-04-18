import os
import requests
import time
import re
from bs4 import BeautifulSoup
import urllib.parse
from datetime import datetime

# 시작 시각 기록 (릴레이용)
start_time = time.time()

print("🚀 [System] 오류 수정 및 릴레이 엔진 가동!")

# 환경 변수 설정
token = os.environ.get('TELEGRAM_TOKEN')
chat_id = os.environ.get('TELEGRAM_CHAT_ID')
github_pat = os.environ.get('MY_GITHUB_PAT')
repo_full_name = os.environ.get('GITHUB_REPOSITORY') 

GOOGLE_PROXY_URL = "https://script.google.com/macros/s/AKfycbwHH20V6XscVYYIek80dI0symQT3P3cnCZkqqCyGijhpjOkNNzbQsvUR5oNyU0ndUMR/exec"

# 데이터 저장소
known_in_stock_ids = set()      # 이미 알림을 보낸 재고 있는 상품 ID
current_tracked_names = {}      # 현재 리스트에 떠 있는 모든 상품명 (ID: Name)
category_counts = {}            # 등급별 상품 개수 집계용

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
    """6시간 종료 전 다음 봇을 깨웁니다."""
    if not github_pat or not repo_full_name:
        print("⚠️ [Relay] 토큰 정보가 없어 릴레이를 포기합니다.")
        return
    url = f"https://api.telegram.org/repos/{repo_full_name}/dispatches"
    headers = {"Authorization": f"token {github_pat}", "Accept": "application/vnd.github.v3+json"}
    data = {"event_type": "restart_bot"}
    try:
        r = requests.post(url, headers=headers, json=data)
        if r.status_code == 204:
            send_message("🔄 [Relay] 6시간 도달 전 다음 봇에게 바통을 터치했습니다!")
        else: print(f"❌ 릴레이 실패: {r.status_code}")
    except Exception as e: print(f"❌ 릴레이 에러: {e}")

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
                        send_message("🔍 명령 확인. 모든 페이지 스캔 후 등급별 요약을 보고하겠습니다.")
                    elif cmd == "/추적상품확인":
                        confirmation_requested = True
                        send_message("📋 명령 확인. 현재 추적 중인 전체 상품 목록을 준비하겠습니다.")
    except: pass

def scan_target(session, url, label, cycle_data):
    """개별 페이지 스캔"""
    global last_check_time
    try:
        encoded_url = urllib.parse.quote(url, safe='')
        proxy_url = f"{GOOGLE_PROXY_URL}?url={encoded_url}"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
        response = session.get(proxy_url, headers=headers, timeout=30)
        
        last_check_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        if len(response.text) < 1000: return
        
        soup = BeautifulSoup(response.text, 'html.parser')
        product_links = soup.find_all('a', href=re.compile(r'gno=\d+'))
        
        count = 0
        for link in product_links:
            p_id = link['href'].split('gno=')[-1].split('&')[0]
            raw_name = link.get_text(strip=True)
            if len(raw_name) < 10: continue
            
            clean_name = clean_product_name(raw_name)
            cycle_data[p_id] = clean_name
            count += 1
        category_counts[label] = category_counts.get(label, 0) + count
    except Exception as e: print(f"❌ 스캔 에러: {e}")

if __name__ == "__main__":
    if os.path.exists("list.txt"):
        tasks = []
        current_label = "기타"
        with open("list.txt", "r") as f:
            for line in f:
                line = line.strip()
                if line.startswith("#"): current_label = line.replace("#", "").strip()
                elif line: tasks.append({"url": line, "label": current_label})
        
        send_message(f"🤖 24시간 릴레이 감시 시스템 가동!")
        session = requests.Session()
        
        while True:
            # 6시간 종료 전 릴레이 (5시간 50분 기준)
            if time.time() - start_time > 21000:
                restart_myself()
                break

            cycle_count += 1
            cycle_data = {} 
            category_counts = {} 
            new_restocked = []
            
            for task in tasks:
                check_commands()
                scan_target(session, task["url"], task["label"], cycle_data)
                time.sleep(2)
            
            # 신규 재입고 분석
            for p_id, p_name in cycle_data.items():
                if p_id not in known_in_stock_ids:
                    new_restocked.append(p_name)
            
            known_in_stock_ids = set(cycle_data.keys())
            current_tracked_names = cycle_data.copy()
            
            # 1. 알림 보고 (신규 발생 시)
            if new_restocked:
                for i in range(0, len(new_restocked), 30):
                    chunk = new_restocked[i:i+30]
                    msg = [f"{i+idx+1}. {name}" for idx, name in enumerate(chunk)]
                    send_message(f"🚨 [재입고/신규 포착]\n" + "\n".join(msg))
                    time.sleep(0.5)
            
            # 2. /상태 보고
            if status_report_requested:
                summary = [f"📍 {label}: {count}개" for label, count in category_counts.items()]
                status_msg = (f"📊 [감시 완료 보고]\n🔄 {cycle_count}회차 완료\n" + "\n".join(summary) +
                            f"\n\n📦 총합: {len(known_in_stock_ids)}개\n⏱️ 시각: {last_check_time}")
                send_message(status_msg)
                status_report_requested = False
            
            # 3. /추적상품확인
            if confirmation_requested:
                sorted_names = sorted(current_tracked_names.values())
                send_message(f"📂 현재 전체 목록 (총 {len(sorted_names)}개)")
                for i in range(0, len(sorted_names), 30):
                    chunk = sorted_names[i:i+30]
                    msg = [f"{i+idx+1}. {name}" for idx, name in enumerate(chunk)]
                    send_message(f"📋 [목록 {i//30 + 1}]\n" + "\n".join(msg))
                    time.sleep(0.5)
                confirmation_requested = False
            
            print(f"⏳ {cycle_count}회차 완료. 인지: {len(known_in_stock_ids)}개.")
            for _ in range(10): # 쉬는 시간
                check_commands()
                time.sleep(1)
