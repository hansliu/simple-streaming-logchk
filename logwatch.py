#!/usr/bin/env python3
# -*- coding: utf-8 -*- #

import argparse
import hashlib
import os
import re
import subprocess
import sys
import time
# import json
import logging

pid = str(os.getpid())


def get_md5(data):
  m = hashlib.md5()
  m.update(data.encode('utf-8'))
  return m.hexdigest()


def lock(lock_file, path='/var/run'):
  if os.path.isfile(lock_file):
    print("{} already exists, exiting".format(lock_file))
    return False
  else:
    with open(lock_file, 'w') as f:
      f.write(pid)
  return True


def unlock(lock_file, path='/var/run'):
  if not os.remove(lock_file):
    return False
  return True


def get_file_count(file_path):
  if not check_file_permission(file_path, method='readable'):
    sys.exit()
  cmd = "wc -l {} | awk '{{print $1}}'".format(file_path)
  stdout = subprocess.check_output(cmd, shell=True)
  return int(stdout.strip())


def check_file_permission(file_path, method='readable'):
  if method == 'readable':
    if os.access(file_path, os.F_OK) and os.access(file_path, os.R_OK):
      return True
  elif method == 'readwrite':
    if os.access(file_path, os.F_OK) and os.access(file_path, os.R_OK) and os.access(file_path, os.W_OK):
      return True
  return False


class LogWatch(object):
  """docstring for LogScanner"""
  def __init__(self, path='/tmp'):
    if not os.path.isdir(path):
      os.makedirs(path)
    self.work_path = '{}'.format(path)
    self.__wf = {}

  def set_log_file_env(self, log_hashkey):
    self.__wf['count'] = '{}/{}incoming.count'.format(self.work_path, log_hashkey)
    self.__wf['incoming'] = '{}/{}incoming'.format(self.work_path, log_hashkey)

  def set_pattern_config_env(self, log_hashkey, pattern_hashkey):
    self.__wf['timestamp'] = '{}/{}{}pattern.timestamp'.format(self.work_path, log_hashkey, pattern_hashkey)
    self.__wf['pattern'] = '{}/{}{}pattern.log'.format(self.work_path, log_hashkey, pattern_hashkey)

  def set_incoming_file_count(self, count):
    with open(self.__wf['count'], 'w') as f:
      f.write(str(count))

  def get_incoming_file_count(self, log_file):
    log_file_count = get_file_count(log_file)
    if not check_file_permission(self.__wf['count'], method='readwrite'):
      self.set_incoming_file_count(log_file_count)
      incoming_file_count = log_file_count
    else:
      incoming_file_count = int(open(self.__wf['count'], 'r').read().strip())
      # if has new log
      if log_file_count > incoming_file_count:
        cmd = "tail -n +{} {} | tee {} | wc -l".format(incoming_file_count + 1, log_file, self.__wf['incoming'])
        stdout = subprocess.check_output(cmd, shell=True)
        incoming_file_count += int(stdout.strip())
      # if log rotation
      elif log_file_count < incoming_file_count:
        cmd = "cat {} | tee {} | wc -l".format(log_file, self.__wf['incoming'])
        stdout = subprocess.check_output(cmd, shell=True)
        incoming_file_count = int(stdout.strip())
      else:
        open(self.__wf['incoming'], 'w').close()
    return incoming_file_count

  def set_last_pattern_match_timestamp(self, timestamp):
    with open(self.__wf['timestamp'], 'w') as f:
      f.write(str(timestamp))

  def get_last_pattern_match_timestamp(self):
    if not check_file_permission(self.__wf['timestamp'], method='readwrite'):
      last_timestamp = int(time.time())
      self.set_last_pattern_match_timestamp(last_timestamp)
      return last_timestamp
    else:
      with open(self.__wf['timestamp'], 'r') as f:
        last_timestamp = f.read()
      return int(last_timestamp.strip())

  def find_log_file(self, log_path, log_regex_name, exclude_log_name=''):
    log_files = []
    default_ignore_suffix = '^/.|.gz$|.tar$|.md5$'
    if not check_file_permission(log_path, 'readable'):
      sys.exit()
    cmd = "find -L {} -maxdepth 1 -type f -mtime -1 | sed -e 's/ //g' -e 's#.*/##'".format(log_path)
    stdout = subprocess.check_output(cmd, shell=True).decode(sys.stdout.encoding)
    for log_file_name in stdout.split('\n'):
      log_file_name = log_file_name.strip()
      if re.fullmatch(log_regex_name, log_file_name) and not re.fullmatch(exclude_log_name, log_file_name):
        if re.search(default_ignore_suffix, log_file_name):
          continue
        log_files.append(os.path.expanduser('{}/{}'.format(log_path, log_file_name)))
    return log_files

  def fetch_pattern_match_count(self, pattern, pattern_exclude=None):
    log_patterns = []
    if check_file_permission(self.__wf['incoming'], method='readable'):
      with open(self.__wf['incoming'], 'r') as f:
        for line in f:
          print(line)
          if pattern_exclude is not None and re.search(pattern_exclude, line):
            continue
          if re.search(pattern, line):
            print(pattern)
            log_patterns.append(line)
      with open(self.__wf['pattern'], 'a') as f:
        for log in log_patterns:
          f.write(log)
    return len(log_patterns)

  def reset_pattern_match_count(self):
    open(self.__wf['pattern'], 'w').close()

  def gc_env(self):
    current_time = time.time()
    for f in os.listdir(self.work_path):
      if os.path.isfile(f):
        creation_time = os.path.getctime(f)
        if current_time - creation_time / 86400 >= 7:
          os.remove(f)


