import os
from django.conf import settings
from rest_framework import serializers
from .models import POI, POIVote
from apps.accounts.serializers import PublicUserSerializer


class POISerializer(serializers.ModelSerializer):
    user      = PublicUserSerializer(read_only=True)
    user_vote = serializers.SerializerMethodField()

    class Meta:
        model  = POI
        fields = ("id", "user", "latitude", "longitude", "poi_type",
                  "description", "image", "status", "upvotes", "downvotes",
                  "user_vote", "reject_reason", "created_at", "updated_at")
        read_only_fields = ("id", "user", "status", "upvotes", "downvotes",
                            "user_vote", "reject_reason", "created_at", "updated_at")

    def get_user_vote(self, obj):
        req = self.context.get("request")
        if req and req.user.is_authenticated:
            v = POIVote.objects.filter(poi=obj, user=req.user).first()
            return v.vote_type if v else None
        return None

    # ── US-023: image upload server-side validation ──────────────────────────
    def validate_image(self, image):
        """
        Серверт зураг шалгах:
          1. Хэмжээ ≤ 5 MB
          2. MIME type ∈ {image/jpeg, image/png}
          3. Өргөтгөл ∈ {.jpg, .jpeg, .png}
          4. Pillow-аар жинхэнэ зураг эсэхийг шалгах
        """
        if image is None:
            return image

        # 1. Size
        max_size = getattr(settings, "FILE_UPLOAD_MAX_MEMORY_SIZE", 5 * 1024 * 1024)
        if image.size > max_size:
            raise serializers.ValidationError(
                f"Image too large ({image.size} bytes). Max {max_size // 1024 // 1024} MB."
            )

        # 2. MIME type
        allowed_mime = getattr(settings, "ALLOWED_IMAGE_MIME",
                               ("image/jpeg", "image/png", "image/jpg"))
        if getattr(image, "content_type", None) not in allowed_mime:
            raise serializers.ValidationError(
                f"Invalid image type ({image.content_type}). "
                f"Allowed: {', '.join(allowed_mime)}"
            )

        # 3. Extension
        allowed_ext = getattr(settings, "ALLOWED_IMAGE_EXT",
                              (".jpg", ".jpeg", ".png"))
        ext = os.path.splitext(image.name)[1].lower()
        if ext not in allowed_ext:
            raise serializers.ValidationError(
                f"Invalid file extension ({ext}). Allowed: {', '.join(allowed_ext)}"
            )

        # 4. Pillow verify — magic byte шалгалт
        try:
            from PIL import Image
            img = Image.open(image)
            img.verify()
            image.seek(0)  # Pointer-ыг буцааж тавих
        except Exception:
            raise serializers.ValidationError(
                "File is not a valid image (corrupted or fake extension)."
            )

        return image

    def create(self, validated_data):
        validated_data["user"] = self.context["request"].user
        return super().create(validated_data)