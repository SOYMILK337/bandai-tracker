import os
import requests
import time
import re
from bs4 import BeautifulSoup

print("🚀 [System] 모바일 기반 정밀 감시 엔진 가동!")

token = os.environ.get('TELEGRAM_TOKEN')
chat_id = os.environ.get('TELEGRAM_CHAT_ID')
GOOGLE_PROXY_URL = "https://script.google.com/macros/s/AKfycbwHH20V6XscVYYIek80dI0symQT3P3cnCZkqqCyGijhpjOkNNzbQsvUR5oNyU0ndUMR/exec"

# 상품 정보를 저장 (ID: 상품명)
tracked_products = {} 
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
                        send_message("🔍 실시간 재고 현황을 파악 중입니다.")
                    elif cmd == "/추적상품확인":
                        if not tracked_products:
                            send_message("아직 수집된 데이터가 없습니다.")
                            continue
                        
                        # 전체 리스트 30개씩 끊어 보내기
                        sorted_names = sorted(tracked_products.values())
                        total = len(sorted_names)
                        send_message(f"📦 총 {total}개의 상품을 감시 중입니다.")
                        
                        for i in range(0, total, 30):
                            chunk = sorted_names[i:i+30]
                            msg = [f"{i+idx+1}. {name}" for idx, name in enumerate(chunk)]
                            send_message(f"📋 [목록 {i//30 + 1}]\n" + "\n".join(msg))
                            time.sleep(0.5)
    except: pass

def scan_target(session, url, new_items_list):
    try:
        proxy_url = f"{GOOGLE_PROXY_URL}?url={url}"
        response = session.get(proxy_url, timeout=30)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 모바일 버전과 PC 버전 모두 대응 가능한 선택자
        items = soup.select('.main-product-tab-goods > li') or soup.select('.goods_item') or soup.find_all('li', attrs={'data-childno': True})
        
        for item in items:
            link_tag = item.find('a', href=re.compile(r'gno='))
            if not link_tag: continue
            
            p_id = link_tag['href'].split('gno=')[-1].split('&')[0]
            if p_id not in tracked_products:
                name_tag = item.find('h5') or item.select_one('.font-15') or item.select_one('.name')
                p_name = name_tag.get_text(strip=True) if name_tag else "상품명 미상"
                
                tracked_products[p_id] = p_name
                new_items_list.append(p_name)
                
        return len(items)
    except: return 0

if __name__ == "__main__":
    if os.path.exists("list.txt"):
        with open("list.txt", "r") as f:
            urls = [line.strip() for line in f.readlines() if line.strip() and not line.startswith("#")]
        
        send_message(f"🤖 모바일 모드 감시 시작! (대상: {len(urls)}개 카테고리)")
        session = requests.Session()
        
        while True:
            cycle_count += 1
            total_visible_now = 0
            found_this_cycle = [] 
            
            for url in urls:
                check_commands()
                total_visible_now += scan_target(session, url, found_this_cycle)
                time.sleep(5)
            
            # 신규 상품 발견 시 30개씩 묶어서 보고
            if found_this_cycle:
                for i in range(0, len(found_this_cycle), 30):
                    chunk = found_this_cycle[i:i+30]
                    msg = [f"{i+idx+1}. {name}" for idx, name in enumerate(chunk)]
                    send_message(f"🚨 [신규 포착]\n" + "\n".join(msg))
                    time.sleep(0.5)
            
            if report_requested:
                send_message(f"📋 [보고] {cycle_count}회차 완료\n📦 현재 감시 중인 고유 상품: {len(tracked_products)}개\n✨ 중복 없이 정상 수집 중입니다.")
                report_requested = False
            
            for _ in range(30):
                check_commands()
                time.sleep(1)
