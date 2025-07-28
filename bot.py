#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections import defaultdict

import nonebot
from nonebot.adapters.onebot.v11 import Adapter, Message, MessageSegment
from nonebot import require, get_bot, get_driver

# Custom your logger
# 
# from nonebot.log import logger, default_format
# logger.add("error.log",
#            rotation="00:00",
#            diagnose=False,
#            level="ERROR",
#            format=default_format)

# You can pass some keyword args config to init function
nonebot.init()
# nonebot.load_builtin_plugins()
app = nonebot.get_asgi()

driver = nonebot.get_driver()
driver.register_adapter(Adapter)
driver.config.help_text = {}

import src.quart

driver.server_app.mount("/web", src.quart.quart_app)

nonebot.load_plugins("src/plugins")
nonebot.load_plugins("private/plugins")

# Modify some config / config depends on loaded configs
# 
# config = driver.config
# do something...


if __name__ == "__main__":
    nonebot.run(port=8000)

