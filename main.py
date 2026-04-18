import os
import requests
import time
import re
import json
from bs4 import BeautifulSoup
import urllib.parse
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor

# 시작 시각 기록
start_time = time.time()

# 한국 표준시(KST) 설정
KST = timezone(timedelta(hours=9))

print("🚀 [System] 골든 타임 보호 시스템(14:50-16:15) 탑재 완료!")

# ==========================================
# 프록시 ID 세팅
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
all_seen_names = {}
category_counts = {}
current_tracked_names = {}
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
                    msg = "📊 [골든 타임 보호 모드 가동 중]\n✅ 본진: " + last_bnkr_time + "\n✅ 네이버: " + last_naver_time + "\n\n"
                    msg += "\n".join([f"📍 {l}: {c}개" for l, c in category_counts.items()])
                    send_message(msg + f"\n\n📦 총합: {len(known_in_stock_ids)}개\n⏱️ 주기: 약 21~22초")
                elif cmd == "/추적상품확인":
                    if not current_tracked_names:
                        send_message("⏳ 데이터 수집 중입니다.")
                    else:
                        items = sorted([("[네이버] " if pid.startswith("N_") else "[본진] ") + name for pid, name in current_tracked_names.items()])
                        send_message(f"📂 감시 목록 (총 {len(items)}개)")
                        for i in range(0, len(items), 30):
                            send_message(f"📋 [목록 {i//30+1}]\n" + "\n".join([f"{i+idx+1}. {n}" for idx, n in enumerate(items[i:i+30])]))
    except: pass

def scan_target_parallel(task):
    global proxy_index
    url, label = task['url'], task['label']
    try:
        current_id = PROXY_IDS[proxy_index % len(PROXY_IDS)]
        proxy_index += 1
        proxy_url = f"https://script.google.com/macros/s/{current_id}/exec?url=" + urllib.parse.quote(url, safe='')
        res = requests.get(proxy_url, headers={'User-Agent': 'Mozilla/5.0 Chrome/120.0.0'}, timeout=30)
        if len(res.text) < 1000: return label, {}, url
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
        return label, local_data, url
    except: return label, {}, url

if __name__ == "__main__":
    tasks = []
    current_label = "기타"
    if not os.path.exists("list.txt"): exit(1)
    with open("list.txt", "r") as f:
        for line in f:
            line = line.strip()
            if line.startswith("#"): current_label = line.replace("#", "").strip()
            elif line: tasks.append({"url": line, "label": current_label})
    
    send_message("🤖 골든 타임 보호 엔진 가동! (오후 2:50~4:15 자동 재시작 방지)")
    
    while True:
        # --- [골든 타임 보호 및 리셋 로직] ---
        now_kst = datetime.now(KST)
        curr_hm = now_kst.hour * 100 + now_kst.minute
        elapsed = time.time() - start_time
        
        # 1. '사전 예방 리셋': 오후 2:35 ~ 2:45 사이에 봇이 이미 1시간 이상 돌았다면 미리 재시작
        # (골든 타임 직전에 새 봇으로 교체하여 6시간의 수명을 확보함)
        if 1435 <= curr_hm <= 1445 and elapsed > 3600:
            restart_myself()
            break
            
        # 2. '일반 리셋': 5시간 50분이 지났을 때 실행
        # 단, 현재 시각이 골든 타임(14:50~16:15) 사이라면 리셋을 미룸
        if elapsed > 21000:
            if 1450 <= curr_hm <= 1615:
                # 골든 타임에는 리셋하지 않고 통과 (단, 6시간 한계에 아주 가까우면 예외적으로 실행)
                if elapsed > 21300: # 5시간 55분 돌파 시 어쩔 수 없이 리셋
                    restart_myself()
                    break
                pass 
            else:
                restart_myself()
                break
        # ------------------------------------

        cycle_count += 1
        cycle_data, category_counts = {}, {}
        with ThreadPoolExecutor(max_workers=20) as ex:
            results = list(ex.map(scan_target_parallel, tasks))
        
        now_str = datetime.now(KST).strftime('%H:%M:%S')
        for label, data, url in results:
            cycle_data.update(data)
            category_counts[label] = category_counts.get(label, 0) + len(data)
            all_seen_names.update(data)
            if "naver.com" in url: last_naver_time = now_str
            else: last_bnkr_time = now_str
        
        current_ids = set(cycle_data.keys())
        event_time = datetime.now(KST).strftime('%H:%M:%S')

        if cycle_count > 1:
            new_ids = current_ids - known_in_stock_ids
            if new_ids:
                new_list = [("[네이버] " if pid.startswith("N_") else "[본진] ") + cycle_data[pid] for pid in new_ids]
                for i in range(0, len(new_list), 30):
                    send_message(f"🚨 [신규/재입고 포착] ({event_time})\n" + "\n".join([f"{idx+1}. {n}" for idx, n in enumerate(new_list[i:i+30])]))
            
            gone_ids = known_in_stock_ids - current_ids
            if gone_ids:
                gone_list = [("[네이버] " if pid.startswith("N_") else "[본진] ") + all_seen_names[pid] for pid in gone_ids]
                for i in range(0, len(gone_list), 30):
                    send_message(f"🗑️ [품절 포착] ({event_time})\n" + "\n".join([f"{idx+1}. {n}" for idx, n in enumerate(gone_list[i:i+30])]))

        known_in_stock_ids = current_ids
        current_tracked_names = cycle_data.copy()
        for _ in range(7):
            check_commands()
            time.sleep(2)
