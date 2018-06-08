#!/usr/bin/env python3
# -*- coding: utf-8 -*- #

import argparse
import hashlib
import os
import re
import subprocess
import sys
import time
import json
import logging

pid = str(os.getpid())

def get_md5(data):
  m = hashlib.md5()
  m.update(data.encode('utf-8'))
  return m.hexdigest()

def lock(lock_file, path='/var/run'):
  if os.path.isfile(lock_file):
    print("{} already exists, exiting".format(pid_file))
    return False
  else:
    with open(pid_file, 'w') as f:
      f.write(pid)
  return True

def unlock(lock_file):
  os.remove(lock_file)

class LogWatch(object):
  """docstring for LogScanner"""
  def __init__(self, path='/tmp'):
    self.work_path = '{}/{}'.format(path, log_path.rstrip('/'))
    self.__wf = {}

  def check_file_permission(self, file_path, method='readonly'):
    if method == 'readonly':
      if os.access(file_path, os.F_OK) and os.access(file_path, os.R_OK):
        return True
    elif method == 'readwrite':
      if os.access(file_path, os.F_OK) and os.access(file_path, os.R_OK) and os.access(file_path, os.W_OK):
        return True
    return False

  def get_file_count(self, file_path):
    if not self.check_file_permission(file_path, method='readonly'):
      sys.exit()
    cmd = "wc -l {} | awk '{print $1}'".format(file_path)
    stdout = subprocess.check_output(cmd, shell=True)
    return int(stdout.strip())

  def set_log_config_env(self, log_hashkey):
    self.__wf['count'] = '{}/{}.count'.format(self.work_path, log_hashkey)
    self.__wf['incoming'] = '{}/{}incoming.log'.format(self.work_path, log_hashkey)

  def set_pattern_config_env(self, log_hashkey, pattern_hashkey):
    self.__wf['timestamp'] = '{}/{}{}.timestamp'.format(self.work_path, log_hashkey, pattern_hashkey)
    self.__wf['pattern'] = '{}/{}{}pattern.log'.format(self.work_path, log_hashkey, pattern_hashkey)

  def set_last_count(self, count):
    with open(self.__wf['count'], 'w') as f:
      f.write(str(count))

  def get_last_count(self, log_file):
    if not self.check_file_permission(self.__wf['count'], method='readwrite'):
      os.makedirs(os.path.dirname(self.__wf['count']))
      count = self.get_file_count(log_file)
      self.set_last_count(count)
      return int(count.strip())
    else:
      with open(self.__wf['count'], 'r') as f:
        count = f.read()
      return int(count.strip())

  def set_last_timestamp(self, timestamp):
    with open(self.__wf['timestamp'], 'w') as f:
      f.write(str(timestamp))

  def get_last_timestamp(self):
    if not self.check_file_permission(self.__wf['timestamp'], method='readwrite'):
      os.makedirs(os.path.dirname(self.__wf['timestamp']))
      last_timestamp = int(time.time())
      self.set_last_timestamp(last_timestamp)
      return last_timestamp
    else:
      with open(self.__wf['timestamp'], 'r') as f:
        last_timestamp = f.read()
      return int(last_timestamp.strip())

  def find_log_file(self, log_path, log_regex_name, exclude_log_name=''):
    log_files = []
    default_ignore_suffix = '^/.|.gz$|.tar$|.md5$'
    cmd = "find -L {} -maxdepth 1 -type f -mtime -1 | sed -e 's/ //g' -e 's#.*/##'".format(log_path)
    stdout = subprocess.check_output(cmd, shell=True).decode(sys.stdout.encoding)
    for log_file in stdout.split('\n'):
      log_file = log_file.strip()
      if re.fullmatch(log_regex_name, log_file) and not re.fullmatch(exclude_log_name, log_file):
        if re.search(default_ignore_suffix, log_file):
          continue
        log_files.append(os.path.expanduser('{}/{}'.format(log_path, log_file)))
    return log_files

  def fetch_incoming_log(self, log_file):
    incoming_count = self.get_incoming_count(log_file)
    last_count = self.get_last_count(log_file)
    # if has new log
    if incoming_count > last_count:
      cmd = "tail --lines=+{} {} | tee -a {} | wc -l".format(last_count+1, log_file, self.__wf['incoming'])
      stdout = subprocess.check_output(cmd, shell=True)
      return int(stdout.strip()) + last_count
    # elif log rotation
    elif incoming_count < last_count:
      cmd = "cat {} | tee -a {} | wc -l".format(log_file, self.__wf['incoming'])
      stdout = subprocess.check_output(cmd, shell=True)
      return int(stdout.strip())
    else:
      pass
    return 0

  def fetch_pattern_log(self, pattern, pattern_exclude=None):
    log_patterns = []
    with open(self.__wf['incoming'], 'r') as f:
      for line in f.readline():
        if pattern_exclude != None and re.search(pattern_exclude, line):
          continue
        if re.search(pattern, line):
          log_patterns.append(line)
    with open(self.__wf['pattern'], 'a') as f:
      for log in log_patterns:
        f.write(log)
    return self.get_file_count(self.__wf['pattern'])

  def gc_env():
    current_time = time.time()
    for f in os.listdir(self.work_path):
      creation_time = os.path.getctime(f)
      if (current_time - creation_time) // (24 * 3600) >= 7:
          os.remove(f)

