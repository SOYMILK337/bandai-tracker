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
    # [업그레이드] 보안 가드를 속이기 위한 정밀한 변장 도구 (Headers)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
        'Referer': 'https://www.bnkrmall.co.kr/', # 반다이몰 메인에서 타고 들어온 척 합니다.
        'Connection': 'keep-alive'
    }
    
    try:
        # 세션(Session)을 사용해 한 번 연결된 통로를 유지합니다. (더 사람 같습니다)
        session = requests.Session()
        response = session.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 만약 또 차단당했다면?
        if "Request Rejected" in response.text or response.status_code == 403:
            return "⛔ 보안 시스템에 의해 접속이 차단되었습니다. (변장 실패)"

        # [상품명 찾기]
        name_tag = soup.find('p', class_='prod_name')
        if name_tag:
            product_name = name_tag.get_text(strip=True)
        else:
            product_name = soup.title.string.split('|')[0].strip() if soup.title else "알 수 없는 상품"

        # [품절 체크]
        # 장바구니/구매하기 버튼이 코드 안에 있는지 확인
        if "장바구니" in response.text or "구매하기" in response.text:
            if "품절" in response.text and "장바구니" not in response.text:
                return f"❌ [{product_name}]\n현재 품절 상태입니다."
            return f"✅ [{product_name}]\n재입고 완료!! 지금 바로 지르세요!"
        else:
            return f"❌ [{product_name}]\n현재 품절 상태입니다."

    except Exception as e:
        return f"⚠️ 접속 실패: {e}"

if __name__ == "__main__":
    # 테스트용 주소
    target_url = "https://www.bnkrmall.co.kr/goods/detail.do?gno=91246553"
    
    result = check_stock(target_url)
    send_message(f"반다이몰 감시 결과:\n{result}")
