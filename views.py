
# Create your views here.

from django.views.generic.simple import direct_to_template
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.core.urlresolvers import reverse
from django.conf import settings
from django.contrib.sites.models import Site
from django.db.models import get_model
from django.core.exceptions import ImproperlyConfigured

from subscriptions.models import Episode
from djson.http import JSONResponse
from djson.decorators import login_required
from __init__ import flix
from models import NetflixProfile
from decorators import netflix_account_required
# this should be kept generic
try:
    UserProfile = get_model(*settings.AUTH_PROFILE_MODULE.split('.'))
    if UserProfile is None:
        raise ImproperlyConfigured("Your AUTH_PROFILE_MODULE setting doesn't point to a valid model")
    elif not issubclass(UserProfile, NetflixProfile):
        raise ImproperlyConfigured("Your UserProfile class should inherit from %s" % NetflixProfile)
except AttributeError:
    raise ImproperlyConfigured("You must set AUTH_PROFILE_MODULE in your settings.py")

import urllib

@login_required
def login(request):
    next = request.GET.get('next', '')
    return direct_to_template(request, template="flix/login.html", extra_context={'next': next})

@login_required
def ask(request):
    next = request.GET.get('next', '')
    return direct_to_template(request, template="flix/ask.html", extra_context={'next': next})

@login_required
def auth(request):
    "/auth/"
    callback = "http://%s%s" % (Site.objects.get_current().domain, reverse('netflix_oauth_return'))

    try:
        next = request.GET['next']
    except KeyError:
        pass
    else:
        callback += '?%s' % urllib.urlencode({'next': next})

    auth_url, token = flix.get_authorization_url(
        callback=callback,
        )
    request.session['unauthed_token'] = token
    return HttpResponseRedirect(auth_url)

def return_(request, next=None):
    try:
        token = request.session['unauthed_token']
    except KeyError:
        return HttpResponse("No un-authed token")
    if not token.key == request.GET.get('oauth_token', None):
        return HttpResponse("Something went wrong! Tokens do not match")
    user_id, access_token = flix.authorize(token)
    try:
        profile = request.user.get_profile()
    except UserProfile.DoesNotExist:
        profile = UserProfile.objects.create(user=request.user)

    profile.netflix_authorize(user_id, access_token)

    next = request.GET.get('next', next) or getattr(settings, 'NETFLIX_AFTER_OAUTH_URL', '/')
    return HttpResponseRedirect(next)

@netflix_account_required
def deauthorize(request, blocked=None):
    next = request.GET.get('next') or request.POST.get("next")
    if request.method == "POST":
        request.user.get_profile().netflix_deauthorize()
        url = reverse('netflix_oauth_login')
        if next:
            url += '?%s' % next
        return HttpResponseRedirect(reverse('netflix_oauth_login'))
    else:
        return direct_to_template(request, "flix/deauthorize.html", {"blocked": blocked,
                                                                     "next": next, })


# this should be removed!
@netflix_account_required
def flix_test(request):
    import pprint
    profile = request.user.get_profile()
    recommendations = profile._netflix_request('http://api.netflix.com/users/%s/recommendations' % profile.netflix_id)
    return HttpResponse('<html><body><pre>' + pprint.pformat(recommendations, 2) + '</pre></body></html>')



@netflix_account_required
def show_queue(request, queue='disc'):
    the_queue = request.user.get_profile().netflix_queue(queue=queue)
    return direct_to_template(request, 'flix/queue.html', {'queue': the_queue,
                                                           'type':queue})

@netflix_account_required
def add_to_queue(request, id=None, queue='disc'):
    # this should be done in a post
    episode = get_object_or_404(Episode, pk=id)
    request.user.get_profile().netflix_add_to_queue(episode)
    if request.method == 'GET':
        return HttpResponseRedirect(reverse('subscriptions'))
    else:
        if request.is_ajax():
            return JSONResponse(True)
        else:
            return HttpResponseRedirect(episode.subscription.get_absolute_url())

