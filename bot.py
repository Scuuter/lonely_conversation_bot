#!/usr/bin/env python3
# pylint: disable=C0116

"""
Usage:
Send /start to initiate the conversation.
Press Ctrl-C on the command line or send a signal to the process to stop the
bot.
"""

import logging
import time, threading
from random import randint
from datetime import datetime
from bot_token import BOT_TOKEN
from phrases import PHRASES

from telegram import Update, Message, User
from telegram.ext import (
    Updater,
    CommandHandler,
    Filters,
    CallbackContext,
    PicklePersistence
)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)

logger = logging.getLogger(__name__)

default_timeout = 2

def start(update: Update, _: CallbackContext):
    user = update.message.from_user
    logger.info("User %s started bot.", user.username)
    update.message.reply_text(
        "Привет! Ты написал мне, значит ты хочешь получать кучу странных сообщений.\n"
        "По команде /spam я начну их присылать. По команде /stop прекращу.\n"
        'Также можно задать интервал сообщений командой "/interval x"'
    )

def spam(update: Update, context: CallbackContext):
    user = update.message.from_user
    this_timeout = context.chat_data.get('interval', default_timeout)
    logger.info("User %s started spamming.", user.username)
    context.job_queue.run_repeating(spam_phrase, this_timeout, name="spam_to_"+str(user.id), context=(update.message, context))
    
def spam_phrase(context: CallbackContext):
    message = context.job.context[0]
    chat_context = context.job.context[1]

    phrase_iterator = chat_context.chat_data.get('phrase_iterator', 0)

    phrase = PHRASES[phrase_iterator]

    message.reply_text(phrase)

    phrase_iterator = (phrase_iterator + 1) % len(PHRASES)
    chat_context.chat_data['phrase_iterator'] = phrase_iterator

def stop(update: Update, context: CallbackContext):
    user = update.message.from_user
    logger.info("User %s stopped spamming.", user.username)
    stop_spamming_job(user, context)
    update.message.reply_text(
        "Ок, прекращаю"
    )

def stop_spamming_job(user: User, context: CallbackContext):
    for job in list(context.job_queue.get_jobs_by_name("spam_to_"+str(user.id))):
        job.schedule_removal()

def interval(update: Update, context: CallbackContext):
    new_timeout = 0
    user = update.message.from_user
    if (len(context.args) == 0):
        logger.info(f"User {user.username} provided zero arguments for interval")
        update.message.reply_text(
            'Задайте интервал между сообщениями в формате "/interval x", где x - желаемый интервал.\n'
            'Интервал не может быть меньше 1.'
        )
        return
    if (len(context.args) > 1):
        logger.info(f"User {user.username} provided too much arguments for interval")
        update.message.reply_text(
            "Неверный формат. Нужно одно число."
        )
        return
    try:
        new_timeout = float(context.args[0])
    except ValueError:
        logger.info(f"User {user.username} provided string for interval")
        update.message.reply_text(
            "Неверный формат. Нужно одно число."
        )
        return
    if (new_timeout < 1): 
        new_timeout = 1
        update.message.reply_text(
            "Интервал не может быть меньше 1."
        )
    context.chat_data['interval'] = new_timeout
    update.message.reply_text(
       f"Задан интервал {new_timeout}."
    )
    logger.info(f"User {user.username} set interval to {new_timeout}.")
    stop_spamming_job(user, context)
    spam(update, context)


def main() -> None:
    persistence = PicklePersistence(filename='persistence')
    updater = Updater(BOT_TOKEN, persistence=persistence, use_context=True)

    dispatcher = updater.dispatcher

    dispatcher.add_handler(CommandHandler('start', start))
    dispatcher.add_handler(CommandHandler('spam', spam))
    dispatcher.add_handler(CommandHandler('stop', stop))
    dispatcher.add_handler(CommandHandler('interval', interval))

    updater.start_polling()

    # Run the bot until you press Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    updater.idle()


if __name__ == '__main__':
    main()
