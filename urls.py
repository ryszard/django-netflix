from django.conf.urls.defaults import * # pyflakes:ignore
from views import login, auth, return_, flix_test, show_queue, deauthorize, add_to_queue, ask

urlpatterns = patterns(
    '',
    url(r'^$',
        login,
        name="netflix_oauth_login"),
    url(r'^ask/$',
        view=ask,
        name='netflix_ask'),
    url(r'^auth/$',
        view=auth,
        name='netflix_oauth_auth'),
    url(r'^return/?$',
        view=return_,
        name='netflix_oauth_return'),
    url(r'^deauthorize/?$',
        view=deauthorize,
        name="netflix_deauthorize"),
    url(r'^blocked/?$',
        deauthorize,
        {'blocked': True},
        name="netflix_blocked_account"),
    url(r'^queue/(?P<queue>instant|disc)/?$',
        show_queue,
        name='netflix_show_queue'),
    url(r'^queue/add/(?P<id>\d+)/?$',
        add_to_queue,
        name='netflix_add_to_queue'),
    # this should be removed
    url(r'^test/?$',
        view=flix_test),
    )
