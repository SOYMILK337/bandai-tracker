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

print("🚀 [System] 상태 보고 로직 최적화 완료! 엔진 재출격!")

token = os.environ.get('TELEGRAM_TOKEN')
chat_id = os.environ.get('TELEGRAM_CHAT_ID')
github_pat = os.environ.get('MY_GITHUB_PAT')
repo_full_name = os.environ.get('GITHUB_REPOSITORY') 

G_URL = "https://script.google.com/macros/s/"
G_ID = "AKfycbwHH20V6XscVYYIek80dI0symQT3P3cnCZkqqCyGijhpjOkNNzbQsvUR5oNyU0ndUMR"
GOOGLE_PROXY_URL = G_URL + G_ID + "/exec"

known_in_stock_ids = set()
all_seen_names = {}
category_counts = {}
current_tracked_names = {}

# 몰별 마지막 스캔 시각 저장
last_bnkr_time = "대기 중"
last_naver_time = "대기 중"

cycle_count = 0
last_update_id = -1

def send_message(text):
    url = "https://api.telegram.org/bot" + str(token) + "/sendMessage"
    payload = {'chat_id': chat_id, 'text': text}
    try:
        requests.post(url, data=payload, timeout=10)
    except:
        pass

def restart_myself():
    if not github_pat or not repo_full_name: return
    url = "https://api.telegram.org/repos/" + str(repo_full_name) + "/dispatches"
    headers = {
        "Authorization": "token " + str(github_pat),
        "Accept": "application/vnd.github.v3+json"
    }
    data = {"event_type": "restart_bot"}
    try:
        requests.post(url, headers=headers, json=data, timeout=10)
    except:
        pass

def clean_product_name(raw_name):
    p1 = r'좋아요|장바구니|\d{1,3}(,\d{3})*원|'
    p2 = r'구매진행중|예약진행중|오픈예정|품절|\d{2}\.\d{2}까지'
    clean = re.sub(p1 + p2, '', raw_name)
    return clean.strip()

