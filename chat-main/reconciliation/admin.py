from django.contrib import admin
from .models import PriceCatalog, ProcedurePrice


@admin.register(PriceCatalog)
class PriceCatalogAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "version", "competencia", "created_at")
    search_fields = ("name", "version", "competencia")
    ordering = ("-id",)


@admin.register(ProcedurePrice)
class ProcedurePriceAdmin(admin.ModelAdmin):
    list_display = ("id", "catalog", "codigo", "convenio", "preco_referencia", "ativo")
    list_filter = ("catalog", "convenio", "ativo")
    search_fields = ("codigo", "codigo_original", "descricao", "convenio")
    ordering = ("-id",)
