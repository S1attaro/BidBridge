import re

from django import forms

from contracts import codes

from .models import ContractorProfile

EXTRA_SET_ASIDES = [(k, v) for k, v in codes.SET_ASIDE_CHOICES if k not in ("small", "none")]


class ProfileForm(forms.ModelForm):
    trades = forms.MultipleChoiceField(
        choices=codes.TRADE_CHOICES, widget=forms.CheckboxSelectMultiple, label="What work do you do?",
        error_messages={"required": "Pick at least one type of work."},
    )
    states = forms.MultipleChoiceField(
        choices=codes.STATE_CHOICES, widget=forms.CheckboxSelectMultiple, label="Where do you work?",
        error_messages={"required": "Pick at least one state."},
    )
    set_asides = forms.MultipleChoiceField(
        choices=EXTRA_SET_ASIDES, required=False, widget=forms.CheckboxSelectMultiple,
        label="Is your business certified?",
    )

    class Meta:
        model = ContractorProfile
        fields = ["trades", "services", "states", "zip_code", "is_small", "set_asides", "business_name",
                  "alerts_on", "alert_email"]
        labels = {
            "business_name": "Business name",
            "services": "Anything else you do? (optional)",
            "zip_code": "ZIP code (optional)",
            "is_small": "Small business",
            "alerts_on": "Email me new jobs that fit",
            "alert_email": "Email",
        }
        widgets = {
            "services": forms.TextInput(attrs={"placeholder": "Example: metal roofs, gutters"}),
            "zip_code": forms.TextInput(attrs={"inputmode": "numeric", "maxlength": 5, "placeholder": "61820"}),
            "business_name": forms.TextInput(attrs={"placeholder": "Optional"}),
            "alert_email": forms.EmailInput(attrs={"placeholder": "you@business.com", "autocomplete": "email"}),
        }

    def clean_zip_code(self):
        zip_code = self.cleaned_data["zip_code"].strip()
        if zip_code and not re.fullmatch(r"\d{5}", zip_code):
            raise forms.ValidationError("A ZIP code is 5 numbers, like 61820.")
        return zip_code

    def clean(self):
        data = super().clean()
        if data.get("alerts_on") and not data.get("alert_email"):
            self.add_error("alert_email", "Add an email so we know where to send new jobs.")
        return data

    def clean_services(self):
        return re.sub(r"\s+", " ", self.cleaned_data["services"]).strip()
