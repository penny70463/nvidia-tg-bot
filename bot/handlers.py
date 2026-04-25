from __future__ import annotations

import logging
from typing import Any

from telegram import Update
from telegram.ext import ContextTypes

from bot.config import settings
from bot.memory import MemoryStore
from bot.prompts import build_system_prompt


logger = logging.getLogger(__name__)
VALID_MODES = {"career", "ielts"}


def build_handlers(memory: MemoryStore, nim_client: Any) -> dict[str, Any]:
    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.effective_chat or not update.message:
            return
        chat_id = update.effective_chat.id
        memory.ensure_chat(chat_id)
        mode = memory.get_mode(chat_id)
        await update.message.reply_text(
            "NVIDIA Telegram 助理已啟動。\n"
            f"目前模式：`{mode}`\n\n"
            "可用指令：/mode career, /mode ielts, /ielts_speaking, /ielts_writing, "
            "/ielts_new, /ielts_eval, /ielts_status, /clear",
            parse_mode="Markdown",
        )

    async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message:
            return
        await update.message.reply_text(
            "/mode career - 切換到職涯顧問\n"
            "/mode ielts - 切換到雅思教練\n"
            "/ielts_speaking - 切換到口說練習\n"
            "/ielts_writing - 切換到寫作練習\n"
            "/ielts_new - 產生新的 IELTS 題目\n"
            "/ielts_eval - 產生目前 IELTS 總結評估\n"
            "/ielts_status - 查看 IELTS 練習狀態\n"
            "/clear - 清空記憶與狀態"
        )

    async def set_mode(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.effective_chat or not update.message:
            return
        chat_id = update.effective_chat.id
        if not context.args or context.args[0] not in VALID_MODES:
            await update.message.reply_text("請使用 `/mode career` 或 `/mode ielts`", parse_mode="Markdown")
            return

        mode = context.args[0]
        memory.set_mode(chat_id, mode)
        reply = "已切換到職涯顧問模式。" if mode == "career" else "已切換到雅思教練模式。"
        await update.message.reply_text(reply)

    async def clear(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.effective_chat or not update.message:
            return
        memory.clear_chat(update.effective_chat.id)
        await update.message.reply_text("已清空對話記憶與 IELTS 狀態。")

    async def ielts_new(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.effective_chat or not update.message:
            return
        chat_id = update.effective_chat.id
        memory.set_mode(chat_id, "ielts")
        state = memory.get_ielts_state(chat_id)
        track = state.get("track", "speaking")
        prompt = (
            f"The user wants a brand new IELTS {track} practice question.\n"
            "Ask exactly one question. If speaking, label the part. "
            "If writing, give a compact prompt and expected response target."
        )
        await _generate_and_reply(update, chat_id, prompt, mode_override="ielts", store_user=False)

    async def ielts_speaking(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await _set_ielts_track(update, "speaking")

    async def ielts_writing(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await _set_ielts_track(update, "writing")

    async def ielts_eval(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.effective_chat or not update.message:
            return
        chat_id = update.effective_chat.id
        memory.set_mode(chat_id, "ielts")
        prompt = (
            "Summarize the user's current IELTS performance based on the conversation so far. "
            "Include strengths, weaknesses, an estimated band score, and the next recommended drill."
        )
        await _generate_and_reply(update, chat_id, prompt, mode_override="ielts", store_user=False)

    async def ielts_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.effective_chat or not update.message:
            return
        state = memory.get_ielts_state(update.effective_chat.id)
        practice_counts = state["practice_counts"]
        estimated_band = state.get("estimated_band") or "N/A"
        lines = [
            f"目前軌道：{state.get('track', 'speaking')}",
            f"預估 Band：{estimated_band}",
            "練習次數：",
        ]
        for key, value in practice_counts.items():
            lines.append(f"- {key}: {value}")
        if state.get("last_question"):
            lines.append(f"上一題：{state['last_question']}")
        await update.message.reply_text("\n".join(lines))

    async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.effective_chat or not update.message or not update.message.text:
            return
        chat_id = update.effective_chat.id
        user_text = update.message.text.strip()
        mode = memory.get_mode(chat_id)
        await _generate_and_reply(update, chat_id, user_text, mode_override=mode, store_user=True)

    async def _set_ielts_track(update: Update, track: str) -> None:
        if not update.effective_chat or not update.message:
            return
        chat_id = update.effective_chat.id
        memory.set_mode(chat_id, "ielts")
        state = memory.get_ielts_state(chat_id)
        state["track"] = track
        memory.update_ielts_state(chat_id, state)
        await update.message.reply_text(f"已切換 IELTS 練習軌道為 {track}。接著可使用 /ielts_new 出題。")

    async def _generate_and_reply(
        update: Update,
        chat_id: int,
        user_input: str,
        *,
        mode_override: str,
        store_user: bool,
    ) -> None:
        if not update.message:
            return
        try:
            if store_user:
                memory.append_message(chat_id, "user", user_input)

            extra_context = None
            if mode_override == "ielts":
                extra_context = format_ielts_context(memory.get_ielts_state(chat_id))

            messages = [{"role": "system", "content": build_system_prompt(mode_override, extra_context)}]
            messages.extend(memory.get_recent_messages(chat_id, settings.max_history_messages))

            if not store_user:
                messages.append({"role": "user", "content": user_input})

            reply = await nim_client.chat(messages)
            if not reply:
                reply = "目前模型沒有回傳內容，請再試一次。"

            memory.append_message(chat_id, "assistant", reply)
            if mode_override == "ielts":
                update_ielts_state_from_reply(memory, chat_id, user_input, reply, store_user)

            await update.message.reply_text(reply)
        except ValueError as exc:
            await update.message.reply_text(
                f"設定尚未完成：{exc}\n請先補上 `.env` 內的必要值再啟動完整功能。"
            )
        except Exception as exc:  # pragma: no cover
            logger.exception("Failed to generate reply")
            await update.message.reply_text(f"處理訊息時發生錯誤：{exc}")

    return {
        "start": start,
        "help": help_command,
        "mode": set_mode,
        "clear": clear,
        "ielts_new": ielts_new,
        "ielts_speaking": ielts_speaking,
        "ielts_writing": ielts_writing,
        "ielts_eval": ielts_eval,
        "ielts_status": ielts_status,
        "message": handle_text,
    }


def format_ielts_context(state: dict[str, Any]) -> str:
    return (
        f"Current track: {state.get('track', 'speaking')}\n"
        f"Estimated band: {state.get('estimated_band', 'N/A')}\n"
        f"Last question: {state.get('last_question', '')}\n"
        f"Practice counts: {state.get('practice_counts', {})}"
    )


def update_ielts_state_from_reply(
    memory: MemoryStore,
    chat_id: int,
    user_input: str,
    reply: str,
    store_user: bool,
) -> None:
    state = memory.get_ielts_state(chat_id)
    lower_reply = reply.lower()
    if "writing" in lower_reply:
        state["track"] = "writing"
    elif "speaking" in lower_reply:
        state["track"] = "speaking"

    if "part 1" in lower_reply:
        state["practice_counts"]["speaking_part_1"] += 1
    elif "part 2" in lower_reply:
        state["practice_counts"]["speaking_part_2"] += 1
    elif "part 3" in lower_reply:
        state["practice_counts"]["speaking_part_3"] += 1
    elif "task 1" in lower_reply:
        state["practice_counts"]["writing_task_1"] += 1
    elif "task 2" in lower_reply:
        state["practice_counts"]["writing_task_2"] += 1

    if not store_user:
        state["last_question"] = reply.splitlines()[0][:280]
    elif "estimated band score" in lower_reply:
        state["estimated_band"] = extract_band_hint(reply)

    memory.update_ielts_state(chat_id, state)


def extract_band_hint(reply: str) -> str:
    for line in reply.splitlines():
        if "band" in line.lower():
            return line.strip()
    return "See latest evaluation"
