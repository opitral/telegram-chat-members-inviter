import json
import os
import re
from glob import glob
import asyncio
import logging
import sqlite3

from pyrogram import Client

from typing import List, Dict


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

file_handler = logging.FileHandler("inviter.log")
file_handler.setLevel(logging.INFO)

formatter = logging.Formatter("%(asctime)s - [%(levelname)s] - %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
console_handler.setFormatter(formatter)
file_handler.setFormatter(formatter)

logger.addHandler(console_handler)
logger.addHandler(file_handler)


def get_configs() -> List[Dict]:
    configs = []

    try:
        pattern = os.path.join(os.getcwd(), "configs", "*.json")
        os.makedirs(os.path.dirname(pattern), exist_ok=True)
        config_paths = glob(pattern)

        for config_path in config_paths:
            if os.path.basename(config_path).split(".")[0] == "example":
                continue

            with open(config_path, "r") as f:
                config_data = f.read()

            configs.append(json.loads(config_data))

    except Exception as ex:
        logger.error(f"Error while receiving configs, details: {ex}")

    else:
        logger.info(f"Received configs: {len(configs)}")
        return configs


async def has_spam_block(bot: Client) -> bool:
    try:
        await bot.send_message("SpamBot", '/start')
        await asyncio.sleep(2)

        async for message in bot.get_chat_history("SpamBot", limit=1):
            if "Ваш аккаунт временно ограничен" in message.text:
                logger.warning("Account is temporarily limited until " + str(re.findall(r'(?<=сняты ).+(?= \(по)',
                                                                                        message.text)[0]))
                return True

            elif "Ваш аккаунт ограничен" in message.text:
                logger.error("Account is permanently limited")
                return True

            logger.info("Account has no limits")
            return False

    except Exception as ex:
        logger.error(f"Error while received spam status, details: {ex}")


async def main():
    configs = get_configs()

    for config in configs:
        bot = None
        session_name = config["session"]
        session_path = os.path.join(os.getcwd(), "sessions", session_name)
        os.makedirs(os.path.dirname(session_path), exist_ok=True)

        db_path = os.path.join(os.getcwd(), "databases", f"{config['db']}.db")
        os.makedirs(os.path.dirname(db_path), exist_ok=True)

        proxy = config["proxy"]
        to_chat_link = config["to_chat"]

        try:
            try:
                bot = Client(session_path, proxy=proxy, lang_code="ru")
                await bot.start()

            except Exception as ex:
                logger.error(f"Error while connecting to session \"{config['session']}\", details: {ex}")
                continue

            else:
                logger.info(f"Connected to session: {session_name}")

            if await has_spam_block(bot):
                continue

        except Exception as ex:
            logger.error(ex)

        finally:
            await bot.stop()


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
