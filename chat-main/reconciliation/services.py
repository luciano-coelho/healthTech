from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Tuple

import pandas as pd
import pdfplumber
import re
import unicodedata

# Models serão importados dentro de funções que persistem dados para permitir uso de parse_* sem Django settings


def _norm(s: str | None) -> str:
    return " ".join(str(s).split()) if s is not None else ""


def _strip_accents(s: str) -> str:
    nfkd = unicodedata.normalize('NFKD', s)
    return ''.join([c for c in nfkd if not unicodedata.combining(c)])


def _ptbr_to_decimal(s: str | None) -> float | None:
    if s is None:
        return None
    t = str(s)
    if not t:
        return None
    t = t.strip()
    # remove currency and percent markers
    t = t.replace('R$', '').replace('%', '')
    # remove spaces and thousand separators
    t = t.replace('\xa0', ' ').replace(' ', '')
    # handle negatives like (1.234,56) or 1.234,56-
    negative = False
    if t.endswith('-'):
        negative = True
        t = t[:-1]
    if t.startswith('(') and t.endswith(')'):
        negative = True
        t = t[1:-1]
    t = t.replace('.', '').replace(',', '.')
    try:
        val = float(t)
        return -val if negative else val
    except ValueError:
        return None


# ---- Date helpers ---------------------------------------------------------
# Accepts variants like: 01/08/2025, 01/08/25, 01-08-2025, 01.08.2025, 01 / 08 / 2025
# and also ISO-like 2025-08-01 (will be reformatted to dd/mm/yyyy)
DATE_DMY_RE = re.compile(r"\b(\d{2})\s*[\/.\-]\s*(\d{2})(?:\s*[\/.\-]\s*(\d{2,4}))?\b")
DATE_YMD_RE = re.compile(r"\b(\d{4})\s*[-/.]\s*(\d{2})\s*[-/.]\s*(\d{2})\b")


def _normalize_date_str(day: str, month: str, year: str | None) -> str:
    d = day.zfill(2)
    m = month.zfill(2)
    if year is None:
        return f"{d}/{m}"
    y = year
    # Keep 2-digit year if provided, otherwise 4-digit
    if len(y) == 2:
        return f"{d}/{m}/{y}"
    return f"{d}/{m}/{y.zfill(4)}"


def _find_date(text: str) -> str:
    """Find a date in text and return normalized BR format (dd/mm[/yy|yyyy])."""
    if not text:
        return ""
    m = DATE_DMY_RE.search(text)
    if m:
        return _normalize_date_str(m.group(1), m.group(2), m.group(3))
    m = DATE_YMD_RE.search(text)
    if m:
        # Convert yyyy-mm-dd -> dd/mm/yyyy
        return f"{m.group(3).zfill(2)}/{m.group(2).zfill(2)}/{m.group(1)}"
    return ""


# Monetary amount regex (pt-BR) usable across parsers
monetary_re = re.compile(r"\b\d{1,3}(?:\.\d{3})*,\d{2}\b")


def parse_line_fallback(text: str) -> dict[str, str | float | None]:
    """Best-effort extraction from a flat line: date, code, procedure, qty and amounts.
    Returns a possibly partial dict with keys among: data, codigo, procedimento, quantidade, valor_produzido, imposto, valor_liquido.
    """
    res: dict[str, str | float | None] = {}
    # date
    d = _find_date(text)
    if d:
        res['data'] = d
    # amounts: take the last three as produzido, imposto, liquido
    amts = monetary_re.findall(text)
    if len(amts) >= 3:
        res['valor_produzido'] = _ptbr_to_decimal(amts[-3])
        res['imposto'] = _ptbr_to_decimal(amts[-2])
        res['valor_liquido'] = _ptbr_to_decimal(amts[-1])
        # qty: token before produzido
        pre = text.rsplit(amts[-3], 1)[0]
        mqty = re.search(r"(\d{1,3})(?:\s*)$", pre.strip())
        if mqty:
            res['quantidade'] = _ptbr_to_decimal(mqty.group(1))
    # code: first token with any digit after date
    parts = text.split()
    code = ''
    if 'data' in res:
        try:
            di = parts.index(res['data'])
        except ValueError:
            di = -1
    else:
        di = -1
    span = parts[di+1:] if di != -1 else parts
    for tok in span:
        if any(ch.isdigit() for ch in tok) and len(tok) <= 12:
            code = tok
            break
    if code:
        res['codigo'] = code
    # procedimento: between code and last amount
    if code and len(amts) >= 1:
        rightmost = amts[-1]
        try:
            left = text.index(code) + len(code)
            right = text.rfind(rightmost)
            proc = _norm(text[left:right])
            res['procedimento'] = proc
        except ValueError:
            pass
    return res


