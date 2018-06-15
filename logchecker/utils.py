#!/usr/bin/env python3
# -*- coding: utf-8 -*- #

import hashlib
import os

import logging

logger = logging.getLogger(__name__)


def get_md5(data):
  m = hashlib.md5()
  m.update(data.encode('utf-8'))
  return m.hexdigest()


def lock(lock_file, path='/tmp'):
  lock_file = '{}/{}'.format(path, lock_file)
  if os.path.isfile(lock_file):
    logger.info('{} already exists, exiting'.format(lock_file))
    return False
  else:
    with open(lock_file, 'w') as f:
      f.write(str(os.getpid()))
    logger.info('{} lock completed'.format(lock_file))
    return True


def unlock(lock_file, path='/tmp'):
  lock_file = '{}/{}'.format(path, lock_file)
  if os.path.isfile(lock_file):
    os.remove(lock_file)
    if os.path.exists(lock_file):
      logger.info('{} cannot removed, exiting'.format(lock_file))
      return False
    else:
      logger.info('{} unlock completed'.format(lock_file))
      return True
  else:
    logger.info('{} already not exists, exiting'.format(lock_file))
    return True
