from django.urls import path
from . import views

app_name = "reviews"
urlpatterns = [
    path("<int:call_id>/", views.review_form, name="form"),
]
