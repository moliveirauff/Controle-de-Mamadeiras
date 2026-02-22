import json
import os
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
from collections import defaultdict

# --- CONFIGURAÇÃO DE CAMINHOS ---
DATA_DIR = "/root/.openclaw/familia-donato-suarez/data/"
OUTPUT_FILE = DATA_DIR + "dashboard_investimentos.json"

# --- AUXILIARES ---
MESES_PT = {
    1: 'jan', 2: 'fev', 3: 'mar', 4: 'abr', 5: 'mai', 6: 'jun',
    7: 'jul', 8: 'ago', 9: 'set', 10: 'out', 11: 'nov', 12: 'dez'
}

# Benchmarks Oficiais (Anual %)
BENCHMARKS = {
    "cdi": {2012: 8.48, 2013: 8.06, 2014: 10.81, 2015: 13.24, 2016: 14.01, 2017: 9.95, 2018: 6.42, 2019: 5.96, 2020: 2.76, 2021: 4.42, 2022: 12.39, 2023: 13.04, 2024: 11.24, 2025: 12.15, 2026: 12.0},
    "ifix": {2021: 1.3, 2022: 2.2, 2023: 15.5, 2024: 1.4, 2025: 5.0, 2026: 5.0},
    "dolar": {2021: 7.3, 2022: -6.5, 2023: -8.1, 2024: 14.7, 2025: 2.0, 2026: 2.0},
    "imovel": {2021: 5.3, 2022: 6.1, 2023: 5.1, 2024: 5.7, 2025: 5.0, 2026: 5.0}
}

def get_base_name(full_name):
    if "_" in full_name: return full_name.split("_")[0]
    return full_name

def load_json(filename):
    path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(path): return None
    with open(path, 'r', encoding='utf-8') as f: return json.load(f)

