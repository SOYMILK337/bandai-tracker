import os, requests, time, re, json, html, urllib.parse, threading
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

# 1. 시스템 설정
ST_TIME = time.time() 
KST = timezone(timedelta(hours=9))

# ✅ 정예 프록시 요원 (5개)
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
category_counts, cycle_count = {}, 0
last_update_id, measured_cycle_time = -1, 0.0
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
    txt = html.unescape(raw_name)
    p = r'좋아요|장바구니|\d{1,3}(,\d{3})*원|구매진행중|예약진행중|오픈예정|품절|\d{2}\.\d.까지'
    return re.sub(p, '', txt).strip()

def check_commands():
    global last_update_id
    try:
        url = f"https://api.telegram.org/bot{token}/getUpdates"
        res = requests.get(url, params={'offset': last_update_id + 1, 'timeout': 0.1}, timeout=1)
        response = res.json()
        if response.get("ok"):
            for update in response["result"]:
                last_update_id = update["update_id"]
                if "message" in update and "text" in update["message"] and str(update["message"]["chat"]["id"]) == str(chat_id):
                    if update["message"]["text"] == "/상태":
                        with lock:
                            msg = f"📊 [V2.99999 - ETERNAL PLUS]\n✅ 본진: {last_bnkr_time}\n✅ 네이버: {last_naver_time}\n"
                            msg += "\n".join([f"📍 {l}: {c}개" for l, c in category_counts.items()])
                            msg += f"\n⏱️ 실측 주기: {measured_cycle_time:.1f}s | 📦 추적: {len(known_in_stock_ids)}개"
                        send_message(msg)
    except: pass

proxy_index = 0
def scan_task(task):
    global proxy_index
    url, label = task['url'], task['label']
    if not url.startswith("http"): url = "https://" + url
    for _ in range(2):
        try:
            with lock:
                curr_id = PROXY_IDS[proxy_index % len(PROXY_IDS)]; proxy_index += 1
            p_url = f"https://script.google.com/macros/s/{curr_id}/exec?url=" + urllib.parse.quote(url, safe='')
            res = requests.get(p_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=25)
            if len(res.text) < 1000 or (("naver.com" in url) and ("naver" not in res.text.lower())): continue 
            
            clean_html = re.sub(r'<script.*?</script>', '', res.text, flags=re.DOTALL | re.IGNORECASE)
            soup = BeautifulSoup(clean_html, 'html.parser')
            data = {}
            if "naver.com" in url:
                for link in soup.find_all('a', href=re.compile(r'/products/\d+')):
                    if '품절' in link.get_text(): continue
                    p_id = "N_" + link.get('href').split('/')[-1].split('?')[0]
                    name, stock, attr = "", "", link.get('data-shp-contents-dtl')
                    if attr:
                        try:
                            for item in json.loads(attr):
                                if item.get('key') == 'chnl_prod_nm': name = item.get('value')
                                if item.get('key') == 'stk_qty': stock = str(item.get('value'))
                        except: pass
                    if not name: name = link.get_text(strip=True)
                    if len(name) >= 3: data[p_id] = {"name": clean_product_name(name), "stock": stock}
            else:
                for link in soup.find_all('a', href=re.compile(r'(gno|pno)=\d+')):
                    txt = link.get_text(strip=True).lower()
                    if any(x in txt for x in ['sold out', '예약종료', '품절']): continue
                    href = link.get('href')
                    p_id = ("B_" if 'gno=' in href else "PB_") + (href.split('gno=')[-1] if 'gno=' in href else href.split('pno=')[-1]).split('&')[0]
                    name_tag = link.find('h5')
                    p_name = name_tag.get_text(strip=True) if name_tag else link.get_text(strip=True)
                    if len(p_name) >= 3: data[p_id] = {"name": clean_product_name(p_name), "stock": ""}
            
            # 🚨 [비타민 한 알] 메모리 해제
            soup.decompose()
            return label, data, url, True
        except: continue
    return label, {}, url, False

if __name__ == "__main__":
    send_message("🟢 [V2.99999 - THE ETERNAL PLUS] 가동.\n아무 걱정 없이 믿고 맡기셔도 되는 '완성된 자식'입니다.")
    while True:
        cycle_start = time.time()
        # 🚨 [생존 로직] GitHub의 6시간 강제 종료벽 돌파
        if time.time() - ST_TIME > 20400: restart_myself(); break
        
        tasks = []
        try:
            with open("list.txt", "r", encoding="utf-8") as f:
                lbl = "기타"
                for line in f:
                    line = line.strip()
                    if line.startswith("#"): lbl = line.replace("#", "").strip()
                    elif line: tasks.append({"url": line, "label": lbl})
        except: pass

        cycle_count += 1
        current_cycle_ids, success_urls = set(), set()
        
        with ThreadPoolExecutor(max_workers=20) as executor:
            future_to_url = {executor.submit(scan_task, t): t for t in tasks}
            for future in as_completed(future_to_url):
                label, data, url, is_success = future.result()
                if is_success:
                    with lock:
                        now_str = datetime.now(KST).strftime('%H:%M:%S')
                        if "naver.com" in url: last_naver_time = now_str
                        else: last_bnkr_time = now_str
                        
                        new_items = set(data.keys()) - known_in_stock_ids
                        if cycle_count > 1 and new_items:
                            alert_list = [f"{('[네이버] ' if pid.startswith('N_') else '[본진] ')}{data[pid]['name']}{(' [재고: '+data[pid]['stock']+'개]' if data[pid]['stock'] else '')}" for pid in new_items]
                            for i in range(0, len(alert_list), 30):
                                send_message(f"🟢 입고 ({now_str})\n" + "\n".join(alert_list[i:i+30]))
                        
                        known_in_stock_ids.update(data.keys())
                        current_cycle_ids.update(data.keys())
                        success_urls.add(url)
                        for pid, info in data.items(): item_info[pid] = {"name": info['name'], "url": url, "label": label}

        with lock:
            if cycle_count > 1:
                gone_ids = [pid for pid in (known_in_stock_ids - current_cycle_ids) if item_info.get(pid, {}).get('url') in success_urls]
                if gone_ids:
                    gone_list = [f"{('[네이버] ' if pid.startswith('N_') else '[본진] ')}{item_info[pid]['name']}" for pid in gone_ids]
                    for i in range(0, len(gone_list), 30): send_message(f"❌ 품절 ({datetime.now(KST).strftime('%H:%M:%S')})\n" + "\n".join(gone_list[i:i+30]))
                    for pid in gone_ids: 
                        known_in_stock_ids.discard(pid); item_info.pop(pid, None)
            
            temp_counts, v_labels = {t['label']: 0 for t in tasks}, {t['label'] for t in tasks}
            for pid in list(known_in_stock_ids):
                info = item_info.get(pid, {})
                cur_lbl = info.get('label')
                if cur_lbl in v_labels: temp_counts[cur_lbl] = temp_counts.get(cur_lbl, 0) + 1
                else: known_in_stock_ids.discard(pid); item_info.pop(pid, None)
            category_counts = temp_counts

        check_commands()
        target_cycle = 18.2
        elapsed = time.time() - cycle_start
        # 🚨 [정직한 리포트] 대기 시간까지 포함한 '진짜' 주기를 기록
        wait_time = max(0.1, target_cycle - elapsed)
        time.sleep(wait_time)
        measured_cycle_time = time.time() - cycle_start
