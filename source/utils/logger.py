import logging
import os

BOT_NAME = os.environ.get("BOT_NAME")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(BOT_NAME)
