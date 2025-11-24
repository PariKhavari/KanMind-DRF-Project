from django.urls import path
from .views import RegistrationView, LoginView, EmailCheckView

urlpatterns = [
    path("registration/", RegistrationView.as_view(), name="api-registration"),
    path("login/", LoginView.as_view(), name="api-login"),
    path("email-check/", EmailCheckView.as_view(), name="api-email-check"),
]
