from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.http import JsonResponse
from django.urls import reverse
from pathlib import Path
from decimal import Decimal
from django.db.models import Sum

from .forms import RemittanceUploadForm
from .models import RemittanceHeader
from django.contrib import messages
from django.db import transaction
from .services import import_hospital_pdf, parse_pdf
from chatbot.views import call_gemini_api


@login_required
def upload_remittance(request):
    if request.method == 'POST':
        form = RemittanceUploadForm(request.POST, request.FILES)
        if form.is_valid():
            f = form.cleaned_data['pdf']
            # Garantir caminho físico mesmo para InMemoryUploadedFile
            import os
            import tempfile
            created_temp = False
            if hasattr(f, 'temporary_file_path'):
                tmp_path = f.temporary_file_path()
            else:
                with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
                    for chunk in f.chunks():
                        tmp.write(chunk)
                    tmp_path = tmp.name
                    created_temp = True
            try:
                hdrs = import_hospital_pdf(tmp_path, file_field=f)
                # Se vários headers, informar na UI
                if not hdrs:
                    messages.error(request, 'Nenhum item detectado no PDF enviado.')
                    return redirect('upload_remittance')
                if len(hdrs) > 1:
                    # Montar entradas com resumo e itens para visualização consolidada, replicando layout do detalhe
                    from collections import defaultdict
                    entries = []
                    for h in hdrs:
                        items_qs = h.items.all()
                        # Agregações
                        agg = items_qs.aggregate(
                            total_qtd=Sum('quantidade'),
                            total_bruto=Sum('valor_produzido'),
                            total_imposto=Sum('imposto'),
                            total_liquido=Sum('valor_liquido'),
                        )
                        zero = Decimal('0.00')
                        total_bruto = agg['total_bruto'] or zero
                        total_imposto = agg['total_imposto'] or zero
                        total_liquido_informado = agg['total_liquido'] or zero
                        liquido_calculado = (total_bruto or zero) - (total_imposto or zero)
                        diferenca = total_liquido_informado - liquido_calculado
                        taxa_media_impostos = (total_imposto / total_bruto * Decimal('100')) if total_bruto and total_bruto != zero else None
                        percent_diferenca = (diferenca / liquido_calculado * Decimal('100')) if liquido_calculado and liquido_calculado != zero else None

                        # Analytics por procedimento/convênio e alertas (igual à página de detalhe)
                        profit_by_proc: dict[str, Decimal] = defaultdict(lambda: zero)
                        profit_by_conv: dict[str, Decimal] = defaultdict(lambda: zero)
                        tax_by_conv: dict[str, Decimal] = defaultdict(lambda: zero)
                        for it in items_qs:
                            vp = it.valor_produzido or zero
                            imp = it.imposto or zero
                            liq = it.valor_liquido if it.valor_liquido is not None else (vp - imp)
                            profit_by_proc[it.procedimento or '(sem procedimento)'] += (liq or zero)
                            conv = it.convenio or '(sem convênio)'
                            profit_by_conv[conv] += (liq or zero)
                            tax_by_conv[conv] += (imp or zero)
                        top_proc_name, top_proc_value = (None, zero)
                        if profit_by_proc:
                            top_proc_name, top_proc_value = max(profit_by_proc.items(), key=lambda kv: kv[1])
                        top_conv_name, top_conv_value = (None, zero)
                        if profit_by_conv:
                            top_conv_name, top_conv_value = max(profit_by_conv.items(), key=lambda kv: kv[1])

                        alerts = []
                        tolerance = Decimal('0.10')
                        for conv, lucro in profit_by_conv.items():
                            imp = tax_by_conv.get(conv, zero)
                            if imp == zero and lucro == zero:
                                continue
                            if lucro < imp:
                                alerts.append({
                                    'tipo': 'lucro_menor_que_imposto',
                                    'convenio': conv,
                                    'lucro': lucro,
                                    'imposto': imp,
                                    'diferenca': lucro - imp,
                                    'percent': ((lucro - imp) / imp * Decimal('100')) if imp != zero else None,
                                })
                            else:
                                diff = abs(lucro - imp)
                                if imp != zero and (diff <= (imp * tolerance)):
                                    signed_diff = lucro - imp
                                    alerts.append({
                                        'tipo': 'lucro_quase_igual_imposto',
                                        'convenio': conv,
                                        'lucro': lucro,
                                        'imposto': imp,
                                        'diferenca': signed_diff,
                                        'percent': (signed_diff / imp * Decimal('100')) if imp != zero else None,
                                    })

                        worst_conv_name, worst_conv_pct = None, None
                        worst_conv_lucro, worst_conv_imposto = zero, zero
                        percents = []
                        for conv, lucro in profit_by_conv.items():
                            imp = tax_by_conv.get(conv, zero)
                            if lucro == zero:
                                continue
                            pct = (imp / lucro * Decimal('100')) if lucro != zero else None
                            if pct is not None:
                                percents.append((conv, pct, lucro, imp))
                        if percents:
                            worst_conv_name, worst_conv_pct, worst_conv_lucro, worst_conv_imposto = max(percents, key=lambda x: x[1])

                        summary = {
                            'count': items_qs.count(),
                            'total_qtd': agg['total_qtd'] or zero,
                            'bruto': total_bruto,
                            'impostos': total_imposto,
                            'liquido_calculado': liquido_calculado,
                            'liquido_informado': total_liquido_informado,
                            'diferenca': diferenca,
                            'taxa_media_impostos': taxa_media_impostos,
                            'percent_diferenca': percent_diferenca,
                            'top_procedimento_nome': top_proc_name,
                            'top_procedimento_valor': top_proc_value,
                            'top_convenio_nome': top_conv_name,
                            'top_convenio_valor': top_conv_value,
                            'alerts': alerts,
                            'worst_convenio_nome': worst_conv_name,
                            'worst_convenio_percent': worst_conv_pct,
                            'worst_convenio_lucro': worst_conv_lucro,
                            'worst_convenio_imposto': worst_conv_imposto,
                        }
                        entries.append({'header': h, 'summary': summary, 'items': items_qs})

                    # Consolidado geral (todos os profissionais)
                    zero = Decimal('0.00')
                    total_count = 0
                    total_qtd = Decimal('0')
                    total_bruto_all = zero
                    total_imposto_all = zero
                    total_liquido_info_all = zero
                    from collections import defaultdict
                    profit_by_proc_all: dict[str, Decimal] = defaultdict(lambda: zero)
                    profit_by_conv_all: dict[str, Decimal] = defaultdict(lambda: zero)
                    tax_by_conv_all: dict[str, Decimal] = defaultdict(lambda: zero)
                    for e in entries:
                        for it in e['items']:
                            total_count += 1
                            total_qtd += (it.quantidade or Decimal('0'))
                            vp = it.valor_produzido or zero
                            imp = it.imposto or zero
                            total_bruto_all += vp
                            total_imposto_all += imp
                            liq_info = it.valor_liquido
                            if liq_info is not None:
                                total_liquido_info_all += liq_info
                            # para analytics
                            liq = liq_info if liq_info is not None else (vp - imp)
                            proc = it.procedimento or '(sem procedimento)'
                            conv = it.convenio or '(sem convênio)'
                            profit_by_proc_all[proc] += (liq or zero)
                            profit_by_conv_all[conv] += (liq or zero)
                            tax_by_conv_all[conv] += (imp or zero)

                    liquido_calc_all = total_bruto_all - total_imposto_all
                    diferenca_all = total_liquido_info_all - liquido_calc_all
                    taxa_media_imp_all = (total_imposto_all / total_bruto_all * Decimal('100')) if total_bruto_all and total_bruto_all != zero else None
                    percent_dif_all = (diferenca_all / liquido_calc_all * Decimal('100')) if liquido_calc_all and liquido_calc_all != zero else None

                    top_proc_name, top_proc_value = (None, zero)
                    if profit_by_proc_all:
                        top_proc_name, top_proc_value = max(profit_by_proc_all.items(), key=lambda kv: kv[1])
                    top_conv_name, top_conv_value = (None, zero)
                    if profit_by_conv_all:
                        top_conv_name, top_conv_value = max(profit_by_conv_all.items(), key=lambda kv: kv[1])

                    worst_conv_name, worst_conv_pct = None, None
                    worst_conv_lucro, worst_conv_imposto = zero, zero
                    percents = []
                    for conv, lucro in profit_by_conv_all.items():
                        imp = tax_by_conv_all.get(conv, zero)
                        if lucro == zero:
                            continue
                        pct = (imp / lucro * Decimal('100')) if lucro != zero else None
                        if pct is not None:
                            percents.append((conv, pct, lucro, imp))
                    if percents:
                        worst_conv_name, worst_conv_pct, worst_conv_lucro, worst_conv_imposto = max(percents, key=lambda x: x[1])

                    summary_all = {
                        'count': total_count,
                        'total_qtd': total_qtd,
                        'bruto': total_bruto_all,
                        'impostos': total_imposto_all,
                        'liquido_calculado': liquido_calc_all,
                        'liquido_informado': total_liquido_info_all,
                        'diferenca': diferenca_all,
                        'taxa_media_impostos': taxa_media_imp_all,
                        'percent_diferenca': percent_dif_all,
                        'top_procedimento_nome': top_proc_name,
                        'top_procedimento_valor': top_proc_value,
                        'top_convenio_nome': top_conv_name,
                        'top_convenio_valor': top_conv_value,
                        'worst_convenio_nome': worst_conv_name,
                        'worst_convenio_percent': worst_conv_pct,
                        'worst_convenio_lucro': worst_conv_lucro,
                        'worst_convenio_imposto': worst_conv_imposto,
                    }

                    return render(request, 'reconciliation/consolidated.html', {
                        'entries': entries,
                        'summary_all': summary_all,
                        'repasse_numero': hdrs[0].repasse_numero,
                        'terceiro_nome': hdrs[0].terceiro_nome,
                        'competencia': hdrs[0].competencia,
                        'cnpj': hdrs[0].cnpj,
                        'previsao_pagamento': hdrs[0].previsao_pagamento,
                        # IDs dos headers para o chat consolidado
                        'header_ids': [h.id for h in hdrs],
                    })
                hdr = hdrs[0]
            finally:
                if created_temp:
                    try:
                        os.remove(tmp_path)
                    except OSError:
                        pass
            return redirect(reverse('remittance_detail', args=[hdr.id]))
    else:
        form = RemittanceUploadForm()
    return render(request, 'reconciliation/upload.html', {'form': form})


