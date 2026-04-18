import os
import requests

# 1. 깃허브 금고(Secrets)에 숨겨둔 우리만의 토큰과 ID를 불러옵니다.
token = os.environ['TELEGRAM_TOKEN']
chat_id = os.environ['TELEGRAM_CHAT_ID']

# 2. 텔레그램으로 메시지를 보내는 '기능'을 정의합니다.
def send_message(text):
    # 이 주소로 요청을 보내면 텔레그램이 우리에게 메시지를 전달해줍니다.
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {'chat_id': chat_id, 'text': text}
    requests.post(url, data=payload)

# 3. 프로그램이 실행되면 가장 먼저 할 일입니다.
if __name__ == "__main__":
    send_message("오용진 주인님, 반다이 추적기 엔진 가동 성공! 🤖")
