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
    # 노이즈 제거 (품절, 환불, 날짜 등)
    p = r'좋아요|장바구니|\d{1,3}(,\d{3})*원|구매진행중|예약진행중|오픈예정|품절|환불|반품|\d{2}\.\d{2}까지'
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
                            msg = f"📊 [V2.99999c - SAFEGUARD]\n✅ 본진: {last_bnkr_time}\n✅ 네이버: {last_naver_time}\n"
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
            
            # 🚨 검증: HTML이 너무 짧으면 무시
            if len(res.text) < 1500: continue 
            if "naver.com" in url and "naver" not in res.text.lower(): continue 
            
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
            
            # 🚨 [양치기 방어] 하나도 안 보이면 성공이라고 하지 않음 (재시도 유도)
            if not data:
                soup.decompose()
                continue

            soup.decompose()
            return label, data, url, True
        except: continue
    return label, {}, url, False

if __name__ == "__main__":
    send_message("🟢 [V2.99999c] 긴급 수술 완료.\n더 이상 '가짜 품절'로 검사관님을 기만하지 않습니다.")
    while True:
        cycle_start = time.time()
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
                        
                        # 신규 입고 판단
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
                # 🚨 [품절 판정 강화] 완벽하게 스캔 성공한 URL에 속한 아이템만 품절 대상
                gone_ids = [pid for pid in (known_in_stock_ids - current_cycle_ids) if item_info.get(pid, {}).get('url') in success_urls]
                if gone_ids:
                    gone_list = [f"{('[네이버] ' if pid.startswith('N_') else '[본진] ')}{item_info[pid]['name']}" for pid in gone_ids]
                    for i in range(0, len(gone_list), 30): send_message(f"❌ 품절 ({datetime.now(KST).strftime('%H:%M:%S')})\n" + "\n".join(gone_list[i:i+30]))
                    for pid in gone_ids: 
                        known_in_stock_ids.discard(pid); item_info.pop(pid, None)
            
            # 유령 데이터 정리
            v_labels = {t['label'] for t in tasks}
            v_urls = {t['url'] for t in tasks}
            for pid in list(known_in_stock_ids):
                info = item_info.get(pid, {})
                if info.get('url') not in v_urls or info.get('label') not in v_labels:
                    known_in_stock_ids.discard(pid); item_info.pop(pid, None)
            
            temp_counts = {l: 0 for l in v_labels}
            for pid in known_in_stock_ids:
                lbl = item_info.get(pid, {}).get('label')
                if lbl in temp_counts: temp_counts[lbl] += 1
            category_counts = temp_counts

        check_commands()
        target_cycle = 18.2
        elapsed = time.time() - cycle_start
        time.sleep(max(0.1, target_cycle - elapsed))
        measured_cycle_time = time.time() - cycle_start