def run():
    print("🚀 Iniciando processamento patrimonial v3.52...")
    
    movimentacoes_data = load_json("movimentacoes_financeiras.json")
    cotacoes_data = load_json("invest_cotacoes_mensais.json")
    dividendos_data = load_json("dividendos_historico.json")
    ativos_data = load_json("ativos_financeiros.json")
    meta_alocacao_data = load_json("meta_alocacao.json")

    if not all([movimentacoes_data, cotacoes_data, dividendos_data, ativos_data]):
        print("❌ Erro: Dados base incompletos.")
        return

    movs = sorted(movimentacoes_data.get("movimentacoes", []), key=lambda x: x["data"])
    divs = sorted(dividendos_data.get("movimentacoes", []), key=lambda x: x["data"])
    base_class_map = {a["nome"]: a["macro_classe"] for a in ativos_data.get("ativos", [])}
    
    TIPOS_SOMA = ['APORTE', 'APORTE (Ajuste Zeramento)', 'COMPRA']
    TIPOS_SUBTRAI = ['RETIRADA', 'RETIRADA (Ajuste Zeramento)', 'RESGATE', 'VENDA']

    start_date = date(2012, 1, 1)
    end_date = date.today()
    current = start_date
    months = []
    while current <= end_date:
        months.append(current.strftime("%Y-%m"))
        current += relativedelta(months=1)

    positions = defaultdict(float) 
    aportes_liquidos_per_asset = defaultdict(float) 
    total_divs_acumulados = 0.0
    
    evolucao_anual = []
    evolucao_mensal_full = []
    lucro_mensal_reais = []
    aportes_mensais_detalhe = []
    
    mov_idx = 0
    div_idx = 0
    pat_anterior_mes = 0.0
    
    print(f"📊 Processando {len(months)} meses...")

    for month_key in months:
        year_val, month_val = map(int, month_key.split("-"))
        last_day = (datetime(year_val, month_val, 1) + relativedelta(months=1, days=-1)).date()
        
        aportes_mes = 0.0
        retiradas_mes = 0.0
        divs_mes = 0.0
        
        # 1. Movimentações
        while mov_idx < len(movs):
            m = movs[mov_idx]
            if datetime.strptime(m["data"], "%Y-%m-%d").date() > last_day: break
            asset_full = m["ativo"]
            qty = float(m.get("quantidade", 0))
            valor_mov = m["valor_total"]
            if m["tipo"] in TIPOS_SOMA:
                positions[asset_full] += qty
                aportes_liquidos_per_asset[asset_full] += valor_mov
                aportes_mes += valor_mov
            elif m["tipo"] in TIPOS_SUBTRAI:
                positions[asset_full] -= qty
                aportes_liquidos_per_asset[asset_full] -= valor_mov
                retiradas_mes += valor_mov
            mov_idx += 1

        # 2. Dividendos
        while div_idx < len(divs):
            d = divs[div_idx]
            if datetime.strptime(d["data"], "%Y-%m-%d").date() > last_day: break
            val = float(d["valor_total"])
            divs_mes += val
            total_divs_acumulados += val
            div_idx += 1

        # 3. Valuation
        pat_mes_total = 0.0
        for asset_full, qty in positions.items():
            if qty <= 0.0001: continue
            asset_cots = cotacoes_data.get(asset_full, {}) or cotacoes_data.get(get_base_name(asset_full), {})
            price = asset_cots.get(f"{MESES_PT[month_val]}/{year_val}", 0.0)
            if not price:
                try:
                    valid = {k: v for k, v in asset_cots.items() if v is not None and v > 0}
                    price = valid[max([k for k in valid.keys() if (datetime.strptime(k, "%b/%Y").date() if '/' in k else date.min) <= last_day])]
                except: price = 0.0
            pat_mes_total += qty * price

        # 4. Cálculo de Lucro e Aportes (Lógica Mauricio)
        liq_mes = aportes_mes - retiradas_mes
        variacao_pat = pat_mes_total - pat_anterior_mes
        
        # Aporte Total Mensal = liq_mes (que já inclui reinvestimento se estiver no JSON)
        # Se os dividendos são reinvestidos e aparecem como APORTE, subtraímos para achar o "Dinheiro Novo"
        dinheiro_novo_mes = liq_mes - divs_mes
        
        # Valorização = Crescimento orgânico que não veio de aporte
        valorizacao_mes = variacao_pat - liq_mes

        lucro_mensal_reais.append({
            "mes": month_key,
            "valorizacao": round(valorizacao_mes, 2),
            "dividendos": round(divs_mes, 2),
            "total": round(valorizacao_mes + divs_mes, 2)
        })
        
        aportes_mensais_detalhe.append({
            "mes": month_key,
            "aporte_real": round(dinheiro_novo_mes, 2),
            "dividendos": round(divs_mes, 2),
            "total": round(liq_mes, 2)
        })

        evolucao_mensal_full.append({"mes": month_key, "patrimonio": round(pat_mes_total, 2)})
        if month_val == 12 or month_key == months[-1]:
            evolucao_anual.append({"ano": year_val, "patrimonio": round(pat_mes_total, 2)})

        pat_anterior_mes = pat_mes_total

    # 5. Consolidação Anual
    lucro_anual_reais = []
    aportes_anuais_detalhe = []
    rentabilidade_anual_comp = []
    
    anos = sorted(list(set(int(m.split('-')[0]) for m in months)))
    for ano in anos:
        m_lucro = [d for d in lucro_mensal_reais if d["mes"].startswith(str(ano))]
        m_aport = [d for d in aportes_mensais_detalhe if d["mes"].startswith(str(ano))]
        
        val_ano = sum(d["valorizacao"] for d in m_lucro)
        div_ano = sum(d["dividendos"] for d in m_lucro)
        new_ano = sum(d["aporte_real"] for d in m_aport)
        tot_ano = sum(d["total"] for d in m_aport)

        lucro_anual_reais.append({"ano": ano, "valorizacao": round(val_ano, 2), "dividendos": round(div_ano, 2), "total": round(val_ano + div_ano, 2)})
        aportes_anuais_detalhe.append({"ano": ano, "aporte_real": round(new_ano, 2), "dividendos": round(div_ano, 2), "total": round(tot_ano, 2)})
        
        pat_ini = next((d["patrimonio"] for d in evolucao_anual if d["ano"] == ano - 1), 0.0)
        pat_fim = next((d["patrimonio"] for d in evolucao_anual if d["ano"] == ano), 0.0)
        denominador = (pat_ini + tot_ano)
        r_sem = ((pat_fim - div_ano - denominador) / denominador * 100) if denominador > 0 else 0
        r_com = ((pat_fim - denominador) / denominador * 100) if denominador > 0 else 0
        
        rentabilidade_anual_comp.append({
            "ano": ano, "sem_dividendos": round(r_sem, 2), "com_dividendos": round(r_com, 2),
            "cdi": BENCHMARKS["cdi"].get(ano, 0.0), "ifix": BENCHMARKS["ifix"].get(ano, 0.0),
            "dolar": BENCHMARKS["dolar"].get(ano, 0.0), "imovel": BENCHMARKS["imovel"].get(ano, 0.0)
        })

    # --- EXPORT ---
    output = {
        "kpis": {
            "patrimonio_total": round(evolucao_mensal_full[-1]["patrimonio"], 2),
            "aportes_liquido_total": round(sum(d["total"] for d in aportes_mensais_detalhe), 2),
            "rentabilidade_nominal": round(((evolucao_mensal_full[-1]["patrimonio"] - sum(d["total"] for d in aportes_mensais_detalhe))/sum(d["total"] for d in aportes_mensais_detalhe)*100), 2) if sum(d["total"] for d in aportes_mensais_detalhe) > 0 else 0,
            "cagr_5anos": round((((evolucao_mensal_full[-1]["patrimonio"] / evolucao_mensal_full[-61]["patrimonio"])**(1/5))-1)*100, 2) if len(evolucao_mensal_full) >= 61 else 0
        },
        "anual": {"evolucao": evolucao_anual, "aportes": aportes_anuais_detalhe, "lucro_reais": lucro_anual_reais, "rentabilidade_pct": rentabilidade_anual_comp},
        "mensal": {"evolucao": evolucao_mensal_full, "aportes": aportes_mensais_detalhe, "lucro_reais": lucro_mensal_reais},
        "last_update": datetime.now().strftime("%Y-%m-%d %H:%M")
    }

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"✅ Dashboard JSON v3.52 gerado!")

if __name__ == "__main__": run()
