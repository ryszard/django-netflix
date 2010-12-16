from django import template
import logging

log = logging.getLogger("setjam.flix.management.templatetags.netflix")

register = template.Library()

def get_title_attr(episode, user, attr):
    try:
        return getattr(user.get_profile().netflix_at_home().get_title(episode.netflix_id), attr)
    except AttributeError:
        return ''

@register.filter
def netflix_estimated_arrival_date(episode, user):
    return get_title_attr(episode, user, 'estimated_arrival_date')

@register.filter
def netflix_shipped_date(episode, user):
    return get_title_attr(episode, user, 'shipped_date')

