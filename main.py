import os
import requests
import time
import re
import json
import html  # 🚨 특수문자 변환용 추가
from bs4 import BeautifulSoup
import urllib.parse
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# 1. 시스템 설정
start_time = time.time()
KST = timezone(timedelta(hours=9))

# ✅ 프록시 ID (최적의 5개 유지)
PROXY_IDS = [
    "AKfycbwHH20V6XscVYYIek80dI0symQT3P3cnCZkqqCyGijhpjOkNNzbQsvUR5oNyU0ndUMR",
    "AKfycbx57aFHKqx9QzC98TwPNLxDRs158W0Prnb8cZEjn5-n3udOlQ3CqKCgdIVt9at1UQ9X",
    "AKfycbwUJTb02XOUbV-obvpE7WXRdDn9AxJl5H-KWb-kRxCVqQ3AJpkuBFokAoxwkhp_gWXB",
    "AKfycbxVaQC2Y3ZUYFsls80Ny4aKZS_3zzbPxsNtZQnUUQOnulyfZQ5rf7n0uq29wYBVHpnMIw",
    "AKfycby-qFnD922uw9WfCebRtSmVe_FhOPvmdP2m8X-xRLbuzK29Xx0oGGe18dv7-A4zBoir"
]

token = os.environ.get('TELEGRAM_TOKEN')
chat_id = os.environ.get('TELEGRAM_CHAT_ID')
github_pat = os.environ.get('MY_GITHUB_PAT')
repo_full_name = os.environ.get('GITHUB_REPOSITORY') 

# 2. 데이터 저장소
known_in_stock_ids = set()
item_info = {} 
last_bnkr_time, last_naver_time = "대기 중", "대기 중"
category_counts = {}
cycle_count = 0
last_update_id = -1
measured_cycle_time = 0
lock = threading.Lock()

def send_message(text):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try: requests.post(url, data={'chat_id': chat_id, 'text': text}, timeout=10)
    except: pass

def restart_myself():
    if not github_pat or not repo_full_name: return
    url = f"https://api.github.com/repos/{repo_full_name}/dispatches"
    headers = {"Authorization": f"token {github_pat}", "Accept": "application/vnd.github.v3+json"}
    for _ in range(3):
        try: 
            res = requests.post(url, headers=headers, json={"event_type": "restart_bot"}, timeout=10)
            if res.status_code in [200, 204]: break
        except: time.sleep(2)

def clean_product_name(raw_name):
    # HTML 특수문자 복구 (&amp; -> &) 후 노이즈 제거
    txt = html.unescape(raw_name)
    p = r'좋아요|장바구니|\d{1,3}(,\d{3})*원|구매진행중|예약진행중|오픈예정|품절|\d{2}\.\d{2}까지'
    return re.sub(p, '', txt).strip()

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
                    sender_id = str(update["message"]["chat"]["id"])
                    if sender_id != str(chat_id): continue
                    if update["message"]["text"] == "/상태":
                        with lock:
                            msg = f"📊 [V2.97 - 파이널 에디션]\n✅ 본진: {last_bnkr_time}\n✅ 네이버: {last_naver_time}\n\n"
                            msg += "\n".join([f"📍 {l}: {c}개" for l, c in category_counts.items()])
                            msg += f"\n\n⏱️ 전체 주기: {measured_cycle_time:.1f}초\n📦 현재 재고: {len(known_in_stock_ids)}개"
                        send_message(msg)
    except: pass

proxy_index = 0
def scan_task(task):
    global proxy_index
    url, label = task['url'], task['label']
    task_start = time.time()
    if not url.startswith("http"): url = "https://" + url

    for _ in range(2):
        try:
            with lock:
                curr_id = PROXY_IDS[proxy_index % len(PROXY_IDS)]
                proxy_index += 1
            proxy_url = f"https://script.google.com/macros/s/{curr_id}/exec?url=" + urllib.parse.quote(url, safe='')
            res = requests.get(proxy_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=25)
            if len(res.text) < 1000: continue
            
            html_lower = res.text.lower()
            if "naver.com" in url and "naver" not in html_lower: continue 
            if "bnkrmall" in url and "bnkr" not in html_lower: continue 

            clean_html = re.sub(r'<script.*?</script>', '', res.text, flags=re.DOTALL | re.IGNORECASE)
            clean_html = clean_html.replace('<!DOCTYPE html>', '').replace('xmlns="http://www.w3.org/1999/xhtml"', '')
            soup = BeautifulSoup(clean_html, 'html.parser')
            data = {}
            
            if "naver.com" in url:
                links = soup.find_all('a', href=re.compile(r'/products/\d+'))
                for link in links:
                    text = link.get_text(strip=True)
                    if '품절' in text: continue
                    p_id = "N_" + link.get('href').split('/')[-1].split('?')[0]
                    name, stock = "", ""
                    attr = link.get('data-shp-contents-dtl')
                    if attr:
                        try:
                            json_data = json.loads(attr)
                            for item in json_data:
                                if item.get('key') == 'chnl_prod_nm': name = item.get('value')
                                if item.get('key') == 'stk_qty': stock = str(item.get('value'))
                        except: pass
                    if not name: name = text.replace('좋아요', '').replace('장바구니', '').strip()
                    if len(name) >= 3: 
                        data[p_id] = {"name": clean_product_name(name), "stock": stock}
            else:
                links = soup.find_all('a', href=re.compile(r'(gno|pno)=\d+'))
                for link in links:
                    text = link.get_text(strip=True)
                    if 'sold out' in text.lower() or '예약종료' in text or '품절' in text: continue
                    href = link.get('href')
                    if 'gno=' in href: p_id = "B_" + href.split('gno=')[-1].split('&')[0]
                    else: p_id = "PB_" + href.split('pno=')[-1].split('&')[0]
                    name_tag = link.find('h5')
                    pure_name = name_tag.get_text(strip=True) if name_tag else text
                    if len(pure_name) >= 3: 
                        data[p_id] = {"name": clean_product_name(pure_name), "stock": ""}
            
            return label, data, url, True, time.time() - task_start
        except: continue
    return label, {}, url, False, time.time() - task_start

