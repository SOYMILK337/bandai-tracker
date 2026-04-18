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
    # 테스트용: RG 하이뉴 건담 주소
    url = "https://www.bnkrmall.co.kr/goods/detail.do?gno=50720"
    
    # 봇이 아니라 사람인 척 하기 위한 설정 (헤더)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    response = requests.get(url, headers=headers)
    
    # 사이트 전체 내용 중에서 '품절'이라는 글자가 있는지 확인합니다.
    if "품절" in response.text:
        return "❌ 현재 품절 상태입니다."
    else:
        # '품절' 글자가 없으면 재입고된 것으로 간주합니다.
        return "✅ 재입고 완료! 지금 바로 확인하세요!"

if __name__ == "__main__":
    status = check_bandai_mall()
    send_message(f"반다이몰 감시 결과: {status}")