@dataclass
class ParsedHeader:
    repasse_numero: str = ""
    terceiro_nome: str = ""
    competencia: str = ""
    cnpj: str = ""
    previsao_pagamento: str = ""
    profissional_nome: str = ""
    especialidade: str = ""


@dataclass
class ParsedItem:
    atendimento: str = ""
    conta: str = ""
    paciente: str = ""
    convenio: str = ""
    categoria: str = ""
    data: str = ""
    codigo: str = ""
    procedimento: str = ""
    funcao: str = ""
    quantidade: float | None = None
    valor_produzido: float | None = None
    imposto: float | None = None
    valor_liquido: float | None = None
    page: int = 0


def extract_pdf_dataframe(pdf_path: Path) -> pd.DataFrame:
    """Extract tables into a flat DataFrame with page/table indexes.
    Uses pdfplumber default table detection; normalizes cell text.
    """
    rows = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_index, page in enumerate(pdf.pages, start=1):
            tables = page.extract_tables() or []
            for t_index, table in enumerate(tables):
                for row in table or []:
                    cells = [
                        _norm(cell) if cell is not None else ''
                        for cell in row
                    ]
                    rows.append({
                        'page': page_index,
                        'table': t_index,
                        **{f'c{i}': cells[i] if i < len(cells) else '' for i in range(max(15, len(cells)))}
                    })
    return pd.DataFrame(rows)


def _tables_look_collapsed(df: pd.DataFrame) -> bool:
    """Heurística: muitas linhas com apenas a primeira coluna preenchida indicam extração "achatada".
    Considera 'colapsado' se >70% das linhas têm texto apenas em c0.
    """
    if df.empty:
        return False
    total = len(df)
    collapsed = 0
    for _, r in df.iterrows():
        vals = [ _norm(r.get(f'c{i}', '')) for i in range(10) ]
        if vals and vals[0] and all(not v for v in vals[1:]):
            collapsed += 1
    return (collapsed / total) >= 0.7


def parse_header_from_words(pdf_path: Path) -> ParsedHeader:
    """Fallback simples: usa palavras da primeira página para capturar o cabeçalho."""
    with pdfplumber.open(pdf_path) as pdf:
        page = pdf.pages[0]
        words = page.extract_words(x_tolerance=3, y_tolerance=3) or []
        text = " ".join(w.get('text', '') for w in words)

    hdr = ParsedHeader()
    # Heurísticas simples
    m = re.search(r"REPASSE:\s*(\d+)", text)
    if m:
        hdr.repasse_numero = m.group(1)
    m = re.search(r"TERCEIRO:\s*([\w\s\./&-]+) COMPETÊNCIA:", text)
    if m:
        hdr.terceiro_nome = m.group(1).strip()
    m = re.search(r"COMPETÊNCIA:\s*([0-9/]{7})", text)
    if m:
        hdr.competencia = m.group(1)
    m = re.search(r"CNPJ:\s*([\d\./-]+)", text)
    if m:
        hdr.cnpj = m.group(1)
    m = re.search(r"Previs[aã]o\s*:\s*([0-9/]{4,5})", text, flags=re.IGNORECASE)
    if m:
        hdr.previsao_pagamento = m.group(1)
    else:
        m = re.search(r"Previs[aã]o\s+de\s+pagamento\s*:\s*([0-9/]{4,5})", text, flags=re.IGNORECASE)
        if m:
            hdr.previsao_pagamento = m.group(1)
    # Profissional e especialidade
    m = re.search(r"\b([A-ZÁÉÍÓÚÂÊÔÃÕÇ][\wÁÉÍÓÚÂÊÔÃÕÇ\s]+)\s+Especialidade:\s+([A-Za-z\sÁÉÍÓÚâêôãõç]+)\b", text)
    if m:
        hdr.profissional_nome = m.group(1).strip()
        esp = m.group(2).strip()
        # Evitar capturar cabeçalho da tabela junto da especialidade
        stop_tokens = [
            'Atendimento', 'Conta', 'Paciente', 'Convênio', 'Convenio', 'Categoria', 'Data', 'Código', 'Codigo', 'Procedimento', 'Função', 'Funcao', 'Quantidade', 'Qtd'
        ]
        cut_idx = len(esp)
        for tok in stop_tokens:
            k = esp.find(tok)
            if k != -1:
                cut_idx = min(cut_idx, k)
        hdr.especialidade = esp[:cut_idx].strip()

    return hdr