if __name__ == "__main__":
    tasks = []
    with open("list.txt", "r", encoding="utf-8") as f:
        lbl = "기타"
        for line in f:
            line = line.strip(); 
            if line.startswith("#"): lbl = line.replace("#", "").strip()
            elif line: tasks.append({"url": line, "label": lbl})

    send_message("🟢 [V2.97] 가동. 모든 예외 상황이 통제된 파이널 에디션입니다.")

    while True:
        cycle_start = time.time()
        now_kst = datetime.now(KST)
        if 1435 <= (now_kst.hour * 100 + now_kst.minute) <= 1445: restart_myself(); break

        cycle_count += 1
        current_cycle_ids = set()
        success_urls = set()
        
        with ThreadPoolExecutor(max_workers=20) as executor:
            future_to_url = {executor.submit(scan_task, t): t for t in tasks}
            for future in as_completed(future_to_url):
                label, data, url, is_success, task_dur = future.result()
                if is_success:
                    with lock:
                        now_str = datetime.now(KST).strftime('%H:%M:%S')
                        if "naver.com" in url: last_naver_time = now_str
                        else: last_bnkr_time = now_str
                        
                        new_items = set(data.keys()) - known_in_stock_ids
                        if cycle_count > 1 and new_items:
                            alert_list = []
                            for pid in new_items:
                                prefix = "[네이버] " if pid.startswith('N_') else "[본진] "
                                s_info = f" [재고: {data[pid]['stock']}개]" if data[pid]['stock'] else ""
                                alert_list.append(f"{prefix}{data[pid]['name']}{s_info}")
                            send_message(f"🟢 신규/재입고 ({now_str})\n" + "\n".join(alert_list))
                        
                        known_in_stock_ids.update(data.keys())
                        current_cycle_ids.update(data.keys())
                        success_urls.add(url)
                        for pid, info in data.items():
                            item_info[pid] = {"name": info['name'], "url": url, "label": label}

        with lock:
            if cycle_count > 1:
                # 🚨 [유령 데이터 방지] 현재 list.txt에 유효한 주소 기반으로만 품절 판단
                gone_ids = [pid for pid in (known_in_stock_ids - current_cycle_ids) if item_info.get(pid, {}).get('url') in success_urls]
                if gone_ids:
                    gone_list = [f"{('[네이버] ' if pid.startswith('N_') else '[본진] ')}{item_info[pid]['name']}" for pid in gone_ids]
                    for i in range(0, len(gone_list), 30):
                        send_message(f"❌ 품절 ({datetime.now(KST).strftime('%H:%M:%S')})\n" + "\n".join(gone_list[i:i+30]))
                    for pid in gone_ids: 
                        known_in_stock_ids.discard(pid)
                        if pid in item_info: del item_info[pid]
            
            temp_counts = {t['label']: 0 for t in tasks}
            valid_labels = {t['label'] for t in tasks}
            for pid in list(known_in_stock_ids):
                info = item_info.get(pid, {})
                if info.get('label') in valid_labels:
                    temp_counts[info['label']] += 1
                else: # list.txt에서 삭제된 라벨의 상품은 자동 정리
                    known_in_stock_ids.discard(pid)
                    if pid in item_info: del item_info[pid]
            category_counts = temp_counts

        target_cycle = 18.0
        elapsed = time.time() - cycle_start
        wait_total = max(2.0, target_cycle - elapsed)
        step = wait_total / 5
        for _ in range(5):
            check_commands()
            time.sleep(step)
        measured_cycle_time = time.time() - cycle_start
