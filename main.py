import os
import cloudscraper # 방패 뚫는 도구로 교체
from bs4 import BeautifulSoup

token = os.environ['TELEGRAM_TOKEN']
chat_id = os.environ['TELEGRAM_CHAT_ID']

def send_message(text):
    # 텔레그램 메시지 발송은 그대로 둡니다.
    import requests
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {'chat_id': chat_id, 'text': text}
    requests.post(url, data=payload)

def check_stock(url):
    # 방패를 뚫는 크롤러 객체를 만듭니다.
    scraper = cloudscraper.create_scraper(
        browser={
            'browser': 'chrome',
            'platform': 'windows',
            'desktop': True
        }
    )
    
    try:
        # 이제 scraper를 통해 접속합니다.
        response = scraper.get(url, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 다시 한 번 보안 차단 문구가 있는지 확인
        if "Request Rejected" in response.text or response.status_code == 403:
            return "⛔ [강력 차단] 보안 장벽이 너무 높습니다. 다른 우회 방법이 필요합니다."

        # 상품명 찾기
        name_tag = soup.find('p', class_='prod_name')
        if name_tag:
            product_name = name_tag.get_text(strip=True)
        else:
            product_name = soup.title.string.split('|')[0].strip() if soup.title else "알 수 없는 상품"

        # 품절 체크 (버튼 텍스트 검사)
        if "장바구니" in response.text or "구매하기" in response.text:
            if "품절" in response.text and "장바구니" not in response.text:
                return f"❌ [{product_name}]\n현재 품절 상태입니다."
            return f"✅ [{product_name}]\n재입고 완료!! 어서 확인하세요!"
        else:
            return f"❌ [{product_name}]\n현재 품절 상태입니다."

    except Exception as e:
        return f"⚠️ 접속 실패: {e}"

if __name__ == "__main__":
    target_url = "https://www.bnkrmall.co.kr/goods/detail.do?gno=91246553"
    result = check_stock(target_url)
    send_message(f"반다이몰 3차 정밀 감시:\n{result}")
