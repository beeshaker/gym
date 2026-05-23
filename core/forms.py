from django import forms


class PinForm(forms.Form):
    pin = forms.CharField(
        max_length=20,
        widget=forms.HiddenInput(),
        required=False,
    )
