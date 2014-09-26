#!/usr/bin/env python

# Libraries
import __builtin__
import base64
import datetime
import email
import email.header
import imapclient
import os
import re
import shutil
import subprocess

# Local imports
import account_settings


HOST = 'imap.googlemail.com'
PORT = 993
SSL = True

FULL_MSG_FIELD = 'RFC822'
DATE_FIELD = 'INTERNALDATE'
SUBJECT_FIELD = 'BODY[HEADER.FIELDS (SUBJECT)]'
FROM_FIELD = 'BODY[HEADER.FIELDS (FROM)]'
FETCH_FIELDS = [FULL_MSG_FIELD, DATE_FIELD, SUBJECT_FIELD, FROM_FIELD]

if hasattr(__builtin__, '__IPYTHON__'):
  CURRENT_DIR = os.getcwd()
else:
  CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
STUDENTS_DIR = os.path.join(CURRENT_DIR, 'students')
CHECKPOINT_FILE = os.path.join(STUDENTS_DIR, 'CHECKPOINT')
FILENAME_RE = re.compile('^(\d{8})_?(hw|HW)(\d{1}).(tar|tar.gz|zip)$')
DATETIME_STRING_FORMAT = '%Y-%m-%dT%H:%M:%S.%f'
SEPARATOR = ('=' * 70 + '\n') * 3


def login_to_server(username, password):
  print 'Logging in to server as:', username
  server = imapclient.IMAPClient(HOST, port=PORT, ssl=SSL, use_uid=True)
  server.login(username, password)
  return server


def get_attachment(imap_payload_dict):
  # Assumes a single attachment.
  msg_date = imap_payload_dict[DATE_FIELD]

  msg = email.message_from_string(imap_payload_dict[FULL_MSG_FIELD])
  attachment = None
  for part in msg.walk():
    part_filename = part.get_filename()
    if part_filename is not None:
      if attachment is not None:
        raise ValueError('Expected a single attachment.')
      attachment = (part_filename, part.get_payload())

  if attachment is None:
    return None

  payload = ''.join(attachment[1].split())
  payload_bytes = base64.urlsafe_b64decode(payload)
  return msg_date, attachment[0], payload_bytes


def parse_filename(filename):
  match = FILENAME_RE.match(filename)

  if match is None:
    print 'Could not parse attachment filename:', filename
    proceed = raw_input('Would you like to proceed? [y/N] ')
    if proceed.lower() != 'y':
      # Re-raise the error.
      raise
    else:
      return

  student_id, _, assignment, zip_type = match.groups()
  return student_id, assignment, zip_type


# mkdir students
# mkdir -p students/21123113
def create_folder(student_id, assignment, msg_date):
  student_directory = os.path.join(STUDENTS_DIR, student_id)
  if os.path.exists(student_directory):
    if not os.path.isdir(student_directory):
      raise OSError('File %s should be a student\'s directory.' %
                    (student_directory,))
  else:
    os.mkdir(student_directory)

  assignment_directory = os.path.join(student_directory, assignment)
  timestamp_fi = os.path.join(assignment_directory, 'TIMESTAMP')
  update_directory = False
  if os.path.exists(assignment_directory):
    if not os.path.isdir(assignment_directory):
      raise OSError('File %s should be an assignment directory.' %
                    (assignment_directory,))

    with open(timestamp_fi, 'r') as fh:
      saved_msg_date = datetime.datetime.strptime(fh.read(),
                                                  DATETIME_STRING_FORMAT)

    if saved_msg_date < msg_date:
      print 'Conflict in', assignment_directory
      print 'Assignment already saved at time',
      print saved_msg_date.strftime(DATETIME_STRING_FORMAT)
      print 'We will over-write, since received at',
      print msg_date.strftime(DATETIME_STRING_FORMAT)
      shutil.rmtree(assignment_directory)
      update_directory = True
  else:
    update_directory = True

  if update_directory:
    os.mkdir(assignment_directory)
    timestamp_fi = os.path.join(assignment_directory, 'TIMESTAMP')
    with open(timestamp_fi, 'w') as fh:
      fh.write(msg_date.strftime(DATETIME_STRING_FORMAT))

  return assignment_directory, update_directory


