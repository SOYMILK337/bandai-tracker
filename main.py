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

print("🚀 [System] 들여쓰기 구조 전면 개편. 안정성 100% 엔진 가동!")

token = os.environ.get('TELEGRAM_TOKEN')
chat_id = os.environ.get('TELEGRAM_CHAT_ID')
github_pat = os.environ.get('MY_GITHUB_PAT')
repo_full_name = os.environ.get('GITHUB_REPOSITORY') 

GOOGLE_PROXY_URL = "https://script.google.com/macros/s/AKfycbwHH20V6XscVYYIek80dI0symQT3P3cnCZkqqCyGijhpjOkNNzbQsvUR5oNyU0ndUMR/exec"

known_in_stock_ids = set()
all_seen_names = {}
category_counts = {}
current_tracked_names = {}

cycle_count = 0
last_update_id = -1
last_check_time = "대기 중..."

def send_message(text):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {'chat_id': chat_id, 'text': text}
    try:
        requests.post(url, data=payload, timeout=10)
    except:
        pass

def restart_myself():
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
    clean = re.sub(r'좋아요|장바구니|\d{1,3}(,\d{3})*원|구매진행중|예약진행중|오픈예정|품절|\d{2}\.\d{2}까지', '', raw_name)
    return clean.strip()

def check_commands():
    global last_update_id
    
    # 1. 텔레그램 명령 가져오기 (오류 방지를 위해 통신과 분석 분리)
    try:
        url = f"https://api.telegram.org/bot{token}/getUpdates"
        params = {'offset': last_update_id + 1, 'timeout': 1}
        res = requests.get(url, params=params, timeout=10)
        response = res.json()
    except:
        return

    if not response or not response.get("ok") or not response.get("result"):
        return

    # 2. 명령어 분석 및 즉시 응답
    for update in response["result"]:
        last_update_id = update["update_id"]
        if "message" not in update or "text" not in update["message"]:
            continue
            
        cmd = update["message"]["text"]
        
        if cmd == "/상태":
            if cycle_count == 0:
                send_message("⏳ 현재 첫 번째 정밀 스캔을 진행 중입니다. 잠시만 기다려주세요!")
            else:
                sum_text = [f"📍 {l}: {c}개" for l, c in category_counts.items()]
                report = f"📊 [실시간 즉시 보고]\n🔄 현재 {cycle_count}회차 정보\n" + "\n".join(sum_text) + f"\n\n📦 총합: {len(known_in_stock_ids)}개\n⏱️ 마지막 시각: {last_check_time}"
                send_message(report)
                
        elif cmd == "/추적상품확인":
            if not current_tracked_names:
                send_message("⏳ 데이터 수집 중입니다. 첫 사이클 완료 후 다시 시도해주세요.")
            else:
                names = sorted(current_tracked_names.values())
                send_message(f"📂 현재 전체 목록 (총 {len(names)}개)")
                for i in range(0, len(names), 30):
                    chunk = names[i:i+30]
                    msg = "\n".join([f"{i+idx+1}. {name}" for idx, name in enumerate(chunk)])
                    send_message(f"📋 [목록 {i//30 + 1}]\n{msg}")

def scan_target_parallel(task):
    url = task['url']
    label = task['label']
    try:
        encoded_url = urllib.parse.quote(url, safe='')
        proxy_url = f"{GOOGLE_PROXY_URL}?url={encoded_url}"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
        
        res = requests.get(proxy_url, headers=headers, timeout=30)
        
        if len(res.text) < 1000:
            return label, {}
        
        soup = BeautifulSoup(res.text, 'html.parser')
        product_links = soup.find_all('a', href=re.compile(r'gno=\d+'))
        
        local_data = {}
        for link in product_links:
            p_id = link['href'].split('gno=')[-1].split('&')[0]
            raw_name = link.get_text(strip=True)
            if len(raw_name) >= 10:
                local_data[p_id] = clean_product_name(raw_name)
                
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
        
        send_message("🤖 프반+일반 듀얼 병렬 감시 시스템 가동! (오류 방지 적용)")
        session = requests.Session()
        
        while True:
