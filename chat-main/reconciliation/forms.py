from django import forms
from decimal import Decimal, InvalidOperation
from .models import ProcedurePrice


class RemittanceUploadForm(forms.Form):
    pdf = forms.FileField(label='Demonstrativo do Hospital/Plano (PDF)')


class ProcedurePriceForm(forms.ModelForm):
    # Sobrescrever o campo preco_referencia como CharField para aceitar formato brasileiro
    preco_referencia = forms.CharField(
        label='Preço referência',
        widget=forms.TextInput(attrs={
            'placeholder': '2.403,00',
            'class': 'form-control'
        }),
        help_text='Use vírgula para decimais (ex: 2.403,00)'
    )
    
    class Meta:
        model = ProcedurePrice
        fields = [
            'catalog', 'codigo', 'codigo_original', 'descricao', 'convenio',
            'hospital_cnpj', 'hospital_nome', 'categoria', 'funcao',
            'preco_referencia', 'vigencia_inicio', 'vigencia_fim', 'ativo'
        ]
        widgets = {
            'codigo': forms.TextInput(attrs={'class': 'form-control'}),
            'codigo_original': forms.TextInput(attrs={'class': 'form-control'}),
            'descricao': forms.TextInput(attrs={'class': 'form-control'}),
            'convenio': forms.TextInput(attrs={'class': 'form-control'}),
            'hospital_cnpj': forms.TextInput(attrs={'class': 'form-control'}),
            'hospital_nome': forms.TextInput(attrs={'class': 'form-control'}),
            'categoria': forms.TextInput(attrs={'class': 'form-control'}),
            'funcao': forms.TextInput(attrs={'class': 'form-control'}),
            'catalog': forms.Select(attrs={'class': 'form-select'}),
            'vigencia_inicio': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'vigencia_fim': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'ativo': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Formatar o valor inicial do preço no padrão brasileiro quando estiver editando
        if self.instance and self.instance.pk and self.instance.preco_referencia:
            # Converter Decimal para formato brasileiro (ex: 2403.00 -> "2.403,00")
            valor = self.instance.preco_referencia
            valor_str = f"{valor:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
            self.initial['preco_referencia'] = valor_str

    def clean_codigo(self):
        codigo = self.cleaned_data.get('codigo') or ''
        digits = ''.join(ch for ch in str(codigo) if ch.isdigit())
        return digits or codigo.strip()

    def clean_hospital_cnpj(self):
        cnpj = self.cleaned_data.get('hospital_cnpj') or ''
        return ''.join(ch for ch in str(cnpj) if ch.isdigit())

    def clean_preco_referencia(self):
        """Aceita valores no formato brasileiro (vírgula decimal) e converte para Decimal."""
        preco = self.cleaned_data.get('preco_referencia')
        if not preco:
            raise forms.ValidationError('Este campo é obrigatório.')
        
        # Remove espaços
        preco_str = str(preco).strip()
        if not preco_str:
            raise forms.ValidationError('Este campo é obrigatório.')
            
        # Remove pontos (separadores de milhares) e substitui vírgula por ponto
        # Ex: "2.403,00" -> "2403.00"
        preco_str = preco_str.replace('.', '').replace(',', '.')
        
        try:
            valor_decimal = Decimal(preco_str)
            if valor_decimal < 0:
                raise forms.ValidationError('O preço deve ser positivo.')
            return valor_decimal
        except (InvalidOperation, ValueError):
            raise forms.ValidationError('Formato de preço inválido. Use o formato: 2.403,00 ou 2403.00')
