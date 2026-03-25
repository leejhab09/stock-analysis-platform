import requests

TELEGRAM_TOKEN = "8725612249:AAFgUl7UQ1mn0HRkchm1ZXO2R4uLgtN4CJM"
TELEGRAM_CHAT_ID = "8588301063"

def send_telegram(message: str) -> bool:
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        resp = requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": message})
        return resp.ok
    except Exception as e:
        print(f"텔레그램 전송 실패: {e}")
        return False
