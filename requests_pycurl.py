#!/usr/bin/env python
#-*-coding:utf-8 -*-
#
#Author: tony - birdaccp at gmail.com
#Create by:2014-12-10 19:57:14
#Last modified:2015-03-05 15:03:24
#Filename:requests_pycurl.py
#Description:

import re
import cgi
import chardet
import urllib
import pycurl
import cStringIO as StringIO

__all__ = ("get", "post", "Session")

REG_PROXY = re.compile("^(socks5|socks4|http|https)://(.*):(\d+)$")
REG_COOKIE = re.compile("(.*)=([^;]*)")

class Response(object):

    __attrs__ = ["encoding"]

    def __init__(self, url, status_code, headers_output, body_output, cookies=None):
        self._url = url
        self._status = status_code
        self._headers = headers_output
        self._content = body_output
        self._cookies = cookies
        self.encoding = None

    def __repr__(self):
        return '<Response [%s]>' % (self._status)

    @property
    def url(self):
        return self._url

    @property
    def status_code(self):
        return self._status

    @property
    def headers(self):
        return self._headers.getvalue()

    @property
    def _apparent_encoding(self):
        return chardet.detect(self.content)['encoding']

    def _get_encoding_from_headers(self, headers):
        content_type = headers.get('content-type')
        if not content_type:
            return None
        content_type, params = cgi.parse_header(content_type)
        if 'charset' in params:
            return params['charset'].strip("'\"")
        if 'text' in content_type:
            return 'ISO-8859-1'

    def _get_encodings_from_content(self, content):
        charset_re = re.compile(r'<meta.*?charset=["\']*(.+?)["\'>]', flags=re.I)
        pragma_re = re.compile(r'<meta.*?content=["\']*;?charset=(.+?)["\'>]', flags=re.I)
        xml_re = re.compile(r'^<\?xml.*?encoding=["\']*(.+?)["\'>]')

        return (charset_re.findall(content) +
                pragma_re.findall(content) +
                xml_re.findall(content))

    @property
    def text(self):
        encoding = self.encoding
        if not self.content:
            return ''

        # content is unicode
        if isinstance(self.content, unicode):
            return 'unicode'
        # Try charset from content-type
        #encoding = self._get_encoding_from_headers(self.headers)
        #if encoding == 'ISO-8859-1':
        #    encoding = None
        # Try charset from content
        if not encoding and self._get_encodings_from_content:
            encoding = self._get_encodings_from_content(self.content)
            encoding = encoding and encoding[0] or None

        # Fallback to auto-detected encoding.
        if not encoding and chardet is not None:
            encoding = chardet.detect(self.content)['encoding']

        if encoding and encoding.lower() == 'gb2312':
            encoding = 'gb18030'

        self.encoding = encoding or 'utf-8'
        #return self._encoding




        #encoding = self.encoding

        #if not self.content:
        #    return ''

        #if self.encoding is None:
        #    encoding = self._apparent_encoding

        #print '...............encoding...................', self.encoding
        try:
            content = unicode(self.content, self.encoding, errors='replace')
        except :
            content = unicode(self.content, errors='replace')
        return content

    @property
    def content(self):
        return self._content.getvalue()

    @property
    def cookies(self):
        return self._cookies.getvalue()

class Request(object):
    def __init__(self, curl=None):
        self._curl = curl if curl else pycurl.Curl()
        self._body_output = StringIO.StringIO()
        self._headers_output = StringIO.StringIO()

    def setproxy(self, proxy):
        #import pdb;pdb.set_trace()
        matchgroups = REG_PROXY.match(proxy)
        if matchgroups:
            proto, host, port = matchgroups.groups()
            if proto not in ("socks5", "http"):
                return
            if proto =="socks5":
                self._curl.setopt(pycurl.PROXYTYPE, pycurl.PROXYTYPE_SOCKS5)
            self._curl.setopt(pycurl.PROXY, host+":"+port)
            #self._curl.setopt(pycurl.PROXYUSERPWD, "aaa:bbb")

    def setopt(self, method='GET', url=None, headers=None, data=None, proxy=None, timeout=60, allow_redirect=False):
        self._curl.reset()

        method = method.upper()

        if method not in ("GET", "POST"):
            raise pycurl.error("not support method:%s" % method)

        self._curl.setopt(pycurl.NOSIGNAL, True)
        self._curl.setopt(pycurl.URL, str(url))
        self._curl.setopt(pycurl.REFERER, str(url))

        #self._curl.setopt(pycurl.USERAGENT, headers)
        if headers:
            self._curl.setopt(pycurl.HTTPHEADER, map(lambda x:(x[0]+":"+x[1]), headers.iteritems()))

        if method in ("POST"):
            self._curl.setopt(pycurl.POST, True)
            if isinstance(data, str):
                self._curl.setopt(pycurl.POSTFIELDS, data)
            elif hasattr(data, "read"):
                self._curl.setopt(pycurl.UPLOAD, True)
                self._curl.setopt(pycurl.READFUNCTION, data.read)
                data.seek(0, 2)
                filesize = data.tell()
                data.seek(0)
                self._curl.setopt(pycurl.INFILESIZE, filesize)
            elif isinstance(data, dict):
                self._curl.setopt(pycurl.POSTFIELDS, urllib.urlencode(data))

        self._curl.setopt(pycurl.TIMEOUT, timeout)
        self._curl.setopt(pycurl.CONNECTTIMEOUT, timeout)

        self._curl.setopt(pycurl.HEADERFUNCTION, self._headers_output.write)
        self._curl.setopt(pycurl.WRITEFUNCTION, self._body_output.write)

        if proxy:
            self.setproxy(proxy)

        if allow_redirect:
            self._curl.setopt(pycurl.FOLLOWLOCATION, 1)
            self._curl.setopt(pycurl.MAXREDIRS, 5)

    def _method(self, method, url, **kwargs):
        try:
            kwargs.update(dict(url=url, method=method))
            self.setopt(**kwargs)
            self._curl.perform()
            _status_code = self._curl.getinfo(pycurl.HTTP_CODE)
            return Response(url, _status_code, self._headers_output, self._body_output)
        except pycurl.error, error:
            raise Exception(error)
        #finally:
            #self._curl.close()

    def post(self, url, **kwargs):
        assert "data" in kwargs, "post must have data field"
        return self._method("POST", url, **kwargs)

    def get(self, url, **kwargs):
        return self._method("GET", url, **kwargs)

class Session(object):
    def __init__(self):
        self.curl = pycurl.Curl()

    def get(self, url, **kwargs):
        return Request(curl=self.curl).get(url, **kwargs)

    def post(self, url, **kwargs):
        return Request(curl=self.curl).post(url, **kwargs)

    def close(self):
        if self.curl:
            self.curl.close()

def get(url, **kwargs):
    return Request().get(url, **kwargs)

def post(url, **kwargs):
    return Request().post(url, **kwargs)


if __name__ == '__main__':
    import random
    url = "http://demo.throwexcept.com"
    proxys = [
            "http://119.6.144.74:82",
            "http://120.193.146.95:82",
            "http://124.192.60.117:80",
            ]
    #proxy = "http://119.6.144.74:82"

    c = get(url, headers= {"Referer": '',"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/36.0.1750.117"}, proxy=random.choice(proxys))
    #print dir(c)
    print c.url
    #print c.headers
    print c.status_code
    #print c.content.getvalue()
