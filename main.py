import os
import requests
from bs4 import BeautifulSoup

# 텔레그램 설정
token = os.environ['TELEGRAM_TOKEN']
chat_id = os.environ['TELEGRAM_CHAT_ID']

# 오용진 님의 전용 구글 우회 주소 (그대로 유지)
GOOGLE_PROXY_URL = "https://script.google.com/macros/s/AKfycbwHH20V6XscVYYIek80dI0symQT3P3cnCZkqqCyGijhpjOkNNzbQsvUR5oNyU0ndUMR/exec"

def send_message(text):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {'chat_id': chat_id, 'text': text}
    requests.post(url, data=payload)

def check_stock(target_url):
    try:
        proxy_url = f"{GOOGLE_PROXY_URL}?url={target_url}"
        response = requests.get(proxy_url, timeout=30)
        soup = BeautifulSoup(response.text, 'html.parser')

        # [상품명 찾기 - 정밀 스캔 모드]
        product_name = "이름 확인 불가"
        
        # 1. 메타 데이터 중 'description' 확인 (여기에 상품명이 들어가는 경우가 많습니다)
        desc_meta = soup.find("meta", {"name": "description"}) or soup.find("meta", {"property": "og:description"})
        if desc_meta and desc_meta.get("content"):
            # 보통 "상품명 - 반다이남코코리아몰" 형태이므로 자릅니다.
            product_name = desc_meta["content"].split('-')[0].strip()

        # 2. 만약 여전히 '상품상세'거나 확인 불가면, 소스코드 전체에서 'goods_nm' 문구 추적
        if "상품상세" in product_name or product_name == "이름 확인 불가":
            # input 태그의 value 값에 들어있는지 확인
            nm_input = soup.find("input", {"id": "goods_nm"}) or soup.find("input", {"name": "goods_nm"})
            if nm_input and nm_input.get("value"):
                product_name = nm_input["value"].strip()

        # 3. 최후의 보루: og:title 재확인
        if "상품상세" in product_name or product_name == "이름 확인 불가":
            og_title = soup.find("meta", property="og:title")
            if og_title and og_title.get("content"):
                product_name = og_title["content"].split('|')[0].strip()

        # [재고 판정 - 버튼 위주]
        page_html = response.text.lower()
        # '재입고'라고 판단할 확실한 버튼 키워드들
        has_buy_button = any(btn in page_html for btn in ['btn_buy', 'btn_cart', 'cart_btn', 'btn_reservation'])
        # '품절'이라고 판단할 확실한 키워드들
        has_soldout_signal = any(sig in page_html for sig in ['btn_soldout', 'sold_out', 'stock_out'])

        if has_buy_button and not has_soldout_signal:
            return f"✅ [{product_name}]\n재입고 완료!! 링크 확인하세요!"
        else:
            return f"❌ [{product_name}]\n현재 품절 상태입니다."

    except Exception as e:
        return f"⚠️ 접속 오류: {e}"

if __name__ == "__main__":
    target_url = "https://www.bnkrmall.co.kr/goods/detail.do?gno=91246553"
    result = check_stock(target_url)
    send_message(f"반다이몰 정밀 우회 결과:\n{result}")
