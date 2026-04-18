import os
import requests

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
        
        # [핵심] 페이지 전체 내용(text)에서 직접 단어를 찾습니다.
        # '장바구니' 또는 '구매하기'라는 글자가 있으면 재입고된 것으로 봅니다.
        if "장바구니" in response.text or "구매하기" in response.text:
            # 그런데 '품절'이라는 글자가 동시에 있으면 진짜 품절인지 확인해야 합니다.
            if "품절" in response.text and "장바구니" not in response.text:
                return "❌ 현재 품절 상태입니다."
            return "✅ 재입고 완료!! 지금 바로 접속하세요!"
        else:
            return "❌ 현재 품절 상태입니다."

    except Exception as e:
        return f"⚠️ 접속 실패: {e}"

if __name__ == "__main__":
    # 주인님께서 주신 바로 그 링크로 테스트합니다!
    target_url = "https://www.bnkrmall.co.kr/goods/detail.do?gno=91246553"
    
    result = check_stock(target_url)
    send_message(f"반다이몰 감시 결과:\n{result}")
