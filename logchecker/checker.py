#!/usr/bin/env python3
# -*- coding: utf-8 -*- #

import os
import time
import subprocess
import sys
import re

import logging

logger = logging.getLogger(__name__)


def check_file_permission(file_path, method='readable'):
  if method == 'readable':
    if os.access(file_path, os.F_OK) and os.access(file_path, os.R_OK):
      return True
  elif method == 'readwrite':
    if os.access(file_path, os.F_OK) and os.access(file_path, os.R_OK) and os.access(file_path, os.W_OK):
      return True
  return False


class LogChecker(object):
  '''LogChecker'''
  def __init__(self, path='/var/log/logchecker'):
    if not os.path.isdir(path):
      os.makedirs(path)
    self.__wf = {}
    self.work_path = path
    self.logger = logging.getLogger('LogChecker')

  def set_log_file_env(self, log_hashkey):
    self.__wf['count'] = '{}/{}_incoming.count'.format(self.work_path, log_hashkey)
    self.__wf['incoming'] = '{}/{}_incoming'.format(self.work_path, log_hashkey)

  def set_pattern_config_env(self, log_hashkey, pattern_hashkey):
    self.__wf['timestamp'] = '{}/{}{}_pattern.timestamp'.format(self.work_path, log_hashkey, pattern_hashkey)
    self.__wf['pattern'] = '{}/{}{}_pattern.log'.format(self.work_path, log_hashkey, pattern_hashkey)

  def get_file_line_count(self, file_path):
    count = 0
    if not check_file_permission(file_path, method='readable'):
      logger.error('{} is not readable'.format(file_path))
      sys.exit()
    cmd = "wc -l {} | awk '{{print $1}}'".format(file_path)
    stdout = subprocess.check_output(cmd, shell=True)
    count = int(stdout.strip())
    self.logger.debug('get {} file line count: {}'.format(file_path, count))
    return count

  def set_incoming_file_line_count(self, count):
    with open(self.__wf['count'], 'w') as f:
      f.write(str(count))
    self.logger.debug('set incoming file line count: {}'.format(count))

  def get_incoming_file_line_count(self, log_file, log_file_line_count):
    if not check_file_permission(self.__wf['count'], method='readwrite'):
      incoming_file_line_count = log_file_line_count
    else:
      incoming_file_line_count = int(open(self.__wf['count'], 'r').read().strip())
      # if has new log
      if log_file_line_count > incoming_file_line_count:
        cmd = "tail -n +{} {} | tee {} | wc -l".format(incoming_file_line_count + 1, log_file, self.__wf['incoming'])
        stdout = subprocess.check_output(cmd, shell=True)
        incoming_file_line_count += int(stdout.strip())
      # if log rotation
      elif log_file_line_count < incoming_file_line_count:
        cmd = "cat {} | tee {} | wc -l".format(log_file, self.__wf['incoming'])
        stdout = subprocess.check_output(cmd, shell=True)
        incoming_file_line_count = int(stdout.strip())
      else:
        open(self.__wf['incoming'], 'w').close()
    self.logger.debug('get incoming file line count: {}'.format(incoming_file_line_count))
    return incoming_file_line_count

  def set_last_pattern_match_timestamp(self, timestamp):
    with open(self.__wf['timestamp'], 'w') as f:
      f.write(str(timestamp))
    self.logger.debug('set last pattern match timestamp: {}'.format(timestamp))

  def get_last_pattern_match_timestamp(self):
    if not check_file_permission(self.__wf['timestamp'], method='readwrite'):
      last_timestamp = int(time.time())
      self.set_last_pattern_match_timestamp(last_timestamp)
    else:
      with open(self.__wf['timestamp'], 'r') as f:
        last_timestamp = int(f.read().strip())
    self.logger.debug('get last pattern match timestamp: {}'.format(last_timestamp))
    return last_timestamp

  def find_log_file(self, log_path, log_regex_name, exclude_log_name=''):
    log_files = []
    default_ignore_suffix = '^/.|.gz$|.tar$|.md5$'
    if not check_file_permission(log_path, method='readable'):
      self.logger.error('{} is not readable'.format(file_path))
      sys.exit()
    cmd = "find -L {} -maxdepth 1 -type f -mtime -1 | sed -e 's/ //g' -e 's#.*/##'".format(log_path)
    stdout = subprocess.check_output(cmd, shell=True).decode(sys.stdout.encoding)
    for log_file_name in stdout.split('\n'):
      log_file_name = log_file_name.strip()
      if re.fullmatch(log_regex_name, log_file_name) and not re.fullmatch(exclude_log_name, log_file_name):
        if re.search(default_ignore_suffix, log_file_name):
          continue
        log_files.append(os.path.expanduser('{}/{}'.format(log_path, log_file_name)))
        self.logger.debug('find log file: {}/{}'.format(log_path, log_file_name))
    return log_files

  def fetch_pattern_match_count(self, pattern, pattern_exclude=None):
    log_patterns = []
    if check_file_permission(self.__wf['incoming'], method='readable'):
      with open(self.__wf['incoming'], 'r') as f:
        for line in f:
          if pattern_exclude is not None and re.search(pattern_exclude, line):
            continue
          if re.search(pattern, line):
            log_patterns.append(line)
      with open(self.__wf['pattern'], 'a') as f:
        for log in log_patterns:
          f.write(log)
    self.logger.info('fetch pattern \'{}\' match count: {}'.format(pattern, len(log_patterns)))
    return len(log_patterns)

  def check_pattern_match_duration(self, freq, pattern_match_duration):
    if pattern_match_duration >= int(freq) * 60:
      return True
    else:
      return False

  def check_pattern_match_status_code(self, count, pattern_match_count):
    if pattern_match_count >= int(count):
      return 1
    else:
      return 0

  def reset_pattern_match_count(self):
    open(self.__wf['pattern'], 'w').close()

  def gc_env(self):
    for f in os.listdir(self.work_path):
      if os.path.isfile(f):
        creation_timestamp = os.path.getctime(f)
        if int(time.time()) - creation_timestamp / 86400 >= 7:
          os.remove(f)
