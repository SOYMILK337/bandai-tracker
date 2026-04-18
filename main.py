import os
import requests
from bs4 import BeautifulSoup

token = os.environ['TELEGRAM_TOKEN']
chat_id = os.environ['TELEGRAM_CHAT_ID']

def send_message(text):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {'chat_id': chat_id, 'text': text}
    requests.post(url, data=payload)

def check_stock(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        # allow_redirects=False: 메인으로 튕겨나가지 못하게 막습니다.
        response = requests.get(url, headers=headers, allow_redirects=False)
        
        # 만약 사이트가 우리를 다른 곳(메인 등)으로 보내려 한다면(302 에러 등)
        if response.status_code == 302 or response.status_code == 301:
            return "⚠️ [주소 오류] 이 상품 번호는 공식몰에 존재하지 않습니다. (메인으로 이동됨)"

        soup = BeautifulSoup(response.text, 'html.parser')

        # 공식몰 상품명 태그 찾기
        title_tag = soup.find('p', class_='prod_name')
        
        if not title_tag:
            return "⚠️ [데이터 없음] 상품 페이지 형식은 맞으나 정보를 읽을 수 없습니다."

        product_name = title_tag.get_text(strip=True)
        
        # 품절 여부 확인 (반다이몰 특유의 'sold_out' 이미지나 텍스트 감지)
        if "품절" in response.text or "sold_out" in response.text:
            return f"❌ [{product_name}] 현재 품절입니다."
        else:
            return f"✅ [{product_name}] 재입고 완료!! 지금 확인하세요!"

    except Exception as e:
        return f"⚠️ 접속 실패: {e}"

if __name__ == "__main__":
    # 주인님께서 주신 그 문제의 링크입니다!
    target_url = "https://www.bnkrmall.co.kr/goods/detail.do?gno=91246553"
    
    result = check_stock(target_url)
    send_message(f"반다이몰 정밀 감시 결과:\n{result}")