def check_commands():
    global last_update_id
    try:
        url = "https://api.telegram.org/bot" + str(token) + "/getUpdates"
        params = {'offset': last_update_id + 1, 'timeout': 1}
        res = requests.get(url, params=params, timeout=10)
        response = res.json()
    except:
        return

    if not response or not response.get("ok") or not response.get("result"): return

    for update in response["result"]:
        last_update_id = update["update_id"]
        if "message" not in update or "text" not in update["message"]: continue
            
        cmd = update["message"]["text"]
        
        if cmd == "/상태":
            if cycle_count == 0:
                send_message("⏳ 첫 번째 정밀 스캔을 진행 중입니다...")
            else:
                # 상태 메시지 구성
                status_bnkr = "✅ 반다이몰: 정상 가동 (" + last_bnkr_time + ")"
                status_naver = "✅ 네이버몰: 정상 가동 (" + last_naver_time + ")"
                
                sum_text = ["📍 " + str(l) + ": " + str(c) + "개" for l, c in category_counts.items()]
                
                msg_head = "📊 [시스템 정밀 감시 상태]\n"
                msg_status = status_bnkr + "\n" + status_naver + "\n\n"
                msg_list = "\n".join(sum_text) + "\n\n"
                msg_foot = "📦 총 감시 상품: " + str(len(known_in_stock_ids)) + "개"
                
                send_message(msg_head + msg_status + msg_list + msg_foot)
                
        elif cmd == "/추적상품확인":
            if not current_tracked_names:
                send_message("⏳ 데이터를 수집 중입니다.")
            else:
                sorted_items = []
                for pid, name in current_tracked_names.items():
                    tag = "[네이버]" if pid.startswith("N_") else "[본진]"
                    sorted_items.append(tag + " " + name)
                
                sorted_items.sort()
                send_message("📂 전체 감시 목록 (총 " + str(len(sorted_items)) + "개)")
                for i in range(0, len(sorted_items), 30):
                    chunk = sorted_items[i:i+30]
                    msg = "\n".join([str(i+idx+1) + ". " + n for idx, n in enumerate(chunk)])
                    send_message("📋 [목록 " + str(i//30 + 1) + "]\n" + msg)

def scan_target_parallel(task):
    url = task['url']
    label = task['label']
    try:
        encoded_url = urllib.parse.quote(url, safe='')
        proxy_url = GOOGLE_PROXY_URL + "?url=" + encoded_url
        ua1 = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        ua2 = 'Chrome/120.0.0.0 Safari/537.36'
        headers = {'User-Agent': ua1 + ua2}
        
        res = requests.get(proxy_url, headers=headers, timeout=30)
        if len(res.text) < 1000: return label, {}, url
        
        soup = BeautifulSoup(res.text, 'html.parser')
        local_data = {}
        
        if "naver.com" in url:
            n_reg = r'/bandai/products/\d+'
            links = soup.find_all('a', href=re.compile(n_reg))
            for link in links:
                href = link.get('href')
                if not href or '품절' in link.get_text(): continue
                p_id = "N_" + href.split('/')[-1].split('?')[0]
                attr_name = 'data-shp-' + 'contents-dtl'
                dtl = link.get(attr_name)
                if dtl:
                    try:
                        dtl_data = json.loads(dtl)
                        for item in dtl_data:
                            if item.get('key') == 'chnl_prod_nm':
                                local_data[p_id] = clean_product_name(item.get('value'))
                                break
                    except: pass
        else:
            links = soup.find_all('a', href=re.compile(r'gno=\d+'))
            for link in links:
                p_id = "B_" + link['href'].split('gno=')[-1].split('&')[0]
                raw_name = link.get_text(strip=True)
                if len(raw_name) >= 10:
                    local_data[p_id] = clean_product_name(raw_name)
        return label, local_data, url
    except:
        return label, {}, url

if __name__ == "__main__":
    if not os.path.exists("list.txt"): exit(1)
    tasks = []
    current_label = "기타"
    with open("list.txt", "r") as f:
        for line in f:
            line = line.strip()
            if line.startswith("#"): current_label = line.replace("#", "").strip()
            elif line: tasks.append({"url": line, "label": current_label})
    
    send_message("🤖 상태 보고 기능이 업그레이드된 봇이 출격합니다!")
    session = requests.Session()
    
    while True:
        if time.time() - start_time > 21000: restart_myself(); break
        cycle_count += 1
        cycle_data, category_counts = {}, {}
        
        with ThreadPoolExecutor(max_workers=10) as ex:
            results = list(ex.map(scan_target_parallel, tasks))
        
        now_str = datetime.now().strftime('%H:%M:%S')
        
        for label, data, url in results:
            cycle_data.update(data)
            category_counts[label] = category_counts.get(label, 0) + len(data)
            all_seen_names.update(data)
            
            # 마지막 성공 시각 업데이트
            if "naver.com" in url: last_naver_time = now_str
            else: last_bnkr_time = now_str
        
        current_ids = set(cycle_data.keys())
        current_tracked_names = cycle_data.copy()
        
        if cycle_count > 1:
            new_ids = current_ids - known_in_stock_ids
            if new_ids:
                new_list = []
                for pid in new_ids:
                    tag = "[네이버]" if pid.startswith("N_") else "[본진]"
                    new_list.append(tag + " " + cycle_data[pid])
                for i in range(0, len(new_list), 30):
                    send_message(f"🚨 [신규/재입고 포착]\n" + "\n".join([str(idx+1) + ". " + n for idx, n in enumerate(new_list[i:i+30])]))
            
            gone_ids = known_in_stock_ids - current_ids
            if gone_ids:
                gone_list = []
                for pid in gone_ids:
                    tag = "[네이버]" if pid.startswith("N_") else "[본진]"
                    gone_list.append(tag + " " + all_seen_names[pid])
                for i in range(0, len(gone_list), 30):
                    send_message(f"🗑️ [품절 포착]\n" + "\n".join([str(idx+1) + ". " + n for idx, n in enumerate(gone_list[i:i+30])]))

        known_in_stock_ids = current_ids
        print("⏳ 사이클 완료. 7초 대기...")
        for _ in range(7):
            check_commands()
            time.sleep(1)
