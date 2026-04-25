from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

from bot.config import settings
from bot.health import start_health_server
from bot.handlers import build_handlers
from bot.memory import create_memory_store
from bot.nim_client import NIMClient


def configure_logging() -> None:
    logging.basicConfig(
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
    )


def main() -> None:
    configure_logging()
    settings.require_telegram()

    start_health_server(settings.port)
    memory = create_memory_store()
    nim_client = NIMClient()
    handlers = build_handlers(memory, nim_client)

    application = Application.builder().token(settings.telegram_bot_token).build()
    application.add_handler(CommandHandler("start", handlers["start"]))
    application.add_handler(CommandHandler("help", handlers["help"]))
    application.add_handler(CommandHandler("mode", handlers["mode"]))
    application.add_handler(CommandHandler("clear", handlers["clear"]))
    application.add_handler(CommandHandler("ielts_new", handlers["ielts_new"]))
    application.add_handler(CommandHandler("ielts_speaking", handlers["ielts_speaking"]))
    application.add_handler(CommandHandler("ielts_writing", handlers["ielts_writing"]))
    application.add_handler(CommandHandler("ielts_eval", handlers["ielts_eval"]))
    application.add_handler(CommandHandler("ielts_status", handlers["ielts_status"]))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handlers["message"]))
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
