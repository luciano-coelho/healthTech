from django.db import models


class RemittanceHeader(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    repasse_numero = models.CharField(max_length=64, blank=True)
    terceiro_nome = models.CharField(max_length=256, blank=True)
    competencia = models.CharField(max_length=32, blank=True)
    cnpj = models.CharField(max_length=32, blank=True)
    previsao_pagamento = models.CharField(max_length=32, blank=True)

    profissional_nome = models.CharField(max_length=256, blank=True)
    especialidade = models.CharField(max_length=128, blank=True)

    original_file = models.FileField(upload_to='remittances/', blank=True, null=True)

    def __str__(self) -> str:
        return f"REPASSE {self.repasse_numero} - {self.competencia} - {self.profissional_nome}"


class RemittanceItem(models.Model):
    header = models.ForeignKey(RemittanceHeader, on_delete=models.CASCADE, related_name='items')

    atendimento = models.CharField(max_length=64, blank=True)
    conta = models.CharField(max_length=64, blank=True)
    paciente = models.CharField(max_length=256, blank=True)
    convenio = models.CharField(max_length=128, blank=True)
    categoria = models.CharField(max_length=64, blank=True)
    data = models.CharField(max_length=32, blank=True)
    codigo = models.CharField(max_length=64, blank=True)
    procedimento = models.CharField(max_length=512, blank=True)
    funcao = models.CharField(max_length=128, blank=True)
    quantidade = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    valor_produzido = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    imposto = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    valor_liquido = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    def __str__(self) -> str:
        return f"{self.data} {self.paciente} {self.codigo} {self.procedimento}"


# -------------------- Price catalog for reconciliation --------------------
class PriceCatalog(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    name = models.CharField(max_length=128)
    version = models.CharField(max_length=64, blank=True)
    competencia = models.CharField(max_length=32, blank=True)
    source_file = models.CharField(max_length=256, blank=True)
    notes = models.TextField(blank=True)

    def __str__(self) -> str:
        ver = f" - {self.version}" if self.version else ""
        comp = f" ({self.competencia})" if self.competencia else ""
        return f"{self.name}{ver}{comp}"


class ProcedurePrice(models.Model):
    catalog = models.ForeignKey(PriceCatalog, on_delete=models.CASCADE, related_name='prices')
    # Código normalizado (somente dígitos), e o texto original para referência
    codigo = models.CharField(max_length=32, db_index=True)
    codigo_original = models.CharField(max_length=64, blank=True)
    descricao = models.CharField(max_length=512, blank=True)

    convenio = models.CharField(max_length=128, blank=True)
    hospital_cnpj = models.CharField(max_length=32, blank=True, help_text="CNPJ normalizado (somente dígitos)")
    hospital_nome = models.CharField(max_length=256, blank=True)
    categoria = models.CharField(max_length=64, blank=True)
    funcao = models.CharField(max_length=128, blank=True)

    preco_referencia = models.DecimalField(max_digits=12, decimal_places=2)
    vigencia_inicio = models.DateField(null=True, blank=True)
    vigencia_fim = models.DateField(null=True, blank=True)
    ativo = models.BooleanField(default=True)

    metadata = models.JSONField(blank=True, null=True)

    class Meta:
        indexes = [
            models.Index(fields=["codigo", "convenio", "hospital_cnpj", "categoria"]),
            models.Index(fields=["catalog", "codigo", "convenio", "hospital_cnpj", "categoria"]),
        ]
        unique_together = (
            ("catalog", "codigo", "convenio", "hospital_cnpj", "categoria", "vigencia_inicio", "vigencia_fim"),
        )

    def __str__(self) -> str:
        conv = f"/{self.convenio}" if self.convenio else ""
        hosp = f" @{self.hospital_cnpj}" if self.hospital_cnpj else ""
        cat = f" [{self.categoria}]" if self.categoria else ""
        return f"{self.codigo}{conv}{cat}{hosp} - {self.descricao[:50]}"
