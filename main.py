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

def send_message(text):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {'chat_id': chat_id, 'text': text}
    requests.post(url, data=payload)

def scan_category(category_url):
    try:
        proxy_url = f"{GOOGLE_PROXY_URL}?url={category_url}"
        response = requests.get(proxy_url, timeout=30)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 상품 리스트 영역 찾기
        items = soup.select('.prod_list > li') or soup.select('.list_common > li')
        updates = []
        
        for item in items:
            # 상품명 태그 찾기
            name_tag = item.select_one('.prod_name') or item.select_one('.goods_name')
            if not name_tag: continue
            
            p_name = name_tag.get_text(strip=True)
            # 주인이 발견한 핵심: 재입고 시 a 태그(링크)가 생김!
            link_tag = name_tag.find('a')
            
            # 1. 고유 ID 추출 (태그 내의 gno 번호 또는 상품명 자체를 ID로 사용)
            if link_tag and 'gno=' in link_tag['href']:
                p_id = link_tag['href'].split('gno=')[-1].split('&')[0]
                p_url = f"https://www.bnkrmall.co.kr{link_tag['href']}"
            else:
                p_id = p_name # 링크가 없을 땐 이름을 ID로 활용
                p_url = "링크 없음"

            # 2. 상태 판정 (링크 태그가 존재하면 재고 있음)
            current_status = "재고있음" if link_tag else "품절"
            
            # 3. 상태 변화 체크 (품절 -> 재고있음)
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
        
        print("🛠️ 반다이몰 정밀 카테고리 스캔 모드 가동")
        
        while True:
            for line in lines:
                if '|' in line:
                    raw_url, max_page = line.split('|')
                    max_page = int(max_page)
                else:
                    raw_url, max_page = line, 1
                
                # 주소에서 기존 page=X 부분을 제거 (나중에 우리가 붙이기 위해)
                clean_url = re.sub(r'[&?]page=\d+', '', raw_url)
                # ?가 이미 있으면 &로 연결, 없으면 ?로 연결
                separator = '&' if '?' in clean_url else '?'

                for p in range(1, max_page + 1):
                    p_url = f"{clean_url}{separator}page={p}"
                    print(f"🔍 감시 중: {p_url}")
                    
                    found_updates = scan_category(p_url)
                    for msg in found_updates:
                        send_message(msg)
                    
                    time.sleep(2) # 페이지 간 휴식
            
            print("⏳ 사이클 완료. 10초 대기...")
            time.sleep(10)
    else:
        print("⚠️ list.txt 파일이 보이지 않습니다.")
