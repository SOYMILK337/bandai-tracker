import os
import requests
import time
import re
from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

# [설정]
token = os.environ['TELEGRAM_TOKEN']
chat_id = os.environ['TELEGRAM_CHAT_ID']
GOOGLE_PROXY_URL = "https://script.google.com/macros/s/AKfycbwHH20V6XscVYYIek80dI0symQT3P3cnCZkqqCyGijhpjOkNNzbQsvUR5oNyU0ndUMR/exec"

last_stock_status = {}
cycle_count = 0
last_update_id = -1

def send_message(text):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {'chat_id': chat_id, 'text': text}
    requests.post(url, data=payload)

def check_commands():
    global last_update_id, cycle_count
    try:
        url = f"https://api.telegram.org/bot{token}/getUpdates"
        params = {'offset': last_update_id + 1, 'timeout': 1}
        response = requests.get(url, params=params).json()
        if response.get("ok") and response.get("result"):
            for update in response["result"]:
                last_update_id = update["update_id"]
                if "message" in update and "text" in update["message"]:
                    if update["message"]["text"] == "/상태":
                        msg = (f"🤖 [반다이 봇 상태 보고]\n"
                               f"🔄 감시 횟수: {cycle_count}회차\n"
                               f"📦 감시 상품 총합: {len(last_stock_status)}개")
                        send_message(msg)
    except: pass

def get_paged_url(url, page_num):
    """긴 주소에서 page 파라미터만 정확히 교체합니다."""
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    params['page'] = [str(page_num)] # page 번호 교체
    new_query = urlencode(params, doseq=True)
    return urlunparse(parsed._replace(query=new_query))

def scan_category(category_url):
    try:
        proxy_url = f"{GOOGLE_PROXY_URL}?url={category_url}"
        response = requests.get(proxy_url, timeout=30)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        items = soup.find_all('li')
        updates = []
        found_in_page = 0
        
        for item in items:
            link_tag = item.find('a', href=re.compile(r'gno='))
            if not link_tag: continue
            
            found_in_page += 1
            p_name = ' '.join(item.get_text(separator=' ', strip=True).split())
            p_id = link_tag['href'].split('gno=')[-1].split('&')[0]
            p_url = f"https://www.bnkrmall.co.kr{link_tag['href']}" if link_tag['href'].startswith('/') else link_tag['href']

            # 링크(a 태그)가 존재하면 재고 있음으로 판단
            current_status = "재고있음"
            
            if p_id in last_stock_status:
                if last_stock_status[p_id] == "품절" and current_status == "재고있음":
                    updates.append(f"🚨 [재입고!] {p_name[:35]}...\n{p_url}")
            
            last_stock_status[p_id] = current_status
        return updates, found_in_page
    except Exception as e:
        print(f"오류: {e}")
        return [], 0

if __name__ == "__main__":
    if os.path.exists("list.txt"):
        with open("list.txt", "r") as f:
            lines = [line.strip() for line in f.readlines() if line.strip()]
        
        send_message("🛠️ 주소 정밀 수술 완료! 이제 모든 페이지를 훑기 시작합니다.")
        
        while True:
            cycle_count += 1
            for line in lines:
                if '|' in line:
                    base_url, max_page = line.split('|')
                    max_page = int(max_page)
                else:
                    base_url, max_page = line, 1

                for p in range(1, max_page + 1):
                    target_p_url = get_paged_url(base_url, p)
                    print(f"🔍 {cycle_count}회차 - {p}/{max_page}페이지 감시 중")
                    
                    found_updates, count = scan_category(target_p_url)
                    for msg in found_updates:
                        send_message(msg)
                    
                    check_commands()
                    time.sleep(2) # 페이지 간 간격
            
            print(f"⏳ {cycle_count}회차 완료. 총 {len(last_stock_status)}개 상품 감시 중.")
            for _ in range(10): # 10초 대기 중 명령어 확인
                check_commands()
                time.sleep(1)
