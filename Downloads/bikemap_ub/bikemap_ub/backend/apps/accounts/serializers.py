from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from .models import User


class RegisterSerializer(serializers.ModelSerializer):
    password  = serializers.CharField(write_only=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True, label="Confirm password")

    class Meta:
        model  = User
        fields = ("id", "email", "username", "password", "password2")

    def validate(self, data):
        if data["password"] != data["password2"]:
            raise serializers.ValidationError({"password": "Passwords do not match."})
        return data

    def create(self, validated_data):
        validated_data.pop("password2")
        return User.objects.create_user(**validated_data)


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model  = User
        fields = ("id", "email", "username", "role", "avatar", "bio",
                  "total_distance_km", "total_pois", "total_segments",
                  "is_banned", "created_at")
        read_only_fields = ("id", "email", "role", "total_distance_km",
                            "total_pois", "total_segments", "is_banned", "created_at")


class PublicUserSerializer(serializers.ModelSerializer):
    class Meta:
        model  = User
        fields = ("id", "username", "avatar", "total_distance_km",
                  "total_pois", "total_segments")