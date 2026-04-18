import os
import requests
import time
import re
from bs4 import BeautifulSoup

# [진단] 봇 엔진 가동
print("🚀 [System] 봇 엔진 가동 시작!")

token = os.environ.get('TELEGRAM_TOKEN')
chat_id = os.environ.get('TELEGRAM_CHAT_ID')
GOOGLE_PROXY_URL = "https://script.google.com/macros/s/AKfycbwHH20V6XscVYYIek80dI0symQT3P3cnCZkqqCyGijhpjOkNNzbQsvUR5oNyU0ndUMR/exec"

if not token or not chat_id:
    print("❌ [Error] 텔레그램 설정값(Secrets)이 비어있습니다!")
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
                        send_message("🔍 명령 확인! 이번 사이클이 끝난 후 보고서를 제출하겠습니다.")
                    
                    elif user_text == "/추적상품확인":
                        if not tracked_products:
                            send_message("아직 수집된 상품이 없습니다. 잠시만 기다려 주세요!")
                            continue
                        
                        product_list = [f"{i+1}. {p['name']} ({p['status']})" for i, p in enumerate(tracked_products.values())]
                        total = len(product_list)
                        send_message(f"📦 현재 총 {total}개 상품을 관리 중입니다.")
                        
                        for i in range(0, total, 30):
                            send_message(f"📋 [리스트 {i//30 + 1}]\n" + "\n".join(product_list[i:i+30]))
                            time.sleep(0.5)
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
        
        # 주인님의 필터 링크 전용 상품 추출 (li 태그 기반)
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
            
            if p_id in tracked_products:
                if tracked_products[p_id]['status'] == "품절" and current_status == "재고있음":
                    send_message(f"🚨 [입고 알림!]\n📦 {p_name}\n🔗 {p_url}")
            
            tracked_products[p_id] = {"name": p_name, "status": current_status}
            found_in_page += 1
            
        return found_in_page
    except:
        return 0

if __name__ == "__main__":
    if os.path.exists("list.txt"):
        with open("list.txt", "r") as f:
            urls = [line.strip() for line in f.readlines() if line.strip()]
        
        print(f"✅ [System] 감시 시작! 대상 페이지: {len(urls)}개")
        send_message(f"🤖 정밀 감시 가동 시작! (대상: {len(urls)}개 페이지)")
        
        session = requests.Session()
        
        while True:
            cycle_count += 1
            items_this_cycle = 0 # 변수명 통일 완료!
            referer = "https://www.bnkrmall.co.kr/"
            
            for url in urls:
                check_commands()
                count = scan_page(session, url, referer)
                items_this_cycle += count # 여기서 에러가 났던 부분을 수정했습니다.
                referer = url
                time.sleep(5)
            
            if report_requested:
                send_message(f"📋 [보고] {cycle_count}회차 완료\n📦 이번 회차 확인: {items_this_cycle}개\n🗃️ 총 관리 상품: {len(tracked_products)}개")
                report_requested = False
            
            print(f"⏳ {cycle_count}회차 완료. 누적 {len(tracked_products)}개.")
            for _ in range(30): # 30초 대기 중에도 명령어 체크
                check_commands()
                time.sleep(1)
    else:
        print("❌ [Fatal] list.txt 파일이 없습니다!")
