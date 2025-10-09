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
