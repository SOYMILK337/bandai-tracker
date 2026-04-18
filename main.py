import os
import requests
import time
import re
from bs4 import BeautifulSoup
import urllib.parse # 주소 암호화를 위해 추가

print("🚀 [System] 주소 정밀 타격 엔진으로 업그레이드!")

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
                        send_message(f"📊 [상태보고]\n🔄 {cycle_count}회차 감시 중\n📦 누적 인지 상품: {len(tracked_products)}개")
                    elif cmd == "/추적상품확인":
                        if not tracked_products:
                            send_message("아직 데이터가 없습니다.")
                            continue
                        names = sorted(tracked_products.values())
                        send_message(f"📦 총 {len(names)}개 상품 감시 중 (30개씩 전송)")
                        for i in range(0, len(names), 30):
                            chunk = names[i:i+30]
                            msg = [f"{i+idx+1}. {name}" for idx, name in enumerate(chunk)]
                            send_message(f"📋 [목록 {i//30 + 1}]\n" + "\n".join(msg))
                            time.sleep(0.5)
    except: pass

def scan_target(session, url, new_items_list):
    try:
        # [핵심 수정] 주소를 통째로 암호화하여 프록시에 전달합니다.
        # 이렇게 해야 'chkbrand' 같은 필터가 잘리지 않고 끝까지 전달됩니다.
        encoded_url = urllib.parse.quote(url, safe='')
        proxy_url = f"{GOOGLE_PROXY_URL}?url={encoded_url}"
        
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
        response = session.get(proxy_url, headers=headers, timeout=30)
        
        if len(response.text) < 1000: return 0

        soup = BeautifulSoup(response.text, 'html.parser')
        # gno=숫자 형태의 링크와 텍스트를 정밀하게 추출
        product_links = soup.find_all('a', href=re.compile(r'gno=\d+'))
        
        found_in_page = 0
        for link in product_links:
            p_name = link.get_text(strip=True)
            if len(p_name) < 5: continue # 너무 짧은 텍스트(장바구니 등) 제외
            
            p_id = link['href'].split('gno=')[-1].split('&')[0]
            if p_id not in tracked_products:
                tracked_products[p_id] = p_name
                new_items_list.append(p_name)
                found_in_page += 1
        
        return found_in_page
    except Exception as e:
        print(f"❌ 스캔 에러: {e}")
        return 0

if __name__ == "__main__":
    if os.path.exists("list.txt"):
        with open("list.txt", "r") as f:
            urls = [line.strip() for line in f.readlines() if line.strip() and not line.startswith("#")]
        
        send_message(f"🤖 정밀 타격 엔진 가동! (대상: {len(urls)}개 주소)")
        session = requests.Session()
        
        while True:
            cycle_count += 1
            found_this_cycle = [] 
            
            for url in urls:
                check_commands()
                # 각 페이지별로 돌면서 신규 상품을 수집합니다.
                scan_target(session, url, found_this_cycle)
                time.sleep(3)
            
            # 신규 상품 발견 시 30개 단위 보고
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