def detect_professionals_by_page(pdf_path: Path) -> dict[int, tuple[str, str]]:
    """Mapeia por página: (profissional_nome, especialidade). Propaga último conhecido para páginas sem cabeçalho explícito."""
    result: dict[int, tuple[str, str]] = {}
    last_prof: tuple[str, str] | None = None
    with pdfplumber.open(pdf_path) as pdf:
        for idx, page in enumerate(pdf.pages, start=1):
            words = page.extract_words(x_tolerance=3, y_tolerance=3) or []
            text = " ".join(w.get('text', '') for w in words)
            # Reutiliza regex do header
            m = re.search(r"\b([A-ZÁÉÍÓÚÂÊÔÃÕÇ][\wÁÉÍÓÚÂÊÔÃÕÇ\s]+)\s+Especialidade:\s+([A-Za-z\sÁÉÍÓÚâêôãõç/]+)\b", text)
            if m:
                prof = m.group(1).strip()
                esp = m.group(2).strip()
                # Remover possíveis sobras do cabeçalho da tabela
                stop_tokens = [
                    'Atendimento', 'Conta', 'Paciente', 'Convênio', 'Convenio', 'Categoria', 'Data', 'Código', 'Codigo', 'Procedimento', 'Função', 'Funcao', 'Quantidade', 'Qtd'
                ]
                cut_idx = len(esp)
                for tok in stop_tokens:
                    k = esp.find(tok)
                    if k != -1:
                        cut_idx = min(cut_idx, k)
                esp = esp[:cut_idx].strip()
                last_prof = (prof, esp)
                result[idx] = last_prof
            else:
                if last_prof:
                    result[idx] = last_prof
    return result


