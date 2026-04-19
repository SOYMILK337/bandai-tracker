import os, requests, time, re, json, html, urllib.parse, threading
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

# 1. 시스템 설정
ST_TIME = time.time() 
KST = timezone(timedelta(hours=9))

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

# 🚨 뇌의 좌우 분리: 반몰과 네반몰의 데이터를 완벽히 격리
group_state = {
    "반몰": {"known": set(), "items": {}, "counts": {}, "last_time": "대기 중", "cycle": 0.0},
    "네반몰": {"known": set(), "items": {}, "counts": {}, "last_time": "대기 중", "cycle": 0.0}
}

last_update_id = -1
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
    p = r'좋아요|장바구니|\d{1,3}(,\d{3})*원|구매진행중|예약진행중|오픈예정|품절|환불|반품|\d{2}\.\d.까지'
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
                            total_known = len(group_state["반몰"]["known"]) + len(group_state["네반몰"]["known"])
                            merged_counts = {}
                            for g in ["반몰", "네반몰"]:
                                for l, c in group_state[g]["counts"].items():
                                    merged_counts[l] = merged_counts.get(l, 0) + c
                                    
                            msg = f"📊 [V2.99999_OMEGA - 절대 완성판]\n"
                            msg += f"🔥 반몰: {group_state['반몰']['last_time']} ({group_state['반몰']['cycle']:.1f}s)\n"
                            msg += f"🍀 네반몰: {group_state['네반몰']['last_time']} ({group_state['네반몰']['cycle']:.1f}s)\n\n"
                            msg += "\n".join([f"📍 {l}: {c}개" for l, c in merged_counts.items()])
                            msg += f"\n📦 전체 추적: {total_known}개"
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
            if len(res.text) < 1500 or (("naver.com" in url) and ("naver" not in res.text.lower())): continue 
            
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
            
            if not data:
                soup.decompose(); continue
            soup.decompose()
            return label, data, url, True
        except: continue
    return label, {}, url, False

# 🚨 완벽히 독립된 감시 엔진
def monitoring_engine(group_name, target_cycle):
    my_state = group_state[group_name]
    cycle_count = 0
    
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
                    elif line:
                        if (group_name == "반몰" and "bnkrmall" in line) or (group_name == "네반몰" and "naver.com" in line):
                            tasks.append({"url": line, "label": lbl})
        except: pass
        
        if not tasks: 
            time.sleep(10); continue

        cycle_count += 1
        current_cycle_ids, success_urls = set(), set()
        
        with ThreadPoolExecutor(max_workers=15) as executor:
            future_to_url = {executor.submit(scan_task, t): t for t in tasks}
            for future in as_completed(future_to_url):
                label, data, url, is_success = future.result()
                if is_success:
                    with lock:
                        now_str = datetime.now(KST).strftime('%H:%M:%S')
                        my_state['last_time'] = now_str
                        
                        new_items = set(data.keys()) - my_state['known']
                        if cycle_count > 1 and new_items:
                            alert_list = [f"{('[네반몰] ' if pid.startswith('N_') else '[반몰] ')}{data[pid]['name']}{(' [재고: '+data[pid]['stock']+'개]' if data[pid]['stock'] else '')}" for pid in new_items]
                            for i in range(0, len(alert_list), 30):
                                send_message(f"🟢 입고 ({now_str})\n" + "\n".join(alert_list[i:i+30]))
                        
                        my_state['known'].update(data.keys())
                        current_cycle_ids.update(data.keys())
                        success_urls.add(url)
                        for pid, info in data.items(): my_state['items'][pid] = {"name": info['name'], "url": url, "label": label}

        with lock:
            if cycle_count > 1:
                gone_ids = [pid for pid in (my_state['known'] - current_cycle_ids) if my_state['items'].get(pid, {}).get('url') in success_urls]
                if gone_ids:
                    gone_list = [f"{('[네반몰] ' if pid.startswith('N_') else '[반몰] ')}{my_state['items'][pid]['name']}" for pid in gone_ids]
                    for i in range(0, len(gone_list), 30): send_message(f"❌ 품절 ({datetime.now(KST).strftime('%H:%M:%S')})\n" + "\n".join(gone_list[i:i+30]))
                    for pid in gone_ids: 
                        my_state['known'].discard(pid); my_state['items'].pop(pid, None)
            
            v_urls, v_labels = {t['url'] for t in tasks}, {t['label'] for t in tasks}
            for pid in list(my_state['known']):
                info = my_state['items'].get(pid, {})
                if info.get('url') not in v_urls or info.get('label') not in v_labels:
                    my_state['known'].discard(pid); my_state['items'].pop(pid, None)
            
            t_counts = {l: 0 for l in v_labels}
            for pid in my_state['known']:
                lbl = my_state['items'].get(pid, {}).get('label')
                if lbl in t_counts: t_counts[lbl] += 1
            my_state['counts'] = t_counts

        elapsed = time.time() - cycle_start
        with lock: my_state['cycle'] = elapsed
        time.sleep(max(0.1, target_cycle - elapsed))

if __name__ == "__main__":
    send_message("🟢 [V2.99999_OMEGA] 구동 시작.\n완벽하게 독립된 듀얼 코어로 감시를 시작합니다.")
    
    t1 = threading.Thread(target=monitoring_engine, args=("반몰", 18.2), daemon=True)
    t2 = threading.Thread(target=monitoring_engine, args=("네반몰", 18.2), daemon=True)
    t1.start(); t2.start()
    
    while True:
        check_commands()
        time.sleep(1)
