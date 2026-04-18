import os
import requests
import time
import re
import json
from bs4 import BeautifulSoup
import urllib.parse
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor

# 시작 시각 및 한국 표준시 설정
start_time = time.time()
KST = timezone(timedelta(hours=9))

print("🚀 [System] 무결점 고스트 방지 엔진 v2.0 가동!")

# ==========================================
# ✅ 프록시 ID 세팅 (오용진 님 계정 4개)
# ==========================================
PROXY_IDS = [
    "AKfycbwHH20V6XscVYYIek80dI0symQT3P3cnCZkqqCyGijhpjOkNNzbQsvUR5oNyU0ndUMR",
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
item_to_label = {} # 상품 ID별 카테고리 매핑
all_seen_names = {}
last_bnkr_time, last_naver_time = "대기 중", "대기 중"
cycle_count = 0
last_update_id = -1

def send_message(text):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try: requests.post(url, data={'chat_id': chat_id, 'text': text}, timeout=10)
    except: pass

def restart_myself():
    if not github_pat or not repo_full_name: return
    url = f"https://api.telegram.org/repos/{repo_full_name}/dispatches"
    headers = {"Authorization": f"token {github_pat}", "Accept": "application/vnd.github.v3+json"}
    try: requests.post(url, headers=headers, json={"event_type": "restart_bot"}, timeout=10)
    except: pass

def clean_product_name(raw_name):
    p = r'좋아요|장바구니|\d{1,3}(,\d{3})*원|구매진행중|예약진행중|오픈예정|품절|\d{2}\.\d{2}까지'
    return re.sub(p, '', raw_name).strip()

def check_commands():
    global last_update_id
    try:
        url = f"https://api.telegram.org/bot{token}/getUpdates"
        res = requests.get(url, params={'offset': last_update_id + 1, 'timeout': 0.5}, timeout=5)
        response = res.json()
        if not response or not response.get("ok"): return
        for update in response["result"]:
            last_update_id = update["update_id"]
            if "message" in update and "text" in update["message"]:
                cmd = update["message"]["text"]
                if cmd == "/상태":
                    msg = "📊 [정밀 엔진 V2 상태 보고]\n✅ 본진: " + last_bnkr_time + "\n✅ 네이버: " + last_naver_time + "\n\n"
                    msg += "\n".join([f"📍 {l}: {c}개" for l, c in category_counts.items()])
                    send_message(msg + f"\n\n📦 총합: {len(known_in_stock_ids)}개\n⏱️ 주기: 약 21~22초")
    except: pass

def scan_target_parallel(task):
    global proxy_index
    url, label = task['url'], task['label']
    for attempt in range(2):
        try:
            current_id = PROXY_IDS[proxy_index % len(PROXY_IDS)]
            proxy_index += 1
            proxy_url = f"https://script.google.com/macros/s/{current_id}/exec?url=" + urllib.parse.quote(url, safe='')
            res = requests.get(proxy_url, headers={'User-Agent': 'Mozilla/5.0 Chrome/120.0.0'}, timeout=25)
            if len(res.text) < 1000:
                time.sleep(1); continue
            
            soup = BeautifulSoup(res.text, 'html.parser')
            local_data = {}
            if "naver.com" in url:
                links = soup.find_all('a', href=re.compile(r'/bandai/products/\d+'))
                for link in links:
                    if not link.get('href') or '품절' in link.get_text(): continue
                    p_id = "N_" + link.get('href').split('/')[-1].split('?')[0]
                    attr = link.get('data-shp-contents-dtl')
                    if attr:
                        try:
                            for item in json.loads(attr):
                                if item.get('key') == 'chnl_prod_nm':
                                    local_data[p_id] = clean_product_name(item.get('value')); break
                        except: pass
            else:
                links = soup.find_all('a', href=re.compile(r'gno=\d+'))
                for link in links:
                    p_id = "B_" + link['href'].split('gno=')[-1].split('&')[0]
                    if len(link.get_text(strip=True)) >= 10:
                        local_data[p_id] = clean_product_name(link.get_text(strip=True))
            return label, local_data, url, True
        except:
            time.sleep(1); continue
    return label, {}, url, False

if __name__ == "__main__":
    tasks = []
    current_label = "기타"
    with open("list.txt", "r") as f:
        for line in f:
            line = line.strip()
            if line.startswith("#"): current_label = line.replace("#", "").strip()
            elif line: tasks.append({"url": line, "label": current_label})
    
    send_message("🤖 무결점 엔진 출격! 골든타임 보호 및 고스트 차단 가동.")
    
    while True:
        now_kst = datetime.now(KST)
        curr_hm = now_kst.hour * 100 + now_kst.minute
        elapsed = time.time() - start_time
        
        # 골든타임 리셋 로직
        if 1435 <= curr_hm <= 1445 and elapsed > 3600: restart_myself(); break
        if elapsed > 21000:
            if not (1450 <= curr_hm <= 1615): restart_myself(); break
            elif elapsed > 21300: restart_myself(); break

        cycle_count += 1
        with ThreadPoolExecutor(max_workers=20) as ex:
            results = list(ex.map(scan_target_parallel, tasks))
        
        now_str = datetime.now(KST).strftime('%H:%M:%S')
        cycle_data, category_counts = {}, {}
        success_labels = set()
        filtered_gone_ids = [] # 변수 범위 에러 방지를 위해 초기화
        
        for label, data, url, is_success in results:
            if is_success:
                cycle_data.update(data)
                success_labels.add(label)
                category_counts[label] = category_counts.get(label, 0) + len(data)
                for pid in data: 
                    item_to_label[pid] = label
                    all_seen_names[pid] = data[pid]
                if "naver.com" in url: last_naver_time = now_str
                else: last_bnkr_time = now_str
        
        current_ids = set(cycle_data.keys())
        event_time = datetime.now(KST).strftime('%H:%M:%S')

        if cycle_count > 1:
            # 신규 포착
            new_ids = current_ids - known_in_stock_ids
            if new_ids:
                new_list = [("[네이버] " if pid.startswith("N_") else "[본진] ") + cycle_data[pid] for pid in new_ids]
                for i in range(0, len(new_list), 30):
                    send_message(f"🚨 [신규/재입고 포착] ({event_time})\n" + "\n".join([f"{idx+1}. {n}" for idx, n in enumerate(new_list[i:i+30])]))
            
            # 품절 포착 (성공한 카테고리만 대상으로 정밀 검사)
            gone_ids = known_in_stock_ids - current_ids
            filtered_gone_ids = [pid for pid in gone_ids if item_to_label.get(pid) in success_labels]
            
            if filtered_gone_ids:
                gone_list = [("[네이버] " if pid.startswith("N_") else "[본진] ") + all_seen_names[pid] for pid in filtered_gone_ids]
                for i in range(0, len(gone_list), 30):
                    send_message(f"🗑️ [품절 포착] ({event_time})\n" + "\n".join([f"{idx+1}. {n}" for idx, n in enumerate(gone_list[i:i+30])]))

        # 메모리 업데이트
        if cycle_count == 1:
            known_in_stock_ids = current_ids
        else:
            for pid in current_ids: known_in_stock_ids.add(pid)
            for pid in filtered_gone_ids: known_in_stock_ids.discard(pid)

        # 14초 대기 (2초마다 명령어 체크)
        for _ in range(7):
            check_commands()
            time.sleep(2)
