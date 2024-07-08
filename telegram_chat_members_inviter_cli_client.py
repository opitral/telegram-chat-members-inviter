import json
import os
import random
import re
from glob import glob
import asyncio
import configparser
import logging
import sqlite3

from pyrogram import Client
from pyrogram.errors import FloodWait, PeerFlood, UserAlreadyParticipant

from typing import List, Dict

from pyrogram.types import Chat

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

file_handler = logging.FileHandler("inviter.log")
file_handler.setLevel(logging.WARNING)

formatter = logging.Formatter("%(asctime)s - [%(levelname)s] - %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
console_handler.setFormatter(formatter)
file_handler.setFormatter(formatter)

logger.addHandler(console_handler)
logger.addHandler(file_handler)

config = configparser.ConfigParser()
config.read("config.ini")

api_id = config["Telegram"]["api_id"]
api_hash = config["Telegram"]["api_hash"]
members_count = int(config["Inviter"]["members_count"])


def get_account_configs() -> List[Dict]:
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


async def has_spam_block(bot: Client, account_config) -> bool:
    try:
        session_name = account_config["session"]

        await bot.send_message("SpamBot", "/start")
        await asyncio.sleep(2)

        async for message in bot.get_chat_history("SpamBot", limit=1):
            if "Ваш аккаунт временно ограничен" in message.text:
                logger.warning(f"Account \"{session_name}\" is temporarily limited until " + str(re.findall(r'(?<=сняты ).+(?= \(по)',
                                                                                        message.text)[0]) + "(SpamBot)")
                return True

            elif "Ваш аккаунт ограничен" in message.text:
                account_config["blocked"] = True
                config_path = os.path.join(os.getcwd(), "configs", f"{session_name}.json")
                with open(config_path, "w") as f:
                    f.write(json.dumps(account_config))

                logger.error(f"Account \"{session_name}\" is permanently limited (SpamBot)")
                return True

            logger.info("Account has no limits (SpamBot)")
            return False

    except Exception as ex:
        logger.error(f"Error while received spam status, details: {ex}")


async def join_chat(bot: Client, link: str) -> Chat:
    try:
        chat = await bot.join_chat(link)
        logger.info(f"Joined chat: {link}")
        return chat

    except UserAlreadyParticipant:
        logger.info(f"Already participant: {link}")
        chat = await bot.get_chat(link)
        return chat

    except FloodWait as e:
        logger.warning(f"Flood wait: {e.value} seconds")
        await asyncio.sleep(e.value)
        await join_chat(bot, link)


async def main():
    account_configs = get_account_configs()

    for account_config in account_configs:
        if account_config["blocked"]:
            continue

        bot = None
        session_name = account_config["session"]
        session_path = os.path.join(os.getcwd(), "sessions", session_name)
        os.makedirs(os.path.dirname(session_path), exist_ok=True)

        db_path = os.path.join(os.getcwd(), "databases", f"{account_config['db']}.db")
        os.makedirs(os.path.dirname(db_path), exist_ok=True)

        session_proxy = account_config["proxy"]
        to_chat_link = account_config["to_chat"]

        try:
            try:
                bot = Client(session_path, proxy=session_proxy, lang_code="ru", api_id=api_id, api_hash=api_hash)
                await bot.start()
                logger.info(f"Connected to session: {session_name}")

            except Exception as ex:
                logger.error(f"Error while connecting to session \"{session_name}\", details: {ex}")
                continue

            if await has_spam_block(bot, account_config):
                continue

            try:
                to_chat = await join_chat(bot, to_chat_link)

            except Exception as ex:
                logger.info(f"({session_name}) Error while joining to chat {to_chat_link}, details: {ex}")
                continue

            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            cursor.execute("SELECT * FROM members WHERE status = 'free' ORDER BY RANDOM() LIMIT ?", (members_count,))
            leads = cursor.fetchall()
            members = []

            for lead in leads:
                try:
                    telegram_id = lead[1]
                    username = lead[2]
                    first_name = lead[3] or "Unknown"
                    last_name = lead[4] or ""

                    await bot.add_contact(username, first_name, last_name)
                    members.append(telegram_id)
                    logger.info(f"Member: {len(members)}/{members_count}")

                    await asyncio.sleep(random.randint(3, 8))

                except FloodWait as ex:
                    logger.info(f"Flood wait: {ex.value} seconds")
                    await asyncio.sleep(ex.value)

                except Exception as ex:
                    logger.error(f"({session_name}) Error while adding to contact, details: {ex}")

            try:
                result = await bot.add_chat_members(to_chat.id, members)

                if result:
                    for member in members:
                        conn.execute("UPDATE members SET status = 'busy' WHERE telegram_id = ?", (member,))

                    conn.commit()

                    logger.info(f"Members added: {to_chat_link}")

            except PeerFlood:
                logger.warning(f"Account \"{session_name}\" currently limited (PeerFlood)")

            except Exception as ex:
                logger.error(f"({session_name}) Error while inviting to chat, details: {ex}")

        except Exception as ex:
            logger.error(f"({session_name})  {ex}")

        finally:
            await bot.stop()


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
