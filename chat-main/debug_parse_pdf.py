from pathlib import Path
from reconciliation.services import parse_pdf

pdf = Path(r"c:\Users\lucia_csx8nlz\Downloads\Relat_1539 (13) (1).PDF")
header, items = parse_pdf(pdf)
print("HEADER:", header)
print("Items:", len(items))
for i, it in enumerate(items[:20], start=1):
    print(i, {
        'data': it.data,
        'paciente': it.paciente,
        'convenio': it.convenio,
        'categoria': it.categoria,
        'codigo': it.codigo,
        'procedimento': it.procedimento[:50],
        'qtd': it.quantidade,
        'prod': it.valor_produzido,
        'imp': it.imposto,
        'liq': it.valor_liquido,
    })
