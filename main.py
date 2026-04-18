import os
import requests
import time
import re
from bs4 import BeautifulSoup

print("🚀 [System] 신규 상품 출현 감지 엔진 가동!")

token = os.environ.get('TELEGRAM_TOKEN')
chat_id = os.environ.get('TELEGRAM_CHAT_ID')
GOOGLE_PROXY_URL = "https://script.google.com/macros/s/AKfycbwHH20V6XscVYYIek80dI0symQT3P3cnCZkqqCyGijhpjOkNNzbQsvUR5oNyU0ndUMR/exec"

tracked_products = set() # 상품 ID만 추적 (존재 여부 확인용)
cycle_count = 0
last_update_id = -1
report_requested = False

def send_message(text):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {'chat_id': chat_id, 'text': text}
    try: requests.post(url, data=payload)
    except: pass

def check_commands():
    global last_update_id, report_requested
    try:
        url = f"https://api.telegram.org/bot{token}/getUpdates"
        params = {'offset': last_update_id + 1, 'timeout': 1}
        response = requests.get(url, params=params).json()
        if response.get("ok") and response.get("result"):
            for update in response["result"]:
                last_update_id = update["update_id"]
                if "message" in update and "text" in update["message"]:
                    cmd = update["message"]["text"]
                    if cmd == "/상태":
                        report_requested = True
                        send_message("🔍 현재 실시간 재고를 스캔 중입니다.")
                    elif cmd == "/추적상품확인":
                        send_message(f"📦 현재 총 {len(tracked_products)}개의 상품이 리스트에 노출되어 있습니다.")
    except: pass

def scan_target(session, url):
    try:
        proxy_url = f"{GOOGLE_PROXY_URL}?url={url}"
        response = session.get(proxy_url, timeout=30)
        soup = BeautifulSoup(response.text, 'html.parser')
        items = soup.select('.main-product-tab-goods > li') or soup.find_all('li', attrs={'data-childno': True})
        
        new_items_found = 0
        for item in items:
            link_tag = item.find('a', href=re.compile(r'gno='))
            if not link_tag: continue
            
            p_id = link_tag['href'].split('gno=')[-1].split('&')[0]
            name_tag = item.find('h5') or item.select_one('.font-15')
            p_name = name_tag.get_text(strip=True) if name_tag else "상품명 미상"
            p_url = f"https://www.bnkrmall.co.kr{link_tag['href']}" if link_tag['href'].startswith('/') else link_tag['href']

            # 핵심 로직: 기존 리스트에 없던 상품이 나타났는가?
            if p_id not in tracked_products:
                # 1회차는 데이터 수집만 하고, 2회차(진짜 감시)부터 알림 전송
                if cycle_count > 1:
                    send_message(f"🚨 [재입고/신규 포착!]\n📦 {p_name}\n🔗 {p_url}")
                
                tracked_products.add(p_id)
                new_items_found += 1
                
        return len(items)
    except: return 0

if __name__ == "__main__":
    if os.path.exists("list.txt"):
        with open("list.txt", "r") as f:
            urls = [line.strip() for line in f.readlines() if line.strip() and not line.startswith("#")]
        
        send_message(f"🤖 실시간 재고 감시 시작! (1회차는 데이터 수집 모드)")
        session = requests.Session()
        
        while True:
            cycle_count += 1
            total_visible = 0
            
            for url in urls:
                check_commands()
                total_visible += scan_target(session, url)
                time.sleep(5)
            
            if report_requested:
                send_message(f"📋 [감시 보고]\n🔄 {cycle_count}회차 완료\n📦 현재 구매 가능 상품: {total_visible}개\n✨ 신규 상품이 나타나면 즉시 알려드릴게요!")
                report_requested = False
            
            print(f"⏳ {cycle_count}회차 완료. 현재 {len(tracked_products)}개 상품 인지 중.")
            for _ in range(30):
                check_commands()
                time.sleep(1)
