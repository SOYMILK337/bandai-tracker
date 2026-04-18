import os
import requests
import time
import re
from bs4 import BeautifulSoup

print("🚀 [System] 벌크 보고 모드(30개 단위) 가동!")

token = os.environ.get('TELEGRAM_TOKEN')
chat_id = os.environ.get('TELEGRAM_CHAT_ID')
GOOGLE_PROXY_URL = "https://script.google.com/macros/s/AKfycbwHH20V6XscVYYIek80dI0symQT3P3cnCZkqqCyGijhpjOkNNzbQsvUR5oNyU0ndUMR/exec"

tracked_products = set() 
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
                        send_message("🔍 현재 판매 중인 목록을 전체 스캔 중입니다.")
                    elif cmd == "/추적상품확인":
                        send_message(f"📦 현재 총 {len(tracked_products)}개의 상품이 목록에 노출되어 있습니다.")
    except: pass

def scan_target(session, url, new_items_list):
    """신규 상품을 찾으면 리스트에 담기만 합니다."""
    try:
        proxy_url = f"{GOOGLE_PROXY_URL}?url={url}"
        response = session.get(proxy_url, timeout=30)
        soup = BeautifulSoup(response.text, 'html.parser')
        items = soup.select('.main-product-tab-goods > li') or soup.find_all('li', attrs={'data-childno': True})
        
        for item in items:
            link_tag = item.find('a', href=re.compile(r'gno='))
            if not link_tag: continue
            
            p_id = link_tag['href'].split('gno=')[-1].split('&')[0]
            if p_id not in tracked_products:
                name_tag = item.find('h5') or item.select_one('.font-15')
                p_name = name_tag.get_text(strip=True) if name_tag else "상품명 미상"
                
                # 링크 없이 이름만 저장
                new_items_list.append(p_name)
                tracked_products.add(p_id)
                
        return len(items)
    except: return 0

if __name__ == "__main__":
    if os.path.exists("list.txt"):
        with open("list.txt", "r") as f:
            urls = [line.strip() for line in f.readlines() if line.strip() and not line.startswith("#")]
        
        send_message(f"🤖 실시간 감시 가동! (30개 단위 벌크 보고)")
        session = requests.Session()
        
        while True:
            cycle_count += 1
            total_visible = 0
            found_this_cycle = [] # 이번 회차에 새로 발견한 상품들 바구니
            
            for url in urls:
                check_commands()
                total_visible += scan_target(session, url, found_this_cycle)
                time.sleep(5)
            
            # [핵심] 새로 발견한 상품이 있다면 30개씩 묶어서 발송
            if found_this_cycle:
                total_new = len(found_this_cycle)
                send_message(f"🚨 [신규 포착!] 총 {total_new}개의 상품이 새로 나타났습니다.")
                
                for i in range(0, total_new, 30):
                    chunk = found_this_cycle[i:i+30]
                    msg_list = [f"{i + idx + 1}. {name}" for idx, name in enumerate(chunk)]
                    send_message(f"📦 [포착 리스트 {i//30 + 1}]\n" + "\n".join(msg_list))
                    time.sleep(0.5)
            
            if report_requested:
                send_message(f"📋 [감시 보고]\n🔄 {cycle_count}회차 완료\n📦 현재 구매 가능 상품: {total_visible}개")
                report_requested = False
            
            print(f"⏳ {cycle_count}회차 완료. 누적 {len(tracked_products)}개 기체 인지 중.")
            for _ in range(30):
                check_commands()
                time.sleep(1)
