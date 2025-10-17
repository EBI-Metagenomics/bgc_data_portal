from django import forms
from .models import Point


class PointForm(forms.ModelForm):
    class Meta:
        model = Point
        fields = ["x_coord", "y_coord", "name"]