def parse_items_from_tables(df: pd.DataFrame) -> list[ParsedItem]:
    """Parse items using flexible header detection and synonym-based mapping.
    This version supports multiple header/footer blocks across the document.
    """
    items: list[ParsedItem] = []

    if df.empty:
        return items

    # Synonyms mapping (normalized, no accents, lower)
    synonyms: dict[str, list[str]] = {
        'data': ['data', 'dt'],
        'paciente': ['paciente', 'nome do paciente', 'nome'],
        'convenio': ['convenio', 'convênio', 'plano'],
        'categoria': ['categoria', 'setor'],
        'codigo': ['codigo', 'código', 'cod', 'cd'],
        'procedimento': ['procedimento', 'descricao', 'descrição', 'servico', 'serviço', 'exame'],
        'funcao': ['funcao', 'função', 'func.'],
        'quantidade': ['qtd', 'quantidade', 'qtde', 'qte'],
        'valor_produzido': ['produzido', 'valor produzido', 'vlr prod', 'valor bruto', 'bruto', 'total'],
        'imposto': ['imposto', 'taxa', 'retencao', 'retenção'],
        'valor_liquido': ['liquido', 'líquido', 'valor liquido', 'valor líquido', 'vlr liq', 'a pagar'],
        'atendimento': ['atendimento'],
        'conta': ['conta'],
    }

    def normalize_for_match(s: str) -> str:
        return _strip_accents(_norm(s)).lower()

    def is_footer(row_text: str) -> bool:
        row_text_n = normalize_for_match(row_text)
        return any(w in row_text_n for w in ['resultado', 'resumo', 'total geral', 'totais', 'ass', 'assinatura', 'total ('])

    # (parse_line_fallback now defined at module level)

    def score_header_row(values: list[str]) -> tuple[int, list[str]]:
        cols = [normalize_for_match(v) for v in values]
        score = 0
        for col in cols:
            for _, keys in synonyms.items():
                if any(k in col for k in keys):
                    score += 1
                    break
        return score, cols

    i = 0
    max_rows = len(df)
    # Walk the whole DataFrame detecting header blocks repeatedly
    while i < max_rows:
        r = df.iloc[i]
        values = [_norm(r.get(f'c{j}', '')) for j in range(20)]
        score, header_cols = score_header_row(values)
        if score < 3:
            i += 1
            continue

        # Build column map for this block
        col_map: dict[int, str] = {}
        for col_idx, col in enumerate(header_cols):
            best_key = None
            best_match_len = 0
            for key, keys in synonyms.items():
                for k in keys:
                    if k in col and len(k) > best_match_len:
                        best_key = key
                        best_match_len = len(k)
            if best_key:
                col_map[col_idx] = best_key

        # Advance to first data row after header
        i += 1
        # Keep last seen date within this block to fill down missing dates
        last_date: str = ""
        empty_rows = 0
        while i < max_rows:
            rr = df.iloc[i]
            row_vals = [_norm(rr.get(f'c{j}', '')) for j in range(20)]
            row_text_all = ' '.join(row_vals)
            if not row_text_all.strip():
                empty_rows += 1
                # give some slack for blank separators within a block
                if empty_rows <= 2:
                    i += 1
                    continue
                else:
                    break
            empty_rows = 0

            if is_footer(row_text_all):
                # End of current block; move past footer and look for next header
                i += 1
                break

            data_dict: dict[str, str] = {}
            for j, val in enumerate(row_vals):
                if j in col_map and val is not None:
                    data_dict[col_map[j]] = _norm(val)

            # If no explicit 'data', try to extract by regex from the row text
            if not data_dict.get('data'):
                d = _find_date(row_text_all)
                if d:
                    data_dict['data'] = d

            # Fill down last seen date if still missing
            if data_dict.get('data'):
                last_date = data_dict['data']  # type: ignore
            elif last_date:
                data_dict['data'] = last_date

            # If still missing critical fields, try fallback from full text
            if not (data_dict.get('codigo') or data_dict.get('procedimento')):
                fb = parse_line_fallback(row_text_all)
                for k in ['data','codigo','procedimento']:
                    if k in fb and fb[k]:
                        data_dict[k] = fb[k]  # type: ignore
                # numeric fields from fallback
                for k in ['quantidade','valor_produzido','imposto','valor_liquido']:
                    if k in fb and fb[k] is not None and data_dict.get(k) in (None, '',):
                        data_dict[k] = fb[k]  # type: ignore
            # Even if we have procedimento, try to fill missing codigo from the line
            if not data_dict.get('codigo'):
                fb2 = parse_line_fallback(row_text_all)
                if 'codigo' in fb2 and fb2['codigo']:
                    data_dict['codigo'] = fb2['codigo']  # type: ignore

            q = _ptbr_to_decimal(data_dict.get('quantidade'))
            vp = _ptbr_to_decimal(data_dict.get('valor_produzido'))
            imp = _ptbr_to_decimal(data_dict.get('imposto'))
            vl = _ptbr_to_decimal(data_dict.get('valor_liquido'))
            # Fallback calculations to avoid None where possible
            if vl is None and vp is not None and imp is not None:
                vl = vp - imp
            if imp is None and vp is not None and vl is not None:
                imp = vp - vl

            # Heuristic: require at least código or procedimento, and at least one numeric value among quantidade/produzido/liquido
            has_code_or_proc = bool(data_dict.get('codigo') or data_dict.get('procedimento'))
            any_numeric = any(v is not None for v in [q, vp, imp, vl])
            if not has_code_or_proc or not any_numeric:
                i += 1
                continue

            items.append(ParsedItem(
                atendimento=data_dict.get('atendimento', ''),
                conta=data_dict.get('conta', ''),
                paciente=data_dict.get('paciente', ''),
                convenio=data_dict.get('convenio', ''),
                categoria=data_dict.get('categoria', ''),
                data=data_dict.get('data', ''),
                codigo=data_dict.get('codigo', ''),
                procedimento=data_dict.get('procedimento', ''),
                funcao=data_dict.get('funcao', ''),
                quantidade=q,
                valor_produzido=vp,
                imposto=imp,
                valor_liquido=vl,
                page=int(rr.get('page', 0) or 0),
            ))

            i += 1

        # Continue outer while to hunt for next header
        continue

    return items


