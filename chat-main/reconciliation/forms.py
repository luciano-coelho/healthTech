from django import forms
from .models import ProcedurePrice


class RemittanceUploadForm(forms.Form):
    pdf = forms.FileField(label='Demonstrativo do Hospital/Plano (PDF)')


class ProcedurePriceForm(forms.ModelForm):
    class Meta:
        model = ProcedurePrice
        fields = [
            'catalog', 'codigo', 'codigo_original', 'descricao', 'convenio',
            'hospital_cnpj', 'hospital_nome', 'categoria', 'funcao',
            'preco_referencia', 'vigencia_inicio', 'vigencia_fim', 'ativo'
        ]

    def clean_codigo(self):
        codigo = self.cleaned_data.get('codigo') or ''
        digits = ''.join(ch for ch in str(codigo) if ch.isdigit())
        return digits or codigo.strip()

    def clean_hospital_cnpj(self):
        cnpj = self.cleaned_data.get('hospital_cnpj') or ''
        return ''.join(ch for ch in str(cnpj) if ch.isdigit())
