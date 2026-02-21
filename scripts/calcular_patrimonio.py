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
    print("🚀 Iniciando processamento patrimonial v3.7...")
    
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
    
    TIPOS_SOMA = ['APORTE', 'APORTE (Ajuste Zeramento)', 'COMPRA']
    TIPOS_SUBTRAI = ['RETIRADA', 'RETIRADA (Ajuste Zeramento)', 'RESGATE', 'VENDA']

    # --- PROCESSAMENTO TEMPORAL ---
    start_date = date(2012, 1, 1)
    end_date = date.today()
    current = start_date
    months = []
    while current <= end_date:
        months.append(current.strftime("%Y-%m"))
        current += relativedelta(months=1)

    positions = defaultdict(float) 
    aportes_liquidos_per_asset = defaultdict(float)  # Renomeado: usar valor_total direto
    total_qty_bought_per_asset = defaultdict(float)
    total_divs_accumulated = 0.0
    total_divs_per_year = defaultdict(float)
    
    evolucao_mensal = []
    evolucao_anual = []
    aportes_anuais = defaultdict(float)
    rentabilidade_anual_data = [] # Para Gráfico 4
    
    mov_idx = 0
    div_idx = 0
    
    print(f"📊 Processando {len(months)} meses...")

    for month_key in months:
        year_val, month_val = map(int, month_key.split("-"))
        last_day = (datetime(year_val, month_val, 1) + relativedelta(months=1, days=-1)).date()
        
        while mov_idx < len(movs):
            m = movs[mov_idx]
            m_date = datetime.strptime(m["data"], "%Y-%m-%d").date()
            if m_date > last_day: break
            asset_full = m["ativo"]
            qty = float(m.get("quantidade", 0))
            price = float(m.get("preco_unitario", 0))
            taxas = float(m.get("taxas", 0))
            if m["tipo"] in TIPOS_SOMA:
                positions[asset_full] += qty
                valor_mov = m.get("valor_total", (qty * price) + taxas)
                aportes_liquidos_per_asset[asset_full] += valor_mov
                total_qty_bought_per_asset[asset_full] += qty
                aportes_anuais[year_val] += valor_mov
            elif m["tipo"] in TIPOS_SUBTRAI:
                # Aportes Líquidos = Aportes - Retiradas (usar valor_total direto)
                valor_mov = m.get("valor_total", qty * price)
                aportes_liquidos_per_asset[asset_full] -= valor_mov
                positions[asset_full] -= qty
                aportes_anuais[year_val] -= valor_mov
            mov_idx += 1

        while div_idx < len(divs):
            d = divs[div_idx]
            d_date = datetime.strptime(d["data"], "%Y-%m-%d").date()
            if d_date > last_day: break
            val = float(d["valor_total"])
            total_divs_accumulated += val
            total_divs_per_year[year_val] += val
            div_idx += 1

        # Valuation
        pat_mes = 0.0
        for asset_full, qty in positions.items():
            if qty <= 0.0001: continue
            # Tentar buscar cotação: primeiro com nome completo, depois com base_name
            asset_cots = cotacoes_data.get(asset_full, {})
            if not asset_cots:
                base_name = get_base_name(asset_full)
                asset_cots = cotacoes_data.get(base_name, {})
            cot_key = f"{MESES_PT[month_val]}/{year_val}"
            price = asset_cots.get(cot_key, 0.0)
            if price is None or price == 0.0:
                try:
                    def cot_to_date(k):
                        m_pt, y = k.split('/')
                        return date(int(y), next(n for n, v in MESES_PT.items() if v == m_pt), 1)
                    valid = {cot_to_date(k): v for k, v in asset_cots.items() if v is not None and v > 0}
                    past = [d for d in valid.keys() if d <= last_day]
                    price = valid[max(past)] if past else 0.0
                except Exception:
                    price = 0.0
            pat_mes += qty * price

        evolucao_mensal.append({"mes": month_key, "patrimonio": round(pat_mes, 2)})

        # Gráfico 4: Rentabilidade Anual (Series A e B)
        if month_val == 12 or month_key == months[-1]:
            evolucao_anual.append({"ano": year_val, "patrimonio": round(pat_mes, 2)})
            aportes_total = sum(v for v in aportes_liquidos_per_asset.values() if v > 0)
            rent_sem_div = ((pat_mes - aportes_total) / aportes_total * 100) if aportes_total > 0 else 0
            aportes_ajustado = aportes_total - total_divs_accumulated
            rent_com_div = ((pat_mes - aportes_ajustado) / aportes_ajustado * 100) if aportes_ajustado > 0 else 0
            rentabilidade_anual_data.append({
                "ano": year_val,
                "sem_dividendos": round(rent_sem_div, 2),
                "com_dividendos": round(rent_com_div, 2)
            })

    # === DEBUG: Verificar patrimônio do último mês ===
    print("\n🔍 DEBUG - Top 10 Ativos (último mês):")
    last_month = months[-1]
    year_val, month_val = map(int, last_month.split("-"))
    debug_values = []
    sem_cotacao = []
    for asset_full, qty in positions.items():
        if qty <= 0.001: continue
        # Buscar cotação: primeiro nome completo, depois base_name
        asset_cots = cotacoes_data.get(asset_full, {})
        base_name = get_base_name(asset_full)
        if not asset_cots:
            asset_cots = cotacoes_data.get(base_name, {})
        cot_key = f"{MESES_PT[month_val]}/{year_val}"
        price = asset_cots.get(cot_key, 0.0)
        if price is None or price == 0.0:
            # Buscar última cotação disponível
            try:
                def cot_to_date(k):
                    m_pt, y = k.split('/')
                    return date(int(y), next(n for n, v in MESES_PT.items() if v == m_pt), 1)
                valid = {cot_to_date(k): v for k, v in asset_cots.items() if v is not None and v > 0}
                last_day = (datetime(year_val, month_val, 1) + relativedelta(months=1, days=-1)).date()
                past = [d for d in valid.keys() if d <= last_day]
                price = valid[max(past)] if past else 0.0
                if price == 0.0:
                    sem_cotacao.append((base_name, qty))
            except Exception:
                price = 0.0
                sem_cotacao.append((base_name, qty))
        valor = qty * price
        debug_values.append((base_name, qty, price, valor))
    debug_values.sort(key=lambda x: x[3], reverse=True)
    for i, (name, qty, price, val) in enumerate(debug_values[:10], 1):
        print(f"  {i}. {name:30} | Cotas: {qty:10.2f} | Cotação: R$ {price:8.2f} | Valor: R$ {val:12,.2f}")
    total_debug = sum(x[3] for x in debug_values)
    print(f"\n💰 Patrimônio Total (calculado): R$ {total_debug:,.2f}")
    if sem_cotacao:
        print(f"\n⚠️  ATIVOS SEM COTAÇÃO ({len(sem_cotacao)}):")
        for name, qty in sem_cotacao[:20]:
            print(f"  - {name:30} | Cotas: {qty:10.2f}")
    print()

    # --- BENCHMARKS (Gráfico 6) ---
    bench_indices = {i["mes"]: i for i in benchmarks_data.get("indices", [])}
    
    def get_benchmark_series(window_months):
        period_months = months[-window_months:] if len(months) >= window_months else months
        series = {"carteira": [0.0], "cdi": [0.0], "ibov": [0.0], "ipca_plus_6": [0.0]}
        
        acc_cart = 1.0
        acc_cdi = 1.0
        acc_ibov = 1.0
        acc_meta = 1.0
        
        for i in range(1, len(period_months)):
            m_curr = period_months[i]
            m_prev = period_months[i-1]
            
            # Rent Carteira Mensal
            val_curr = next(x["patrimonio"] for x in evolucao_mensal if x["mes"] == m_curr)
            val_prev = next(x["patrimonio"] for x in evolucao_mensal if x["mes"] == m_prev)
            
            # Ajuste de aporte para rentabilidade (simplificado: remove aporte líquido do mês do valor final)
            y, m = map(int, m_curr.split("-"))
            # Nota: aportes_anuais está por ano. Precisaríamos de aportes mensais para precisão real.
            # Como o TRD foca em evolução acumulada, usaremos a variação do patrimônio como proxy.
            var_cart = (val_curr / val_prev - 1) if val_prev > 0 else 0
            acc_cart *= (1 + var_cart)
            
            # Buscar Benchmarks
            b = bench_indices.get(m_curr, {"cdi":0, "ibov":0, "ipca_plus_6":0})
            acc_cdi *= (1 + b.get("cdi", 0)/100)
            acc_ibov *= (1 + b.get("ibov", 0)/100)
            acc_meta *= (1 + b.get("ipca_plus_6", 0)/100)
            
            series["carteira"].append(round((acc_cart - 1) * 100, 2))
            series["cdi"].append(round((acc_cdi - 1) * 100, 2))
            series["ibov"].append(round((acc_ibov - 1) * 100, 2))
            series["ipca_plus_6"].append(round((acc_meta - 1) * 100, 2))
        
        return {"labels": [getMonthLabel(m) for m in period_months], "series": series}

    benchmarks_output = {
        "12m": get_benchmark_series(12),
        "24m": get_benchmark_series(24),
        "total": get_benchmark_series(len(months))
    }

    # --- EVOLUÇÃO POR CATEGORIA (para filtros dos gráficos 1 e 2) ---
    categorias_unicas = set(base_class_map.values())
    evolucao_mensal_por_cat = {cat: [] for cat in categorias_unicas}
    evolucao_anual_por_cat = {cat: [] for cat in categorias_unicas}
    
    # Processar novamente para gerar séries filtradas
    positions_temp = defaultdict(float)
    mov_idx_temp = 0
    
    for month_key in months:
        year_val, month_val = map(int, month_key.split("-"))
        last_day = (datetime(year_val, month_val, 1) + relativedelta(months=1, days=-1)).date()
        
        # Atualizar posições
        while mov_idx_temp < len(movs):
            m = movs[mov_idx_temp]
            m_date = datetime.strptime(m["data"], "%Y-%m-%d").date()
            if m_date > last_day: break
            asset_full = m["ativo"]
            qty = float(m.get("quantidade", 0))
            if m["tipo"] in TIPOS_SOMA:
                positions_temp[asset_full] += qty
            elif m["tipo"] in TIPOS_SUBTRAI:
                positions_temp[asset_full] -= qty
            mov_idx_temp += 1
        
        # Calcular patrimônio por categoria
        pat_por_cat = {cat: 0.0 for cat in categorias_unicas}
        for asset_full, qty in positions_temp.items():
            if qty <= 0.0001: continue
            asset_cots = cotacoes_data.get(asset_full, {})
            base_name = get_base_name(asset_full)
            if not asset_cots:
                asset_cots = cotacoes_data.get(base_name, {})
            cat = base_class_map.get(base_name, "7_alternativos_estratega")
            cot_key = f"{MESES_PT[month_val]}/{year_val}"
            price = asset_cots.get(cot_key, 0.0)
            if price is None or price == 0.0:
                try:
                    def cot_to_date(k):
                        m_pt, y = k.split('/')
                        return date(int(y), next(n for n, v in MESES_PT.items() if v == m_pt), 1)
                    valid = {cot_to_date(k): v for k, v in asset_cots.items() if v is not None and v > 0}
                    past = [d for d in valid.keys() if d <= last_day]
                    price = valid[max(past)] if past else 0.0
                except Exception:
                    price = 0.0
            pat_por_cat[cat] += qty * price
        
        # Salvar evolução mensal por categoria
        for cat in categorias_unicas:
            evolucao_mensal_por_cat[cat].append({"mes": month_key, "patrimonio": round(pat_por_cat[cat], 2)})
        
        # Salvar evolução anual por categoria
        if month_val == 12 or month_key == months[-1]:
            for cat in categorias_unicas:
                evolucao_anual_por_cat[cat].append({"ano": year_val, "patrimonio": round(pat_por_cat[cat], 2)})

    # --- FINAL EXPORT ---
    pat_atual = evolucao_mensal[-1]["patrimonio"]
    aportes_total_geral = sum(v for v in aportes_liquidos_per_asset.values() if v > 0)
    
    # Reuso da lógica de Alocação e Ranking do script anterior
    pat_cat_atual = defaultdict(float)
    ranking = []
    for asset_full, qty in positions.items():
        if qty <= 0.001: continue
        base_name = get_base_name(asset_full)
        cat = base_class_map.get(base_name, "7_alternativos_estratega")
        # Buscar cotação: primeiro nome completo, depois base_name
        cot_data = cotacoes_data.get(asset_full, {})
        if not cot_data:
            cot_data = cotacoes_data.get(base_name, {})
        price = cot_data.get(f"{MESES_PT[int(months[-1].split('-')[1])]}/{months[-1].split('-')[0]}", 0) or 0
        val_atual = qty * price
        pat_cat_atual[cat] += val_atual
        aporte_ativo = aportes_liquidos_per_asset[asset_full]
        ranking.append({
            "ticker": base_name, "investido": round(aporte_ativo, 2), "atual": round(val_atual, 2),
            "rent_pct": round(((val_atual - aporte_ativo)/aporte_ativo*100), 2) if aporte_ativo > 0 else 0,
            "categoria": cat
        })
    ranking.sort(key=lambda x: x["investido"], reverse=True)

    alocacao_output = []
    for cid, pm in meta_alocacao_data.get("metas", {}).items():
        real = pat_cat_atual.get(cid, 0)
        meta = pat_atual * pm
        alocacao_output.append({"categoria": cid, "meta_rs": round(meta, 2), "real_rs": round(real, 2), "diferenca_rs": round(real - meta, 2)})

    output = {
        "kpis": {
            "patrimonio_total": round(pat_atual, 2),
            "aportes_liquido_total": round(aportes_total_geral, 2),
            "rentabilidade_nominal": round(((pat_atual - aportes_total_geral)/aportes_total_geral*100), 2) if aportes_total_geral > 0 else 0,
            "cagr_5anos": round((((pat_atual / evolucao_mensal[-61]["patrimonio"])**(1/5))-1)*100, 2) if len(evolucao_mensal) >= 61 and evolucao_mensal[-61]["patrimonio"] > 0 else 0
        },
        "evolucao_mensal": evolucao_mensal[-24:],
        "evolucao_mensal_por_categoria": {cat: data[-24:] for cat, data in evolucao_mensal_por_cat.items()},
        "evolucao_anual": evolucao_anual,
        "evolucao_anual_por_categoria": evolucao_anual_por_cat,
        "aportes_liquidos": [{"ano": y, "aporte": round(v, 2)} for y, v in sorted(aportes_anuais.items())],
        "rentabilidade_anual": rentabilidade_anual_data,
        "alocacao": alocacao_output,
        "benchmarks": benchmarks_output,
        "ranking_ativos": ranking,
        "last_update": datetime.now().strftime("%Y-%m-%d %H:%M")
    }

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"✅ Dashboard JSON gerado com sucesso!")

if __name__ == "__main__": run()
