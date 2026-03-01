#!/usr/bin/env python3
"""
Gera data/argos_dashboard.json a partir de data/argos_historico.json
Lógica de valuation: cada aporte corrigido em 0,1% a.m. composto
Participação de Mauricio: 1/3 exato
"""
import json
from datetime import datetime
from dateutil.relativedelta import relativedelta
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUT    = os.path.join(BASE_DIR, 'data', 'argos_historico.json')
OUTPUT   = os.path.join(BASE_DIR, 'data', 'argos_dashboard.json')

PARTICIPACAO = 1 / 3
TAXA_MENSAL  = 0.001   # 0,1% a.m.

def meses_entre(data_inicio, data_fim):
    d = datetime.strptime(data_inicio, '%Y-%m-%d')
    delta = relativedelta(data_fim, d)
    return delta.years * 12 + delta.months

def corrigir(valor, n_meses):
    return valor * ((1 + TAXA_MENSAL) ** n_meses)

def main():
    with open(INPUT, encoding='utf-8') as f:
        hist = json.load(f)

    movs  = hist['movimentacoes']
    hoje  = datetime.now()
    hoje_ym = hoje.strftime('%Y-%m')

    # KPIs
    total_investido = sum(m['valor_total'] for m in movs)
    valor_mercado   = sum(corrigir(m['valor_total'], meses_entre(m['data'], hoje)) for m in movs)
    rendimento      = valor_mercado - total_investido
    rentabilidade   = (rendimento / total_investido * 100) if total_investido else 0
    valuation_total = valor_mercado * 3

    # Serie mensal
    mes_ini = datetime.strptime(movs[0]['data'], '%Y-%m-%d').replace(day=1)
    mes_fim = hoje.replace(day=1)

    series = []
    cur = mes_ini
    while cur <= mes_fim:
        ym = cur.strftime('%Y-%m')
        aportes_acum = sum(m['valor_total'] for m in movs if m['data'][:7] <= ym)
        aportes_mes  = sum(m['valor_total'] for m in movs if m['data'][:7] == ym)
        vm_acum = sum(
            corrigir(m['valor_total'], meses_entre(m['data'], cur))
            for m in movs if m['data'][:7] <= ym
        )
        series.append({
            'mes':              ym,
            'aportes_mes':      round(aportes_mes, 2),
            'aportes_acum':     round(aportes_acum, 2),
            'vm_minha_parte':   round(vm_acum, 2),
            'valuation_empresa': round(vm_acum * 3, 2),
        })
        cur += relativedelta(months=1)

    # Por aporte
    por_aporte = []
    for m in movs:
        n  = meses_entre(m['data'], hoje)
        vc = corrigir(m['valor_total'], n)
        por_aporte.append({
            'data':            m['data'],
            'valor_aportado':  round(m['valor_total'], 2),
            'meses_desde':     n,
            'valor_corrigido': round(vc, 2),
            'rendimento':      round(vc - m['valor_total'], 2),
        })

    output = {
        'gerado_em':   hoje.isoformat(),
        'metodologia': 'Aportes corrigidos a 0,1% a.m. composto. Participacao: 1/3. Valuation empresa = minha parte x 3.',
        'kpis': {
            'total_investido':   round(total_investido, 2),
            'valor_mercado':     round(valor_mercado, 2),
            'valuation_empresa': round(valuation_total, 2),
            'participacao_pct':  round(PARTICIPACAO * 100, 4),
            'rendimento':        round(rendimento, 2),
            'rentabilidade_pct': round(rentabilidade, 4),
            'ultimo_mes':        hoje_ym,
        },
        'por_mes':    series,
        'por_aporte': por_aporte,
    }

    with open(OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f'argos_dashboard.json gerado — {len(series)} meses, {len(por_aporte)} aportes')
    print(f'  Total Investido:   R$ {total_investido:,.2f}')
    print(f'  Valor Minha Parte: R$ {valor_mercado:,.2f}')
    print(f'  Valuation Empresa: R$ {valuation_total:,.2f}')
    print(f'  Rendimento:        R$ {rendimento:,.2f} ({rentabilidade:.2f}%)')

if __name__ == '__main__':
    main()
