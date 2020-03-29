import logging
import os

DEV = not os.environ.get("PRODUCTION", "false").lower() == "true"


def env(key, default=None):
    if DEV:
        key = "DEV_" + key
    return os.environ.get(key, default)


FB_VERIFY_TOKEN = env("FB_VERIFY_TOKEN")
FB_APP_ID = env("FB_APP_ID")
FB_APP_SECRET = env("FB_APP_SECRET")
FB_PAGE_ID = env("FB_PAGE_ID")
FB_PAGE_TOKEN = env("FB_PAGE_TOKEN")
TELEGRAM_TOKEN = env("TELEGRAM_TOKEN")
TELEGRAM_API = "https://api.telegram.org/bot" + TELEGRAM_TOKEN + "/"
TABLE_PREFIX = "helium_dev_" if DEV else "helium_prod_"

if DEV:
    logging.basicConfig(level=logging.DEBUG)
