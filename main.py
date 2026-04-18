import os
import requests
import time
import re
from bs4 import BeautifulSoup

print("🚀 [System] 그물망 파싱 엔진으로 긴급 교체!")

token = os.environ.get('TELEGRAM_TOKEN')
chat_id = os.environ.get('TELEGRAM_CHAT_ID')
GOOGLE_PROXY_URL = "https://script.google.com/macros/s/AKfycbwHH20V6XscVYYIek80dI0symQT3P3cnCZkqqCyGijhpjOkNNzbQsvUR5oNyU0ndUMR/exec"

tracked_products = {} 
cycle_count = 0
last_update_id = -1

def send_message(text):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {'chat_id': chat_id, 'text': text}
    try: requests.post(url, data=payload)
    except: pass

def check_commands():
    global last_update_id
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
                        send_message(f"📊 [상태보고]\n🔄 {cycle_count}회차 감시 중\n📦 현재 인지 상품: {len(tracked_products)}개")
                    elif cmd == "/추적상품확인":
                        if not tracked_products:
                            send_message("아직 수집된 데이터가 없습니다.")
                            continue
                        names = sorted(tracked_products.values())
                        send_message(f"📦 총 {len(names)}개 상품 감시 중")
                        for i in range(0, len(names), 30):
                            chunk = names[i:i+30]
                            msg = [f"{i+idx+1}. {name}" for idx, name in enumerate(chunk)]
                            send_message(f"📋 [목록 {i//30 + 1}]\n" + "\n".join(msg))
                            time.sleep(0.5)
    except: pass

def scan_target(session, url, new_items_list):
    try:
        # PC 버전 헤더로 원복
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
        proxy_url = f"{GOOGLE_PROXY_URL}?url={url}"
        response = session.get(proxy_url, headers=headers, timeout=30)
        
        # [핵심] HTML 소스가 너무 짧으면(차단) 에러 처리
        if len(response.text) < 1000:
            print(f"⚠️ 페이지 로딩 실패 혹은 차단됨: {url}")
            return 0

        soup = BeautifulSoup(response.text, 'html.parser')
        
        # [그물망 로직] gno=숫자 형태의 모든 링크를 다 찾음
        product_links = soup.find_all('a', href=re.compile(r'gno=\d+'))
        
        found_count = 0
        for link in product_links:
            href = link.get_text(strip=True)
            # 링크 텍스트가 너무 짧으면 상품명이 아닐 확률이 높으므로 건너뜀
            if len(href) < 5: continue 
            
            p_id = link['href'].split('gno=')[-1].split('&')[0]
            if p_id not in tracked_products:
                tracked_products[p_id] = href
                new_items_list.append(href)
                found_count += 1
        return found_count
    except Exception as e:
        print(f"❌ 에러: {e}")
        return 0

if __name__ == "__main__":
    if os.path.exists("list.txt"):
        with open("list.txt", "r") as f:
            urls = [line.strip() for line in f.readlines() if line.strip() and not line.startswith("#")]
        
        send_message(f"🤖 PC 버전 그물망 감시 엔진 가동!")
        session = requests.Session()
        
        while True:
            cycle_count += 1
            found_this_cycle = [] 
            
            for url in urls:
                check_commands()
                scan_target(session, url, found_this_cycle)
                time.sleep(3) # 안정성을 위해 3초 대기
            
            if found_this_cycle:
                for i in range(0, len(found_this_cycle), 30):
                    chunk = found_this_cycle[i:i+30]
                    msg = [f"{i+idx+1}. {name}" for idx, name in enumerate(chunk)]
                    send_message(f"🚨 [신규 포착]\n" + "\n".join(msg))
                    time.sleep(0.5)
            
            print(f"⏳ {cycle_count}회차 완료. 누적 {len(tracked_products)}개.")
            for _ in range(30):
                check_commands()
                time.sleep(1)
