from django import forms


class RemittanceUploadForm(forms.Form):
    pdf = forms.FileField(label='Demonstrativo do Hospital/Plano (PDF)')