def parse_items_from_text(pdf_path: Path) -> list[ParsedItem]:
    """Fallback: parse lines of text splitting by multiple spaces; best-effort mapping.
    Works for statements where tables aren't detected but columns are visually aligned.
    """
    items: list[ParsedItem] = []
    date_re = re.compile(r"\b(\d{2}/\d{2}(?:/\d{2,4})?)\b")

    def looks_like_footer(line: str) -> bool:
        n = _strip_accents(line.lower())
        return any(k in n for k in ['resultado', 'resumo', 'total geral', 'totais', 'assinatura'])

    with pdfplumber.open(pdf_path) as pdf:
        for pi, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ''
            lines = [l for l in text.splitlines() if l.strip()]
            seen_header = False
            last_date = ''
            for line in lines:
                ln = _strip_accents(line.lower())
                if not seen_header and all(k in ln for k in ['paciente', 'convenio', 'procedimento']):
                    seen_header = True
                    last_date = ''  # reset at new header
                    continue
                if not seen_header:
                    continue
                if looks_like_footer(line):
                    last_date = ''  # end of block
                    break
                parts = re.split(r"\s{2,}", line.strip())
                if len(parts) < 6:
                    continue
                # Map from the right: ... Qtd, Produzido, Imposto, Liquido
                qtd = _ptbr_to_decimal(parts[-4]) if len(parts) >= 4 else None
                produzido = _ptbr_to_decimal(parts[-3]) if len(parts) >= 3 else None
                imposto = _ptbr_to_decimal(parts[-2]) if len(parts) >= 2 else None
                liquido = _ptbr_to_decimal(parts[-1]) if len(parts) >= 1 else None

                left = parts[:-4]
                if not left:
                    continue
                # Try to capture Atendimento and Conta from the beginning of the left segment
                left_join = ' '.join(left)
                atendimento = ''
                conta = ''
                m_ac = re.match(r"\s*(\d{4,})\s+(\d{4,})\s+(.*)$", left_join)
                if m_ac:
                    atendimento = m_ac.group(1)
                    conta = m_ac.group(2)
                    # replace left with the remainder to avoid confusing code/procedure extraction
                    left = [m_ac.group(3)]
                # Try find date (robusto)
                data = ''
                for p in left:
                    data = _find_date(p)
                    if data:
                        break
                # Fill down last seen date if still missing
                if data:
                    last_date = data
                elif last_date:
                    data = last_date

                # Try find code (token with any digit and short-ish)
                codigo = ''
                for p in left:
                    if any(ch.isdigit() for ch in p) and len(p) <= 12:
                        codigo = p
                        break

                # Procedure: take the longest chunk
                procedimento = max(left, key=len) if left else ''

                if not (codigo or procedimento) or not any(v is not None for v in [qtd, produzido, imposto, liquido]):
                    continue

                items.append(ParsedItem(
                    atendimento=atendimento,
                    conta=conta,
                    data=data,
                    codigo=codigo,
                    procedimento=procedimento,
                    quantidade=qtd,
                    valor_produzido=produzido,
                    imposto=imposto,
                    valor_liquido=liquido,
                    page=pi,
                ))

    return items


