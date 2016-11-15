# Quickmail

Package for creating and sending multipart emails in python 2.7.

### Features
 - Send plain text emails
 - Send HTML emails
 - Add attachments
 - Inline all rules of referenced stylesheets
 - Embed images and backgrounds

### Dependencies
For HTML and stylesheet processing:
 - tinycss
 - pyquery

### Example: Send a plain text email

```python
from quickmail import Mail, Connection

mail = Mail(fr='sender@foo.com',
            to='recipient@foo.com',
            subject='Hello',
            text='This is a plain text email',
            attachments=['path/to/file.zip'])

with Connection('smtp.foo.com', 'user', 'pass') as conn:
    conn.send(mail)
```

Or use the shorthand

```python
with Connection('smtp.foo.com', 'user', 'pass') as conn:
    conn.send(fr='sender@foo.com',
              to='recipient@foo.com',
              subject='Hello',
              text='This is a plain text email'))
```


### Example: Send an HTML email

This example has 4 files:

 - email/email.html
 - email/styles.css
 - email/logo.png
 - email/send_mail.py

```html
<!-- email.html -->
<html>
    <head>
        <link rel="stylesheet" href="email.css">
    </head>
    </body>
        <div class="logo">
            <img src="logo.png">
        </div>

        <div class="section">
            <h2>I am header</h2>
            <p>Lorem ipsum dolor sit amet, consectetur adipisicing elit</p>
        </div>
    </body>
</html>
```
```css
/* styles.css */
.logo {
    border: 1px solid #999;
}
p {
  margin: 20px 0;
}
```

```python
# send_mail.py

from quickmail import Mail, Connection

with file('email/email.html') as f:
    html = f.read()

# Create a new HTMLDoument
doc = HTMLDocument(html,
               # Prepend to relative paths
               base_url='https://www.acme.com/',
               pub_dir=os.path.dirname(__file__))


# Optionally inline styles and embed images and backgrounds
doc.embed_images()
doc.embed_backgrounds()
doc.inline_styles()
# >>> doc.html
# '<html>.......<div style="border: 1px solid #999;"><img src="cid:logo.png".......'
# >>> doc.images
# {'logo.png': 'path/to/logo.png'}

# Send it
with Connection('smtp.foo.com', 'user', 'pass') as conn:
    conn.send(fr='sender@foo.com',
              to='recipient@foo.com',
              subject='Hello',
              text='Plain text version',
              html=doc.html,
              images=doc.images))

```




### Todo

- Add tests
- Python 3 support
- More documentation
