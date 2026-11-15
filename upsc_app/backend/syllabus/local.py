"""Single-user local mode: there is no login, one learner, always resolved."""

from functools import wraps

from django.conf import settings
from django.contrib.auth import get_user_model

from .models import LearnerAccount


def local_learner(request=None):
    """Return the one learner for this app, creating it if absent."""
    User = get_user_model()
    username = getattr(settings, "LOCAL_LEARNER_USERNAME", "user")
    user, _ = User.objects.get_or_create(
        username=username,
        defaults={"is_active": True},
    )
    learner, _ = LearnerAccount.objects.get_or_create(
        user=user,
        defaults={"display_name": user.username},
    )
    return learner


def local_learner_required(view_func):
    """Attach the local learner to the request. Never redirects."""

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        request.learner = local_learner(request)
        return view_func(request, *args, **kwargs)

    return wrapper