def main():
  alerts = []
  current_timestamp = int(time.time())
  # argparse
  parser = argparse.ArgumentParser()
  parser.add_argument("--find_logfile", nargs="+")
  parser.add_argument("--include", nargs="+")
  parser.add_argument("--exclude", nargs="+")
  argv = parser.parse_args()

  lw = LowWatch()
  for log_config in argv.find_logfile:
    log_hashkey = get_md5(log_config)
    lw.set_log_config_env(log_hashkey)
    log_path, log_regex_name = log_config.split('|')
    if not lw.check_file_permission(log_path, 'readonly')
      sys.exit()

    lock('logwatch-{}.pid'.format(log_hashkey))

    for log_file in lw.find_log_file(log_path, log_regex_name):
      incomming_log_count = lw.fetch_incoming_log(log_path, log_file)
      lw.set_last_count(incomming_log_count)

    for pattern_config in argv.include:
      pattern_hashkey = get_md5(pattern_config)
      lw.set_pattern_config_env(log_hashkey, pattern_hashkey)
      pattern, freq, count = pattern_config.split('|')
      pattern_exclude = '|'.join(argv.exclude) if argv.exclude else None

      pattern_log_count = lw.fetch_pattern_log(pattern, pattern_exclude)
      duration = current_timestamp - lw.get_last_timestamp()

      alert['application'] = 'logwatch-{}'.format(log_hashkey)
      alert['timestamp'] = current_timestamp
      alert['dimensions']['log_config'] = log_config
      alert['dimensions']['pattern_config'] = pattern_config
      alert['dimensions']['host'] = 'host'
      if duration >= int(freq) * 60:
        if pattern_log_count >= int(count):
          alert['status_code'] = 1
          alert['status_message'] = '(log_config:$log_config pattern:$pattern) [config freq:${pattern_freq} min cnt:${pattern_count}] [real freq:${mins}min${secs}s cnt:${alert_count}]'
        else:
          alert['status_code'] = 0
          alert['status_message'] = '(log_config:$log_config pattern:$pattern) [config freq:${pattern_freq}min cnt:${pattern_count}] [real freq:${mins}min${secs}s cnt:${alert_count}]'
      alerts.append(alert)

      lw.set_last_timestamp(current_timestamp)
    lw.gc_env()

    unlock('logwatch-{}.pid'.format(log_hashkey))
  print(alerts)
  pass

if __name__ == '__main__':
  main()
