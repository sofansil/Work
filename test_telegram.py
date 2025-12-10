import asyncio
from telegram import Bot
import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

async def test_connection():
    """텔레그램 봇 연결 및 채팅 ID 확인"""
    try:
        bot = Bot(token=TELEGRAM_TOKEN)
        async with bot:
            # 봇 정보 확인
            me = await bot.get_me()
            print(f"Bot connected: @{me.username}")
            print(f"Bot name: {me.first_name}")
            print(f"Bot ID: {me.id}\n")

            # 최근 메시지 확인
            print("Fetching recent messages...")
            updates = await bot.get_updates()

            if updates:
                print(f"\nFound {len(updates)} message(s):\n")
                for update in updates[-5:]:  # 최근 5개만
                    if update.message:
                        chat = update.message.chat
                        print(f"Chat ID: {chat.id}")
                        print(f"Chat Type: {chat.type}")
                        if chat.username:
                            print(f"Username: @{chat.username}")
                        print(f"Message: {update.message.text}")
                        print("-" * 50)
            else:
                print("\nNo messages found!")
                print("Please send a message to your bot first.")
                print(f"Search for @{me.username} in Telegram and send /start")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_connection())
