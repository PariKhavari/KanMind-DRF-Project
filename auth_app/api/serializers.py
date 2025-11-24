from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers


class RegistrationSerializer(serializers.ModelSerializer):

    fullname = serializers.CharField(write_only=True, required=True)
    password = serializers.CharField(write_only=True, required=True)
    repeated_password = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = User
        # Achtung: username kommt NICHT im Request vor, wir erzeugen ihn aus der E-Mail
        fields = ["id", "fullname", "email", "password", "repeated_password"]

    def validate(self, attrs):
        # Passwörter identisch?
        if attrs["password"] != attrs["repeated_password"]:
            raise serializers.ValidationError({"password": "Passwörter stimmen nicht überein."})

        # Passwortregeln prüfen (Länge, Komplexität etc.)
        validate_password(attrs["password"])

        # E-Mail muss eindeutig sein
        email = attrs.get("email")
        if not email:
            raise serializers.ValidationError({"email": "E-Mail-Adresse ist erforderlich."})
        if User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError({"email": "Ein Benutzer mit dieser E-Mail existiert bereits."})

        return attrs

    def create(self, validated_data):
        fullname = validated_data.pop("fullname").strip()
        password = validated_data.pop("password")
        validated_data.pop("repeated_password", None)

        email = validated_data.get("email", "").strip()

        # username z.B. aus E-Mail ableiten
        base_username = email.split("@")[0] if email else "user"
        username = base_username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1

        first_name = ""
        last_name = ""
        if fullname:
            parts = fullname.split(" ", 1)
            first_name = parts[0]
            if len(parts) > 1:
                last_name = parts[1]

        user = User(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
        )
        user.set_password(password)
        user.save()
        return user


class LoginSerializer(serializers.Serializer):

    email = serializers.EmailField(required=True)
    password = serializers.CharField(write_only=True, required=True)

class EmailCheckSerializer(serializers.Serializer):

    email = serializers.EmailField(required=True)