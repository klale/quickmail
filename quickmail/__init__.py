import smtplib
import mimetypes
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from email.mime.base import MIMEBase
from email import Encoders
import logging
import email

from quickmail.error import MailException

log = logging.getLogger(__name__)




# =========
# = Utils =
# =========

def guess_mime_tuple(filename, default='application/octet-stream'):
    mimetype, encoding = mimetypes.guess_type(filename or '')
    return (mimetype or default).split('/')


# ==========
# = Models =
# ==========
class Mail(object):
    """
    Send a simple text and/or html e-mail with optional attachments


    Example
    -------
    mail = Mail(fr='sender@foo.com',
                to='recipient@foo.com',
                subject='Hello',
                text='Hello there, this is a plain text email')

    with Connection('smtp.foo.com', 'user', 'pass') as conn:
        conn.send(mail)

    """


    def __init__(self, fr, to, subject, **kw):
        """
        Init Mail.
        fr = Unicode, email address of sender, /w or w/o name, eg: <John Alb> john@company.com
        to = Unicode or list. Use python list of email addresses for multiple recipients.
        subject = Unicode
        kw[html] = Unicode
        kw[text] = Unicode
        kw[encoding] = String, encoding of message, default is "utf-8"
        kw[returnPath] = Unicode, email address
        kw[attachments] = Files to attach to message. List of filelike, path or 2- or 3 tuples, or
            any combination of these. Examples:
            attachments=['/path/to/file/']
            attachments=[filelike, '/path/to/second_file.jpg']
            attachments=[('attached_file_name.jpg', filelike)]
            attachments=[('attached_file_name.jpg', filelike, 'image/jpeg')]

        kw[images] = List of (id, image) tuples (or the equivalent dict) to embed in the email
                     for use in a html message.
                     Example: [('myphoto', 'path/to/photo.jpg')] <img src="cid:myphoto">
        kw[headers] = Dict of additional headers, eg: {headerName: "headerValue"}

        A Mail instance should have one or more of kw[html] or kw[text] specified.
        """
        self.fr = fr
        self.to = to
        self.subject = subject
        self.html = kw.get('html', None)
        self.text = kw.get('text', None)
        self.encoding = kw.get('encoding', 'utf-8') # encoding of supplied text and/or html
        self.attachments = kw.get('attachments', None)
        self.images = kw.get('images', None)
        self.returnPath = kw.get('returnPath', None)
        self.headers = kw.get('headers', {})

        if isinstance(self.images, dict):
            self.images = self.images.items()

        # encode any given unicodes to self.encoding (python's mail module doesn't do any encoding)
        for a in ['html', 'text']:
            v = getattr(self, a)
            if v:
                setattr(self, a, v.encode(self.encoding, 'xmlcharrefreplace'))


    def isMultipart(self):
        return self.html or self.attachments or self.images


    def build(self):
        # Create the root message
        if self.isMultipart():
            # Todo: support both "related" and "mixed" parts in the same mail.
            # "related" is used to (to some degree) hide the embedded images
            # of a html mail. "mixed" is the classic arbitrary attachement mode
            # normally used by this module
            multipart_type = 'related' if self.images else 'mixed'
            msgRoot = MIMEMultipart(multipart_type)
            msgRoot.preamble = 'This is a multi-part message in MIME format.'


            # Encapsulate the plain and HTML versions of the message body in an
            # 'alternative' part, so message agents can decide which they want to display.
            if self.text and self.html:
                msgBody = MIMEMultipart('alternative')
                msgRoot.attach(msgBody)
            else:
                msgBody = msgRoot


            if self.text:
                msgText = MIMEText(self.text, 'plain', self.encoding)
                msgBody.attach(msgText)

            if self.html:
                msgHtml = MIMEText(self.html, 'html', self.encoding)
                msgBody.attach(msgHtml)


            # Arbitrary attachments of any file type
            if self.attachments:
                for f in self.attachments:
                    mime_type = ''
                    mime_tuple = None
                    if type(f) is tuple:
                        if len(f) == 3:
                            filename, f, mime_type = f
                            mime_tuple = mime_type.split('/')
                        else:
                            filename, f = f
                    else:
                        filename = None

                    if hasattr(f, 'read'):
                        # File-like
                        if not filename:
                            filename = getattr(f, 'filename', None)
                        part = MIMEBase(*(mime_tuple or guess_mime_tuple(filename)))

                        # Ensure pointer is at beginning of file
                        f.seek(0)
                        part.set_payload(f.read())

                    elif isinstance(f, basestring):
                        # File path
                        if not filename:
                            filename = os.path.basename(f)
                        part = MIMEBase(*(mime_tuple or guess_mime_tuple(filename)))
                        with open(f, 'rb') as fp:
                            part.set_payload(fp.read())
                    else:
                        raise MailException('Invalid attachment: %s' % f)

                    if not filename:
                        filename = 'no_file_name'

                    Encoders.encode_base64(part)
                    # Content-Disposition can also be set to inline, then attached files wont show up
                    # in list over attached files, but can be used in mail message, eg embedded images.
                    # See source of an apple mail created with a stationary.
                    part.add_header('Content-Disposition', 'attachment; filename="%s"' % filename)
                    part.add_header('Content-ID', "<%s>" % filename)
                    msgRoot.attach(part)

            # Embedded images for use in html mail
            if self.images:
                for cid, img in self.images:
                    # Create part
                    with open(img, 'rb') as fp:
                        part = MIMEImage(fp.read())

                    # UPDATE: setting inline made the images appear as attachments
                    # Removing the header fixed it.
                    # part.add_header('Content-Disposition', 'inline; filename=%s' % cid)
                    part.add_header('Content-ID', "<%s>" % cid)
                    msgRoot.attach(part)

        else:
            # non-multipart message
            msgRoot = MIMEText(self.text, 'plain', self.encoding)


        # fill in the from, to, and subject headers
        msgRoot['Subject'] = self.subject
        msgRoot['From'] = self.fr
        msgRoot['Date'] = email.utils.formatdate(localtime=True)

        # msgRoot['To'] must be a string
        # see: http://mail.python.org/pipermail/python-list/2006-March/374854.html
        to = ', '.join(self.to) if isinstance(self.to, list) else self.to
        msgRoot['To'] = to

        # add optional return-path (where bounced mail goes)
        if self.returnPath:
            msgRoot.add_header('Return-path', self.returnPath)

        # add any extra headers
        for key, val in self.headers.iteritems():
            msgRoot.add_header(key, val)


        return msgRoot.as_string()