@login_required
def remittance_detail(request, id: int):
    hdr = RemittanceHeader.objects.prefetch_related('items').get(id=id)
    agg = hdr.items.aggregate(
        total_qtd=Sum('quantidade'),
        total_bruto=Sum('valor_produzido'),
        total_imposto=Sum('imposto'),
        total_liquido=Sum('valor_liquido'),
    )
    zero = Decimal('0.00')
    total_bruto = agg['total_bruto'] or zero
    total_imposto = agg['total_imposto'] or zero
    total_liquido_informado = agg['total_liquido'] or zero
    liquido_calculado = (total_bruto or zero) - (total_imposto or zero)
    diferenca = total_liquido_informado - liquido_calculado
    taxa_media_impostos = (total_imposto / total_bruto * Decimal('100')) if total_bruto and total_bruto != zero else None
    percent_diferenca = (diferenca / liquido_calculado * Decimal('100')) if liquido_calculado and liquido_calculado != zero else None

    # --- Analytics: profitability by procedure and by convenio ---
    from collections import defaultdict
    items = list(hdr.items.all())
    profit_by_proc: dict[str, Decimal] = defaultdict(lambda: Decimal('0.00'))
    profit_by_conv: dict[str, Decimal] = defaultdict(lambda: Decimal('0.00'))
    tax_by_conv: dict[str, Decimal] = defaultdict(lambda: Decimal('0.00'))
    for it in items:
        vp = it.valor_produzido or zero
        imp = it.imposto or zero
        # Prefer informed líquido when present; otherwise compute
        liq = it.valor_liquido if it.valor_liquido is not None else (vp - imp)
        profit_by_proc[it.procedimento or '(sem procedimento)'] += (liq or zero)
        conv = it.convenio or '(sem convênio)'
        profit_by_conv[conv] += (liq or zero)
        tax_by_conv[conv] += (imp or zero)

    # Top profit by procedure and convenio
    top_proc_name, top_proc_value = None, zero
    if profit_by_proc:
        top_proc_name, top_proc_value = max(profit_by_proc.items(), key=lambda kv: kv[1])
    top_conv_name, top_conv_value = None, zero
    if profit_by_conv:
        top_conv_name, top_conv_value = max(profit_by_conv.items(), key=lambda kv: kv[1])

    # Alerts: convenios where profit < taxes or almost equal
    alerts = []
    tolerance = Decimal('0.10')  # 10% considered "quase igual"
    for conv, lucro in profit_by_conv.items():
        imp = tax_by_conv.get(conv, zero)
        if imp == zero and lucro == zero:
            continue
        if lucro < imp:
            alerts.append({
                'tipo': 'lucro_menor_que_imposto',
                'convenio': conv,
                'lucro': lucro,
                'imposto': imp,
                'diferenca': lucro - imp,
                'percent': ((lucro - imp) / imp * Decimal('100')) if imp != zero else None,
            })
        else:
            # quase igual: |lucro - imposto| <= 10% do imposto
            diff = abs(lucro - imp)
            if imp != zero and (diff <= (imp * tolerance)):
                # sinal da diferença importa para análise
                signed_diff = lucro - imp
                alerts.append({
                    'tipo': 'lucro_quase_igual_imposto',
                    'convenio': conv,
                    'lucro': lucro,
                    'imposto': imp,
                    'diferenca': signed_diff,
                    'percent': (signed_diff / imp * Decimal('100')) if imp != zero else None,
                })

    # Worst convenio by imposto/lucro percentage (higher is worse). Ignore lucro == 0 to avoid division by zero.
    worst_conv_name, worst_conv_pct = None, None
    worst_conv_lucro, worst_conv_imposto = zero, zero
    percents = []
    for conv, lucro in profit_by_conv.items():
        imp = tax_by_conv.get(conv, zero)
        if lucro == zero:
            continue
        pct = (imp / lucro * Decimal('100')) if lucro != zero else None
        if pct is not None:
            percents.append((conv, pct, lucro, imp))
    if percents:
        worst_conv_name, worst_conv_pct, worst_conv_lucro, worst_conv_imposto = max(percents, key=lambda x: x[1])

    summary = {
        'count': hdr.items.count(),
        'total_qtd': agg['total_qtd'] or zero,
        'bruto': total_bruto,
        'impostos': total_imposto,
        'liquido_calculado': liquido_calculado,
        'liquido_informado': total_liquido_informado,
        'diferenca': diferenca,
        'taxa_media_impostos': taxa_media_impostos,
        'percent_diferenca': percent_diferenca,
        # New analytics
        'top_procedimento_nome': top_proc_name,
        'top_procedimento_valor': top_proc_value,
        'top_convenio_nome': top_conv_name,
        'top_convenio_valor': top_conv_value,
        'alerts': alerts,
        'worst_convenio_nome': worst_conv_name,
        'worst_convenio_percent': worst_conv_pct,
        'worst_convenio_lucro': worst_conv_lucro,
        'worst_convenio_imposto': worst_conv_imposto,
    }
    return render(request, 'reconciliation/detail.html', {'header': hdr, 'summary': summary})


