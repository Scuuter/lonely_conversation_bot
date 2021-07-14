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
from typing import Dict, List
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

def start(update: Update, context: CallbackContext):
    user = update.message.from_user
    logger.info("User %s started bot.", user.username)
    init_default_dict(context.chat_data)

    update.message.reply_text(
        "Привет! Ты написал мне, значит ты хочешь получать кучу странных сообщений.\n"
        "По команде /spam я начну их присылать. По команде /stop прекращу.\n"
        'Также можно задать интервал сообщений командой "/interval x"'
    )

def spam(update: Update, context: CallbackContext):
    user = update.message.from_user
    init_default_dict(context.chat_data)
    cur_dict = current_dict(context.chat_data)
    if len(cur_dict) == 0:
        logger.info(f"User {user.username} spammed empty dict")
        update.message.reply_text(
            'Словарь не содержит фраз. Добавьте или выберите другой'
        )
        return

    this_timeout = context.chat_data.get('interval', default_timeout)
    logger.info("User %s started spamming.", user.username)
    context.job_queue.run_repeating(spam_phrase, this_timeout, name="spam_to_"+str(user.id), context=(update.message, context, cur_dict))
    
def spam_phrase(context: CallbackContext):
    message = context.job.context[0]
    chat_context = context.job.context[1]
    cur_dict = context.job.context[2]

    phrase_iterator = chat_context.chat_data.get('phrase_iterator', 0)
    if (phrase_iterator > len(cur_dict)):
        phrase_iterator = 0
    phrase = cur_dict[phrase_iterator]

    message.reply_text(phrase)

    phrase_iterator = (phrase_iterator + 1) % len(cur_dict)
    chat_context.chat_data['phrase_iterator'] = phrase_iterator

def stop(update: Update, context: CallbackContext):
    user = update.message.from_user
    logger.info("User %s stopped spamming.", user.username)
    stop_spamming_job(user, context)
    update.message.reply_text(
        "Ок, прекращаю"
    )

def stop_spamming_job(user: User, context: CallbackContext) -> bool:
    deleted = False
    for job in list(context.job_queue.get_jobs_by_name("spam_to_"+str(user.id))):
        job.schedule_removal()
        deleted = True
    return deleted 

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
    if (stop_spamming_job(user, context)):
        spam(update, context)

def new_dict(update: Update, context: CallbackContext):
    user = update.message.from_user
    if (len(context.args) == 0):
        logger.info(f"User {user.username} provided zero arguments for new_dict")
        update.message.reply_text(
            'Создайте словарь в формате "/new_dict name", где name - название словаря.'
        )
        return
    if (len(context.args) > 1):
        logger.info(f"User {user.username} provided too much arguments for new_dict")
        update.message.reply_text(
            "Неверный формат названия. Нужно одно слово."
        )
        return
    dict_name = context.args[0]
    add_dict(context.chat_data, dict_name)
    
    update.message.reply_text(
       f"Создан словарь {dict_name}. Он установлен в качестве текущего"
    )
    logger.info(f"User {user.username} created dict {dict_name}.")

def add_phrase(update: Update, context: CallbackContext):
    user = update.message.from_user
    if (len(context.args) == 0):
        logger.info(f"User {user.username} provided zero arguments for add_phrase")
        update.message.reply_text(
            'Добавьте фразу в формате "/add_phrase phrase"'
        )
        return

    phrase = ' '.join(context.args)
    dict_name = current_dict_name(context.chat_data)
    context.chat_data[dict_name].append(phrase)
    update.message.reply_text(
       f"{phrase}"
    )
    update.message.reply_text(
       f"Фраза добавлена в словарь {dict_name}."
    )
    logger.info(f"User {user.username} добавил фразу {phrase} в словарь {dict_name}.")

def set_dict(update: Update, context: CallbackContext):
    user = update.message.from_user
    if (len(context.args) == 0):
        logger.info(f"User {user.username} provided zero arguments for set_dict")
        update.message.reply_text(
            'Задайте текущий словарь в формате "/set_dict name", где name - название словаря.'
        )
        return
    if (len(context.args) > 1):
        logger.info(f"User {user.username} provided too much arguments for set_dict")
        update.message.reply_text(
            "Неверный формат названия. Нужно одно слово."
        )
        return
    dict_name = context.args[0]
    if (dict_name not in context.chat_data['dicts']):
        logger.info(f"User {user.username} set wrong dict")
        update.message.reply_text(
            "Такого словаря не существует."
        )
        return
    context.chat_data['current_dict'] = dict_name
    context.chat_data['phrase_iterator'] = 0

    update.message.reply_text(
       f"Словарь {dict_name} установлен в качестве текущего"
    )
    logger.info(f"User {user.username} set dict {dict_name} as current.")

def ask_dicts(update: Update, context: CallbackContext):
    user = update.message.from_user
    init_default_dict(context.chat_data)
    update.message.reply_text(
       ' '.join(context.chat_data['dicts'])
    )
    logger.info(f"User {user.username} asked for dicts list.")

def ask_current_dict(update: Update, context: CallbackContext):
    user = update.message.from_user
    init_default_dict(context.chat_data)
    update.message.reply_text(
        current_dict_name(context.chat_data)
    )
    logger.info(f"User {user.username} asked about current dict.")


def current_dict_name(chat_data: Dict) -> str: 
    return chat_data['current_dict']

def add_dict(chat_data: Dict, new_dict: str):
    init_default_dict(chat_data)
    chat_data[new_dict] = []
    chat_data['current_dict'] = new_dict
    chat_data['dicts'].append(new_dict)
    chat_data['phrase_iterator'] = 0

def init_default_dict(chat_data: Dict):
    if chat_data.get('dicts') == None:
        chat_data['dicts'] = ['default']
        chat_data['current_dict'] = 'default'
        chat_data['default'] = PHRASES 
        chat_data['phrase_iterator'] = 0


def current_dict(chat_data: Dict) -> List[str]:
    return chat_data[current_dict_name(chat_data)]


def main() -> None:
    persistence = PicklePersistence(filename='persistence')
    updater = Updater(BOT_TOKEN, persistence=persistence, use_context=True)

    dispatcher = updater.dispatcher

    dispatcher.add_handler(CommandHandler('start', start))
    dispatcher.add_handler(CommandHandler('spam', spam))
    dispatcher.add_handler(CommandHandler('stop', stop))
    dispatcher.add_handler(CommandHandler('interval', interval))
    dispatcher.add_handler(CommandHandler('new_dict', new_dict))
    dispatcher.add_handler(CommandHandler('set_dict', set_dict))
    dispatcher.add_handler(CommandHandler('add_phrase', add_phrase))
    dispatcher.add_handler(CommandHandler('dicts', ask_dicts))
    dispatcher.add_handler(CommandHandler('current_dict', ask_current_dict))


    updater.start_polling()

    # Run the bot until you press Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    updater.idle()


if __name__ == '__main__':
    main()
