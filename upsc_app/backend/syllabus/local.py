from django.contrib.auth.models import User
from django.conf import settings
from .models import LearnerAccount

LOCAL_LEARNER_USERNAME = getattr(settings, "LOCAL_LEARNER_USERNAME", "user")


def local_learner(request=None):
    """Always returns the single local learner, creates if missing."""
    user, _ = User.objects.get_or_create(
        username=LOCAL_LEARNER_USERNAME,
        defaults={"is_active": True},
    )
    learner, _ = LearnerAccount.objects.get_or_create(
        user=user,
        defaults={"display_name": user.username},
    )
    return learner


def local_learner_required(view_func):
    """Decorator that attaches request.learner without redirect."""
    def wrapper(request, *args, **kwargs):
        request.learner = local_learner(request)
        return view_func(request, *args, **kwargs)
    return wrapper
