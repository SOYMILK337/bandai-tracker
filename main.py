import os
import requests
import time
import re
from bs4 import BeautifulSoup

# [설정]
token = os.environ['TELEGRAM_TOKEN']
chat_id = os.environ['TELEGRAM_CHAT_ID']
GOOGLE_PROXY_URL = "https://script.google.com/macros/s/AKfycbwHH20V6XscVYYIek80dI0symQT3P3cnCZkqqCyGijhpjOkNNzbQsvUR5oNyU0ndUMR/exec"

# 상품 정보를 저장할 딕셔너리 (ID: {"name": 이름, "status": 상태})
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
                    user_text = update["message"]["text"]
                    
                    if user_text == "/상태":
                        report_requested = True
                        send_message("🔍 사이클 완료 후 전체 요약을 보고하겠습니다.")
                    
                    elif user_text == "/추적상품확인":
                        if not tracked_products:
                            send_message("아직 수집된 상품이 없습니다. 한 바퀴 돌 때까지 기다려 주세요!")
                            continue
                        
                        # 상품명 리스트 추출
                        product_names = [info['name'] for info in tracked_products.values()]
                        total_count = len(product_names)
                        send_message(f"📋 총 {total_count}개의 상품을 추적 중입니다. 리스트를 전송합니다.")
                        
                        # 30개 단위로 끊어서 전송
                        for i in range(0, total_count, 30):
                            chunk = product_names[i:i+30]
                            msg_list = []
                            for idx, name in enumerate(chunk):
                                msg_list.append(f"{i + idx + 1}. {name}")
                            
                            send_message(f"📦 [추적 상품 리스트 {i//30 + 1}]\n" + "\n".join(msg_list))
                            time.sleep(0.5) # 텔레그램 도배 방지용 짧은 휴식
    except: pass

def scan_page(session, target_url, prev_url):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': prev_url
        }
        proxy_url = f"{GOOGLE_PROXY_URL}?url={target_url}"
        response = session.get(proxy_url, headers=headers, timeout=30)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        items = soup.select('.main-product-tab-goods > li') or soup.find_all('li', attrs={'data-childno': True})
        found_in_page = 0
        
        for item in items:
            link_tag = item.find('a', href=re.compile(r'gno='))
            if not link_tag: continue
            
            p_id = link_tag['href'].split('gno=')[-1].split('&')[0]
            name_tag = item.find('h5') or item.select_one('.font-15')
            p_name = name_tag.get_text(strip=True) if name_tag else "상품명 미상"
            p_url = f"https://www.bnkrmall.co.kr{link_tag['href']}" if link_tag['href'].startswith('/') else link_tag['href']

            is_sold_out = "sold_out" in str(item).lower() or "품절" in item.get_text()
            current_status = "품절" if is_sold_out else "재고있음"
            
            # 재입고 알림 로직
            if p_id in tracked_products:
                if tracked_products[p_id]['status'] == "품절" and current_status == "재고있음":
                    send_message(f"🚨 [재입고 포착!]\n📦 {p_name}\n🔗 {p_url}")
            
            # 정보 업데이트 (이름과 상태를 모두 저장)
            tracked_products[p_id] = {"name": p_name, "status": current_status}
            found_in_page += 1
            
        return found_in_page
    except:
        return 0

if __name__ == "__main__":
    if os.path.exists("list.txt"):
        with open("list.txt", "r") as f:
            urls = [line.strip() for line in f.readlines() if line.strip()]
        
        send_message(f"🛠️ 정밀 감시 시스템 가동!\n- 감시 페이지: {len(urls)}개\n- 명령어: /상태, /추적상품확인")
        
        session = requests.Session()
        
        while True:
            cycle_count += 1
            items_this_cycle = 0
            referer = "https://www.bnkrmall.co.kr/main/gunpla_index.do"
            
            for url in urls:
                check_commands()
                count = scan_page(session, url, referer)
                items_this_cycle += count
                referer = url
                time.sleep(4)
            
            if report_requested:
                msg = (f"📋 [정밀 감시 보고]\n"
                       f"🔄 {cycle_count}회차 완료\n"
                       f"📦 이번 회차 확인 상품: {items_this_cycle}개\n"
                       f"🗃️ 누적 관리 상품 총합: {len(tracked_products)}개")
                send_message(msg)
                report_requested = False
            
            for _ in range(15):
                check_commands()
                time.sleep(1)
    else:
        print("list.txt 파일이 없습니다.")
