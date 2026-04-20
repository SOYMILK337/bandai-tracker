import os, requests, time, re, json, html, urllib.parse, threading
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

# 1. 시스템 설정
ST_TIME = time.time() 
KST = timezone(timedelta(hours=9))

proxy_secret_str = os.environ.get('PROXY_SECRET', '')
PROXY_IDS = [p.strip() for p in proxy_secret_str.split(',')] if proxy_secret_str else []

token = os.environ.get('TELEGRAM_TOKEN')
chat_id = os.environ.get('TELEGRAM_CHAT_ID')
github_pat = os.environ.get('MY_GITHUB_PAT')
repo_full_name = os.environ.get('GITHUB_REPOSITORY') 

group_state = {
    "반몰": {"known": set(), "items": {}, "counts": {}, "last_time": "대기 중", "work_time": 0.0, "cycle": 0.0},
    "네반몰": {"known": set(), "items": {}, "counts": {}, "last_time": "대기 중", "work_time": 0.0, "cycle": 0.0}
}

last_update_id = -1
lock = threading.Lock()
is_restarting = False 

def send_message(text):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try: requests.post(url, data={'chat_id': chat_id, 'text': text}, timeout=10)
    except: pass

def execute_reincarnation():
    global is_restarting
    if not github_pat or not repo_full_name: return
    url = f"https://api.github.com/repos/{repo_full_name}/dispatches"
    headers = {"Authorization": f"token {github_pat}", "Accept": "application/vnd.github.v3+json"}
    
    for _ in range(3):
        try: 
            res = requests.post(url, headers=headers, json={"event_type": "restart_bot"}, timeout=10)
            if res.status_code in [200, 204]: os._exit(0) 
        except: time.sleep(2)
        
    send_message("🚨 [오류] 봇 부활 실패. 수동 확인 요망.")
    with lock: is_restarting = False 

