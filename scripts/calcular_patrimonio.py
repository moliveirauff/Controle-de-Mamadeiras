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

def get_base_name(full_name):
    if "_" in full_name: return full_name.split("_")[0]
    return full_name

def getMonthLabel(key):
    if not key: return '-'
    y, m = key.split('-')
    return f"{m}/{y}"

def load_json(filename):
    path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(path): return None
    with open(path, 'r', encoding='utf-8') as f: return json.load(f)

def run():
    print("🚀 Iniciando processamento patrimonial v3.50 (Reestruturação)...")
    
    movimentacoes_data = load_json("movimentacoes_financeiras.json")
    cotacoes_data = load_json("invest_cotacoes_mensais.json")
    dividendos_data = load_json("dividendos_historico.json")
    ativos_data = load_json("ativos_financeiros.json")
    benchmarks_data = load_json("benchmarks.json")
    meta_alocacao_data = load_json("meta_alocacao.json")

    if not all([movimentacoes_data, cotacoes_data, dividendos_data, ativos_data]):
        print("❌ Erro: Dados base incompletos.")
        return

    movs = sorted(movimentacoes_data.get("movimentacoes", []), key=lambda x: x["data"])
    divs = sorted(dividendos_data.get("movimentacoes", []), key=lambda x: x["data"])
    base_class_map = {a["nome"]: a["macro_classe"] for a in ativos_data.get("ativos", [])}
    categorias_unicas = sorted(list(set(list(base_class_map.values()) + ["9_uncategorized"])))
    
    TIPOS_SOMA = ['APORTE', 'APORTE (Ajuste Zeramento)', 'COMPRA']
    TIPOS_SUBTRAI = ['RETIRADA', 'RETIRADA (Ajuste Zeramento)', 'RESGATE', 'VENDA']

    # Benchmarks lookup
    bench_indices = {i["mes"]: i for i in benchmarks_data.get("indices", [])}

    # --- PROCESSAMENTO TEMPORAL ---
    start_date = date(2012, 1, 1)
    end_date = date.today()
    current = start_date
    months = []
    while current <= end_date:
        months.append(current.strftime("%Y-%m"))
        current += relativedelta(months=1)

    # State variables
    positions = defaultdict(float) 
    aportes_liquidos_per_asset = defaultdict(float) 
    
    # Global accumulators
    total_aportes_geral = 0.0
    total_retiradas_geral = 0.0
    total_divs_acumulados = 0.0
    
    # Yearly metrics
    evolucao_anual = []
    evolucao_anual_por_cat = {cat: [] for cat in categorias_unicas}
    aportes_anuais_detalhe = []
    lucro_anual_reais = []
    rentabilidade_anual_comparativa = []
    
    # Monthly metrics
    evolucao_mensal_full = []
    evolucao_mensal_por_cat = {cat: [] for cat in categorias_unicas}
    aportes_mensais_detalhe = []
    
    mov_idx = 0
    div_idx = 0
    pat_anterior = 0.0
    
    print(f"📊 Processando {len(months)} meses...")

    for month_key in months:
        year_val, month_val = map(int, month_key.split("-"))
        last_day = (datetime(year_val, month_val, 1) + relativedelta(months=1, days=-1)).date()
        
        # Mudar estado para o mês
        aportes_mes = 0.0
        retiradas_mes = 0.0
        divs_mes = 0.0
        divs_mes_por_cat = defaultdict(float)
        aportes_mes_por_cat = defaultdict(float)
        retiradas_mes_por_cat = defaultdict(float)
        
        # 1. Movimentações
        while mov_idx < len(movs):
            m = movs[mov_idx]
            m_date = datetime.strptime(m["data"], "%Y-%m-%d").date()
            if m_date > last_day: break
            asset_full = m["ativo"]
            qty = float(m.get("quantidade", 0))
            valor_mov = m["valor_total"]
            cat = base_class_map.get(asset_full) or base_class_map.get(get_base_name(asset_full), "9_uncategorized")

            if m["tipo"] in TIPOS_SOMA:
                positions[asset_full] += qty
                aportes_liquidos_per_asset[asset_full] += valor_mov
                aportes_mes += valor_mov
                aportes_mes_por_cat[cat] += valor_mov
                total_aportes_geral += valor_mov
            elif m["tipo"] in TIPOS_SUBTRAI:
                positions[asset_full] -= qty
                aportes_liquidos_per_asset[asset_full] -= valor_mov
                retiradas_mes += valor_mov
                retiradas_mes_por_cat[cat] += valor_mov
                total_retiradas_geral += valor_mov
            mov_idx += 1

        # 2. Dividendos
        while div_idx < len(divs):
            d = divs[div_idx]
            d_date = datetime.strptime(d["data"], "%Y-%m-%d").date()
            if d_date > last_day: break
            val = float(d["valor_total"])
            ticker = get_base_name(d["ativo"])
            cat = base_class_map.get(d["ativo"]) or base_class_map.get(ticker, "9_uncategorized")
            divs_mes += val
            divs_mes_por_cat[cat] += val
            total_divs_acumulados += val
            div_idx += 1

        # 3. Valuation
        pat_mes_total = 0.0
        pat_por_cat_mes = {cat: 0.0 for cat in categorias_unicas}
        for asset_full, qty in positions.items():
            if qty <= 0.0001: continue
            asset_cots = cotacoes_data.get(asset_full, {}) or cotacoes_data.get(get_base_name(asset_full), {})
            price = asset_cots.get(f"{MESES_PT[month_val]}/{year_val}", 0.0)
            if not price:
                try:
                    valid = {k: v for k, v in asset_cots.items() if v is not None and v > 0}
                    past = [k for k in valid.keys() if (datetime.strptime(k, "%b/%Y").date() if '/' in k else date.min) <= last_day] # Simplified check
                    price = valid[max(past)] if past else 0.0
                except: price = 0.0
            
            valor = qty * price
            pat_mes_total += valor
            cat = base_class_map.get(asset_full) or base_class_map.get(get_base_name(asset_full), "9_uncategorized")
            pat_por_cat_mes[cat] += valor

        # 4. Storage Mensal
        evolucao_mensal_full.append({"mes": month_key, "patrimonio": round(pat_mes_total, 2)})
        for cat in categorias_unicas:
            evolucao_mensal_por_cat[cat].append({"mes": month_key, "patrimonio": round(pat_por_cat_mes[cat], 2)})
        
        aportes_mensais_detalhe.append({
            "mes": month_key,
            "aporte_real": round(aportes_mes - retiradas_mes, 2),
            "dividendos": round(divs_mes, 2),
            "categorias": {cat: {"aporte_real": round(aportes_mes_por_cat[cat] - retiradas_mes_por_cat[cat], 2), "dividendos": round(divs_mes_por_cat[cat], 2)} for cat in categorias_unicas}
        })

        # 5. Storage Anual (31/Dez ou Hoje)
        if month_val == 12 or month_key == months[-1]:
            # Evolução
            evolucao_anual.append({"ano": year_val, "patrimonio": round(pat_mes_total, 2)})
            for cat in categorias_unicas:
                evolucao_anual_por_cat[cat].append({"ano": year_val, "patrimonio": round(pat_por_cat_mes[cat], 2)})
            
            # Aportes Anuais
            anual_data = [d for d in aportes_mensais_detalhe if d["mes"].startswith(str(year_val))]
            aport_r = sum(d["aporte_real"] for d in anual_data)
            divs_r = sum(d["dividendos"] for d in anual_data)
            aportes_anuais_detalhe.append({
                "ano": year_val,
                "aporte_real": round(aport_r, 2),
                "dividendos": round(divs_r, 2),
                "categorias": {cat: {"aporte_real": round(sum(d["categorias"][cat]["aporte_real"] for d in anual_data), 2), "dividendos": round(sum(d["categorias"][cat]["dividendos"] for d in anual_data), 2)} for cat in categorias_unicas}
            })

            # Lucro Nominal (R$) - Rentabilidade do período em dinheiro
            # Lucro = Variação Patrimônio - Aporte Líquido Real
            pat_inicio_ano = next((d["patrimonio"] for d in evolucao_anual if d["ano"] == year_val - 1), 0.0)
            valorizacao = (pat_mes_total - pat_inicio_ano) - aport_r - divs_r
            lucro_anual_reais.append({
                "ano": year_val,
                "valorizacao": round(valorizacao, 2),
                "dividendos": round(divs_r, 2),
                "total": round(valorizacao + divs_r, 2)
            })

            # Rentabilidade % Discreta vs CDI
            rent_ano = ( (pat_mes_total / (pat_inicio_ano + aport_r + divs_r)) - 1 ) * 100 if (pat_inicio_ano + aport_r + divs_r) > 0 else 0
            # CDI do ano (estimado ou do benchmarks.json)
            cdi_ano = 0.0
            for d_mes in [m for m in bench_indices if m.startswith(str(year_val))]:
                cdi_ano += bench_indices[d_mes].get("cdi", 0.0)
            
            rentabilidade_anual_comparativa.append({
                "ano": year_val,
                "carteira": round(rent_ano, 2),
                "cdi": round(cdi_ano, 2)
            })

    # --- FINAL EXPORT ---
    pat_atual = evolucao_mensal_full[-1]["patrimonio"]
    liq_total = total_aportes_geral - total_retiradas_geral
    
    ranking = []
    for asset_full, qty in positions.items():
        if qty <= 0.001: continue
        base_name = get_base_name(asset_full)
        cat = base_class_map.get(asset_full) or base_class_map.get(base_name, "9_uncategorized")
        cot_data = cotacoes_data.get(asset_full, {}) or cotacoes_data.get(base_name, {})
        price = cot_data.get(f"{MESES_PT[int(months[-1].split('-')[1])]}/{months[-1].split('-')[0]}", 0) or 0
        ranking.append({
            "ticker": asset_full, "quantidade": round(qty, 4),
            "investido": round(aportes_liquidos_per_asset[asset_full], 2),
            "atual": round(qty * price, 2),
            "categoria": cat
        })
    ranking.sort(key=lambda x: x["atual"], reverse=True)

    output = {
        "kpis": {
            "patrimonio_total": round(pat_atual, 2),
            "aportes_liquido_total": round(liq_total, 2),
            "rentabilidade_nominal": round(((pat_atual - liq_total)/liq_total*100), 2) if liq_total > 0 else 0,
            "cagr_5anos": round((((pat_atual / evolucao_mensal_full[-61]["patrimonio"])**(1/5))-1)*100, 2) if len(evolucao_mensal_full) >= 61 and evolucao_mensal_full[-61]["patrimonio"] > 0 else 0
        },
        "anual": {
            "evolucao": evolucao_anual,
            "evolucao_por_cat": evolucao_anual_por_cat,
            "aportes": aportes_anuais_detalhe,
            "lucro_reais": lucro_anual_reais,
            "rentabilidade_pct": rentabilidade_anual_comparativa
        },
        "mensal": {
            "evolucao": evolucao_mensal_full,
            "evolucao_por_cat": evolucao_mensal_por_cat,
            "aportes": aportes_mensais_detalhe
        },
        "alocacao": [], # Already handled by frontend from existing data
        "ranking_ativos": ranking,
        "last_update": datetime.now().strftime("%Y-%m-%d %H:%M")
    }

    # Recalcular Alocação baseada no snapshot final
    pat_cat_atual = defaultdict(float)
    for r in ranking: pat_cat_atual[r["categoria"]] += r["atual"]
    for cid, pm in meta_alocacao_data.get("metas", {}).items():
        real = pat_cat_atual.get(cid, 0)
        meta = pat_atual * pm
        output["alocacao"].append({"categoria": cid, "meta_rs": round(meta, 2), "real_rs": round(real, 2)})

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"✅ Dashboard JSON v3.50 gerado!")

if __name__ == "__main__": run()