def parse_items_from_words(pdf_path: Path) -> list[ParsedItem]:
    """Fallback using word positions: detect header columns by synonyms and split lines by x-positions."""
    items: list[ParsedItem] = []

    synonyms: dict[str, list[str]] = {
        'data': ['data', 'dt'],
        'paciente': ['paciente', 'nome do paciente', 'nome'],
        'convenio': ['convenio', 'convênio', 'plano'],
        'categoria': ['categoria', 'setor'],
        'codigo': ['codigo', 'código', 'cod', 'cd'],
        'procedimento': ['procedimento', 'descricao', 'descrição', 'servico', 'serviço', 'exame'],
        'funcao': ['funcao', 'função', 'func.'],
        'quantidade': ['qtd', 'quantidade', 'qtde', 'qte'],
        'valor_produzido': ['produzido', 'valor produzido', 'vlr prod', 'valor bruto', 'bruto', 'total'],
        'imposto': ['imposto', 'taxa', 'retencao', 'retenção'],
        'valor_liquido': ['liquido', 'líquido', 'valor liquido', 'valor líquido', 'vlr liq', 'a pagar'],
        'atendimento': ['atendimento'],
        'conta': ['conta'],
    }

    def norm_text(s: str) -> str:
        return _strip_accents(_norm(s)).lower()

    def cluster_lines(words: List[dict], y_tol: float = 2.0) -> List[List[dict]]:
        """Group words into lines by proximity of 'top' coordinate."""
        if not words:
            return []
        words_sorted = sorted(words, key=lambda w: (w.get('top', 0), w.get('x0', 0)))
        lines: List[List[dict]] = []
        current: List[dict] = []
        current_top: float = None  # type: ignore
        for w in words_sorted:
            top = float(w.get('top', 0))
            if current_top is None or abs(top - current_top) <= y_tol:
                current.append(w)
                if current_top is None:
                    current_top = top
            else:
                lines.append(sorted(current, key=lambda x: x.get('x0', 0)))
                current = [w]
                current_top = top
        if current:
            lines.append(sorted(current, key=lambda x: x.get('x0', 0)))
        return lines

    def score_header(line_words: List[dict]) -> Tuple[int, dict]:
        score = 0
        col_hits: dict[float, str] = {}
        for w in line_words:
            t = norm_text(w.get('text', ''))
            for key, keys in synonyms.items():
                if any(k in t for k in keys):
                    score += 1
                    # map by x0 (left position)
                    x0 = float(w.get('x0', 0.0))
                    if key not in col_hits.values():
                        col_hits[x0] = key
                    break
        return score, col_hits

    def build_boundaries(col_hits: dict, page_width: float) -> List[Tuple[float, float, str]]:
        # returns list of (x_left, x_right, key) in order
        if not col_hits:
            return []
        cols_sorted = sorted(((float(x), key) for x, key in col_hits.items()), key=lambda x: x[0])
        bounds: List[Tuple[float, float, str]] = []
        for i, (x, key) in enumerate(cols_sorted):
            left = x - 1
            right = (cols_sorted[i + 1][0] + x) / 2 if i + 1 < len(cols_sorted) else page_width + 10
            bounds.append((left, right, key))
        return bounds

    with pdfplumber.open(pdf_path) as pdf:
        for pi, page in enumerate(pdf.pages, start=1):
            words = page.extract_words(x_tolerance=2, y_tolerance=2, keep_blank_chars=False) or []
            lines = cluster_lines(words, y_tol=2.0)
            header_idx = -1
            boundaries: List[Tuple[float, float, str]] = []
            best_score = -1
            # find header line with best score
            for idx, line in enumerate(lines):
                score, col_hits = score_header(line)
                if score > best_score and score >= 3:
                    best_score = score
                    header_idx = idx
                    boundaries = build_boundaries(col_hits, page.width)
            if header_idx == -1 or not boundaries:
                continue

            # parse data lines after header
            last_date = ''
            for line in lines[header_idx + 1:]:
                texts_by_key: dict[str, List[str]] = {b[2]: [] for b in boundaries}
                for w in line:
                    x = float(w.get('x0', 0.0))
                    t = _norm(w.get('text', ''))
                    for left, right, key in boundaries:
                        if left <= x < right:
                            texts_by_key[key].append(t)
                            break
                # Build row dict
                row = {k: ' '.join(v).strip() for k, v in texts_by_key.items()}
                # Skip if empty
                if not any(row.values()):
                    continue
                # Footer detection
                row_text_all = ' '.join(row.values())
                if any(tok in norm_text(row_text_all) for tok in ['resultado', 'resumo', 'total geral', 'totais', 'assinatura']):
                    last_date = ''
                    break
                # Try to extract date if missing
                if not row.get('data'):
                    d = _find_date(row_text_all)
                    if d:
                        row['data'] = d
                # Try to extract missing codigo from full line
                if not row.get('codigo'):
                    fb = parse_line_fallback(row_text_all)
                    if 'codigo' in fb and fb['codigo']:
                        row['codigo'] = fb['codigo']  # type: ignore
                # Fill down last seen date if still missing
                if row.get('data'):
                    last_date = row['data']  # type: ignore
                elif last_date:
                    row['data'] = last_date

                # Heuristic validity
                has_code_or_proc = bool(row.get('codigo') or row.get('procedimento'))
                q = _ptbr_to_decimal(row.get('quantidade'))
                vp = _ptbr_to_decimal(row.get('valor_produzido'))
                imp = _ptbr_to_decimal(row.get('imposto'))
                vl = _ptbr_to_decimal(row.get('valor_liquido'))
                # Fallbacks
                if vl is None and vp is not None and imp is not None:
                    vl = vp - imp
                if imp is None and vp is not None and vl is not None:
                    imp = vp - vl
                any_numeric = any(v is not None for v in [q, vp, imp, vl])
                if not has_code_or_proc or not any_numeric:
                    continue

                items.append(ParsedItem(
                    atendimento=row.get('atendimento', ''),
                    conta=row.get('conta', ''),
                    paciente=row.get('paciente', ''),
                    convenio=row.get('convenio', ''),
                    categoria=row.get('categoria', ''),
                    data=row.get('data', ''),
                    codigo=row.get('codigo', ''),
                    procedimento=row.get('procedimento', ''),
                    funcao=row.get('funcao', ''),
                    quantidade=q,
                    valor_produzido=vp,
                    imposto=imp,
                    valor_liquido=vl,
                    page=pi,
                ))

    return items