def save_email(imap_payload_dict):
  attachment = get_attachment(imap_payload_dict)
  if attachment is None:
    print 'Nothing to save:'
    print 'From:', imap_payload_dict[FROM_FIELD],
    print 'Subject:', imap_payload_dict[SUBJECT_FIELD]
    return

  msg_date, filename, payload_bytes = attachment
  [(filename, _)] = email.header.decode_header(filename)
  parsed = parse_filename(filename)
  if parsed is None:
    return

  student_id, assignment, zip_type = parsed
  directory, new_directory = create_folder(student_id, assignment, msg_date)
  if not new_directory:
    print 'Directory %r already has newer content.' % (directory,)
    return

  full_path = os.path.join(directory, filename)
  with open(full_path, 'w') as fh:
    fh.write(payload_bytes)

  try:
    if zip_type == 'zip':
      subprocess.check_call(['unzip', full_path,
                             '-d', os.path.dirname(full_path)])
    elif zip_type == 'tar':
      subprocess.check_call(['tar', '-xvf', full_path,
                             '--directory', os.path.dirname(full_path)])
    elif zip_type == 'tar.gz':
      subprocess.check_call(['tar', '-zxvf', full_path,
                             '--directory', os.path.dirname(full_path)])
    else:
      raise ValueError('Unexpected zip type: %s' % (zip_type,))
  except subprocess.CalledProcessError as err:
    print 'An error has occurred:', err.returncode
    print 'From:', ' '.join(err.cmd)
    proceed = raw_input('Would you like to proceed? [y/N] ')
    if proceed.lower() != 'y':
      # Re-raise the error.
      raise


def make_data_dir():
  if os.path.exists(STUDENTS_DIR):
    if not os.path.isdir(STUDENTS_DIR):
      raise OSError('File %s should be a directory.' %
                    (STUDENTS_DIR,))
  else:
    os.mkdir(STUDENTS_DIR)


def get_email_content(last_uid=None):
  server = login_to_server(account_settings.USERNAME,
                           account_settings.PASSWORD)
  server.select_folder(account_settings.FOLDER_NAME, readonly=True)
  print 'Getting message IDs (IDs local to folder).'
  if last_uid is None:
    folder_msg_ids = server.search()
  else:
    criteria = '%d:*' % ((last_uid + 1),)
    folder_msg_ids = server.search(criteria=criteria)
    # In the case that `last_uid` is the max, this will return [last_uid],
    # when we actually want [].
    folder_msg_ids = [msg_id for msg_id in folder_msg_ids
                      if msg_id > last_uid]
  print 'Retrieved %d message IDs.' % len(folder_msg_ids)

  if folder_msg_ids:
    # NOTE: This could be problematic if there are too many messages.
    folder_msg_contents = server.fetch(folder_msg_ids, FETCH_FIELDS)
    print 'Retrieved full emails from server.'
  else:
    folder_msg_contents = {}

  return server, folder_msg_contents


def determine_work_checkpoint():
  if os.path.exists(CHECKPOINT_FILE):
    with open(CHECKPOINT_FILE, 'r') as fh:
      return int(fh.read())


def set_work_checkpoint(last_uid):
  # NOTE: This assumes the label will be unchanged server side.
  #       If the account owner deletes messages, then the labels
  #       may change.
  with open(CHECKPOINT_FILE, 'w') as fh:
    fh.write('%d' % (last_uid,))


def main():
  make_data_dir()

  last_uid = determine_work_checkpoint()

  server, folder_msg_contents = get_email_content(last_uid=last_uid)

  for imap_payload_dict in folder_msg_contents.itervalues():
    save_email(imap_payload_dict)
    print SEPARATOR

  if folder_msg_contents:
    set_work_checkpoint(max(folder_msg_contents.keys()))

  server.logout()


if __name__ == '__main__':
  # H/T: http://stackoverflow.com/a/9093598/1068170
  if hasattr(__builtin__, '__IPYTHON__'):
    print 'In IPYTHON, not running main().'
  else:
    main()
