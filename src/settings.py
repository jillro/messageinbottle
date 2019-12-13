import os

FB_VERIFY_TOKEN = os.environ.get("FB_VERIFY_TOKEN")
FB_APP_ID = os.environ.get("FB_APP_ID")
FB_APP_SECRET = os.environ.get("FB_APP_SECRET")
FB_PAGE_ID = os.environ.get("FB_PAGE_ID")
FB_PAGE_TOKEN = os.environ.get("FB_PAGE_TOKEN")
TELEGRAM_TOKEN = (
    os.environ.get("TELEGRAM_TOKEN")
    if os.environ.get("PRODUCTION")
    else os.environ.get("DEV_TELEGRAM_TOKEN")
)
TELEGRAM_API = "https://api.telegram.org/bot" + TELEGRAM_TOKEN + "/"
