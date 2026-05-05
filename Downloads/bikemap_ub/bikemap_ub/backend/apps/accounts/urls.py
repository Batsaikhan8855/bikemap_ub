from django.urls import path
from .views import (
    RegisterView, LoginView, LogoutView, CookieTokenRefreshView, ProfileView,
    PasswordResetRequestView, PasswordResetConfirmView,
)

urlpatterns = [
    path("register/",                RegisterView.as_view(),             name="auth-register"),
    path("login/",                   LoginView.as_view(),                name="auth-login"),
    path("logout/",                  LogoutView.as_view(),               name="auth-logout"),
    path("refresh/",                 CookieTokenRefreshView.as_view(),   name="auth-refresh"),
    path("profile/",                 ProfileView.as_view(),              name="auth-profile"),
    path("password-reset/",          PasswordResetRequestView.as_view(), name="auth-password-reset"),
    path("password-reset/confirm/",  PasswordResetConfirmView.as_view(), name="auth-password-reset-confirm"),
]