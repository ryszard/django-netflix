try:
    from functools import wraps
except ImportError:
    from django.utils.functional import wraps  # pyflakes:ignore Python 2.3, 2.4 fallback.
import urllib
import logging
import netflix

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from djson.decorators import login_required
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.db.models import get_model

from models import NetflixProfile
from exceptions import NetflixAccountRequired, NetflixAccountBlocked

log = logging.getLogger("setjam.flix.decorators")

def netflix_account_required(fun):
    """Decorator allowing only authenticated Netflix users to access
    the view.

    """

    try:
        UserProfile = get_model(*settings.AUTH_PROFILE_MODULE.split('.'))
        if UserProfile is None:
            raise ImproperlyConfigured("Your AUTH_PROFILE_MODULE setting doesn't point to a valid model")
        elif not issubclass(UserProfile, NetflixProfile):
            raise ImproperlyConfigured("Your UserProfile class should inherit from %s" % NetflixProfile)
    except AttributeError:
        raise ImproperlyConfigured("You must set AUTH_PROFILE_MODULE in your settings.py")

    @login_required
    @wraps(fun)
    def wrapper(request, *a, **kw):
        try:
            profile = request.user.get_profile()
        except UserProfile.DoesNotExist:
            pass
        else:
            if profile.netflix_is_authorized:
                log.debug(profile.netflix_id)
                try:
                    return fun(request, *a, **kw)
                except netflix.AuthError:
                    if request.is_ajax():
                        raise NetflixAccountBlocked(request)
                    url = "%s?%s" % (reverse('netflix_blocked_account'), urllib.urlencode({'next': request.path}))
                    return HttpResponseRedirect(url)
        if request.is_ajax():
            raise NetflixAccountRequired(request)
        url = "%s?%s" % (reverse('netflix_oauth_login'), urllib.urlencode({'next': request.path}))
        return HttpResponseRedirect(url)

    return wrapper