@login_required
def reprocess_remittance(request, id: int):
    hdr = RemittanceHeader.objects.get(id=id)
    if not hdr.original_file:
        messages.error(request, 'Arquivo original não disponível para reprocessamento.')
        return redirect(reverse('remittance_detail', args=[hdr.id]))
    try:
        header_parsed, items = parse_pdf(Path(hdr.original_file.path))
        with transaction.atomic():
            hdr.items.all().delete()
            from .models import RemittanceItem
            RemittanceItem.objects.bulk_create([
                RemittanceItem(
                    header=hdr,
                    atendimento=i.atendimento,
                    conta=i.conta,
                    paciente=i.paciente,
                    convenio=i.convenio,
                    categoria=i.categoria,
                    data=i.data,
                    codigo=i.codigo,
                    procedimento=i.procedimento,
                    funcao=i.funcao,
                    quantidade=i.quantidade,
                    valor_produzido=i.valor_produzido,
                    imposto=i.imposto,
                    valor_liquido=i.valor_liquido,
                ) for i in items
            ])
        messages.success(request, f'Reprocessamento concluído. Itens importados: {len(items)}')
    except Exception as e:
        messages.error(request, f'Falha ao reprocessar: {e}')
    return redirect(reverse('remittance_detail', args=[hdr.id]))


