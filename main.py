import os
import requests
from bs4 import BeautifulSoup

# 텔레그램 설정
token = os.environ['TELEGRAM_TOKEN']
chat_id = os.environ['TELEGRAM_CHAT_ID']

# 오용진 님의 전용 구글 우회 주소
GOOGLE_PROXY_URL = "https://script.google.com/macros/s/AKfycbwHH20V6XscVYYIek80dI0symQT3P3cnCZkqqCyGijhpjOkNNzbQsvUR5oNyU0ndUMR/exec"

def send_message(text):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {'chat_id': chat_id, 'text': text}
    requests.post(url, data=payload)

def check_stock(target_url):
    try:
        proxy_url = f"{GOOGLE_PROXY_URL}?url={target_url}"
        response = requests.get(proxy_url, timeout=30)
        soup = BeautifulSoup(response.text, 'html.parser')

        # [상품명 찾기 3중 필터]
        product_name = "이름 확인 불가"
        
        # 1순위: 공유용 메타 데이터(og:title) - 가장 정확함
        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"):
            product_name = og_title["content"].split('|')[0].strip()
        
        # 2순위: 메타 데이터 실패 시 기존 이름표 찾기
        if product_name == "이름 확인 불가" or product_name == "상품상세":
            name_tag = soup.find('p', class_='prod_name') or soup.find('div', class_='goods_name')
            if name_tag:
                product_name = name_tag.get_text(strip=True)
                
        # 3순위: 최후의 수단 (제목 태그)
        if product_name == "이름 확인 불가" or product_name == "상품상세":
            product_name = soup.title.string.split('|')[0].strip() if soup.title else "상품 정보 없음"

        # [재고 판정]
        page_html = response.text.lower()
        # 구매/장바구니/예약 버튼이 있는지 확인
        has_buy_button = any(btn in page_html for btn in ['btn_buy', 'btn_cart', 'cart_btn', 'btn_reservation', 'buy_now'])
        # 품절 마크가 있는지 확인
        has_soldout_signal = any(sign in page_html for sign in ['btn_soldout', 'sold_out', 'stock_out'])

        if has_buy_button and not has_soldout_signal:
            return f"✅ [{product_name}]\n재입고 완료!! 지금 지르세요!"
        else:
            return f"❌ [{product_name}]\n현재 품절 상태입니다."

    except Exception as e:
        return f"⚠️ 접속 오류: {e}"

if __name__ == "__main__":
    # 테스트 대상: HG 구스타프 칼
    target_url = "https://www.bnkrmall.co.kr/goods/detail.do?gno=91246553"
    
    result = check_stock(target_url)
    send_message(f"반다이몰 정밀 우회 결과:\n{result}")
