import os
import requests
import time
import re
from bs4 import BeautifulSoup

# [진단] 봇이 실행되자마자 깃허브 로그에 찍힐 메시지
print("🚀 [System] 봇 엔진 가동 시작!")

# 환경 변수 로드
token = os.environ.get('TELEGRAM_TOKEN')
chat_id = os.environ.get('TELEGRAM_CHAT_ID')
GOOGLE_PROXY_URL = "https://script.google.com/macros/s/AKfycbwHH20V6XscVYYIek80dI0symQT3P3cnCZkqqCyGijhpjOkNNzbQsvUR5oNyU0ndUMR/exec"

# [진단] 변수 체크
if not token or not chat_id:
    print("❌ [Error] 텔레그램 토큰이나 ID가 설정되지 않았습니다. Secrets를 확인하세요!")
    exit()

tracked_products = {}
cycle_count = 0
last_update_id = -1
report_requested = False

def send_message(text):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {'chat_id': chat_id, 'text': text}
    try:
        r = requests.post(url, data=payload)
        print(f"📡 [Telegram] 메시지 전송 상태: {r.status_code}")
    except Exception as e:
        print(f"❌ [Telegram] 전송 실패: {e}")

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
                    txt = update["message"]["text"]
                    if txt == "/상태":
                        report_requested = True
                        send_message("🫡 현재 사이클 완료 후 보고하겠습니다.")
                    elif txt == "/추적상품확인":
                        # (추적 상품 리스트 전송 로직 생략 - 이전 답변과 동일)
                        send_message(f"📦 현재 {len(tracked_products)}개 상품 추적 중...")
    except: pass

def scan_page(session, target_url, prev_url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0...', 'Referer': prev_url}
        proxy_url = f"{GOOGLE_PROXY_URL}?url={target_url}"
        response = session.get(proxy_url, headers=headers, timeout=30)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 주인님의 필터 링크 전용 수집 로직
        items = soup.select('.main-product-tab-goods > li')
        found_count = 0
        
        for item in items:
            link_tag = item.find('a', href=re.compile(r'gno='))
            if not link_tag: continue
            
            p_id = link_tag['href'].split('gno=')[-1].split('&')[0]
            name_tag = item.find('h5') or item.select_one('.font-15')
            p_name = name_tag.get_text(strip=True) if name_tag else "상품명 미상"
            
            is_sold_out = "sold_out" in str(item).lower() or "품절" in item.get_text()
            current_status = "품절" if is_sold_out else "재고있음"
            
            # 상태 변화 감지 (품절 -> 재고있음)
            if p_id in tracked_products:
                if tracked_products[p_id]['status'] == "품절" and current_status == "재고있음":
                    send_message(f"🚨 [입고!] {p_name}\nhttps://www.bnkrmall.co.kr{link_tag['href']}")
            
            tracked_products[p_id] = {"name": p_name, "status": current_status}
            found_count += 1
            
        return found_count
    except Exception as e:
        print(f"❌ [Scan Error] {e}")
        return 0

if __name__ == "__main__":
    print("🔍 [System] 메인 감시 루프 진입 시도...")
    
    if os.path.exists("list.txt"):
        with open("list.txt", "r") as f:
            urls = [line.strip() for line in f.readlines() if line.strip()]
        
        if not urls:
            print("⚠️ [Warning] list.txt 파일이 비어 있습니다. 감시할 주소를 넣어주세요!")
            exit()
            
        print(f"✅ [System] 감시 시작! 대상 페이지: {len(urls)}개")
        send_message(f"🤖 반다이 봇 가동! ({len(urls)}개 페이지)")
        
        session = requests.Session()
        
        while True:
            cycle_count += 1
            items_this_cycle = 0
            referer = "https://www.bnkrmall.co.kr/"
            
            for url in urls:
                check_commands()
                count = scan_page(session, url, referer)
                items_scanned_now += count
                referer = url
                time.sleep(5)
            
            if report_requested:
                send_message(f"📋 [보고] {cycle_count}회차 완료. 상품 {len(tracked_products)}개 관리 중.")
                report_requested = False
                
            print(f"⏳ {cycle_count}회차 완료. 대기 중...")
            for _ in range(30): # 30초 대기
                check_commands()
                time.sleep(1)
    else:
        # 이 메시지가 뜬다면 파일 위치가 잘못된 것입니다!
        print("❌ [Fatal Error] list.txt 파일을 찾을 수 없습니다!")
