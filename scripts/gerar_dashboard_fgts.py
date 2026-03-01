#!/usr/bin/env python3
"""Gera fgts_dashboard.json a partir de fgts_historico.json"""

import json
from datetime import datetime
from pathlib import Path
from collections import defaultdict

BASE = Path(__file__).resolve().parent.parent / "data"

def load_json(name):
    with open(BASE / name, encoding="utf-8") as f:
        return json.load(f)

def save_json(name, data):
    with open(BASE / name, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"✅ Salvo em: {BASE / name}")

def main():
    print("📊 Gerando Dashboard FGTS...")
    hist = load_json("fgts_historico.json")
    movs = sorted(hist["movimentacoes"], key=lambda m: m["data"])

    # --- Running balances by month ---
    # cotas:        saldo real (aportes - retiradas)
    # cotas_brutas: saldo teórico (apenas aportes, nunca desconta retiradas — base rescisória)
    monthly = defaultdict(lambda: {"cotas": 0, "cotas_brutas": 0, "aportes": 0, "retiradas": 0, "preco": 0})
    running_cotas = 0
    running_cotas_brutas = 0  # nunca decrementado — base para multa rescisória
    last_price = 1.0

    for m in movs:
        mes = m["data"][:7]  # YYYY-MM
        p = m["preco_unitario"]
        if p > 0:
            last_price = p
        monthly[mes]["preco"] = last_price

        if m["tipo"] == "APORTE":
            running_cotas += m["quantidade"]
            running_cotas_brutas += m["quantidade"]  # base rescisória cresce com aportes
            monthly[mes]["aportes"] += m["valor_total"]
        elif m["tipo"] == "RETIRADA":
            running_cotas -= m["quantidade"]          # saldo real diminui
            # cotas_brutas NÃO diminui — saques não reduzem base rescisória (CLT Art. 18 §1º)
            monthly[mes]["retiradas"] += m["valor_total"]

        monthly[mes]["cotas"] = running_cotas
        monthly[mes]["cotas_brutas"] = running_cotas_brutas

    # Build sorted month list
    months_sorted = sorted(monthly.keys())

    # Accumulate and build por_mes
    por_mes = []
    acum_aportes = 0
    acum_retiradas = 0

    for mes in months_sorted:
        d = monthly[mes]
        acum_aportes += d["aportes"]
        acum_retiradas += d["retiradas"]
        saldo = d["cotas"] * d["preco"]
        rendimento_acum = saldo + acum_retiradas - acum_aportes

        por_mes.append({
            "mes": mes,
            "saldo": round(saldo, 2),
            "aportes_mes": round(d["aportes"], 2),
            "retiradas_mes": round(d["retiradas"], 2),
            "aportes_acum": round(acum_aportes, 2),
            "retiradas_acum": round(acum_retiradas, 2),
            "rendimento_acum": round(rendimento_acum, 2),
        })

    # --- Por ano ---
    por_ano = []
    anos = sorted(set(m["mes"][:4] for m in por_mes))
    prev_rendimento_acum = 0.0
    prev_saldo_fim = 0.0

    for ano in anos:
        meses_ano = [m for m in por_mes if m["mes"][:4] == ano]
        ultimo = meses_ano[-1]
        aportes_ano = sum(m["aportes_mes"] for m in meses_ano)
        retiradas_ano = sum(m["retiradas_mes"] for m in meses_ano)

        # Rendimento em R$ gerado NESTE ano (não acumulado)
        rendimento_ano = ultimo["rendimento_acum"] - prev_rendimento_acum

        # % de rendimento no ano: rendimento_ano / saldo início do ano
        # Para 2012 (primeiro ano) usa aportes como base
        if prev_saldo_fim > 0:
            rendimento_pct_ano = (rendimento_ano / prev_saldo_fim) * 100
        elif aportes_ano > 0:
            rendimento_pct_ano = (rendimento_ano / aportes_ano) * 100
        else:
            rendimento_pct_ano = 0.0

        # Saldo teórico rescisório: cotas_brutas × preco (sem descontar saques)
        preco_fim_ano = monthly[meses_ano[-1]["mes"]]["preco"]
        cotas_brutas_fim_ano = monthly[meses_ano[-1]["mes"]]["cotas_brutas"]
        saldo_teorico_rescisao = cotas_brutas_fim_ano * preco_fim_ano

        por_ano.append({
            "ano": ano,
            "saldo_fim_ano": ultimo["saldo"],
            "aportes_ano": round(aportes_ano, 2),
            "retiradas_ano": round(retiradas_ano, 2),
            "rendimento_acum": ultimo["rendimento_acum"],
            "rendimento_ano": round(rendimento_ano, 2),
            "rendimento_pct_ano": round(rendimento_pct_ano, 2),
            "saldo_teorico_rescisao": round(saldo_teorico_rescisao, 2),
        })

        prev_rendimento_acum = ultimo["rendimento_acum"]
        prev_saldo_fim = ultimo["saldo"]

    # --- KPIs ---
    ultimo_mes = por_mes[-1]
    saldo_total = ultimo_mes["saldo"]

    # Saldo teórico atual para rescisão
    ultimo_mes_key = months_sorted[-1]
    cotas_brutas_atual = monthly[ultimo_mes_key]["cotas_brutas"]
    preco_atual = monthly[ultimo_mes_key]["preco"]
    saldo_teorico_atual = cotas_brutas_atual * preco_atual

    # Investido 12M
    now = datetime.now()
    cutoff = f"{now.year - 1}-{now.month:02d}"
    investido_12m = sum(m["aportes_mes"] for m in por_mes if m["mes"] >= cutoff)

    # --- Rescisão por ano (base teórica) ---
    rescisao_por_ano = []
    for a in por_ano:
        st    = a["saldo_teorico_rescisao"]
        multa = round(st * 0.40, 2)
        total = round(a["saldo_fim_ano"] + multa, 2)   # saldo real + multa 40%
        rescisao_por_ano.append({
            "ano": a["ano"],
            "saldo_teorico": st,
            "multa_40pct": multa,
            "total_rescisao": total,
        })

    # --- Output ---
    output = {
        "gerado_em": datetime.now().isoformat(),
        "kpis": {
            "saldo_total": round(saldo_total, 2),
            "saldo_teorico_rescisao": round(saldo_teorico_atual, 2),
            "multa_40pct_teorico": round(saldo_teorico_atual * 0.40, 2),
            "investido_12m": round(investido_12m, 2),
            "ultimo_mes": ultimo_mes["mes"],
        },
        "por_ano": por_ano,
        "por_mes": por_mes,
        "rescisao": {
            "metodologia": (
                "Multa rescisória = 40% × saldo teórico FGTS (todos os depósitos corrigidos, "
                "independente de saques). Saques reduzem o saldo real, mas não a base de cálculo "
                "da multa. Base legal: CLT Art. 18 §1º."
            ),
            "saldo_teorico_atual": round(saldo_teorico_atual, 2),
            "multa_40pct": round(saldo_teorico_atual * 0.40, 2),
            "por_ano": rescisao_por_ano,
        },
    }

    save_json("fgts_dashboard.json", output)

    print(f"\n📊 KPIs:")
    print(f"  • Saldo Real:          R$ {saldo_total:,.2f}")
    print(f"  • Saldo Teórico:       R$ {saldo_teorico_atual:,.2f}  (base rescisória)")
    print(f"  • Multa 40% (teórico): R$ {saldo_teorico_atual * 0.40:,.2f}")
    print(f"  • Investido 12M:       R$ {investido_12m:,.2f}")
    print(f"  • Período: {months_sorted[0]} a {months_sorted[-1]}")
    print(f"  • {len(por_mes)} meses, {len(por_ano)} anos")
    print(f"\n📈 Rendimento por ano (sample):")
    for a in por_ano[-5:]:
        print(f"  {a['ano']}: R$ {a['rendimento_ano']:,.2f} ({a['rendimento_pct_ano']:.2f}%)")

if __name__ == "__main__":
    main()
