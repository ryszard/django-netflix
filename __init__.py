"""
    >>> flix.request('/catalog/titles/', term="$9.99")
    [<CatalogTitle u'$9.99', u'http://api.netflix.com/catalog/titles/movies/70108543'>]


"""
import logging
import time
import itertools
from os import path

from netflix import Netflix, TooManyRequestsPerDayError

from django.core.exceptions import ImproperlyConfigured
from django.core.cache import cache
from django.core.cache.backends.filebased import CacheClass
from django.conf import settings

# Netflix configuration
try:
    (NETFLIX_API_KEY,
     NETFLIX_API_SECRET,
     NETFLIX_APPLICATION_NAME) = (settings.NETFLIX_API_KEY,
                                  settings.NETFLIX_API_SECRET,
                                  settings.NETFLIX_APPLICATION_NAME)
except AttributeError:
    raise ImproperlyConfigured("You must set NETFLIX_API_KEY and NETFLIX_API_SECRET and NETFLIX_APPLICATION_NAME in your settings!")

NETFLIX_CACHE_SECONDS = getattr(settings, 'NETFLIX_CACHE_SECONDS', 3)

class CachedNetflix(Netflix):
    """A Netflix instance that makes use of Django's cache system."""
    log = logging.getLogger('setjam.flix.netflix')
    cache = cache

    def get_request_token(self):
        self.log.debug('get_request_token')
        try:
            rv = super(CachedNetflix, self).get_request_token()
        except:
            self.log.exception('get_request_token raised exception')
            raise
        else:
            self.log.debug('get_request_token => %r' % rv)
            return rv

    def get_authorization_url(self, callback=None):
        self.log.debug('get_authorization_url %r' % callback)
        try:
            rv = super(CachedNetflix, self).get_authorization_url(callback)
        except Exception, e:
            self.log.exception('get_authorization_url raised exception %r' % e)
            raise
        self.log.debug('get_authorization_url => %r' % (rv,))
        return rv

    def authorize(self, token):
        self.log.debug('authorize %s' % token)
        try:
            rv = super(CachedNetflix, self).authorize(token)
        except:
            self.log.exception('authorize raised exception')
            raise
        self.log.debug('authorize => %r, %r' % rv)
        return rv

    def request(self,
                url,
                token=None,
                verb='GET',
                use_cache=True,
                cache_seconds=None,
                **kw):
        """Make a request to Netflix (through Django's cache). Takes
        all the argumens the non-cached version takes, and the
        following additinal arguments:

          * use_cache (default: True) - if this is a false value, do
            NOT use Django's cache.

          * cache_seconds (default: None) - how long should the cache
            remain valid. If you do not set this parameter, the
            NETFLIX_CACHE_SECONDS will be used.

        """
        self.log.debug("netflix_request key: %s use_cache: %s, cache_seconds %s, verb: %s, url: %s",
                       self.consumer.key[:10],
                       use_cache,
                       cache_seconds,
                       verb,
                       url)
        if verb.upper() == 'GET' and use_cache:
            cache_seconds = cache_seconds or NETFLIX_CACHE_SECONDS
            key = '%s.request %r %r' % (type(self).__name__, (url, token, verb), kw)
            old = self.cache.get(key)
            if old:
                self.log.debug('found in cache')
                new = old
            else:
                new = super(CachedNetflix, self).request(url, token=token, verb=verb, **kw)
                self.cache.set(key, new, cache_seconds)
                self.log.debug('added to cache')
        else:
            new = super(CachedNetflix, self).request(url, token=token, verb=verb, **kw)
        return new

class SimpleFileBasedCache(CacheClass):
    """Cache backend which always uses the default timeout, doesn't
    care about the number of files in the cache and uses human
    readable filenames.

    """
    def _key_to_file(self, key):
        key = '__'.join(v.replace(' ', '_').replace('/', '+') for v in key.split('_'))
        return path.join(self._dir, key)

    def _cull(self, *args, **kwargs):
        pass

    def set(self, key, value, timeout=None):
        super(SimpleFileBasedCache, self).set(key, value, None)


class RanOutOfKeysError(Exception):
    pass

class KeyFailoverNetflix(CachedNetflix):
    """A proxy that switches to another netflix key when necessary.

    It does not implement the full Netflix interface, just the parts
    used by other parts of setjam.
    """

    log = logging.getLogger('setjam.flix.netflix.KeyFailoverNetflix')

    TOO_MANY_REQUESTS_PER_DAY_DELAY = 2
    MAX_CALLS_PER_KEY = None

    def __init__(self, netflix_auth_data):
        """Initializer.

        `netflix_auth_data` must be a list of 3-element tuples:
        [(key_0, secret_0, app_name_0),
         (key_1, secret_1, app_name_1),
         ...]
        
        """
        self.netflix_auth_data = netflix_auth_data
        self.auth_generator = itertools.cycle(self.netflix_auth_data)
        self._flix = None
        self.call_counter = 0

    def request(self, *args, **kwargs):
        return self.call('request', args, kwargs)

    def get_authorization_url(self, *args, **kwargs):
        return self.call('get_authorization_url', args, kwargs)

    def authorize(self, *args, **kwargs):
        return self.call('authorize', args, kwargs)

    ## plumbing

    def get_flix(self):
        if not self._flix:
            (key, secret, app_name) = self.next_auth_tuple()
            self.log.info('Using key %s, secret %s...%s, app %s'
                           % (key, secret[:5], secret[-5:], app_name))
            self._flix = CachedNetflix(key=key, secret=secret,
                                       application_name=app_name)
        return self._flix

    def force_flix_replacement(self):
        self._flix = None

    def call(self, method_name, args, kwargs):
        # no point in looping over the keys more than once
        for i in xrange(0, len(self.netflix_auth_data)):
            the_flix = self.get_flix()
            # TODO: handle TooManyRequestsPerSecond as well
            try:
                self.call_counter += 1
                if ((self.MAX_CALLS_PER_KEY is not None)
                    and (self.call_counter > self.MAX_CALLS_PER_KEY)):
                    # mainly for testing
                    self.call_counter = 0
                    raise TooManyRequestsPerDayError()

                method = getattr(the_flix, method_name)
                return method(*args, **kwargs)
            except TooManyRequestsPerDayError:
                self.force_flix_replacement()
                time.sleep(self.TOO_MANY_REQUESTS_PER_DAY_DELAY)

        # All the keys are used up, time to give up.
        raise RanOutOfKeysError

    def next_auth_tuple(self):
        """Iterates over all the keys, in loop.
        """
        return self.auth_generator.next()

netflix_auth_data = ([(NETFLIX_API_KEY, NETFLIX_API_SECRET, NETFLIX_APPLICATION_NAME)]
                     + getattr(settings, 'NETFLIX_FALLBACK_AUTH_DATA', []))

#real_flix = KeyFailoverNetflix(netflix_auth_data)
real_flix = Netflix(key=NETFLIX_API_KEY, secret=NETFLIX_API_SECRET, application_name=NETFLIX_APPLICATION_NAME)
flix = real_flix

if settings.TESTING:
    class FileBasedCachedNetflix(CachedNetflix):
        """Netflix with a file-based cache with an extremely long timeout
        (3 months).

        """
        cache = SimpleFileBasedCache(
            path.join(settings.PROJECT_ROOT, '..', 'var', 'test-data', 'netflix_cache'),
            dict(timeout=60 * 60 * 24 * 30 * 3)
            )
    test_flix = FileBasedCachedNetflix(key=NETFLIX_API_KEY, secret=NETFLIX_API_SECRET, application_name=NETFLIX_APPLICATION_NAME)
