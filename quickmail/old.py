
"""
Misc old code, seems to be some work started for collecting bounced messages. Etc.
"""




    
    # Note: genuine vacaition messages rarely* detect any email in subject or body
    #       However the From is most likely the recipient's email
    
    # Note: From-header might look like: FROM "Lager, Mats" <Mats.Lager@kpmg.se>.
    #       Hence always use the regex
    
    # *) If they do, it could be errorous mentioning a colleague's email
    
    
    # Crap, "postmaster" could be used as From in vacation messages. However in 99% it is a bounce.
    # Using three-bounces-in-a-row-before-mark-as-spam ensures these are not accidentally marked as bounces.
    # Further more, by making it possible for admin to manually go though 3-time bounced emails, the 
    # chanses for an accidentally bounced-marked recipient are minimal.
    
    
    
    # FROM: postmaster
    # FROM: bounces
    # FROM: MAILER-DAEMON















from datetime import datetime
import re

email_RE = re.compile(r"[^ \t\n\r@<>()]+\@[a-z0-9][a-z0-9\.\-_]*\.[a-z]+", re.I)

def get_bounced():
    
    # TODO:
    # Store processed emails in database, running get_bounced
    # retrieves all mails with a date later than the last entry
    # in the processed-emails table.
    #datetime.strptime('2008-01-05 14:01:50', '%Y-%m-%d %H:%M:%S')
    
    # 1. Connect to imap
    import imaplib
    import email
    import time
    import elementtree
    conn = imaplib.IMAP4(host='mail.impentab.se')
    conn.login('nyhetsbrev@impentab.se', '123456')
    conn.select('INBOX')
    resp, result = conn.search(None, 'ALL')
    message_ids = result[0].split() # space-separated list of imap message id's
    


    for i, msg_id in enumerate(message_ids):
        # resp is 'OK' even if msg_id does not exist, msg becomes [None]
        # if found, msg[0] = [0]="3 (RFC822 {28864}"
        #                    [1]=<the complete raw message>
        #           msg[1] = ?
        #           msg[2] = ?
        resp, msg = conn.fetch(msg_id, '(RFC822)')
        if not msg[0]:
            continue
            
        msg = email.message_from_string(msg[0][1]) # safe, index msg[0] always exist
        recieved_at = email.utils.parsedate(msg['Date']) # returns 9-tuple
        if recieved_at:
            recieved_at = time.mktime(recieved_at)
        else:
            log.debug('Cannot read or parse Date header of mail #%s' % msg_id)
        

            
        # if i == 8:
        #     # ----------- debug --------------
        #     from IPython.Shell import IPShellEmbed
        #     ipshell = IPShellEmbed(['-pdb', '-pi1', 'In <\#>: ', '-pi2', '   .\D.: ', '-po', 'Out<\#>: ', '-nosep'])
        #     ipshell.IP.exit_now = False
        #     ipshell('Debug')
        #     # ----------- /debug -------------
        #     break;


        
        
        is_bounce = False
        
        def get_email(s): 
            """ Returns the first email encountered in given string "s" """
            email = email_RE.findall(s or '') 
            if email:
                return email[0].lower() # findall always return a list
            return None
            
        
        def get_error_body(msg):
            """ Return the body of msg containg the error message """    
            if msg.is_multipart(): 
                # in multipart bounces, only the first payload (part) is interesting
                # since it contains the error report. In single-part bounces, the
                # error message is prepended to the one and only message part.

                # Note: finding the original message is unpredictable, can be deeply
                # nested, eg: 
                # msg.get_payload()[2].get_payload()[0].get_payload()[0].get_payload()
                error_msg = msg.get_payload()[0].get_payload() or ''
            else:
                error_msg = msg.get_payload() or ''
                
            if not isinstance(error_msg, basestring):
                return ''
            else:
                return error_msg
            


                
                        
        
        # A bunch of tests
        def test_1(msg):
            # Consider existance of "X-Failed-Recipients" header a bounce
            f = msg.get('X-Failed-Recipients', '')
            email = get_email(f) 
            if email:
                return True, email
            else:
                return False, False                
        
        def test_2(msg):
            # Consider email address in subject a bounce
            subject = msg.get('Subject', '')
            email = get_email(subject) 
            if email:  
                return True, email
            else:
                return False, False
        
        def test_3(msg):
            s = msg.get('Subject').lower()
            bounce = s.find('undelivered mail returned to sender') <> -1
            email = get_email(get_error_body(msg))
            return bounce, email
            
        
        def test_4(msg):
            s = msg.get('Subject').lower()
            bounce = s.find('delivery status notification') <> -1
            email = get_email(get_error_body(msg))
            return bounce, email            

        def test_5(msg):
            s = msg.get('Subject').lower()
            bounce = s.find('undeliverable mail:') <> -1
            email = get_email(get_error_body(msg))
            return bounce, email            
            
        def test_6(msg):
            s = msg.get('Subject').lower()
            bounce = s.find('returned mail:') <> -1
            email = get_email(get_error_body(msg))
            return bounce, email            
        
        def test_7(msg):
            s = msg.get('Subject').lower()
            bounce = s.find('failure notice') <> -1
            email = get_email(get_error_body(msg))
            return bounce, email                    
        
        tests = [func for name, func in locals().iteritems() if name[:5] == 'test_']
        
        # Try and grab the faild address:
        for test in tests:
            is_bounce, email_address = test(msg)
            if is_bounce:
                break;
        
        uncertain_email = False
        if not is_bounce:
            # From is most likely the correct orignial recipient
            # If From should be mailer-daemon or postmaster, grab
            # first email in body, and raise uncertain_email flag.
            email_address = get_email(msg.get('From'))
            
            # In some rare occations email_address is None, hence "not email_address" below
            if not email_address or \
               'mailer-daemon' in email_address or \
               'postmaster' in email_address:
                email_address = get_email(get_error_body(msg))
                uncertain_email = True
        
        
        print msg_id, email_address
        yield msg_id, email_address, msg.get('Subject'), is_bounce, uncertain_email, get_error_body(msg)[:300]
        
        # if not is_bounce:
        #     print "======================== VACATION ============================="
        #     print "SUBJECT %s." % msg['Subject']
        #     # print "FROM %s." % msg['From']
        #     if email_address:
        #         print 'DETECTED EMAIL %s:' % email_address
        #         print "UNCERTAIN? %s" % ('YES' if uncertain_email else 'NO')                 
        #         print ""
        #         print get_error_body(msg)[:300]                
        #     else:
        #         print 'FAILED EMAIL DETECTION'
        #     print "-------------------------------------------------------------"
        
        # tpl = (
        #     msg_id, 
        #     time.strftime('%Y-%M-%d %H:%M:%S'), 
        #     failed,
        #     'Vacation? (%s)' % msg['Subject'] if maybe_vacation else 'Bounced',
        #     # error_msg[:300],
        # )
        # log.debug('#%s, %s, %s, %s' % tpl)
        
        
        
    # end for
    conn.close()



