#!/usr/bin/env python3
# -*- coding: utf-8 -*- #

import os
import logging
import logging.handlers

LOG_FILEDIR = '/var/log/logchecker'
LOG_FILENAME = LOG_FILEDIR + '/logchecker.log'
if not os.path.isdir(LOG_FILEDIR):
  os.makedirs(LOG_FILEDIR)

# Add the log message handler to the logger
handler = logging.handlers.RotatingFileHandler(LOG_FILENAME, maxBytes=100000, backupCount=5)
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.DEBUG, handlers=[handler])
