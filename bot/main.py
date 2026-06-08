from __future__ import annotations

import logging
from datetime import time as dt_time
from zoneinfo import ZoneInfo

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from bot.brief import build_daily_brief
from bot.config import settings
from bot.health import start_health_server
from bot.handlers import build_handlers
from bot.memory import create_memory_store
from bot.nim_client import NIMClient

logger = logging.getLogger(__name__)


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
    application.add_handler(CommandHandler("brief", handlers["brief"]))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handlers["message"]))

    schedule_daily_brief(application, nim_client)

    application.run_polling(allowed_updates=Update.ALL_TYPES)


def schedule_daily_brief(application: Application, nim_client: NIMClient) -> None:
    if not settings.target_chat_id:
        logger.info("TARGET_CHAT_ID 未設定，略過每日晨報排程")
        return
    if application.job_queue is None:
        logger.warning("JobQueue 未啟用，無法排程晨報（請安裝 python-telegram-bot[job-queue]）")
        return

    async def _daily_job(context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            text = await build_daily_brief(nim_client)
            await context.bot.send_message(
                chat_id=int(settings.target_chat_id),
                text=text,
                disable_web_page_preview=True,
            )
        except Exception:  # pragma: no cover
            logger.exception("daily brief job failed")

    application.job_queue.run_daily(
        _daily_job,
        time=dt_time(
            hour=settings.brief_hour,
            minute=settings.brief_minute,
            tzinfo=ZoneInfo(settings.brief_tz),
        ),
        name="daily_semi_brief",
    )
    logger.info(
        "已排程每日晨報：%02d:%02d %s",
        settings.brief_hour,
        settings.brief_minute,
        settings.brief_tz,
    )


if __name__ == "__main__":
    main()
