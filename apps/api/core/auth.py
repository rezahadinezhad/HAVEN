from rest_framework.authentication import BaseAuthentication


class CookieAuthentication(BaseAuthentication):
    def authenticate(self, request):
        user = request._request.user
        if user.is_authenticated:
            return user, request._request.haven_session
        return None
