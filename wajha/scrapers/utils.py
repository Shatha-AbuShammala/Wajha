def is_admin(user):
    """Return True if the user has admin or superuser privileges."""
    return user.is_authenticated and (user.role == 'admin' or user.is_superuser)


def get_referer(request, fallback='scrapers:list'):
    """Return the HTTP Referer URL, falling back to a named URL string."""
    return request.META.get('HTTP_REFERER', fallback)