@login_required
def qa_remittance(request, id: int):
    """Answer user questions about a specific remittance using Gemini and the remittance data as context."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Método não permitido'}, status=405)

    question = request.POST.get('q', '').strip()
    if not question:
        return JsonResponse({'error': 'Pergunta vazia'}, status=400)

    hdr = RemittanceHeader.objects.prefetch_related('items').get(id=id)
    zero = Decimal('0.00')
    agg = hdr.items.aggregate(
        total_qtd=Sum('quantidade'),
        total_bruto=Sum('valor_produzido'),
        total_imposto=Sum('imposto'),
        total_liquido=Sum('valor_liquido'),
    )
    total_bruto = agg['total_bruto'] or zero
    total_imposto = agg['total_imposto'] or zero
    total_liquido_informado = agg['total_liquido'] or zero
    liquido_calculado = (total_bruto or zero) - (total_imposto or zero)

    # Intent: handle duplicates deterministically when asked (clientes/pacientes repetidos)
    ql = question.lower()
    if (('cliente' in ql or 'paciente' in ql) and (
        'mais de 1' in ql or 'mais de uma' in ql or 'repetid' in ql or 'duplicad' in ql)):
        from collections import Counter
        names = [ (it.paciente or '').strip() for it in hdr.items.all() if (it.paciente or '').strip() ]
        key_names = [ n.lower() for n in names ]
        counts = Counter(key_names)
        # map back to a display name (first occurrence's casing)
        display_map = {}
        for it in hdr.items.all():
            n = (it.paciente or '').strip()
            if not n: continue
            k = n.lower()
            if k not in display_map:
                display_map[k] = n
        repeated = [(display_map[k], c) for k, c in counts.items() if c > 1]
        repeated.sort(key=lambda x: (-x[1], x[0]))
        if not repeated:
            ai_text = "Nenhum cliente/paciente aparece mais de 1 vez nos registros."
        else:
            lines = ["Clientes/pacientes com mais de 1 ocorrência:", ""]
            for name, c in repeated:
                suf = 'ocorrência' if c == 1 else 'ocorrências'
                lines.append(f"- {name}: {c} {suf}")
            ai_text = "\n".join(lines)
        return JsonResponse({'answer': ai_text})

    # Small, structured context
    items = list(hdr.items.all())
    # Build CSV-like rows to keep compact
    def fmt(v):
        return '' if v is None else str(v)
    rows = [
        "|".join([
            it.atendimento or '',
            it.data or '',
            it.paciente or '',
            it.convenio or '',
            it.categoria or '',
            it.codigo or '',
            (it.procedimento or '')[:120],
            fmt(it.quantidade),
            fmt(it.valor_produzido),
            fmt(it.imposto),
            fmt(it.valor_liquido if it.valor_liquido is not None else ((it.valor_produzido or zero) - (it.imposto or zero)))
        ]) for it in items
    ]
    header_row = "Atendimento|Data|Paciente|Convênio|Categoria|Código|Procedimento|Qtd|Produzido|Imposto|Líquido"
    table_text = "\n".join([header_row] + rows[:800])  # safety cap

    sys_preamble = (
        "Você é uma assistente financeira. Responda em português, de forma objetiva e com números em padrão brasileiro (R$ e vírgula decimal). "
        "Use apenas os dados fornecidos no contexto. Ao fazer contas, explique em 1 linha quando útil. "
        "Formate em Markdown simples (títulos curtos e listas com '-'), evitando tabelas e blocos de código."
    )
    summary_text = (
        f"Resumo: Bruto={total_bruto}; Impostos={total_imposto}; Líquido_calculado={liquido_calculado}; "
        f"Líquido_informado={total_liquido_informado}; Itens={len(items)}."
    )
    prompt = (
        f"{sys_preamble}\n\n"
        f"Demonstrativo do repasse do profissional {hdr.profissional_nome} (Especialidade: {hdr.especialidade}, Competência: {hdr.competencia}).\n"
        f"{summary_text}\n\n"
        f"Tabela (campos separados por |):\n{table_text}\n\n"
        f"Pergunta: {question}\n\n"
        f"Responda considerando os dados acima. Se referir valores, formate como R$ 1.234,56."
    )

    ai_text = call_gemini_api(prompt) or "Não consegui responder agora. Tente reformular a pergunta."
    return JsonResponse({'answer': ai_text})


@login_required
def qa_consolidated(request):
    """Answer user questions about the consolidated page (multiple headers) using Gemini.

    Expects POST with:
      - q: user question
      - ids: comma-separated list of RemittanceHeader IDs to include
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Método não permitido'}, status=405)

    question = request.POST.get('q', '').strip()
    ids_csv = request.POST.get('ids', '').strip()
    if not question:
        return JsonResponse({'error': 'Pergunta vazia'}, status=400)
    if not ids_csv:
        return JsonResponse({'error': 'IDs ausentes'}, status=400)

    try:
        ids = [int(x) for x in ids_csv.split(',') if x.strip()]
    except ValueError:
        return JsonResponse({'error': 'IDs inválidos'}, status=400)
    if not ids:
        return JsonResponse({'error': 'IDs vazios'}, status=400)

    headers = list(RemittanceHeader.objects.filter(id__in=ids).prefetch_related('items').all())
    if not headers:
        return JsonResponse({'error': 'Nenhum demonstrativo encontrado'}, status=404)

    zero = Decimal('0.00')
    # Totais consolidados
    total_count = 0
    total_qtd = Decimal('0')
    total_bruto = zero
    total_imposto = zero
    total_liquido_info = zero

    # Quebra por profissional
    per_prof = []  # (nome, especialidade, itens, bruto, imposto, liquido_info)

    # Linhas detalhadas (capadas) – adiciona o profissional no início
    rows = []
    header_row = "Profissional|Especialidade|Atendimento|Data|Paciente|Convênio|Categoria|Código|Procedimento|Qtd|Produzido|Imposto|Líquido"

    for h in headers:
        agg = h.items.aggregate(
            total_qtd=Sum('quantidade'),
            total_bruto=Sum('valor_produzido'),
            total_imposto=Sum('imposto'),
            total_liquido=Sum('valor_liquido'),
        )
        b = agg['total_bruto'] or zero
        imp = agg['total_imposto'] or zero
        li = agg['total_liquido'] or zero
        per_prof.append((h.profissional_nome or '-', h.especialidade or '-', h.items.count(), b, imp, li))

        total_count += h.items.count()
        total_qtd += (agg['total_qtd'] or Decimal('0'))
        total_bruto += b
        total_imposto += imp
        total_liquido_info += li

        for it in h.items.all():
            def fmt(v):
                return '' if v is None else str(v)
            rows.append("|".join([
                h.profissional_nome or '-',
                h.especialidade or '-',
                it.atendimento or '',
                it.data or '',
                it.paciente or '',
                it.convenio or '',
                it.categoria or '',
                it.codigo or '',
                (it.procedimento or '')[:120],
                fmt(it.quantidade),
                fmt(it.valor_produzido),
                fmt(it.imposto),
                fmt(it.valor_liquido if it.valor_liquido is not None else ((it.valor_produzido or zero) - (it.imposto or zero)))
            ]))

    liquido_calc = total_bruto - total_imposto
    summary_text = (
        f"Consolidado de {len(headers)} profissionais. Itens={total_count}; "
        f"Qtd_total={total_qtd}; Bruto={total_bruto}; Impostos={total_imposto}; "
        f"Líquido_calculado={liquido_calc}; Líquido_informado={total_liquido_info}."
    )

    # Pequena tabela por profissional
    per_prof_lines = ["Por profissional (itens, bruto, imposto, líquido informado):", ""]
    for nome, esp, count, b, imp, li in per_prof:
        per_prof_lines.append(f"- {nome} ({esp}): itens={count}, bruto={b}, imposto={imp}, líquido={li}")
    per_prof_text = "\n".join(per_prof_lines)

    table_text = "\n".join([header_row] + rows[:1200])  # segurança

    sys_preamble = (
        "Você é uma assistente financeira. Responda em português, de forma objetiva e com números em padrão brasileiro (R$ e vírgula decimal). "
        "Use apenas os dados fornecidos no contexto (consolidado e por profissional). Ao fazer contas, explique em 1 linha quando útil. "
        "Formate em Markdown simples (títulos curtos e listas com '-'), evitando tabelas e blocos de código."
    )
    prompt = (
        f"{sys_preamble}\n\n"
        f"{summary_text}\n\n{per_prof_text}\n\n"
        f"Tabela (campos separados por |):\n{table_text}\n\n"
        f"Pergunta: {question}\n\n"
        f"Responda considerando TODOS os dados acima (consolidado e se necessário por profissional)."
    )

    ai_text = call_gemini_api(prompt) or "Não consegui responder agora. Tente reformular a pergunta."
    return JsonResponse({'answer': ai_text})
