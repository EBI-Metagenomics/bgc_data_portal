from django import forms

class MGYCSearchForm(forms.Form):
    mgyc_value = forms.CharField(label="Enter MGYC value", required=True)