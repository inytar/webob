"""
Does parsing of ETag-related headers: If-None-Matches, If-Matches

Also If-Range parsing
"""

from webob.datetime_utils import *
from webob.util import header_docstring, warn_deprecation

__all__ = ['AnyETag', 'NoETag', 'ETagMatcher', 'IfRange', 'etag_property']


def etag_property(key, default, rfc_section):
    doc = header_docstring(key, rfc_section)
    doc += "  Converts it as a Etag."
    def fget(req):
        value = req.environ.get(key)
        if not value:
            return default
        elif value == '*':
            return AnyETag
        else:
            return ETagMatcher.parse(value)
    def fset(req, val):
        if val is None:
            req.environ[key] = None
        else:
            req.environ[key] = str(val)
    def fdel(req):
        del req.environ[key]
    return property(fget, fset, fdel, doc=doc)

def _warn_weak_match_deprecated():
    warn_deprecation("weak_match is deprecated", '1.2', 3)


class _AnyETag(object):
    """
    Represents an ETag of *, or a missing ETag when matching is 'safe'
    """

    def __repr__(self):
        return '<ETag *>'

    def __nonzero__(self):
        return False

    def __contains__(self, other):
        return True

    def weak_match(self, other):
        _warn_weak_match_deprecated()

    def __str__(self):
        return '*'

AnyETag = _AnyETag()

class _NoETag(object):
    """
    Represents a missing ETag when matching is unsafe
    """

    def __repr__(self):
        return '<No ETag>'

    def __nonzero__(self):
        return False

    def __contains__(self, other):
        return False

    def weak_match(self, other):
        _warn_weak_match_deprecated()

    def __str__(self):
        return ''

NoETag = _NoETag()

class ETagMatcher(object):
    """
    Represents an ETag request.  Supports containment to see if an
    ETag matches.  You can also use
    ``etag_matcher.weak_contains(etag)`` to allow weak ETags to match
    (allowable for conditional GET requests, but not ranges or other
    methods).
    """

    def __init__(self, etags, weak_etags=()):
        self.etags = etags
        self.weak_etags = weak_etags

    def __contains__(self, other):
        return other in self.etags or other in self.weak_etags

    def weak_match(self, other):
        _warn_weak_match_deprecated()

    def __repr__(self):
        return '<ETag %s>' % (
            ' or '.join(self.etags))

    @classmethod
    def parse(cls, value):
        """
        Parse this from a header value
        """
        results = []
        weak_results = []
        while value:
            if value.lower().startswith('w/'):
                # Next item is weak
                weak = True
                value = value[2:]
            else:
                weak = False
            if value.startswith('"'):
                try:
                    etag, rest = value[1:].split('"', 1)
                except ValueError:
                    etag = value.strip(' ",')
                    rest = ''
                else:
                    rest = rest.strip(', ')
            else:
                if ',' in value:
                    etag, rest = value.split(',', 1)
                    rest = rest.strip()
                else:
                    etag = value
                    rest = ''
            if etag == '*':
                return AnyETag
            if etag:
                if weak:
                    weak_results.append(etag)
                else:
                    results.append(etag)
            value = rest
        return cls(results, weak_results)

    def __str__(self):
        items = map('"%s"'.__mod__, self.etags)
        for weak in self.weak_etags:
            items.append('W/"%s"' % weak)
        return ', '.join(items)


class IfRange(object):
    def __init__(self, etag):
        self.etag = etag

    @classmethod
    def parse(cls, value):
        """
        Parse this from a header value.
        """
        if not value:
            return cls(AnyETag)
        elif value.endswith(' GMT'):
            # Must be a date
            return IfRangeDate(parse_date(value))
        else:
            return cls(ETagMatcher.parse(value))

    def match(self, etag=None, last_modified=None):
        """
        Return True if the If-Range header matches the given etag or last_modified
        """
        #TODO: deprecate
        return etag in self.etag

    def match_response(self, response):
        """
        Return True if this matches the given ``webob.Response`` instance.
        """
        return self.match(etag=response.etag)

    def __nonzero__(self):
        return bool(self.etag)

    def __repr__(self):
        return '%s(%r)' % (
            self.__class__.__name__,
            self.etag
        )

    def __str__(self):
        return str(self.etag) if self.etag else ''



class IfRangeDate(object):
    def __init__(self, date):
        self.date = date

    def match(self, etag=None, last_modified=None):
        #TODO: deprecate
        if isinstance(last_modified, str):
            last_modified = parse_date(last_modified)
        return last_modified and (last_modified <= self.date)

    def match_response(self, response):
        return self.match(last_modified=response.last_modified)

    def __repr__(self):
        return '%s(%r)' % (
            self.__class__.__name__,
            self.date
            #serialize_date(self.date)
        )

    def __str__(self):
        return serialize_date(self.date)

