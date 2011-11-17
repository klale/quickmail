import smtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from email.mime.base import MIMEBase
from email import Encoders
import logging

from quickmail.error import MailException

log = logging.getLogger(__name__)


# =========
# = Utils =
# =========
def embed():
    pass

class readfile(object):
    
    def __init__(self, src):
        """
        src can be a path to a file, or anything filelike 
        implementing .read() and .close()
        """
        self.src = src
        self.fp = None
    
    def __enter__(self):
        if hasattr(self.src, 'read'):
            self.fp = self.src
        else:
            self.fp = open(self.src, 'rb')
        return self.fp
        
    def __exit__(self):
        self.fp.close()


# ==========
# = Models =
# ==========
class Mail(object):
    """
    Send a simple text and/or html e-mail with optional attachments
    """

    @classmethod
    def connect(cls, host, user=None, password=None):
        smtp = smtplib.SMTP()
        smtp.connect(host)
        smtp.ehlo()
        try:
            smtp.starttls()        
        except smtplib.SMTPException, e:
            # "STARTTLS extension not supported by server"
            pass 
            
        if user:
            try: 
                smtp.login(user, password)
            except smtplib.SMTPException, e:
                # this occurres when authenticting an already 
                # pop-before-smtp authenticated session
                pass
        return smtp


    
    @classmethod
    def disconnect(cls, smtpConnection):
        smtpConnection.quit()
    
    
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
        kw[attachments] = List of Bin instances or paths (Strings) to files to attach to message.
        kw[images] = List of (id, image) tuples to embed in the email for use in a html message.
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
        
        # encode any given unicodes to self.encoding (python's mail module doesn't do any encoding)
        for a in ['html', 'text']:
            v = getattr(self, a)
            if v:
                setattr(self, a, v.encode(self.encoding, 'xmlcharrefreplace'))
        

    def isMultipart(self):
        return self.html or self.attachments or self.images



    def send(self, smtpConnection=None):
        
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
                    part = MIMEBase('application', 'octet-stream')
                    # if isinstance(f, Bin):
                    if f.__class__.__name__ == 'Attachment': # Todo: remove ACM related from this module
                        part.set_payload(f.read())
                        fileName = f.filename
                    else:
                        part.set_payload(open(f,'rb').read())
                        fileName = os.path.basename(f)
                    
                    Encoders.encode_base64(part)
                    # Content-Disposition can also be set to inline, then attached files wont show up
                    # in list over attached files, but can be used in mail message, eg embedded images. 
                    # See source of an apple mail created with a stationary.
                    part.add_header('Content-Disposition', 'attachment; filename="%s"' % fileName)
                    part.add_header('Content-ID', "<%s>" % fileName)
                    msgRoot.attach(part)

            # Embedded images for use in html mail                    
            if self.images:
                for cid, img in self.images:
                    # Create part
                    if img.__class__.__name__ == 'Attachment': # Todo: remove ACM related from this module
                        part = MIMEImage(img.read())
                    else:
                        fp = open(img, 'rb')
                        part = MIMEImage(fp.read())
                        fp.close()

                    part.add_header('Content-Disposition', 'inline; filename=%s' % cid)                        
                    part.add_header('Content-ID', "<%s>" % cid)
                    msgRoot.attach(part)
                    
                    

        else:
            # non-multipart message
            msgRoot = MIMEText(self.text, 'plain', self.encoding)
                        

        # fill in the from, to, and subject headers
        msgRoot['Subject'] = self.subject
        msgRoot['From'] = self.fr
        
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

        # Send the email (this example assumes SMTP authentication is required)
        try: 
            if smtpConnection:
                # send through already existing connection
                smtpConnection.sendmail(self.fr, self.to, msgRoot.as_string())
            else:
                smtpConnection = Mail.connect()
                smtpConnection.sendmail(self.fr, self.to, msgRoot.as_string())
                Mail.disconnect(smtpConnection)
        except UnicodeEncodeError, e:
            # occurres when self.fr or self.to containes illegal characters
            raise MailException('Invalid sender or recipient, unicode error.')
        except smtplib.SMTPRecipientsRefused, e:
            raise MailException('Invalid recipient')
        except smtplib.SMTPSenderRefused, e:
            raise MailException('Invalid sender')
        #except smtplib.SMTPServerDisconnected, e:
        #    pass


