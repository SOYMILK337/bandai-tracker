import os
import requests
import time
import re
from bs4 import BeautifulSoup

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
                    user_text = update["message"]["text"]
                    if user_text == "/상태":
                        msg = (f"🤖 [반다이 봇 상태 보고]\n"
                               f"✅ 정상 가동 중 (무한 루프)\n"
                               f"🔄 감시 횟수: {cycle_count}회차\n"
                               f"📦 감시 중인 상품: {len(last_stock_status)}개")
                        send_message(msg)
    except: pass

def scan_category(category_url):
    try:
        proxy_url = f"{GOOGLE_PROXY_URL}?url={category_url}"
        response = requests.get(proxy_url, timeout=30)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # [수정] 클래스 이름 대신 'gno=' 링크를 가진 모든 li 태그를 타겟팅합니다.
        items = soup.find_all('li')
        updates = []
        
        found_count = 0
        for item in items:
            # 해당 li 안에 상품 상세 링크가 있는지 확인
            link_tag = item.find('a', href=re.compile(r'gno='))
            if not link_tag: continue
            
            found_count += 1
            # 상품명 추출 (태그 내의 텍스트 중 가장 긴 것을 상품명으로 간주)
            p_name = item.get_text(separator=' ', strip=True)
            # 불필요한 공백/줄바꿈 정리
            p_name = ' '.join(p_name.split())
            
            p_id = link_tag['href'].split('gno=')[-1].split('&')[0]
            p_url = f"https://www.bnkrmall.co.kr{link_tag['href']}" if link_tag['href'].startswith('/') else link_tag['href']

            # 주인님의 통찰: 링크(a 태그) 내부에 특정 '품절' 마크가 있는지 확인
            # (반다이몰은 품절 시 a 태그를 지우거나 특정 클래스를 부여함)
            is_sold_out = "sold_out" in str(item) or "품절" in item.get_text()
            current_status = "품절" if is_sold_out else "재고있음"
            
            if p_id in last_stock_status:
                if last_stock_status[p_id] == "품절" and current_status == "재고있음":
                    updates.append(f"🚨 [재입고!] {p_name[:40]}...\n주소: {p_url}")
            
            last_stock_status[p_id] = current_status
            
        print(f"📊 이 페이지에서 {found_count}개의 상품을 발견했습니다.")
        return updates
    except Exception as e:
        print(f"스캔 오류: {e}")
        return []

if __name__ == "__main__":
    if os.path.exists("list.txt"):
        with open("list.txt", "r") as f:
            lines = [line.strip() for line in f.readlines() if line.strip()]
        
        send_message("🛠️ 시력 교정 완료! 정밀 감시를 다시 시작합니다.")
        
        while True:
            cycle_count += 1
            for line in lines:
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
            
            for _ in range(10):
                check_commands()
                time.sleep(1)
