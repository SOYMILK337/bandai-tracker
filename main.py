import os
import requests
import time
import re
from bs4 import BeautifulSoup

# [설정]
token = os.environ['TELEGRAM_TOKEN']
chat_id = os.environ['TELEGRAM_CHAT_ID']
GOOGLE_PROXY_URL = "https://script.google.com/macros/s/AKfycbwHH20V6XscVYYIek80dI0symQT3P3cnCZkqqCyGijhpjOkNNzbQsvUR5oNyU0ndUMR/exec"

# 상태 관리를 위한 변수
last_stock_status = {}
cycle_count = 0  # 몇 바퀴 돌았는지 카운트
last_update_id = -1 # 읽은 메시지 번호 기억

def send_message(text):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {'chat_id': chat_id, 'text': text}
    requests.post(url, data=payload)

def check_commands():
    """텔레그램 메시지를 확인하여 명령어를 처리합니다."""
    global last_update_id, cycle_count
    try:
        url = f"https://api.telegram.org/bot{token}/getUpdates"
        # 최근 메시지만 가져오기
        params = {'offset': last_update_id + 1, 'timeout': 1}
        response = requests.get(url, params=params).json()
        
        if response.get("ok") and response.get("result"):
            for update in response["result"]:
                last_update_id = update["update_id"]
                if "message" in update and "text" in update["message"]:
                    user_text = update["message"]["text"]
                    
                    if user_text == "/상태":
                        msg = (f"🤖 [반다이 봇 상태 보고]\n"
                               f"✅ 현재 정상 작동 중입니다!\n"
                               f"🔄 감시 횟수: {cycle_count}회차\n"
                               f"📦 감시 중인 상품: {len(last_stock_status)}개")
                        send_message(msg)
    except Exception as e:
        print(f"명령어 확인 중 오류: {e}")

def scan_category(category_url):
    try:
        proxy_url = f"{GOOGLE_PROXY_URL}?url={category_url}"
        response = requests.get(proxy_url, timeout=30)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        items = soup.select('.prod_list > li') or soup.select('.list_common > li')
        updates = []
        
        for item in items:
            name_tag = item.select_one('.prod_name') or item.select_one('.goods_name')
            if not name_tag: continue
            
            p_name = name_tag.get_text(strip=True)
            link_tag = name_tag.find('a')
            
            if link_tag and 'gno=' in link_tag['href']:
                p_id = link_tag['href'].split('gno=')[-1].split('&')[0]
                p_url = f"https://www.bnkrmall.co.kr{link_tag['href']}"
            else:
                p_id = p_name
                p_url = "링크 없음"

            current_status = "재고있음" if link_tag else "품절"
            
            if p_id in last_stock_status:
                if last_stock_status[p_id] == "품절" and current_status == "재고있음":
                    updates.append(f"🚨 [재입고 포착!] {p_name}\n주소: {p_url}")
            
            last_stock_status[p_id] = current_status
            
        return updates
    except Exception as e:
        print(f"스캔 오류: {e}")
        return []

if __name__ == "__main__":
    if os.path.exists("list.txt"):
        with open("list.txt", "r") as f:
            lines = [line.strip() for line in f.readlines() if line.strip()]
        
        send_message("⚙️ 실시간 감시 및 명령어 모드가 시작되었습니다.\n'/상태'를 입력하면 현재 상황을 알려드려요!")
        
        while True:
            cycle_count += 1 # 사이클 횟수 증가
            
            for line in lines:
                # 명령어 확인 (페이지 스캔 사이사이에 확인)
                check_commands()
                
                if '|' in line:
                    raw_url, max_page = line.split('|')
                    max_page = int(max_page)
                else:
                    raw_url, max_page = line, 1
                
                clean_url = re.sub(r'[&?]page=\d+', '', raw_url)
                separator = '&' if '?' in clean_url else '?'

                for p in range(1, max_page + 1):
                    p_url = f"{clean_url}{separator}page={p}"
                    print(f"🔍 {cycle_count}회차 감시 중: {p_url}")
                    
                    found_updates = scan_category(p_url)
                    for msg in found_updates:
                        send_message(msg)
                    
                    time.sleep(2)
            
            # 한 사이클 종료 후 대기 시간에도 명령어 확인
            for _ in range(10): # 10초 대기하는 동안 1초마다 명령어 확인
                check_commands()
                time.sleep(1)
    else:
        print("⚠️ list.txt 파일이 보이지 않습니다.")