def import_hospital_pdf(pdf_path: str, file_field=None) -> list:
    """Importa o PDF criando um RemittanceHeader por profissional detectado.
    Retorna a lista de headers criados.
    """
    from .models import RemittanceHeader, RemittanceItem
    pdfp = Path(pdf_path)
    header, items = parse_pdf(pdfp)

    # Detectar profissional por página e agrupar itens
    page_prof = detect_professionals_by_page(pdfp)
    # Propagar último prof conhecido caso alguma página não tenha
    if not page_prof:
        # fallback: usa o header global para todos
        page_prof = {}
    groups: dict[tuple[str, str], list[ParsedItem]] = {}
    last_prof_key: tuple[str, str] | None = None
    for it in items:
        key = None
        if it.page and it.page in page_prof:
            prof, esp = page_prof[it.page]
            key = (prof or header.profissional_nome, esp or header.especialidade)
            last_prof_key = key
        else:
            key = last_prof_key or (header.profissional_nome, header.especialidade)
        groups.setdefault(key, []).append(it)

    headers_created: list[RemittanceHeader] = []
    for (prof_name, esp), its in groups.items():
        hdr = RemittanceHeader.objects.create(
            repasse_numero=header.repasse_numero,
            terceiro_nome=header.terceiro_nome,
            competencia=header.competencia,
            cnpj=header.cnpj,
            previsao_pagamento=header.previsao_pagamento,
            profissional_nome=prof_name or header.profissional_nome,
            especialidade=esp or header.especialidade,
        )
        if file_field:
            # anexar o arquivo também a este header para permitir reprocessamento individual
            hdr.original_file.save(getattr(file_field, 'name', 'upload.pdf'), file_field, save=True)

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
            ) for i in its
        ])
        headers_created.append(hdr)

    # Caso não tenha separado (p.ex. nenhum prof detectado), cria 1 com todos
    if not headers_created:
        hdr = RemittanceHeader.objects.create(
            repasse_numero=header.repasse_numero,
            terceiro_nome=header.terceiro_nome,
            competencia=header.competencia,
            cnpj=header.cnpj,
            previsao_pagamento=header.previsao_pagamento,
            profissional_nome=header.profissional_nome,
            especialidade=header.especialidade,
        )
        if file_field:
            hdr.original_file.save(getattr(file_field, 'name', 'upload.pdf'), file_field, save=True)
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
        headers_created.append(hdr)

    return headers_created


