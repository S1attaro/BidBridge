from django import forms

from .models import SavedContract


class SavedContractForm(forms.ModelForm):
    class Meta:
        model = SavedContract
        fields = ["status", "note"]
        labels = {"status": "Where are you with this job?", "note": "Your notes"}
        help_texts = {"note": "Only you can see this. Up to 1,000 letters."}
        widgets = {"note": forms.Textarea(attrs={"rows": 4, "placeholder": "Example: Call about the site visit"})}
