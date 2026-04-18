import os
import requests
import time
import re
import json
from bs4 import BeautifulSoup
import urllib.parse
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# 1. 시스템 설정
start_time = time.time()
KST = timezone(timedelta(hours=9))

# ✅ 프록시 ID (8만 건 할당량 최적화)
PROXY_IDS = [
    "AKfycbwHH20V6XscVYYIek80dI0symQT3P3cnCZkqqCyGijhpjOkNNzbQsvUR5oNyU0ndUMR",
    "AKfycbx57aFHKqx9QzC98TwPNLxDRs158W0Prnb8cZEjn5-n3udOlQ3CqKCgdIVt9at1UQ9X",
    "AKfycbwUJTb02XOUbV-obvpE7WXRdDn9AxJl5H-KWb-kRxCVqQ3AJpkuBFokAoxwkhp_gWXB",
    "AKfycbxVaQC2Y3ZUYFsls80Ny4aKZS_3zzbPxsNtZQnUUQOnulyfZQ5rf7n0uq29wYBVHpnMIw"
]

token = os.environ.get('TELEGRAM_TOKEN')
chat_id = os.environ.get('TELEGRAM_CHAT_ID')
github_pat = os.environ.get('MY_GITHUB_PAT')
repo_full_name = os.environ.get('GITHUB_REPOSITORY') 

# 2. 공유 데이터 저장소
known_in_stock_ids = set()
item_to_label = {}
all_seen_names = {}
last_bnkr_time, last_naver_time = "대기 중", "대기 중"
category_counts = {}
cycle_count = 0
last_update_id = -1
measured_cycle_time = 0
avg_scan_time = 0 
lock = threading.Lock()

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
        if response.get("ok"):
            for update in response["result"]:
                last_update_id = update["update_id"]
                if "message" in update and "text" in update["message"]:
                    if update["message"]["text"] == "/상태":
                        with lock:
                            msg = f"📊 [하이퍼 엔진 V2.3 - 타겟팅 26s]\n✅ 본진: {last_bnkr_time}\n✅ 네이버: {last_naver_time}\n\n"
                            msg += "\n".join([f"📍 {l}: {c}개" for l, c in category_counts.items()])
                            msg += f"\n\n⏱️ 전체 주기: {measured_cycle_time:.1f}초 (타겟: 26.0s)"
                            msg += f"\n⏱️ 주소당 평균: {avg_scan_time:.2f}초"
                            msg += f"\n📦 현재 재고: {len(known_in_stock_ids)}개"
                        send_message(msg)
    except: pass

proxy_index = 0
def scan_task(task):
    global proxy_index
    url, label = task['url'], task['label']
    task_start = time.time()
    for _ in range(2):
        try:
            with lock:
                curr_id = PROXY_IDS[proxy_index % len(PROXY_IDS)]
                proxy_index += 1
            proxy_url = f"https://script.google.com/macros/s/{curr_id}/exec?url=" + urllib.parse.quote(url, safe='')
            res = requests.get(proxy_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=25)
            if len(res.text) < 1000: continue
            soup = BeautifulSoup(res.text, 'html.parser')
            data = {}
            if "naver.com" in url:
                links = soup.find_all('a', href=re.compile(r'/bandai/products/\d+'))
                for link in links:
                    if '품절' in link.get_text(): continue
                    p_id = "N_" + link.get('href').split('/')[-1].split('?')[0]
                    attr = link.get('data-shp-contents-dtl')
                    if attr:
                        try:
                            for item in json.loads(attr):
                                if item.get('key') == 'chnl_prod_nm':
                                    data[p_id] = clean_product_name(item.get('value')); break
                        except: pass
            else:
                links = soup.find_all('a', href=re.compile(r'gno=\d+'))
                for link in links:
                    p_id = "B_" + link['href'].split('gno=')[-1].split('&')[0]
                    if len(link.get_text(strip=True)) >= 10:
                        data[p_id] = clean_product_name(link.get_text(strip=True))
            return label, data, url, True, time.time() - task_start
        except: continue
    return label, {}, url, False, time.time() - task_start

if __name__ == "__main__":
    tasks = []
    with open("list.txt", "r") as f:
        lbl = "기타"
        for line in f:
            line = line.strip()
            if line.startswith("#"): lbl = line.replace("#", "").strip()
            elif line: tasks.append({"url": line, "label": lbl})

    send_message("🚨 [엔진 가동] 타겟 주기 26.0초 고정 모드를 시작합니다.")

    while True:
        cycle_start = time.time()
        now_kst = datetime.now(KST)
        curr_hm = now_kst.hour * 100 + now_kst.minute
        elapsed_from_boot = time.time() - start_time

        if 1435 <= curr_hm <= 1445 and elapsed_from_boot > 3600: restart_myself(); break
        if elapsed_from_boot > 21000:
            if not (1450 <= curr_hm <= 1615): restart_myself(); break
            elif elapsed_from_boot > 21300: restart_myself(); break

        cycle_count += 1
        current_cycle_ids = set()
        success_labels = set()
        durations = []
        
        with ThreadPoolExecutor(max_workers=20) as executor:
            future_to_url = {executor.submit(scan_task, t): t for t in tasks}
            for future in as_completed(future_to_url):
                label, data, url, is_success, task_dur = future.result()
                durations.append(task_dur)
                if is_success:
                    with lock:
                        now_str = datetime.now(KST).strftime('%H:%M:%S')
                        if "naver.com" in url: last_naver_time = now_str
                        else: last_bnkr_time = now_str
                        new_items = set(data.keys()) - known_in_stock_ids
                        if cycle_count > 1 and new_items:
                            alert_list = [f"{('[네이버] ' if pid.startswith('N_') else '[본진] ')}{data[pid]}" for pid in new_items]
                            send_message(f"🚨 신규/재입고 ({now_str})\n" + "\n".join(alert_list))
                        known_in_stock_ids.update(data.keys())
                        current_cycle_ids.update(data.keys())
                        all_seen_names.update(data)
                        success_labels.add(label)
                        for pid in data: item_to_label[pid] = label

        with lock:
            if durations: avg_scan_time = sum(durations) / len(durations)
            if cycle_count > 1:
                gone_ids = [pid for pid in (known_in_stock_ids - current_cycle_ids) if item_to_label.get(pid) in success_labels]
                if gone_ids:
                    gone_list = [f"{('[네이버] ' if pid.startswith('N_') else '[본진] ')}{all_seen_names[pid]}" for pid in gone_ids]
                    for i in range(0, len(gone_list), 30):
                        send_message(f"🗑️ 품절 포착 ({datetime.now(KST).strftime('%H:%M:%S')})\n" + "\n".join(gone_list[i:i+30]))
                    for pid in gone_ids: known_in_stock_ids.discard(pid)
            
            temp_counts = {t['label']: 0 for t in tasks}
            for pid in known_in_stock_ids:
                lbl = item_to_label.get(pid)
                if lbl in temp_counts: temp_counts[lbl] += 1
            category_counts = temp_counts

        # ✅ 가변형 타겟 대기 로직 (26.0초 고정)
        target_cycle = 26.0
        elapsed_so_far = time.time() - cycle_start
        # 스캔이 아무리 빨라도 최소 5초는 대기하며 명령어를 체크합니다.
        remaining_wait = max(5.0, target_cycle - elapsed_so_far)
        
        sleep_chunk = remaining_wait / 5
        for _ in range(5):
            check_commands()
            time.sleep(sleep_chunk)
        
        measured_cycle_time = time.time() - cycle_start
