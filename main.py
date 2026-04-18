import os
import requests
from bs4 import BeautifulSoup

token = os.environ['TELEGRAM_TOKEN']
chat_id = os.environ['TELEGRAM_CHAT_ID']

# [여기에 아까 복사한 구글 웹 앱 URL을 붙여넣으세요]
GOOGLE_PROXY_URL = "여기에_복사한_URL을_붙여넣으세요"

def send_message(text):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {'chat_id': chat_id, 'text': text}
    requests.post(url, data=payload)

def check_stock(target_url):
    try:
        # 구글 대리인을 통해 우회 접속합니다.
        proxy_url = f"{GOOGLE_PROXY_URL}?url={target_url}"
        response = requests.get(proxy_url, timeout=30)
        
        # 반다이몰 보안 통과 확인
        if "Request Rejected" in response.text:
            return "⛔ 구글 우회로도 막혔습니다. (다른 구글 계정 필요)"

        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 상품명 찾기 (제목에서 추출)
        product_name = soup.title.string.split('|')[0].strip() if soup.title else "프리미엄 반다이 상품"

        # 품절 체크 (버튼 텍스트 확인)
        if "장바구니" in response.text or "구매하기" in response.text or "예약하기" in response.text:
            # 품절 글자가 있지만 버튼이 있는 경우 '재고 있음'으로 간주
            if "품절" in response.text and "장바구니" not in response.text and "예약하기" not in response.text:
                 return f"❌ [{product_name}]\n현재 품절입니다."
            return f"✅ [{product_name}]\n재입고/예약 가능!! 지금 바로 가세요!"
        else:
            return f"❌ [{product_name}]\n현재 품절입니다."

    except Exception as e:
        return f"⚠️ 우회 접속 실패: {e}"

if __name__ == "__main__":
    # 테스트하고 싶은 프반 상품 주소를 넣으세요.
    target_url = "https://www.bnkrmall.co.kr/goods/detail.do?gno=91246553"
    result = check_stock(target_url)
    send_message(f"반다이몰 우회 감시 결과:\n{result}")
