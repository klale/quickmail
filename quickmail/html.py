import re
import os
from os.path import join
from urlparse import urlparse
from pyquery import PyQuery as q
import tinycss


def ruleset_as_dict(ruleset):
    out = {}
    for decl in ruleset.declarations:
        value = decl.value.as_css() # eg '5px 2px' or 'url(foo.git) no-repeat top right'
        out[decl.name] = value
    return out


class HTMLDocument(object):
    """
    >>> html = '''
    <html>
        <head>
            <link rel="stylesheet" href="/css/email.css">
        </head>
        </body>
            <div class="logo">
                <img src="/img/email/logo.png">
            </div>
        
            <div class="section">
                <h2>I am header</h2>
                <p>Lorem ipsum dolor sit amet, consectetur adipisicing elit</p>
            </div>
        </body>
    </html>'''
    >>> doc = HTMLDocument(html, base_url='http://www.acme.com', pub_dir='/var/www/acme/public')
    >>> doc
    <HTMLDocument>

    >>> doc = Document(html)
    >>> doc.rules
    [RuleSet, RuleSet]
    >>> doc.html
    'same html, nothing changed'
    >>> doc.images
    {}
    
    >>> doc.embed_images()
    >>> doc.html
    'New html <img src="cid:foo.gif">'
    >>> doc.images
    {'foo.gif': 'mysite/public/img/foo.gif'}

    >>> doc.inline_styles()
    >>> doc.html
    'New html again'


    """

    
    def __init__(self, html, base_url, pub_dir=None):
        self._html = html
        self.base_url = base_url
        self.pub_dir = pub_dir
        
        self._rules = []
        self.images = {}
        self.dom = q(html)
        self.css_parser = tinycss.make_parser('page3')
        self.re_url = re.compile(r'url\(([0-9\w_\.\:\/-]+)\)')        
        # self.re_url = re.compile(r'url\((?!http)([0-9\w_\.\/-]+)\)')

    def _full_urls(self, css_text, css_dir):
        """
        Turn "url(../img/logo.png)" into "url(http://www.acme.com/img/logo.png)"
        """
        def repl(matchobj):
            path = matchobj.groups()[0]
            path = os.path.normpath(join(css_dir, path))
            return "url(%s%s)" % (self.base_url, path)
        return self.re_url.sub(repl, css_text)


    @property
    def html(self):
        return '<html>%s</html>' % self.dom.html()
        
    @property
    def rules(self):
        if self._rules:
            return self._rules

        # Collect all css rules from all stylesheets in <head>            
        for link in q(self.html).find('head > link'):
            href = q(link).attr('href')
            # eg "/var/www/acme/public/css"
            css_path = join(self.pub_dir, href.lstrip('/'))
            # eg "/css"
            css_dir = os.path.dirname(href)
            
            # Read the stylesheet file, regex all url(..) and inject 
            # full URL:s everywhere
            with open(css_path) as f:
                css_string = self._full_urls(f.read(), css_dir)
            
            # Pass the monkied stylesheet to the parser
            sheet = self.css_parser.parse_stylesheet_bytes(css_string)
    
            # Collect its rules
            for ruleset in sheet.rules:
                if not isinstance(ruleset, tinycss.css21.RuleSet):
                    continue
                
                # ruleset.selector is a list of all comma separated selectors for this ruleset
                # Join them togeter again as they were written.
                selector = ruleset.selector.as_css()
                css_dir = os.path.dirname(href)
                tup = (
                    selector,
                    ruleset_as_dict(ruleset)
                )
                self._rules.append(tup)
        return self._rules
            
    
    def inline_styles(self):
        """
        Apply stylesheet rules as inline style.

        >>> html = '<p>Foo</p>'
        >>> rules = '''
        >>>     p { 
        >>>         margin: 5px; 
        >>>         background: url(/img/gradient.png);
        >>>     }
        >>> '''
        >>> HTMLDocument(html, base_url='http://acme.org')
        <p style="margin: 5px; background: url(http://www.acme.org/img/gradient.png)">Foo</p>
        """
        # Collect all rules from all stylesheets found in <head>
    
        # Apply all the styles as inline style
        for selector, ruleset_dict in self.rules:
            for el in self.dom.find(selector):
                q(el).css(ruleset_dict)

        # Remove the stylesheets from <head>
        self.dom.find('head > link').remove()

    
    def embed_images(self):
        for el in self.dom.find('img'):
            el = q(el)
            server_path = join(self.pub_dir, el.attr('src').lstrip('/'))
            if os.path.exists(server_path):
                filename = os.path.basename(server_path)
                el.attr('src', 'cid:'+filename)
                self.images[filename] = server_path
    
    
    def embed_backgrounds(self):
        """ Assumes self.inline_html has been run. """
        def repl(matchobj):
            # eg http://www.acme.org/img/foo.gif
            image_url = matchobj.groups()[0]
            image_url = urlparse(image_url)
    
            # eg ming/public/img/foo.gif
            server_path = join(self.pub_dir, image_url.path.lstrip('/'))
    
            if os.path.exists(server_path):
                # Todo: include path in cid as well to support different images with same name
                filename = os.path.basename(image_url.path)  # eg "foo.gif"          
                self.images[filename] = server_path
                return 'url(cid:%s)' % filename
            else:
                # Return untouched if file is missing
                return 'url(%s)' % matchobj.groups()[0]

        
        for el in self.dom.find('*[style*="url"]'):
            el = q(el)
            style = el.attr('style')

            # convert url(http://www.acme.org/img/foo.gif) to url(cid:foo.gif) and
            # add "foo.gif" to self.images
            style = self.re_url.sub(repl, style)
            el.attr('style', style)

            
    