def main():
  pattern_matchs = []
  current_timestamp = int(time.time())
  # argparse
  parser = argparse.ArgumentParser(prog='logwatch')
  parser.add_argument("--find_logfile", nargs='+', default=[])
  parser.add_argument("--include", nargs='+', default=[])
  parser.add_argument("--exclude", nargs='+', default=[])
  argv = parser.parse_args()
  print(argv)

  lw = LogWatch()
  for log_config in argv.find_logfile:
    log_path, log_regex_name = log_config.split('|')
    for log_file in lw.find_log_file(log_path, log_regex_name):
      # initial log watch by log_file
      log_hashkey = get_md5(log_file)
      lw.set_log_file_env(log_hashkey)
      # lock logwatch process by log_file
      lock('logwatch-{}.pid'.format(log_hashkey))
      # get incoming file count
      incoming_file_count = lw.get_incoming_file_count(log_file)
      lw.set_incoming_file_count(incoming_file_count)
      # parse incoming file
      for pattern_config in argv.include:
        pattern_match = {}
        pattern_match['application'] = 'logwatch-{}'.format(log_hashkey)
        pattern_match['timestamp'] = current_timestamp
        # initial log watch by pattern_config
        pattern_hashkey = get_md5(pattern_config)
        lw.set_pattern_config_env(log_hashkey, pattern_hashkey)
        pattern, freq, count = pattern_config.split('|')
        pattern_exclude = '|'.join(argv.exclude) if argv.exclude else None
        # get pattern match count
        pattern_match_count = lw.fetch_pattern_match_count(pattern, pattern_exclude)
        # get pattern duration
        duration = current_timestamp - lw.get_last_pattern_match_timestamp()
        mins = duration // 60
        secs = duration % 60
        if duration >= int(freq) * 60:
          if pattern_match_count >= int(count):
            pattern_match['status_code'] = 1
            pattern_match['status_message'] = '(log_config:{} pattern:{}) [config freq:{}m cnt:{}] [real freq:{}m{}s cnt:{}]'.format(log_config, pattern, freq, count, mins, secs, pattern_match_count)
          else:
            pattern_match['status_code'] = 0
            pattern_match['status_message'] = '(log_config:{} pattern:{}) [config freq:{}m cnt:{}] [real freq:{}m{}s cnt:{}]'.format(log_config, pattern, freq, count, mins, secs, pattern_match_count)
          pattern_match['dimensions'] = {
            'log_config': log_config,
            'pattern_config': pattern_config,
            'host': os.uname()[1]
          }
          pattern_matchs.append(pattern_match)
          lw.set_last_pattern_match_timestamp(current_timestamp)
          lw.reset_pattern_match_count()
        else:
          pass
      # unlock logwatch process by log_file
      unlock('logwatch-{}.pid'.format(log_hashkey))
  lw.gc_env()

  print(pattern_matchs)
  pass


if __name__ == '__main__':
  main()
