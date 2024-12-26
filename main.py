from bot import EvilBot
from config import BOT_TOKEN
from utils import thread_pool
from log import setup_logging  

def main():
    logger = setup_logging()
    bot = EvilBot()
    try:
        bot.run(BOT_TOKEN)
    finally:
        thread_pool.shutdown(wait=True)

if __name__ == "__main__":
    main()