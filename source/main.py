import sys

from bot_core import BotCore
from utils import logger

# from dotenv import load_dotenv


def main(args=None):
    if args is None:
        args = sys.argv[1:]

    core = BotCore()
    logger.info("Attaching Telegram bot message handlers...")
    core.attach_handlers()

    try:
        if "--use-local" in args:
            core.run_local()
        else:
            core.run_webhook()
    except Exception as e:
        logger.error("App startup failed!")
        logger.exception(e)


if __name__ == "__main__":
    main()