def trigger_reincarnation():
    global is_restarting
    with lock:
        if not is_restarting:
            is_restarting = True
            threading.Thread(target=execute_reincarnation, daemon=True).start()

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
                        ordered_labels = []
                        try:
                            with open("list.txt", "r", encoding="utf-8") as f:
                                lbl = "기타"
                                for line in f:
                                    line = line.strip()
                                    if line.startswith("#"): lbl = line.replace("#", "").strip()
                                    if lbl not in ordered_labels and line: ordered_labels.append(lbl)
                        except: pass
                        
                        with lock:
                            total_known = len(group_state["반몰"]["known"]) + len(group_state["네반몰"]["known"])
                            merged_counts = {l: 0 for l in ordered_labels}
                            for g in ["반몰", "네반몰"]:
                                for l, c in group_state[g]["counts"].items():
                                    if l in merged_counts: merged_counts[l] += c
                                    else: merged_counts[l] = c
                                    
                            msg = f"📊 [V3.5]\n"
                            msg += f"🔥 반몰: {group_state['반몰']['last_time']} (⏱ 작업 {group_state['반몰']['work_time']:.1f}s / 주기 {group_state['반몰']['cycle']:.1f}s)\n"
                            msg += f"🍀 네반몰: {group_state['네반몰']['last_time']} (⏱ 작업 {group_state['네반몰']['work_time']:.1f}s / 주기 {group_state['네반몰']['cycle']:.1f}s)\n\n"
                            msg += "\n".join([f"📍 {l}: {c}개" for l, c in merged_counts.items() if l in ordered_labels])
                            msg += f"\n\n📦 전체 추적: {total_known}개"
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
                if not PROXY_IDS: return label, {}, url, False 
                curr_id = PROXY_IDS[proxy_index % len(PROXY_IDS)]; proxy_index += 1
            
            p_url = f"https://script.google.com/macros/s/{curr_id}/exec?url=" + urllib.parse.quote(url, safe='')
            res = requests.get(p_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
            
            if len(res.text) < 1500 or (("naver.com" in url) and ("naver" not in res.text.lower())): continue 
            
            data = {}
            
            if "naver.com" in url:
                # 🚨 [V3.5 핵심: 네이버 숨겨진 재고(JSON) 추적기]
                parsed_naver_json = False
                state_match = re.search(r'window\.__PRELOADED_STATE__\s*=\s*(\{.+?\});\s*</script>', res.text)
                if state_match:
                    try:
                        state_data = json.loads(state_match.group(1))
                        # JSON 내부를 샅샅이 뒤지는 재귀 함수
                        def find_products(d):
                            if isinstance(d, dict):
                                if 'productNo' in d and 'name' in d and 'productStatusType' in d:
                                    yield d
                                for k, v in d.items(): yield from find_products(v)
                            elif isinstance(d, list):
                                for item in d: yield from find_products(item)
                        
                        for prod in find_products(state_data):
                            p_id = "N_" + str(prod.get('productNo'))
                            p_name = str(prod.get('name', ''))
                            status = str(prod.get('productStatusType', ''))
                            stock = str(prod.get('stockQuantity', '')) # 드디어 확보한 찐 재고량!
                            
                            if status == "OUTOFSTOCK" or '품절' in p_name: continue
                            if "mgsd" in label.replace(" ", "").lower() and "mgsd" not in p_name.replace(" ", "").lower(): continue
                            
                            c_name = clean_product_name(p_name)
                            if len(c_name) >= 3: 
                                data[p_id] = {"name": c_name, "stock": stock}
                                parsed_naver_json = True
                    except: pass
                
                # JSON 파싱에 실패했을 경우를 대비한 기존 구형 백업 스캐너
                if not parsed_naver_json:
                    clean_html = re.sub(r'<script.*?</script>', '', res.text, flags=re.DOTALL | re.IGNORECASE)
                    soup = BeautifulSoup(clean_html, 'html.parser')
                    for link in soup.find_all('a', href=re.compile(r'/products/\d+')):
                        if '품절' in link.get_text(): continue
                        p_id = "N_" + link.get('href').split('/')[-1].split('?')[0]
                        name, stock_bk, attr = "", "", link.get('data-shp-contents-dtl')
                        if attr:
                            try:
                                for item in json.loads(attr):
                                    if item.get('key') == 'chnl_prod_nm': name = str(item.get('value', ''))
                                    if item.get('key') == 'stk_qty': stock_bk = str(item.get('value', ''))
                            except: pass
                        if not name: name = link.get_text(strip=True)
                        if "mgsd" in label.replace(" ", "").lower() and "mgsd" not in name.replace(" ", "").lower(): continue
                        c_name = clean_product_name(name)
                        if len(c_name) >= 3: data[p_id] = {"name": c_name, "stock": stock_bk}
                    soup.decompose()

            else:
                # 반다이몰 파싱 로직
                clean_html = re.sub(r'<script.*?</script>', '', res.text, flags=re.DOTALL | re.IGNORECASE)
                soup = BeautifulSoup(clean_html, 'html.parser')
                for link in soup.find_all('a', href=re.compile(r'(gno|pno)=\d+')):
                    txt = link.get_text(strip=True).lower()
                    if any(x in txt for x in ['sold out', '예약종료', '품절']): continue
                    href = link.get('href')
                    p_id = ("B_" if 'gno=' in href else "PB_") + (href.split('gno=')[-1] if 'gno=' in href else href.split('pno=')[-1]).split('&')[0]
                    name_tag = link.find('h5')
                    p_name = name_tag.get_text(strip=True) if name_tag else link.get_text(strip=True)
                    if "mgsd" in label.replace(" ", "").lower() and "mgsd" not in p_name.replace(" ", "").lower(): continue
                    c_name = clean_product_name(p_name)
                    if len(c_name) >= 3: data[p_id] = {"name": c_name, "stock": ""}
                soup.decompose()

            if not data: continue
            return label, data, url, True
        except: continue
    return label, {}, url, False

def monitoring_engine(group_name, target_cycle):
    my_state = group_state[group_name]
    cycle_count = 0
    
    while True:
        cycle_start = time.time()
        now_kst = datetime.now(KST)
        
        current_minutes = now_kst.hour * 60 + now_kst.minute
        is_daily_restart_time = (now_kst.hour == 14 and now_kst.minute == 20)
        is_forbidden_time = (14 * 60 + 40) <= current_minutes <= (16 * 60 + 50)
        
        if is_daily_restart_time or (time.time() - ST_TIME > 20400 and not is_forbidden_time): 
            trigger_reincarnation()
        
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
        
        with ThreadPoolExecutor(max_workers=20) as executor:
            future_to_url = {executor.submit(scan_task, t): t for t in tasks}
            for future in as_completed(future_to_url):
                label, data, url, is_success = future.result()
                if is_success:
                    with lock:
                        now_str = datetime.now(KST).strftime('%H:%M:%S')
                        my_state['last_time'] = now_str
                        new_items = set(data.keys()) - my_state['known']
                        if cycle_count > 1 and new_items:
                            # 🚨 재고량이 존재할 경우 [재고: n개] 형식으로 알림 발송
                            alert_list = [f"{('[네반몰] ' if pid.startswith('N_') else '[반몰] ')}{data[pid]['name']}{(' [재고: '+data[pid]['stock']+'개]' if data[pid]['stock'] else '')}" for pid in new_items]
                            for i in range(0, len(alert_list), 30): send_message(f"🟢 입고 ({now_str})\n" + "\n".join(alert_list[i:i+30]))
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
                    for pid in gone_ids: my_state['known'].discard(pid); my_state['items'].pop(pid, None)
            v_urls, v_labels = {t['url'] for t in tasks}, {t['label'] for t in tasks}
            for pid in list(my_state['known']):
                info = my_state['items'].get(pid, {})
                if info.get('url') not in v_urls or info.get('label') not in v_labels: my_state['known'].discard(pid); my_state['items'].pop(pid, None)
            t_counts = {l: 0 for l in v_labels}
            for pid in my_state['known']:
                lbl = my_state['items'].get(pid, {}).get('label')
                if lbl in t_counts: t_counts[lbl] += 1
            my_state['counts'] = t_counts

        elapsed_work = time.time() - cycle_start
        with lock: my_state['work_time'] = elapsed_work
        
        time.sleep(max(0.1, target_cycle - elapsed_work))
        with lock: my_state['cycle'] = time.time() - cycle_start

if __name__ == "__main__":
    send_message("🛡️ [V3.5] 가동.\n네이버 스토어 심층 재고(JSON) 추적기가 활성화되었습니다.")
    t1 = threading.Thread(target=monitoring_engine, args=("반몰", 18.2), daemon=True)
    t2 = threading.Thread(target=monitoring_engine, args=("네반몰", 18.2), daemon=True)
    t1.start(); t2.start()
    while True: check_commands(); time.sleep(1)