def parse_pdf(pdf_path: Path) -> tuple[ParsedHeader, list[ParsedItem]]:
    """High-level parse: extract header and items with fallbacks."""
    df = extract_pdf_dataframe(pdf_path)
    header = parse_header_from_words(pdf_path)

    items: list[ParsedItem] = []
    if _tables_look_collapsed(df):
        # Preferir modos baseados em palavras/linhas
        items = parse_items_from_words(pdf_path)
        if not items:
            items = parse_items_from_text(pdf_path)
        if not items:
            items = parse_items_from_tables(df)
    else:
        items = parse_items_from_tables(df)
        if not items:
            items = parse_items_from_words(pdf_path)
        if not items:
            items = parse_items_from_text(pdf_path)

    # Enriquecer datas faltantes cruzando com parsers alternativos (words/text)
    def sign_key(it: ParsedItem) -> tuple:
        # Chave de match robusta sem depender de paciente: codigo (se houver), procedimento, qtd e valores
        proc = (it.procedimento or '').strip()[:80].lower()
        cod = (it.codigo or '').strip().lower()
        def rf(x):
            try:
                return round(float(x), 2) if x is not None else None
            except Exception:
                return None
        q = rf(it.quantidade)
        vp = rf(it.valor_produzido)
        imp = rf(it.imposto)
        liq = rf(it.valor_liquido if it.valor_liquido is not None else ((it.valor_produzido or 0) - (it.imposto or 0)))
        return (cod, proc, q, vp, imp, liq)

    missing = [it for it in items if not (it.data or '').strip()]
    if missing:
        # tentar via words
        try:
            words_items = parse_items_from_words(pdf_path)
        except Exception:
            words_items = []
        dates_by_sig: dict[tuple, str] = {}
        for wi in words_items:
            if wi.data:
                dates_by_sig[sign_key(wi)] = wi.data
        # fallback text
        if not dates_by_sig:
            try:
                text_items = parse_items_from_text(pdf_path)
            except Exception:
                text_items = []
            for ti in text_items:
                if ti.data:
                    dates_by_sig[sign_key(ti)] = ti.data

        # preencher a partir de assinaturas
        for it in items:
            if not (it.data or '').strip():
                d = dates_by_sig.get(sign_key(it))
                if d:
                    it.data = d
    # Último reforço: buscar linha no texto da página usando trio monetário (produzido, imposto, líquido)
    if any(not (it.data or '').strip() for it in items):
        try:
            with pdfplumber.open(str(pdf_path)) as pdf:
                page_lines: dict[int, list[str]] = {}
                for pi, page in enumerate(pdf.pages, start=1):
                    tx = page.extract_text() or ''
                    page_lines[pi] = [l for l in tx.splitlines() if l.strip()]

            def fmt_ptbr(val: float | None) -> list[str]:
                if val is None:
                    return []
                try:
                    v = round(float(val), 2)
                except Exception:
                    return []
                # '1234,50' e '1.234,50'
                s = f"{v:,.2f}"  # '1,234.50'
                s = s.replace(',', 'X').replace('.', ',').replace('X', '.')
                no_thousand = s.replace('.', '') if '.' in s and s.count(',') == 1 else s
                variants = {s}
                variants.add(no_thousand)
                return list(variants)

            for it in items:
                if (it.data or '').strip():
                    continue
                lines = page_lines.get(getattr(it, 'page', 0) or 0) or []
                vp_vars = fmt_ptbr(it.valor_produzido)
                imp_vars = fmt_ptbr(it.imposto)
                liq_vars = fmt_ptbr(it.valor_liquido if it.valor_liquido is not None else ((it.valor_produzido or 0) - (it.imposto or 0)))
                if not (vp_vars and imp_vars and liq_vars):
                    continue
                found_line = None
                for ln in lines:
                    if any(v in ln for v in vp_vars) and any(v in ln for v in imp_vars) and any(v in ln for v in liq_vars):
                        found_line = ln
                        break
                if found_line:
                    d = _find_date(found_line)
                    if d:
                        it.data = d
        except Exception:
            pass
    return header, items
