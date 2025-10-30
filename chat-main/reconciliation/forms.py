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


class AdvancedSearchForm(forms.Form):
    """Formulário para pesquisa avançada de demonstrativos."""
    
    # Filtros de RemittanceHeader
    profissional = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Nome do profissional'
        }),
        label='Profissional'
    )
    
    especialidade = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Especialidade médica'
        }),
        label='Especialidade'
    )
    
    competencia = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ex: 2024-01'
        }),
        label='Competência'
    )
    
    terceiro = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Nome do terceiro'
        }),
        label='Terceiro'
    )
    
    cnpj = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'CNPJ (com ou sem formatação)'
        }),
        label='CNPJ'
    )
    
    repasse_numero = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Número do repasse'
        }),
        label='Número do Repasse'
    )
    
    # Filtros de RemittanceItem
    convenio = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Nome do convênio'
        }),
        label='Convênio'
    )
    
    categoria = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Categoria do procedimento'
        }),
        label='Categoria'
    )
    
    procedimento = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Nome do procedimento'
        }),
        label='Procedimento'
    )
    
    # Filtros de valor
    valor_min = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ex: 100,00'
        }),
        label='Valor Mínimo'
    )
    
    valor_max = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ex: 5000,00'
        }),
        label='Valor Máximo'
    )
    
    # Filtros de data (preparados para uso futuro)
    data_inicio = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        }),
        label='Data Início'
    )
    
    data_fim = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        }),
        label='Data Fim'
    )
    
    def clean_valor_min(self):
        """Converte formato brasileiro para Decimal."""
        value = self.cleaned_data.get('valor_min', '').strip()
        if not value:
            return None
        
        # Remove pontos e substitui vírgula por ponto
        value = value.replace('.', '').replace(',', '.')
        
        try:
            return Decimal(value)
        except (ValueError, InvalidOperation):
            raise forms.ValidationError("Formato inválido. Use: 100,00")
    
    def clean_valor_max(self):
        """Converte formato brasileiro para Decimal."""
        value = self.cleaned_data.get('valor_max', '').strip()
        if not value:
            return None
        
        # Remove pontos e substitui vírgula por ponto
        value = value.replace('.', '').replace(',', '.')
        
        try:
            return Decimal(value)
        except (ValueError, InvalidOperation):
            raise forms.ValidationError("Formato inválido. Use: 100,00")
    
    def clean_cnpj(self):
        """Normaliza CNPJ removendo formatação."""
        value = self.cleaned_data.get('cnpj', '').strip()
        if value:
            # Remove tudo que não é dígito
            return ''.join(ch for ch in value if ch.isdigit())
        return value
