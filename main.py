import os
import requests
import time
import re
from bs4 import BeautifulSoup

print("🚀 [System] 즉시 응답형 엔진으로 업그레이드 완료!")

token = os.environ.get('TELEGRAM_TOKEN')
chat_id = os.environ.get('TELEGRAM_CHAT_ID')
GOOGLE_PROXY_URL = "https://script.google.com/macros/s/AKfycbwHH20V6XscVYYIek80dI0symQT3P3cnCZkqqCyGijhpjOkNNzbQsvUR5oNyU0ndUMR/exec"

tracked_products = {} 
cycle_count = 0
last_update_id = -1
# report_requested 변수는 이제 필요 없어서 삭제합니다.

def send_message(text):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {'chat_id': chat_id, 'text': text}
    try: requests.post(url, data=payload)
    except: pass

def check_commands():
    """명령어를 확인하는 즉시 응답합니다."""
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
                    
                    # [수정] 기다리지 않고 즉시 응답!
                    if cmd == "/상태":
                        status_msg = (
                            f"📊 [실시간 봇 상태]\n"
                            f"🔄 현재 {cycle_count}회차 감시 중\n"
                            f"📦 인지 중인 총 상품: {len(tracked_products)}개\n"
                            f"⏱️ 마지막 확인: 방금 전"
                        )
                        send_message(status_msg)
                        
                    elif cmd == "/추적상품확인":
                        if not tracked_products:
                            send_message("아직 수집된 데이터가 없습니다.")
                            continue
                        sorted_names = sorted(tracked_products.values())
                        total = len(sorted_names)
                        send_message(f"📦 총 {total}개 상품 감시 중 (30개씩 전송)")
                        for i in range(0, total, 30):
                            chunk = sorted_names[i:i+30]
                            msg = [f"{i+idx+1}. {name}" for idx, name in enumerate(chunk)]
                            send_message(f"📋 [목록 {i//30 + 1}]\n" + "\n".join(msg))
                            time.sleep(0.5)
    except: pass

def scan_target(session, url, new_items_list):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1'
        }
        proxy_url = f"{GOOGLE_PROXY_URL}?url={url}"
        response = session.get(proxy_url, headers=headers, timeout=30)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        items = soup.find_all('li') + soup.find_all('div', class_=re.compile(r'item|goods'))
        found_count = 0
        for item in items:
            link_tag = item.find('a', href=re.compile(r'gno='))
            if not link_tag: continue
            
            p_id = link_tag['href'].split('gno=')[-1].split('&')[0]
            if p_id not in tracked_products:
                name_tag = item.find('p', class_='name') or item.find('div', class_='name') or item.find('h5') or item.find('span', class_='tit')
                p_name = name_tag.get_text(strip=True) if name_tag else "이름 없는 상품"
                
                tracked_products[p_id] = p_name
                new_items_list.append(p_name)
                found_count += 1
        return found_count
    except: return 0

if __name__ == "__main__":
    if os.path.exists("list.txt"):
        with open("list.txt", "r") as f:
            urls = [line.strip() for line in f.readlines() if line.strip() and not line.startswith("#")]
        
        send_message(f"🤖 감시 엔진 가동! (응답 속도 개선 버전)")
        session = requests.Session()
        
        while True:
            cycle_count += 1
            found_this_cycle = [] 
            
            for url in urls:
                check_commands() # 여기서 명령어를 체크할 때 바로 답장을 보냅니다!
                scan_target(session, url, found_this_cycle)
                # [수정] 대기 시간을 5초에서 2초로 줄여 회전 속도를 높입니다.
                time.sleep(2)
            
            if found_this_cycle:
                for i in range(0, len(found_this_cycle), 30):
                    chunk = found_this_cycle[i:i+30]
                    msg = [f"{i+idx+1}. {name}" for idx, name in enumerate(chunk)]
                    send_message(f"🚨 [신규 포착]\n" + "\n".join(msg))
                    time.sleep(0.5)
            
            # 메인 루프 끝날 때까지 기다리지 않아도 되므로 하단 report 로직 삭제
            
            print(f"⏳ {cycle_count}회차 완료. 누적 {len(tracked_products)}개.")
            for _ in range(20): # 휴식 시간을 조금 줄임
                check_commands()
                time.sleep(1)
