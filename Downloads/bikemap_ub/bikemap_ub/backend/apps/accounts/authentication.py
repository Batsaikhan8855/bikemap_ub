from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError


class CookieJWTAuthentication(JWTAuthentication):
    """
    Reads JWT from httpOnly cookie 'bm_access' first, then falls back to the
    standard Authorization: Bearer header (so curl / Postman / tests still work).
    Addresses the localStorage XSS vulnerability noted in the security audit.
    """

    def authenticate(self, request):
        cookie_token = request.COOKIES.get("bm_access")
        if cookie_token:
            try:
                validated = self.get_validated_token(cookie_token)
                return self.get_user(validated), validated
            except (InvalidToken, TokenError):
                pass  # Cookie expired or invalid — fall through to header
        return super().authenticate(request)
