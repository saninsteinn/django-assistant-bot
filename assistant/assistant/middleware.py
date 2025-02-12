from django.conf import settings


class MediaURLMiddleware:
    """Middleware to include host in MEDIA_URL dynamically."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not settings.MEDIA_URL.startswith('http'):
            host = request.get_host()
            scheme = 'https' if request.is_secure() else 'http'
            settings.MEDIA_URL = f"{scheme}://{host}{settings.MEDIA_URL}"
        response = self.get_response(request)
        return response
