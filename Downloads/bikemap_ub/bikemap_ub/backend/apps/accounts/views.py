from rest_framework import generics, status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from .models import User
from .serializers import RegisterSerializer, UserProfileSerializer
from .permissions import IsCyclistOrAbove


class RegisterView(generics.CreateAPIView):
    """POST /api/auth/register/  — US-070"""
    queryset         = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        s = self.get_serializer(data=request.data)
        s.is_valid(raise_exception=True)
        user    = s.save()
        refresh = RefreshToken.for_user(user)
        return Response({
            "user":    UserProfileSerializer(user).data,
            "refresh": str(refresh),
            "access":  str(refresh.access_token),
        }, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    """POST /api/auth/login/  — US-070"""
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email    = request.data.get("email")
        password = request.data.get("password")
        user     = authenticate(request, username=email, password=password)
        if not user:
            return Response({"error": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED)
        if user.is_banned:
            return Response({"error": "Account is banned"}, status=status.HTTP_403_FORBIDDEN)
        refresh = RefreshToken.for_user(user)
        return Response({
            "user":    UserProfileSerializer(user).data,
            "refresh": str(refresh),
            "access":  str(refresh.access_token),
        })


class LogoutView(APIView):
    """POST /api/auth/logout/"""
    permission_classes = [IsCyclistOrAbove]

    def post(self, request):
        try:
            token = RefreshToken(request.data.get("refresh"))
            token.blacklist()
            return Response({"message": "Logged out."})
        except Exception:
            return Response({"error": "Invalid token"}, status=400)


class ProfileView(generics.RetrieveUpdateAPIView):
    """GET/PATCH /api/auth/profile/  — E7 US-060"""
    serializer_class   = UserProfileSerializer
    permission_classes = [IsCyclistOrAbove]

    def get_object(self):
        return self.request.user