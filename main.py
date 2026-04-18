import os
import requests
import time
import re
from bs4 import BeautifulSoup
import urllib.parse
from datetime import datetime

print("🚀 [System] 오용진 님 전용 정밀 필터링 엔진 가동!")

token = os.environ.get('TELEGRAM_TOKEN')
chat_id = os.environ.get('TELEGRAM_CHAT_ID')
GOOGLE_PROXY_URL = "https://script.google.com/macros/s/AKfycbwHH20V6XscVYYIek80dI0symQT3P3cnCZkqqCyGijhpjOkNNzbQsvUR5oNyU0ndUMR/exec"

# 감시 데이터 저장소
known_in_stock_ids = set() # 이미 알림을 보낸 재고 있는 상품들
cycle_count = 0
last_update_id = -1
last_check_time = "대기 중..."
status_report_requested = False # /상태 명령 대기 플래그

def send_message(text):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {'chat_id': chat_id, 'text': text}
    try: requests.post(url, data=payload)
    except: pass

def clean_product_name(raw_name):
    """불필요한 키워드와 가격 정보를 제거합니다."""
    # 좋아요, 장바구니, 가격(숫자+원) 제거
    clean = re.sub(r'좋아요|장바구니|\d{1,3}(,\d{3})*원', '', raw_name)
    return clean.strip()

def check_commands():
    """사용자 명령어를 체크하여 플래그를 설정합니다."""
    global last_update_id, status_report_requested
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
                        status_report_requested = True
                        send_message("🔍 명령 확인. 모든 페이지 스캔 후 최종 보고서를 전송하겠습니다.")
                    elif cmd == "/추적상품확인":
                        # 수동 확인 시에만 전체 목록 전송
                        send_message(f"📦 현재 감시망에 포착된 상품은 총 {len(known_in_stock_ids)}개입니다.")
    except: pass

def scan_target(session, url, current_cycle_items):
    global last_check_time
    try:
        encoded_url = urllib.parse.quote(url, safe='')
        proxy_url = f"{GOOGLE_PROXY_URL}?url={encoded_url}"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
        response = session.get(proxy_url, headers=headers, timeout=30)
        
        last_check_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        if len(response.text) < 1000: return
        
        soup = BeautifulSoup(response.text, 'html.parser')
        product_links = soup.find_all('a', href=re.compile(r'gno=\d+'))
        
        for link in product_links:
            p_id = link['href'].split('gno=')[-1].split('&')[0]
            raw_name = link.get_text(strip=True)
            if len(raw_name) < 10: continue # 너무 짧은 텍스트 제외
            
            clean_name = clean_product_name(raw_name)
            current_cycle_items[p_id] = clean_name
    except Exception as e:
        print(f"❌ 스캔 에러: {e}")

if __name__ == "__main__":
    if os.path.exists("list.txt"):
        with open("list.txt", "r") as f:
            urls = [line.strip() for line in f.readlines() if line.strip() and not line.startswith("#")]
        
        send_message(f"🤖 오용진 님, 건프라 정밀 감시 시스템 가동합니다. (보고 지연 및 이름 정제 적용)")
        session = requests.Session()
        
        while True:
            cycle_count += 1
            current_cycle_items = {} # 이번 회차에 실제로 '재고 있음'으로 보이는 상품들
            new_restocked = []     # 이번 회차에 새로 나타난 상품들
            
            # 1. 모든 페이지 스캔
            for url in urls:
                check_commands()
                scan_target(session, url, current_cycle_items)
                time.sleep(2)
            
            # 2. 상태 변화 분석
            # (1) 새로 입고된 상품 찾기 (기존 인지 목록에 없던 상품)
            for p_id, p_name in current_cycle_items.items():
                if p_id not in known_in_stock_ids:
                    new_restocked.append(p_name)
            
            # (2) 인지 목록 업데이트
            # 이번 회차에 보인 상품들로 목록을 완전히 교체합니다.
            # (리스트에서 사라진 상품은 품절된 것이므로, 나중에 다시 나타나면 재입고 알림을 보낼 수 있게 됨)
            known_in_stock_ids = set(current_cycle_items.keys())
            
            # 3. 알림 및 보고
            # 신규 재입고 상품이 있을 때만 30개 단위로 보고
            if new_restocked:
                for i in range(0, len(new_restocked), 30):
                    chunk = new_restocked[i:i+30]
                    msg = [f"{i+idx+1}. {name}" for idx, name in enumerate(chunk)]
                    send_message(f"🚨 [재입고/신규 포착]\n" + "\n".join(msg))
                    time.sleep(0.5)
            
            # /상태 요청이 있었다면 모든 스캔 종료 후 최종 보고
            if status_report_requested:
                status_msg = (
                    f"📊 [감시 사이클 완료 보고]\n"
                    f"🔄 회차: {cycle_count}회\n"
                    f"📦 현재 구매 가능 상품: {len(known_in_stock_ids)}개\n"
                    f"⏱️ 최종 확인 시각: {last_check_time}\n"
                    f"✨ 모든 페이지(10개) 확인을 완료했습니다."
                )
                send_message(status_msg)
                status_report_requested = False # 플래그 초기화
            
            print(f"⏳ {cycle_count}회차 완료. 인지 상품: {len(known_in_stock_ids)}개.")
            
            # 다음 사이클 전 휴식
            for _ in range(30):
                check_commands()
                time.sleep(1)
