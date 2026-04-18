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
        # 구글 대리인을 통해 우회 접속
        proxy_url = f"{GOOGLE_PROXY_URL}?url={target_url}"
        response = requests.get(proxy_url, timeout=30)
        soup = BeautifulSoup(response.text, 'html.parser')

        # [1] 상품명 추출
        # 반다이몰의 상품명 태그를 우선 찾고, 없으면 페이지 제목을 사용합니다.
        name_tag = soup.find('p', class_='prod_name') or soup.find('div', class_='goods_name')
        if name_tag:
            product_name = name_tag.get_text(strip=True)
        else:
            product_name = soup.title.string.split('|')[0].strip() if soup.title else "알 수 없는 상품"

        # [2] 정밀 재고 판정
        # HTML 코드 전체를 소문자로 변환해서 검사합니다.
        page_html = response.text.lower()
        
        # 구매 관련 버튼 클래스가 있는지 확인 (PC/모바일 공통)
        has_buy_button = any(btn in page_html for btn in ['btn_buy', 'btn_cart', 'cart_btn', 'btn_reservation'])
        
        # 확실한 품절 신호가 있는지 확인
        has_soldout_signal = any(sign in page_html for sign in ['btn_soldout', 'sold_out', 'stock_out', '품절'])

        # [3] 최종 결과 도출
        # 구매 버튼이 존재하고, 품절 신호가 '구매 버튼'보다 작거나 없을 때 재입고로 판단
        if has_buy_button and not ("btn_soldout" in page_html or "sold_out" in page_html):
            # '품절' 글자가 본문에 있어도 '구매하기' 버튼 클래스가 살아있으면 재입고 가능성이 높음
            return f"✅ [{product_name}]\n재입고 완료!! 지금 바로 접속하세요!"
        else:
            return f"❌ [{product_name}]\n현재 품절 상태입니다."

    except Exception as e:
        return f"⚠️ 접속 오류 발생: {e}"

if __name__ == "__main__":
    # 테스트 대상: HG 구스타프 칼 (현재 품절 상품)
    target_url = "https://www.bnkrmall.co.kr/goods/detail.do?gno=91246553"
    
    result = check_stock(target_url)
    send_message(f"반다이몰 정밀 우회 결과:\n{result}")
