import os
import requests
import time
import re
import json
from bs4 import BeautifulSoup
import urllib.parse
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

# 시작 시각 기록
start_time = time.time()

print("🚀 [System] 10코어 분산 타격! 초고속 듀얼 엔진 가동!")

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
    p = r'좋아요|장바구니|\d{1,3}(,\d{3})*원|구매진행중|예약진행중|오픈예정|품절|\d{2}\.\d{2}까지'
    clean = re.sub(p, '', raw_name)
    return clean.strip()

def check_commands():
    global last_update_id
    try:
        url = f"https://api.telegram.org/bot{token}/getUpdates"
        params = {'offset': last_update_id + 1, 'timeout': 1}
        res = requests.get(url, params=params, timeout=10)
        response = res.json()
    except:
        return

    if not response or not response.get("ok") or not response.get("result"):
        return

    for update in response["result"]:
        last_update_id = update["update_id"]
        if "message" not in update or "text" not in update["message"]:
            continue
            
        cmd = update["message"]["text"]
        
        if cmd == "/상태":
            if cycle_count == 0:
                send_message("⏳ 첫 스캔이 진행 중입니다.")
            else:
                sum_text = [f"📍 {l}: {c}개" for l, c in category_counts.items()]
                msg = f"📊 [실시간 듀얼 보고]\n🔄 {cycle_count}회차\n" + "\n".join(sum_text) + f"\n\n📦 총합: {len(known_in_stock_ids)}개\n⏱️ 시각: {last_check_time}"
                send_message(msg)
                
        elif cmd == "/추적상품확인":
            if not current_tracked_names:
                send_message("⏳ 데이터 수집 중입니다.")
            else:
                sorted_items = []
                for pid, name in current_tracked_names.items():
                    tag = "[네이버]" if pid.startswith("N_") else "[본진]"
                    sorted_items.append(f"{tag} {name}")
                
                sorted_items.sort()
                send_message(f"📂 현재 전체 목록 (총 {len(sorted_items)}개)")
                for i in range(0, len(sorted_items), 30):
                    chunk = sorted_items[i:i+30]
                    msg = "\n".join([f"{i+idx+1}. {n}" for idx, n in enumerate(chunk)])
                    send_message(f"📋 [목록 {i//30 + 1}]\n{msg}")

def scan_target_parallel(task):
    url = task['url']
    label = task['label']
    try:
        encoded_url = urllib.parse.quote(url, safe='')
        proxy_url = GOOGLE_PROXY_URL + "?url=" + encoded_url
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36'}
        res = requests.get(proxy_url, headers=headers, timeout=30)
        if len(res.text) < 1000: return label, {}
        
        soup = BeautifulSoup(res.text, 'html.parser')
        local_data = {}
        
        if "naver.com" in url:
            links = soup.find_all('a', href=re.compile(r'/bandai/products/\d+'))
            for link in links:
                href = link.get('href')
                if not href or '품절' in link.get_text(): continue
                p_id = "N_" + href.split('/')[-1].split('?')[0]
                dtl = link.get('data-shp
