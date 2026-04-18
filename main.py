import os
from curl_cffi import requests # 최강 우회 도구로 교체
from bs4 import BeautifulSoup

token = os.environ['TELEGRAM_TOKEN']
chat_id = os.environ['TELEGRAM_CHAT_ID']

def send_message(text):
    import requests as py_requests # 텔레그램용은 기본 도구 사용
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {'chat_id': chat_id, 'text': text}
    py_requests.post(url, data=payload)

def check_stock(url):
    try:
        # [핵심] impersonate='chrome120': 크롬 120 버전의 지문을 완벽하게 흉내냅니다.
        response = requests.get(
            url, 
            impersonate="chrome120",
            timeout=20
        )
        
        # 다시 한 번 차단 여부 확인
        if "Request Rejected" in response.text or response.status_code == 403:
            return "⛔ [IP 차단] 서버 자체가 차단되었습니다. 네이버 몰부터 공략해볼까요?"

        soup = BeautifulSoup(response.text, 'html.parser')

        # 상품명 찾기
        name_tag = soup.find('p', class_='prod_name')
        if name_tag:
            product_name = name_tag.get_text(strip=True)
        else:
            product_name = soup.title.string.split('|')[0].strip() if soup.title else "알 수 없는 상품"

        # 품절 체크
        if "장바구니" in response.text or "구매하기" in response.text:
            if "품절" in response.text and "장바구니" not in response.text:
                return f"❌ [{product_name}]\n현재 품절 상태입니다."
            return f"✅ [{product_name}]\n재입고 완료!! 어서 확인하세요!"
        else:
            return f"❌ [{product_name}]\n현재 품절 상태입니다."

    except Exception as e:
        return f"⚠️ 접속 실패: {e}"

if __name__ == "__main__":
    # 반다이 공식몰 링크로 마지막 도전!
    target_url = "https://www.bnkrmall.co.kr/goods/detail.do?gno=91246553"
    result = check_stock(target_url)
    send_message(f"반다이몰 4차 최종 공략:\n{result}")
