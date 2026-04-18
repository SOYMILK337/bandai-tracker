import os
import requests
from bs4 import BeautifulSoup

token = os.environ['TELEGRAM_TOKEN']
chat_id = os.environ['TELEGRAM_CHAT_ID']

# 17단계에서 복사한 구글 웹 앱 URL을 아래 큰따옴표 안에 반드시 넣어주세요.
GOOGLE_PROXY_URL = "https://script.google.com/macros/s/AKfycbwHH20V6XscVYYIek80dI0symQT3P3cnCZkqqCyGijhpjOkNNzbQsvUR5oNyU0ndUMR/exec"

def send_message(text):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {'chat_id': chat_id, 'text': text}
    requests.post(url, data=payload)

def check_stock(target_url):
    try:
        # 구글 대리인(Proxy) 주소 생성
        proxy_url = f"{GOOGLE_PROXY_URL}?url={target_url}"
        
        # 구글 서버를 통해 반다이몰에 접속합니다.
        response = requests.get(proxy_url, timeout=30)
        
        if "Request Rejected" in response.text:
            return "⛔ 구글 우회 접속도 차단되었습니다. 다른 구글 계정으로 재배포가 필요할 수 있습니다."

        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 페이지 제목에서 상품명 추출
        product_name = soup.title.string.split('|')[0].strip() if soup.title else "상품 정보"

        # 품절 및 재입고 여부 판단
        # '장바구니', '구매하기', '예약하기' 중 하나라도 있으면 재고가 있는 것으로 간주
        has_stock_button = any(word in response.text for word in ["장바구니", "구매하기", "예약하기"])
        is_sold_out_text = "품절" in response.text

        if has_stock_button:
            # 품절 글자가 있어도 버튼이 살아있으면 재입고로 판단
            if is_sold_out_text and "장바구니" not in response.text and "예약하기" not in response.text:
                 return f"❌ [{product_name}]\n현재 품절입니다."
            return f"✅ [{product_name}]\n재입고/예약 가능!! 지금 바로 접속하세요!"
        else:
            return f"❌ [{product_name}]\n현재 품절입니다."

    except Exception as e:
        return f"⚠️ 우회로 접속 실패: {e}\n(구글 URL이 정확한지 확인해 주세요!)"

if __name__ == "__main__":
    # 테스트용 상품 주소
    target_url = "https://www.bnkrmall.co.kr/goods/detail.do?gno=91246553"
    result = check_stock(target_url)
    send_message(f"반다이몰 우회 감시 결과:\n{result}")
