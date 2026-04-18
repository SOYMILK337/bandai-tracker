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
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # [상품명 찾기 전략]
        # 1순위: 반다이몰 공식 이름표(prod_name)를 찾아봅니다.
        name_tag = soup.find('p', class_='prod_name')
        if name_tag:
            product_name = name_tag.get_text(strip=True)
        else:
            # 2순위: 실패하면 웹페이지의 제목(Title)을 가져와서 다듬습니다.
            # 보통 "상품명 | 반다이남코코리아몰" 식으로 되어 있습니다.
            product_name = soup.title.string.split('|')[0].strip() if soup.title else "알 수 없는 상품"

        # [품절 체크]
        # '장바구니'나 '구매하기' 버튼 글자가 보이면 재고가 있는 것으로 판단
        if "장바구니" in response.text or "구매하기" in response.text:
            # 단, 품절 문구만 있고 버튼이 없는 경우를 한 번 더 걸러줌
            if "품절" in response.text and "장바구니" not in response.text:
                return f"❌ [{product_name}]\n현재 품절 상태입니다."
            return f"✅ [{product_name}]\n재입고 완료!! 지금 바로 지르세요!"
        else:
            return f"❌ [{product_name}]\n현재 품절 상태입니다."

    except Exception as e:
        return f"⚠️ 접속 실패: {e}"

if __name__ == "__main__":
    target_url = "https://www.bnkrmall.co.kr/goods/detail.do?gno=91246553"
    
    result = check_stock(target_url)
    send_message(f"반다이몰 감시 결과:\n{result}")
