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

print("🚀 [System] 반다이 본진 + 네이버 듀얼 코어 엔진 가동!")

token = os.environ.get('TELEGRAM_TOKEN')
chat_id = os.environ.get('TELEGRAM_CHAT_ID')
github_pat = os.environ.get('MY_GITHUB_PAT')
repo_full_name = os.environ.get('GITHUB_REPOSITORY') 

GOOGLE_PROXY_URL = "https://script.google.com/macros/s/AKfycbwHH20V6XscVYYIek80dI0symQT3P3cnCZkqqCyGijhpjOkNNzbQsvUR5oNyU0ndUMR/exec"

known_in_stock_ids = set()
all_seen_names = {}
category_counts = {}
current_tracked_names = {}

cycle_count = 0
last_update_id = -1
last_check_time = "대기 중..."

def send_message(text):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {'chat_id': chat_id, 'text': text}
    try:
        requests.post(url, data=payload, timeout=10)
    except:
        pass

def restart_myself():
    if not github_pat or not repo_full_name:
        return
    url = f"https://api.telegram.org/repos/{repo_full_name}/dispatches"
    headers = {
        "Authorization": f"token {github_pat}",
        "Accept": "application/vnd.github.v3+json"
    }
    data = {"event_type": "restart_bot"}
    try:
        requests.post(url, headers=headers, json=data, timeout=10)
    except:
        pass

def clean_product_name(raw_name):
    p = r'좋아요|장바구니|\d{1,3}(,\d{3})*원|구매진행중|예약진행중|오픈예정|품절|\d{2}\.\d{2}까지'
    clean = re.sub(p, '', raw_name)
    return clean.strip()

def check_commands():
    global last_update_id
    try:
        url = f"https://api.telegram.org/bot{token}/getUpdates"
        params = {'offset': last_update_id + 1, 'timeout': 1}
        res = requests.get(url, params=params, timeout=10)
        response = res.json()
    except:
        return

    if not response or not response.get("ok") or not response.get("result"):
        return

    for update in response["result"]:
        last_update_id = update["update_id"]
        if "message" not in update or "text" not in update["message"]:
            continue
            
        cmd = update["message"]["text"]
        
        if cmd == "/상태":
            if cycle_count == 0:
                send_message("⏳ 첫 번째 정밀 스캔 중입니다.")
            else:
                sum_text = [f"📍 {l}: {c}개" for l, c in category_counts.items()]
                msg1 = f"📊 [실시간 듀얼 보고]\n🔄 현재 {cycle_count}회차\n"
                msg2 = "\n".join(sum_text)
                msg3 = f"\n\n📦 총합: {len(known_in_stock_ids)}개\n⏱️ 시간: {last_check_time}"
                send_message(msg1 + msg2 + msg3)
                
        elif cmd == "/추적상품확인":
            if not current_tracked_names:
                send_message("⏳ 데이터 수집 중입니다.")
            else:
                names = sorted(current_tracked_names.values())
                send_message(f"📂 현재 전체 목록 (총 {len(names)}개)")
                for i in range(0, len(names), 30):
                    chunk = names[i:i+30]
                    msg = "\n".join([f"{i+idx+1}. {n}" for idx, n in enumerate(chunk)])
                    send_message(f"📋 [목록 {i//30 + 1}]\n{msg}")

def scan_target_parallel(task):
    url = task['url']
    label = task['label']
    try:
        encoded_url = urllib.parse.quote(url, safe='')
        proxy_url = GOOGLE_PROXY_URL + "?url=" + encoded_url
        
        ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36'
        headers = {'User-Agent': ua}
        
        res = requests.get(proxy_url, headers=headers, timeout=30)
        
        if len(res.text) < 1000:
            return label, {}
        
        soup = BeautifulSoup(res.text, 'html.parser')
        local_data = {}
        
        # [핵심] 네이버 브랜드스토어 전용 탐색기
        if "naver.com" in url:
            links = soup.find_all('a', href=re.compile(r'/bandai/products/\d+'))
            for link in links:
                href = link.get('href')
                if not href:
                    continue
                
                # 본진 상품번호와 겹치지 않게 N_ 을 붙임
                p_id = "N_" + href.split('/')[-1].split('?')[0]
                
                # 품절 여부 파악 (품절 글자가 있으면 무시)
                if '품절' in link.get_text():
                    continue
                    
                p_name = ""
                dtl = link.get('data-shp-contents-dtl')
                if dtl:
                    try:
                        dtl_data = json.loads(dtl)
                        for item in dtl_data:
                            if item.get('key') == 'chnl_prod_nm':
                                p_name = item.get('value')
                                break
                    except:
                        pass
                        
                if len(p_name) > 2:
                    local_data[p_id] = clean_product_name(p_name)
                    
        # 기존 반다이 본진 탐색기
        else:
            links = soup.find_all('a', href=re.compile(r'gno=\d+'))
            for link in links:
                # 네이버와 겹치지 않게 B_ 를 붙임
                p_id = "B_" + link['href'].split('gno=')[-1].split('&')[0]
                raw_name = link.get_text(strip=True)
                if len(raw_name) >= 10:
                    local_data[p_id] = clean_product_name(raw_name)
                    
        return label, local_data
    except:
        return label, {}

if __name__ == "__main__":
    if not os.path.exists("list.txt"):
        print("❌ list.txt 파일이 없습니다.")
        exit(1)

    tasks = []
    current_label = "기타"
    with open("list.txt", "r") as f:
        for line in f:
            line = line.strip()
            if line.startswith("#"):
                current_label = line.replace("#", "").strip()
            elif line:
                tasks.append({"url": line, "label": current_label})
    
    send_message("🤖 반다이 본진 + 네이버 듀얼 병렬 감시 시스템 가동!")
    session = requests.Session()
    
    while True:
        if time.time() - start_time > 21000:
            restart_myself()
            break

        cycle_count += 1
        cycle_data = {} 
        category_counts = {} 
        
        with ThreadPoolExecutor(max_workers=5) as executor:
            results = list(executor.map(scan_target_parallel, tasks))
        
        for label, data in results:
            cycle_data.update(data)
            category_counts[label] = category_counts.get(label, 0) + len(data)
            all_seen_names.update(data)
        
        last_check_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        current_ids = set(cycle_data.keys())
        current_tracked_names = cycle_data.copy()
        
        if cycle_count > 1:
            new_ids = current_ids - known_in_stock_ids
            if new_ids:
                new_list = [cycle_data[pid] for pid in new_ids]
                for i in range(0, len(new_list), 30):
                    chunk = new_list[i:i+30]
                    msg = "\n".join([f"{idx+1}. {n}" for idx, n in enumerate(chunk)])
                    send_message(f"🚨 [신규/재입고 포착]\n{msg}")
            
            gone_ids = known_in_stock_ids - current_ids
            if gone_ids:
                gone_list = [all_seen_names[pid] for pid in gone_ids]
                for i in range(0, len(gone_list), 30):
                    chunk = gone_list[i:i+30]
                    msg = "\n".join([f"{idx+1}. {n}" for idx, n in enumerate(chunk)])
                    send_message(f"🗑️ [품절 포착]\n{msg}")

        known_in_stock_ids = current_ids
        
        print(f"⏳ {cycle_count}회차 완료. 7초 대기 중...")
        for _ in range(7):
            check_commands()
            time.sleep(1)
