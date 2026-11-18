from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password


class SignupForm(forms.ModelForm):
    """Just a username and one password. Fewer boxes means more people finish."""

    password = forms.CharField(
        label="Password", strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        help_text="At least 8 letters or numbers.",
    )

    class Meta:
        model = User
        fields = ["username"]
        labels = {"username": "Username"}
        help_texts = {"username": ""}
        widgets = {"username": forms.TextInput(attrs={"autocomplete": "username", "autofocus": True})}

    def clean(self):
        cleaned = super().clean()
        password = cleaned.get("password")
        if password:
            user = User(username=cleaned.get("username", ""))
            try:
                validate_password(password, user)
            except forms.ValidationError as e:
                self.add_error("password", e)
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
        return user
