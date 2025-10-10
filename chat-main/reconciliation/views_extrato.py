from django.shortcuts import redirect
from .models import RemittanceHeader
from django.contrib.auth.decorators import login_required

@login_required
def extrato_redirect(request):
    latest = RemittanceHeader.objects.order_by('-id').first()
    if latest:
        # Find all RemittanceHeaders with the same repasse_numero, competencia, terceiro_nome, previsao_pagamento as the latest
        qs = RemittanceHeader.objects.filter(
            repasse_numero=latest.repasse_numero,
            competencia=latest.competencia,
            terceiro_nome=latest.terceiro_nome,
            previsao_pagamento=latest.previsao_pagamento,
        ).order_by('id')
        ids = list(qs.values_list('id', flat=True))
        if ids:
            # Redirect to consolidated dashboard with all header IDs
            from django.urls import reverse
            url = reverse('consolidated_dashboard') + f"?ids={','.join(str(i) for i in ids)}"
            return redirect(url)
    return redirect('upload_remittance')