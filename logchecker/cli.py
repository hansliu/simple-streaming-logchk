#!/usr/bin/env python3
# -*- coding: utf-8 -*- #

import argparse
import time
import sys
import os
import json

from .utils import get_md5, lock, unlock
from .checker import LogChecker

import logging

logger = logging.getLogger(__name__)


def cli():
  application = ''
  pattern_matchs = []
  current_timestamp = int(time.time())
  # parse arguments
  parser = argparse.ArgumentParser()
  parser.add_argument('-l', "--logfile", nargs='+', help='logfile config "log_path|log_regex_name"', metavar='')
  parser.add_argument('-f', "--filter", nargs='+', help='filter pattern config "pattern|freq|count"', metavar='')
  parser.add_argument('-e', "--exclude", nargs='+', help='exclude pattern', metavar='')
  argv = parser.parse_args()
  if argv.logfile == None or argv.filter == None:
    print('Incorrect logfile and filter arguments')
    parser.print_help()
    sys.exit()
  # run LogChecker
  lc = LogChecker()
  for log_config in argv.logfile:
    try:
      log_path, log_regex_name = log_config.split('|')
    except Exception as e:
      print('Incorrect to read logfile parameters')
      logger.debug('Incorrect to read logfile parameters', exc_info=True)
      parser.print_help()
      sys.exit()
    for log_file in lc.find_log_file(log_path, log_regex_name):
      # initial log watch by log_file
      log_hashkey = get_md5(log_file)
      lc.set_log_file_env(log_hashkey)
      # lock logchecker process by log_hashkey
      application = 'logchecker-{}.pid'.format(log_hashkey)
      lock(application)
      # update incoming file count
      log_file_line_count = lc.get_file_line_count(log_file)
      incoming_file_line_count = lc.get_incoming_file_line_count(log_file, log_file_line_count)
      lc.set_incoming_file_line_count(incoming_file_line_count)
      # parse incoming file
      for pattern_config in argv.filter:
        try:
          pattern, freq, count = pattern_config.split('|')
        except Exception as e:
          print('Incorrect to read filter parameters')
          logger.debug('Incorrect to read filter parameters', exc_info=True)
          parser.print_help()
          sys.exit()
        try:
          pattern_exclude = '|'.join(argv.exclude) if argv.exclude else None
        except Exception as e:
          print('Incorrect to read exclude parameters')
          logger.debug('Incorrect to read exclude parameters', exc_info=True)
          parser.print_help()
          sys.exit()

        # create a new pattern match dict
        pattern_match = {}
        pattern_match['application'] = application
        pattern_match['timestamp'] = current_timestamp
        # initial log watch by pattern_config
        pattern_hashkey = get_md5(pattern_config)
        lc.set_pattern_config_env(log_hashkey, pattern_hashkey)
        # get pattern match duration
        duration = current_timestamp - lc.get_last_pattern_match_timestamp()
        if lc.check_pattern_match_duration(freq, duration):
          # get pattern match count, pattern status_code
          pattern_match_count = lc.fetch_pattern_match_count(pattern, pattern_exclude)
          pattern_match['status_code'] = lc.check_pattern_match_status_code(count, pattern_match_count)
          # get pattern status_message
          pattern_match['status_message'] = '(log_config:{} pattern:{}) [config freq:{}m cnt:{}] [real freq:{}m{}s cnt:{}]'.format(log_config, pattern, freq, count, duration // 60, duration % 60, pattern_match_count)
          # set pattern dimensions
          pattern_match['dimensions'] = {
            'log_config': log_config,
            'pattern_config': pattern_config,
            'host': os.uname()[1]
          }
          pattern_matchs.append(pattern_match)
          # when duration match, update timestamp
          lc.set_last_pattern_match_timestamp(current_timestamp)
          # when duration match, reset pattern match count
          lc.reset_pattern_match_count()
      # unlock logchecker process by log_hashkey
      unlock(application)
  lc.gc_env()
  if len(pattern_matchs) > 0:
    logger.info('{}'.format(json.dumps(pattern_matchs)))

if __name__ == '__main__':
  cli()