import elementtree.ElementTree as ET
# import sqlalchemy as SA
# import sqlalchemy.orm as ORM


class Recipient(object):
    pass


def add_to_imp_bounced():
    e = SA.create_engine('mysql://root@localhost/impentab_rec')
    Session = ORM.sessionmaker(bind=e, transactional=True, autoflush=True)
    #Session.configure(bind=e)
    ScopedSession = ORM.scoped_session(Session)
    sess = ScopedSession()
    
    m = SA.MetaData(e)
    m.reflect()
    t = m.tables['imp_recipients2']
    bounced = m.tables['imp_bounced']

    
    ScopedSession.mapper(Recipient, t)

     
    visited = []
    for i, (id, email, subject, is_bounced, uncertain, msg) in enumerate(get_bounced()):
        
        if email in visited:
            continue
        
        if uncertain:
            continue
        
        visited.append(email)
        
        # # check if email already exist in imp_bounced
        # if bounced.select(bounced.c.email == email).execute().fetchone():
        #     continue
        # 
        # bounced.insert({'email': email}).execute()
        # print "Inserted %s" % email
        
        # res = t.select(t.c.email == email).execute()
        # if res.rowcount > 0:
        #     for row in res:
        #         row.status = 3

        
        for rec in Recipient.query.filter_by(email=email):
            if rec.status <> 3:
                rec.status = 3
                # why can't I commit all updates in one go??
                # only the last rec occurrs in sess.dirty
                sess.commit()
                
        


def get_bounced_spreadsheetML():
    
    # read all norwegian recipients
    
    e = SA.create_engine('mysql://root@localhost/impentab_rec')
    m = SA.MetaData(e)
    m.reflect()
    t = m.tables['imp_recipients']
    s = t.select(t.c.category == 8).execute()
    norwegian_emails = []
    for i, row in enumerate(s):
        norwegian_emails.append(row['email'])
    
    
    
    
    
    # build a tree structure
    workbook = ET.Element('ss:Workbook')
    workbook.attrib['xmlns:ss'] = 'urn:schemas-microsoft-com:office:spreadsheet'
    worksheet = ET.SubElement(workbook, 'ss:Worksheet', {'ss:Name': 'Bounced'})
    table = ET.SubElement(worksheet, 'ss:Table')
    
    def add_cell(row, value, format='String'):
        cell = ET.SubElement(row, 'ss:Cell')
        data = ET.SubElement(cell, 'ss:Data', {'ss:Type': format})
        data.text = value
        return cell
    
    # Add headers
    row = ET.SubElement(table, 'ss:Row')
    add_cell(row, 'Msg Id')
    add_cell(row, 'Email')
    add_cell(row, 'Subject')
    add_cell(row, 'Uncertain')
    add_cell(row, 'Message')
    
    visited = []
    for id, email, subject, is_bounced, uncertain, msg in get_bounced():
        
        if not is_bounced or (email in visited) or (email in norwegian_emails):
            continue
        
        visited.append(email)
        
        row = ET.SubElement(table, 'ss:Row')
        
        add_cell(row, str(id))
        add_cell(row, email)
        add_cell(row, subject)
        add_cell(row, 'Yes' if uncertain else '')
        add_cell(row, msg)
        
        
    # wrap it in an ElementTree instance, and save as XML
    tree = ET.ElementTree(workbook)
    tree.write("/Users/kalle/acmsite/workbook.xls")
    return 'ok'
    #return '<?xml verison="1.0" encoding="UTF-8" ?>\n' + ET.tostring(workbook, encoding='UTF-8')
    
    
    

