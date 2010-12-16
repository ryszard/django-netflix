from django.db import models
from django.conf import settings
from oauth.oauth import OAuthToken
from signals import netflix_account_authorized, netflix_account_deauthorized
import netflix
# Create your models here.

from __init__ import flix

import logging

log = logging.getLogger("setjam.flix.models")

NETFLIX_QUEUE_CACHE_SECONDS = getattr(settings, 'NETFLIX_QUEUE_CACHE_SECONDS', 3)

class OAuthTokenField(models.Field):
    """Model field to store OAuth tokens.

    """
    __metaclass__ = models.SubfieldBase

    def __init__(self, *a, **kw):
        kw['max_length'] = 400
        super(OAuthTokenField, self).__init__(*a, **kw)

    def to_python(self, value):
        if value is None or isinstance(value, OAuthToken):
            return value
        return OAuthToken.from_string(value)

    def get_internal_type(self):
        return 'CharField'

    def get_db_prep_value(self, value):
        if value is None:
            return value
        return value.to_string()


class NetflixProfile(models.Model):
    """Abstract base class to store information about the user's
    Netflix account.

    """
    netflix_access_token = OAuthTokenField(editable=False, null=True, blank=True)
    netflix_id = models.CharField(max_length=300, null=True, blank=True)
    netflix_preferred_format = models.CharField(editable=False, max_length=20, null=True, blank=True)

    class Meta:
        abstract = True

    def _netflix_request(self, url, raises=False, **kw):
        if self.netflix_is_authorized:
            try:
                return flix.request(url, self.netflix_access_token, **kw)
            except netflix.AuthError:
                self.netflix_deauthorize()
                if raises:
                    raise
                return None


    @property
    def netflix_is_authorized(self):
        return self.netflix_access_token and self.netflix_id

    def netflix_authorize(self, netflix_id, token):
        self.netflix_id = netflix_id
        self.netflix_access_token = token
        netflix_account_authorized.send(sender=self)
        self.save()

    def netflix_deauthorize(self):
        """Remove the access token and save afterwards."""
        self.netflix_access_token = self.netflix_id = self.netflix_preferred_format = None
        netflix_account_deauthorized.send(sender=self)
        self.save()

    def netflix_queue(self, queue='disc'):
        """queue should be either "disc" or "instant".

        """
        return self._netflix_request('/users/%s/queues/%s' % (self.netflix_id, queue),
                                     raises=True,
                                     max_results=500, 
                                     cache_seconds=NETFLIX_QUEUE_CACHE_SECONDS)

    def netflix_add_to_queue(self, episode):
        q = self.netflix_queue()
        log.debug(q.etag)

        try:
            self._netflix_request('/users/%s/queues/disc' % self.netflix_id,
                                  verb="POST",
                                  title_ref=episode.netflix_disc_id,
                                  etag=q.etag,)
        except netflix.TitleAlreadyInQueue:
            pass
        log.debug("Adding %s to queue" % episode)

    def netflix_at_home(self):
        return self._netflix_request('/users/%s/at_home' % self.netflix_id)


def netflix_populate(sender, **kwargs):
    """Populate the profile with initial data taken from Netflix
    through the API.
    """
    nu = sender._netflix_request("/users/" + sender.netflix_id)
    try:
        sender.netflix_preferred_format = nu.preferred_formats[0].label
    except IndexError:
        pass

netflix_account_authorized.connect(netflix_populate)



