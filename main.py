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

def scan_with_session(session, target_url, referer_url=None):
    """세션을 유지하며 페이지를 훑습니다."""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,sharp',
            'Referer': referer_url if referer_url else 'https://www.bnkrmall.co.kr/'
        }
        
        proxy_url = f"{GOOGLE_PROXY_URL}?url={target_url}"
        # 세션을 사용해 쿠키를 자동으로 주고받습니다.
        response = session.get(proxy_url, headers=headers, timeout=30)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        items = soup.find_all('li')
        updates = []
        found_count = 0
        
        for item in items:
            link_tag = item.find('a', href=re.compile(r'gno='))
            if not link_tag: continue
            
            p_id = link_tag['href'].split('gno=')[-1].split('&')[0]
            p_name = ' '.join(item.get_text(separator=' ', strip=True).split())
            p_url = f"https://www.bnkrmall.co.kr{link_tag['href']}" if link_tag['href'].startswith('/') else link_tag['href']

            current_status = "재고있음" 
            if p_id in last_stock_status:
                if last_stock_status[p_id] == "품절" and current_status == "재고있음":
                    updates.append(f"🚨 [재입고!] {p_name[:35]}...\n{p_url}")
            
            last_stock_status[p_id] = current_status
            found_count += 1
            
        return updates, found_count
    except:
        return [], 0

if __name__ == "__main__":
    if os.path.exists("list.txt"):
        with open("list.txt", "r") as f:
            target_pages = [line.strip() for line in f.readlines() if line.strip()]
        
        send_message(f"📡 세션 모드 가동! {len(target_pages)}개 페이지 정밀 스캔을 시작합니다.")
        
        # [핵심] 세션 객체 생성 (브라우저처럼 행동 시작)
        session = requests.Session()
        
        while True:
            cycle_count += 1
            prev_url = None # 이전 페이지 주소 저장용
            
            for url in target_pages:
                print(f"🔍 {cycle_count}회차 감시 중: {url[:60]}...")
                
                # 이전 페이지를 Referer로 넣어서 서버를 속입니다.
                found_updates, count = scan_with_session(session, url, prev_url)
                for msg in found_updates:
                    send_message(msg)
                
                prev_url = url # 현재 주소를 다음 페이지의 '이전 주소'로 저장
                time.sleep(3) # 보안 우회를 위해 약간 더 여유 있게 쉽니다.
            
            print(f"⏳ {cycle_count}회차 완료. 누적 상품: {len(last_stock_status)}개")
            time.sleep(10)
