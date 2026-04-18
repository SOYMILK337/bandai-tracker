import os
from curl_cffi import requests as curl_requests
from bs4 import BeautifulSoup
import requests as py_requests # 텔레그램용

token = os.environ['TELEGRAM_TOKEN']
chat_id = os.environ['TELEGRAM_CHAT_ID']

def send_message(text):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {'chat_id': chat_id, 'text': text}
    try:
        py_requests.post(url, data=payload)
    except:
        print("텔레그램 발송 실패")

def check_stock(url):
    try:
        # 크롬 120 버전 지문 복제
        response = curl_requests.get(
            url, 
            impersonate="chrome120",
            timeout=30
        )
        
        if "Request Rejected" in response.text or response.status_code == 403:
            return "⛔ [보안 차단] 공식몰의 보안이 너무 강력합니다."

        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 상품명 추출
        name_tag = soup.find('p', class_='prod_name')
        if name_tag:
            product_name = name_tag.get_text(strip=True)
        else:
            product_name = soup.title.string.split('|')[0].strip() if soup.title else "알 수 없는 상품"

        # 품절 여부 체크
        if "장바구니" in response.text or "구매하기" in response.text:
            if "품절" in response.text and "장바구니" not in response.text:
                return f"❌ [{product_name}]\n현재 품절 상태입니다."
            return f"✅ [{product_name}]\n재입고 완료!! 링크 확인하세요!"
        else:
            return f"❌ [{product_name}]\n현재 품절 상태입니다."

    except Exception as e:
        return f"⚠️ 접속 오류: {e}"

if __name__ == "__main__":
    target_url = "https://www.bnkrmall.co.kr/goods/detail.do?gno=91246553"
    result = check_stock(target_url)
    send_message(f"반다이몰 최종 공략 결과:\n{result}")
