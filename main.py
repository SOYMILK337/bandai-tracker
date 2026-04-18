import os
import requests
import time
import re
import json
from bs4 import BeautifulSoup
import urllib.parse
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

start_time = time.time()

print("🚀 [System] 4계정 쿼드 하이퍼 엔진 가동! (오용진님 전용)")

# ==========================================
# 🚨 [수정 필수] 2~4번째 구글 계정 ID를 아래에 마저 채워주세요!
# ==========================================
PROXY_IDS = [
    "AKfycbwHH20V6XscVYYIek80dI0symQT3P3cnCZkqqCyGijhpjOkNNzbQsvUR5oNyU0ndUMR", # 기존 ID
    "AKfycbx57aFHKqx9QzC98TwPNLxDRs158W0Prnb8cZEjn5-n3udOlQ3CqKCgdIVt9at1UQ9X",
    "AKfycbwUJTb02XOUbV-obvpE7WXRdDn9AxJl5H-KWb-kRxCVqQ3AJpkuBFokAoxwkhp_gWXB",
    "AKfycbxVaQC2Y3ZUYFsls80Ny4aKZS_3zzbPxsNtZQnUUQOnulyfZQ5rf7n0uq29wYBVHpnMIw"
]
# ==========================================

proxy_index = 0
token = os.environ.get('TELEGRAM_TOKEN')
chat_id = os.environ.get('TELEGRAM_CHAT_ID')
github_pat = os.environ.get('MY_GITHUB_PAT')
repo_full_name = os.environ.get('GITHUB_REPOSITORY') 

known_in_stock_ids = set()
all_seen_names = {}
category_counts = {}
current_tracked_names = {}
last_bnkr_time, last_naver_time = "대기 중", "대기 중"
cycle_count = 0
last_update_id = -1

def send_message(text):
    url = "https://api.telegram.org/bot" + str(token) + "/sendMessage"
    try: requests.post(url, data={'chat_id': chat_id, 'text': text}, timeout=10)
    except: pass

def restart_myself():
    if not github_pat or not repo_full_name: return
    url = "https://api.telegram.org/repos/" + str(repo_full_name) + "/dispatches"
    headers = {"Authorization": "token " + str(github_pat), "Accept": "application/vnd.github.v3+json"}
    try: requests.post(url, headers=headers, json={"event_type": "restart_bot"}, timeout=10)
    except: pass

def clean_product_name(raw_name):
    p = r'좋아요|장바구니|\d{1,3}(,\d{3})*원|구매진행중|예약진행중|오픈예정|품절|\d{2}\.\d{2}까지'
    return re.sub(p, '', raw_name).strip()

def check_commands():
    global last_update_id
    try:
        url = "https://api.telegram.org/bot" + str(token) + "/getUpdates"
        res = requests.get(url, params={'offset': last_update_id + 1, 'timeout': 1}, timeout=5)
        response = res.json()
        if not response.get("ok"): return
        for update in response["result"]:
            last_update_id = update["update_id"]
            if "message" in update and "text" in update["message"]:
                cmd = update["message"]["text"]
                if cmd == "/상태":
                    msg = "📊 [8만건 하이퍼 엔진 상태]\n✅ 본진: " + last_bnkr_time + "\n✅ 네이버: " + last_naver_time + "\n\n"
                    msg += "\n".join(["📍 " + str(l) + ": " + str(c) + "개" for l, c in category_counts.items()])
                    send_message(msg + "\n\n📦 총합: " + str(len(known_in_stock_ids)) + "개\n⏱️ 주기: 약 22초")
    except: pass

def scan_target_parallel(task):
    global proxy_index
    url, label = task['url'], task['label']
    try:
        current_id = PROXY_IDS[proxy_index % len(PROXY_IDS)]
        proxy_index += 1
        proxy_url = "https://script.google.com/macros/s/" + current_id + "/exec?url=" + urllib.parse.quote(url, safe='')
        res = requests.get(proxy_url, headers={'User-Agent': 'Mozilla/5.0 Chrome/120.0.0.0'}, timeout=30)
        if len(res.text) < 1000: return label, {}, url
        soup = BeautifulSoup(res.text, 'html.parser')
        local_data = {}
        if "naver.com" in url:
            links = soup.find_all('a', href=re.compile(r'/bandai/products/\d+'))
            for link in links:
                if not link.get('href') or '품절' in link.get_text(): continue
                p_id = "N_" + link.get('href').split('/')[-1].split('?')[0]
                attr = link.get('data-shp-' + 'contents-dtl')
                if attr:
                    for item in json.loads(attr):
                        if item.get('key') == 'chnl_prod_nm':
                            local_data[p_id] = clean_product_name(item.get('value')); break
        else:
            links = soup.find_all('a', href=re.compile(r'gno=\d+'))
            for link in links:
                p_id = "B_" + link['href'].split('gno=')[-1].split('&')[0]
                if len(link.get_text(strip=True)) >= 10:
                    local_data[p_id] = clean_product_name(link.get_text(strip=True))
        return label, local_data, url
    except: return label, {}, url

if __name__ == "__main__":
    tasks = []
    current_label = "기타"
    with open("list.txt", "r") as f:
        for line in f:
            line = line.strip()
            if line.startswith("#"): current_label = line.replace("#", "").strip()
            elif line: tasks.append({"url": line, "label": current_label})
    
    send_message("🤖 하이퍼 쿼드 엔진 가동! (22초 주기 무한 감시)")
    
    while True:
        if time.time() - start_time > 21000: restart_myself(); break
        cycle_count += 1
        cycle_data, category_counts = {}, {}
        with ThreadPoolExecutor(max_workers=20) as ex:
            results = list(ex.map(scan_target_parallel, tasks))
        
        now_str = datetime.now().strftime('%H:%M:%S')
        for label, data, url in results:
            cycle_data.update(data)
            category_counts[label] = category_counts.get(label, 0) + len(data)
            all_seen_names.update(data)
            if "naver.com" in url: last_naver_time = now_str
            else: last_bnkr_time = now_str
        
        current_ids = set(cycle_data.keys())
        if cycle_count > 1:
            new_ids = current_ids - known_in_stock_ids
            if new_ids:
                for i in range(0, len(new_ids), 30):
                    msg = "\n".join([("[네이버] " if pid.startswith("N_") else "[본진] ") + cycle_data[pid] for pid in list(new_ids)[i:i+30]])
                    send_message("🚨 [신규/재입고 포착]\n" + msg)
            gone_ids = known_in_stock_ids - current_ids
            if gone_ids:
                for i in range(0, len(gone_ids), 30):
                    msg = "\n".join([("[네이버] " if pid.startswith("N_") else "[본진] ") + all_seen_names[pid] for pid in list(gone_ids)[i:i+30]])
                    send_message("🗑️ [품절 포착]\n" + msg)

        known_in_stock_ids = current_ids
        current_tracked_names = cycle_data.copy()
        for _ in range(20):
            check_commands()
            time.sleep(0.5)
