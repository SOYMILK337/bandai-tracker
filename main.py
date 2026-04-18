import os
import requests
import time
import re
from bs4 import BeautifulSoup

# [진단] 봇 엔진 가동
print("🚀 [System] 모바일 정밀 탐색 엔진 가동!")

token = os.environ.get('TELEGRAM_TOKEN')
chat_id = os.environ.get('TELEGRAM_CHAT_ID')
GOOGLE_PROXY_URL = "https://script.google.com/macros/s/AKfycbwHH20V6XscVYYIek80dI0symQT3P3cnCZkqqCyGijhpjOkNNzbQsvUR5oNyU0ndUMR/exec"

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
                        send_message("🔍 현재 모든 모바일 카테고리를 스캔 중입니다.")
                    elif cmd == "/추적상품확인":
                        if not tracked_products:
                            send_message("수집된 데이터가 0개입니다. 잠시 후 다시 시도해 주세요.")
                            continue
                        sorted_names = sorted(tracked_products.values())
                        total = len(sorted_names)
                        send_message(f"📦 총 {total}개 상품 감시 중")
                        for i in range(0, total, 30):
                            chunk = sorted_names[i:i+30]
                            msg = [f"{i+idx+1}. {name}" for idx, name in enumerate(chunk)]
                            send_message(f"📋 [목록 {i//30 + 1}]\n" + "\n".join(msg))
                            time.sleep(0.5)
    except: pass

def scan_target(session, url, new_items_list):
    try:
        # [수정] 실제 모바일 기기(아이폰)처럼 보이도록 헤더 설정
        headers = {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1',
            'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7'
        }
        proxy_url = f"{GOOGLE_PROXY_URL}?url={url}"
        response = session.get(proxy_url, headers=headers, timeout=30)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # [수정] 모바일 페이지의 모든 상품 리스트 후보군을 탐색
        items = soup.find_all('li') + soup.find_all('div', class_=re.compile(r'item|goods'))
        
        found_in_this_page = 0
        for item in items:
            link_tag = item.find('a', href=re.compile(r'gno='))
            if not link_tag: continue
            
            p_id = link_tag['href'].split('gno=')[-1].split('&')[0]
            if p_id not in tracked_products:
                # 상품명 추출 (p, span, h5 등 모바일에서 쓰이는 모든 태그 확인)
                name_tag = item.find('p', class_='name') or item.find('div', class_='name') or item.find('h5') or item.find('span', class_='tit')
                p_name = name_tag.get_text(strip=True) if name_tag else "이름 없는 상품"
                
                tracked_products[p_id] = p_name
                new_items_list.append(p_name)
                found_in_this_page += 1
                
        return found_in_this_page
    except Exception as e:
        print(f"❌ 스캔 에러: {e}")
        return 0

if __name__ == "__main__":
    if os.path.exists("list.txt"):
        with open("list.txt", "r") as f:
            urls = [line.strip() for line in f.readlines() if line.strip() and not line.startswith("#")]
        
        send_message(f"🤖 모바일 정밀 감시 시작! (감시 페이지: {len(urls)}개)")
        session = requests.Session()
        
        while True:
            cycle_count += 1
            total_found_now = 0
            found_this_cycle = [] 
            
            for url in urls:
                check_commands()
                count = scan_target(session, url, found_this_cycle)
                total_found_now += count
                time.sleep(5)
            
            # 신규 발견 상품 보고 (30개 단위)
            if found_this_cycle:
                for i in range(0, len(found_this_cycle), 30):
                    chunk = found_this_cycle[i:i+30]
                    msg = [f"{i+idx+1}. {name}" for idx, name in enumerate(chunk)]
                    send_message(f"🚨 [신규 포착]\n" + "\n".join(msg))
                    time.sleep(0.5)
            
            if report_requested:
                send_message(f"📋 [보고] {cycle_count}회차 완료\n📦 현재 감시 중인 고유 상품: {len(tracked_products)}개")
                report_requested = False
            
            print(f"⏳ {cycle_count}회차 완료. 누적 {len(tracked_products)}개.")
            for _ in range(30):
                check_commands()
                time.sleep(1)
