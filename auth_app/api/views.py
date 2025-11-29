from django.contrib.auth.models import User
from django.contrib.auth import authenticate

from rest_framework import permissions, status
from rest_framework.authtoken.models import Token
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import RegistrationSerializer, LoginSerializer, EmailCheckSerializer

def _get_fullname(user: User) -> str:
    name = (user.first_name + " " + user.last_name).strip()
    return name or user.username


class RegistrationView(APIView):
    """
    Handle user registration.
    Endpoint:
    - POST /api/registration/
    Creates a new user and returns auth token and basic user data.
    """

    permission_classes = [permissions.AllowAny]

    def post(self, request, format=None):
        serializer = RegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.save()
        token, _ = Token.objects.get_or_create(user=user)

        data = {
            "token": token.key,
            "fullname": _get_fullname(user),
            "email": user.email,
            "user_id": user.id,
        }
        return Response(data, status=status.HTTP_201_CREATED)

class LoginView(APIView):
    """
    Handle user login with email and password.
    Endpoint:
    - POST /api/login/
    Authenticates the user and returns token and basic user data.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request, format=None):
        """
        Validate login credentials, authenticate user and return token payload.
        """
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"]
        password = serializer.validated_data["password"]

        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            return Response(
                {"detail": "Ungültige E-Mail oder Passwort."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not user.check_password(password):
            return Response(
                {"detail": "Ungültige E-Mail oder Passwort."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        token, _ = Token.objects.get_or_create(user=user)

        data = {
            "token": token.key,
            "fullname": _get_fullname(user),
            "email": user.email,
            "user_id": user.id,
        }
        return Response(data, status=status.HTTP_200_OK)
    
class EmailCheckView(APIView):
    """
    Check if a given email address exists and return basic user data.
    Endpoint:
    - GET /api/email-check/?email=...
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, format=None):
        """
        Validate the email query parameter and return user info if found.
        """
        serializer = EmailCheckSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"]

        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            return Response(
                {"detail": "E-Mail nicht gefunden."},
                status=status.HTTP_404_NOT_FOUND,
            )

        data = {
            "id": user.id,
            "email": user.email,
            "fullname": _get_fullname(user),
        }
        return Response(data, status=status.HTTP_200_OK)



