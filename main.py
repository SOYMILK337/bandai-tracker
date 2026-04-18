import os
import requests
from bs4 import BeautifulSoup

token = os.environ['TELEGRAM_TOKEN']
chat_id = os.environ['TELEGRAM_CHAT_ID']

def send_message(text):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {'chat_id': chat_id, 'text': text}
    requests.post(url, data=payload)

def check_bandai_mall():
    # 여기에 직접 찾으신 '살아있는 상품 주소'를 넣으세요!
    url = "https://www.bnkrmall.co.kr/goods/detail.do?gno=91246553" # 예시 주소입니다.
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    response = requests.get(url, headers=headers)
    
    # [추가된 기능] 만약 메인 페이지로 튕겨나갔다면?
    if "detail.do" not in response.url:
        return "⚠️ 오류: 상품 페이지를 찾을 수 없습니다. (주소 확인 필요!)"
    
    # 상품명이 들어가는 부분을 찾아봅니다. (페이지가 정상인지 확인용)
    soup = BeautifulSoup(response.text, 'html.parser')
    title = soup.find('p', class_='prod_name') # 반다이몰 상품명 태그
    
    product_name = title.get_text(strip=True) if title else "알 수 없는 상품"
    
    if "품절" in response.text:
        return f"❌ [{product_name}] 아직 품절입니다."
    else:
        return f"✅ [{product_name}] 재입고 완료! 지르세요!"

if __name__ == "__main__":
    status = check_bandai_mall()
    send_message(f"반다이몰 감시 결과:\n{status}")
