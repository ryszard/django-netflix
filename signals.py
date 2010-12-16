import django.dispatch

netflix_account_authorized = django.dispatch.Signal()
netflix_account_deauthorized = django.dispatch.Signal()