class Connection(object):

    def __init__(self, server, username, password):
        self.server = server
        self.username = username
        self.password = password

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, type, value, traceback):
        self.close()


    def connect(self):
        self.smtp = smtplib.SMTP()
        self.smtp.connect(self.server)
        self.smtp.ehlo()
        try:
            self.smtp.starttls()
        except smtplib.SMTPException:
            # "STARTTLS extension not supported by server"
            pass

        if self.username:
            try:
                self.smtp.login(self.username, self.password)
            except smtplib.SMTPException:
                # this occurres when authenticting an already
                # pop-before-smtp authenticated session
                pass

    def close(self):
        self.smtp.close();


    def send(self, *args, **kw):
        if args and isinstance(args[0], Mail):
            mail = args[0]
        else:
            mail = Mail(*args, **kw)

        # Construct the raw email message
        email_message = mail.build()

        # Send the raw email message to the smtp server
        try:
            self.smtp.sendmail(mail.fr, mail.to, email_message)
        except UnicodeEncodeError:
            # occurres when self.fr or self.to contains illegal characters
            raise MailException('Invalid sender or recipient, unicode error.')
        except smtplib.SMTPRecipientsRefused:
            raise MailException('Invalid recipient')
        except smtplib.SMTPSenderRefused:
            raise MailException('Invalid sender')


# Legacy
QuickMailConnection = Connection

