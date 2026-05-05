from rest_framework import generics, status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django.conf import settings
from .models import User
from .serializers import RegisterSerializer, UserProfileSerializer
from .permissions import IsCyclistOrAbove

# Cookie config
_SECURE = not getattr(settings, "DEBUG", True)
_ACCESS_MAX_AGE  = int(getattr(settings, "SIMPLE_JWT", {}).get("ACCESS_TOKEN_LIFETIME",
                       __import__("datetime").timedelta(hours=1)).total_seconds())
_REFRESH_MAX_AGE = int(getattr(settings, "SIMPLE_JWT", {}).get("REFRESH_TOKEN_LIFETIME",
                        __import__("datetime").timedelta(days=7)).total_seconds())


def _set_auth_cookies(response, refresh):
    """Set httpOnly JWT cookies on the response."""
    response.set_cookie(
        "bm_access", str(refresh.access_token),
        max_age=_ACCESS_MAX_AGE, httponly=True,
        samesite="Strict", secure=_SECURE,
    )
    response.set_cookie(
        "bm_refresh", str(refresh),
        max_age=_REFRESH_MAX_AGE, httponly=True,
        samesite="Strict", secure=_SECURE,
    )


def _clear_auth_cookies(response):
    response.delete_cookie("bm_access")
    response.delete_cookie("bm_refresh")


class RegisterView(generics.CreateAPIView):
    """POST /api/auth/register/  — US-070"""
    queryset           = User.objects.all()
    serializer_class   = RegisterSerializer
    permission_classes = [permissions.AllowAny]
    throttle_classes   = [ScopedRateThrottle]
    throttle_scope     = "login"

    def create(self, request, *args, **kwargs):
        s = self.get_serializer(data=request.data)
        s.is_valid(raise_exception=True)
        user    = s.save()
        refresh = RefreshToken.for_user(user)
        response = Response(
            {"user": UserProfileSerializer(user).data,
             # Keep tokens in body for backward-compat API clients
             "refresh": str(refresh),
             "access":  str(refresh.access_token)},
            status=status.HTTP_201_CREATED,
        )
        _set_auth_cookies(response, refresh)
        return response


class LoginView(APIView):
    """POST /api/auth/login/  — US-070  (throttled — NFR01)"""
    permission_classes = [permissions.AllowAny]
    throttle_classes   = [ScopedRateThrottle]
    throttle_scope     = "login"

    def post(self, request):
        email    = request.data.get("email")
        password = request.data.get("password")
        user     = authenticate(request, username=email, password=password)
        if not user:
            return Response({"error": "Invalid credentials"},
                            status=status.HTTP_401_UNAUTHORIZED)
        if user.is_banned:
            return Response({"error": "Account is banned"},
                            status=status.HTTP_403_FORBIDDEN)
        refresh = RefreshToken.for_user(user)
        response = Response({
            "user":    UserProfileSerializer(user).data,
            "refresh": str(refresh),
            "access":  str(refresh.access_token),
        })
        _set_auth_cookies(response, refresh)
        return response


class CookieTokenRefreshView(APIView):
    """POST /api/auth/refresh/ — reads bm_refresh cookie, sets new bm_access cookie."""
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        refresh_token = (request.COOKIES.get("bm_refresh")
                         or request.data.get("refresh"))
        if not refresh_token:
            return Response({"error": "No refresh token"},
                            status=status.HTTP_401_UNAUTHORIZED)
        try:
            refresh = RefreshToken(refresh_token)
            access  = str(refresh.access_token)
        except Exception:
            return Response({"error": "Invalid or expired refresh token"},
                            status=status.HTTP_401_UNAUTHORIZED)

        response = Response({"access": access})
        response.set_cookie(
            "bm_access", access,
            max_age=_ACCESS_MAX_AGE, httponly=True,
            samesite="Strict", secure=_SECURE,
        )
        return response


class LogoutView(APIView):
    """POST /api/auth/logout/"""
    permission_classes = [IsCyclistOrAbove]

    def post(self, request):
        refresh_token = (request.COOKIES.get("bm_refresh")
                         or request.data.get("refresh"))
        if refresh_token:
            try:
                RefreshToken(refresh_token).blacklist()
            except Exception:
                pass
        response = Response({"message": "Logged out."})
        _clear_auth_cookies(response)
        return response


class ProfileView(generics.RetrieveUpdateAPIView):
    """GET/PATCH /api/auth/profile/  — E7 US-060"""
    serializer_class   = UserProfileSerializer
    permission_classes = [IsCyclistOrAbove]

    def get_object(self):
        return self.request.user


# ── Password Reset (basic email-based) ───────────────────────────────────────
import secrets
from django.core.mail import send_mail
from django.utils import timezone
from datetime import timedelta
from .models import PasswordResetToken
from apps.audit_log.models import AuditLog


class PasswordResetRequestView(APIView):
    """
    POST /api/auth/password-reset/
    Body: { "email": "..." }
    Always returns 200 (даалгавар: enumeration хамгаалалт).
    """
    permission_classes = [permissions.AllowAny]
    throttle_classes   = [ScopedRateThrottle]
    throttle_scope     = "login"

    def post(self, request):
        email = (request.data.get("email") or "").strip().lower()
        if email:
            user = User.objects.filter(email__iexact=email).first()
            if user:
                token = secrets.token_urlsafe(32)
                PasswordResetToken.objects.create(
                    user=user, token=token,
                    expires_at=timezone.now() + timedelta(minutes=30),
                )
                AuditLog.log(actor=user, action="password_reset",
                             target_type="User", target_id=user.id,
                             request=request)
                # Production-д send_mail() жинхэнэ имэйл явуулна
                reset_link = f"{request.scheme}://{request.get_host()}/reset/{token}/"
                try:
                    send_mail(
                        subject="BikeMap UB — Password reset",
                        message=f"Та доорх линкээр нууц үгээ сэргээнэ үү:\n{reset_link}\n\nХугацаа: 30 минут.",
                        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@bikemap.mn"),
                        recipient_list=[email],
                        fail_silently=True,
                    )
                except Exception:
                    pass
        return Response({"message": "If the email exists, a reset link has been sent."})


class PasswordResetConfirmView(APIView):
    """POST /api/auth/password-reset/confirm/  Body: { token, new_password }"""
    permission_classes = [permissions.AllowAny]
    throttle_classes   = [ScopedRateThrottle]
    throttle_scope     = "login"

    def post(self, request):
        token = request.data.get("token", "")
        pwd   = request.data.get("new_password", "")
        if len(pwd) < 6:
            return Response({"error": "Password must be at least 6 characters"},
                            status=status.HTTP_400_BAD_REQUEST)
        prt = PasswordResetToken.objects.filter(token=token, used=False).first()
        if not prt or prt.expires_at < timezone.now():
            return Response({"error": "Invalid or expired token"},
                            status=status.HTTP_400_BAD_REQUEST)
        prt.user.set_password(pwd)
        prt.user.save(update_fields=["password"])
        prt.used = True
        prt.save(update_fields=["used"])
        return Response({"message": "Password reset successful"})
