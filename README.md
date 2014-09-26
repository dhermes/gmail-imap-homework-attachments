Python IMAP Homework Downloader
===============================

For programming assignments in a class I am teach (Fall 2014) I am requesting
students email me the assignments at `<main>+<course>@berkeley.edu` where
`<main>@berkeley.edu` is my typical Berkeley Gmail account and `<course>` is
the course number used as a [Gmail alias][1].

I'm able to set up a [Gmail filter][2] for these emails and so can script
my inbox with the Python `imapclient` library.

The `account_settings.py.example` file has the needed variables to be defined:
- `USERNAME` - your email address (obvious)
- `PASSWORD` - should be an [ASP][3] if you use [2FA][4], which you should
- `FOLDER_NAME` - the label you use for assignments (added by the filter)

In order to run the code, copy `account_settings.py.example` to
`account_settings.py` and then edit the variables to match the actual
data needed.

What does it do?
==================

I told my students to submit with `<student id>_hw<assignment>.zip` as their
filename. I loosened up and also said they could use `tar` or `tar.gz`
compression.

To honor this, the script does the following:
- Loop through every email in the `FOLDER_NAME` label and check
  for an attachment
- For an email with an attachment, check if the name matches the above
- If the name matches, create the appropriate folder, i.e.
  `$GIT_ROOT/<student_id>/<assignment>/`
- Store the bytes of the zip in the student-assignment folder (newly
  created)
- Unzip the attachment using one of the three compression types

The `students/` folder is in `.gitignore` so that data will only be
local. This is also true of the `account_settings.py` file, so that
you don't accidentally commit a password to a `git` repo.

Some Nice Checks
==================

- For consecutive runs (i.e. throughout a semester) the script stores
  a simple `students/CHECKPOINT` file noting the IMAP `uid` of the
  most recent message retrieved. On subsequent runs, only newer message
  IDs are downloaded.
- If a student submits twice, there is a `TIMESTAMP` file in the folder
  which can determine which submission is the latest.
- (Coming Soon) I will add a way to determine if an assignment is past
  due by comparing the time stamp on the email and locally stored
  timestamp representing the due date.
- If one of the unzips fails with a non-0 status code, the script prompts
  the end user on whether it should fail or keep going. This allows
  a note of the failure to be taken (go check later) without wiping away
  the other progress.
- If one of the filenames can't be parsed, the same prompting process
  occurs.

[1]: https://support.google.com/mail/answer/12096?hl=en
[2]: https://support.google.com/mail/answer/6579?hl=en
[3]: https://support.google.com/accounts/answer/185833?hl=en
[4]: https://www.google.com/landing/2step/
