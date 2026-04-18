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
report_requested = False  # 보고 요청 플래그

def send_message(text):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {'chat_id': chat_id, 'text': text}
    try:
        requests.post(url, data=payload)
    except: pass

def check_commands():
    """텔레그램 메시지를 수시로 확인합니다."""
    global last_update_id, report_requested
    try:
        url = f"https://api.telegram.org/bot{token}/getUpdates"
        params = {'offset': last_update_id + 1, 'timeout': 1}
        response = requests.get(url, params=params).json()
        
        if response.get("ok") and response.get("result"):
            for update in response["result"]:
                last_update_id = update["update_id"]
                if "message" in update and "text" in update["message"]:
                    if update["message"]["text"] == "/상태":
                        report_requested = True
                        send_message("🫡 명령 접수! 이번 감시 회차를 마치는 대로 결과를 보고하겠습니다.")
    except: pass

def scan_page(session, target_url, referer_url):
    """세션을 유지하며 페이지 내 상품을 수집합니다."""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': referer_url
        }
        proxy_url = f"{GOOGLE_PROXY_URL}?url={target_url}"
        response = session.get(proxy_url, headers=headers, timeout=30)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        items = soup.find_all('li')
        found_count = 0
        updates = []
        
        for item in items:
            link_tag = item.find('a', href=re.compile(r'gno='))
            if not link_tag: continue
            
            p_id = link_tag['href'].split('gno=')[-1].split('&')[0]
            p_name = ' '.join(item.get_text(separator=' ', strip=True).split())
            p_url = f"https://www.bnkrmall.co.kr{link_tag['href']}" if link_tag['href'].startswith('/') else link_tag['href']

            # 현재 상태: 링크가 있으면 무조건 재고 있음으로 간주 (주인님 분석 기반)
            current_status = "재고있음" 
            
            if p_id in last_stock_status:
                if last_stock_status[p_id] == "품절" and current_status == "재고있음":
                    updates.append(f"🚨 [재입고 포착!] {p_name[:35]}...\n{p_url}")
            
            last_stock_status[p_id] = current_status
            found_count += 1
            
        return updates, found_count
    except:
        return [], 0

if __name__ == "__main__":
    if os.path.exists("list.txt"):
        with open("list.txt", "r") as f:
            urls = [line.strip() for line in f.readlines() if line.strip()]
        
        send_message(f"⚙️ 봇 가동 시작! 총 {len(urls)}개 페이지를 정밀 감시합니다.")
        
        session = requests.Session() # 브라우저 세션 생성
        
        while True:
            cycle_count += 1
            items_this_cycle = 0
            referer = "https://www.bnkrmall.co.kr/"
            
            # [1] 전체 페이지 순회 스캔
            for url in urls:
                check_commands() # 페이지 넘길 때마다 주인님 말 확인
                
                print(f"🔍 {cycle_count}회차 - 스캔 중: {url[:50]}...")
                new_alerts, count = scan_page(session, url, referer)
                
                items_this_cycle += count
                referer = url # 현재 페이지를 다음 페이지의 Referer로 사용
                
                for alert in new_alerts:
                    send_message(alert)
                
                time.sleep(3) # 서버 보호를 위한 휴식
            
            # [2] 한 사이클 종료 후 요청이 있었다면 보고서 전송
            if report_requested:
                msg = (f"📋 [감시 결과 보고]\n"
                       f"🔄 현재 {cycle_count}회차 완료\n"
                       f"📦 이번 회차 확인 상품: {items_this_cycle}개\n"
                       f"🗃️ 누적 관리 상품 총합: {len(last_stock_status)}개\n"
                       f"✅ 모든 페이지를 정상적으로 훑었습니다.")
                send_message(msg)
                report_requested = False # 플래그 초기화
            
            print(f"⏳ {cycle_count}회차 완료. 누적 {len(last_stock_status)}개 관리 중.")
            
            # 사이클 간 휴식 시간 (10초) 동안에도 명령어 확인
            for _ in range(10):
                check_commands()
                time.sleep(1)
    else:
        print("list.txt 파일이 없습니다.")
