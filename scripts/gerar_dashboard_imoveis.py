#!/usr/bin/env python3
"""
Gerador de Dashboard de Imóveis de Renda
Calcula valorização mensal (0,2% a.m.) e agrega dados para visualização
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict

# Caminhos
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
IMOVEL_JSON = DATA_DIR / "imovel_trulli_historico.json"
ALUGUEL_JSON = DATA_DIR / "recebimento_aluguel_historico.json"
OUTPUT_JSON = DATA_DIR / "imoveis_renda_dashboard.json"

# Taxa de valorização mensal
TAXA_VALORIZACAO = 0.002  # 0,2% a.m.


def calcular_valorizacao_mensal(movimentacoes_imoveis):
    """
    Calcula valorização mensal dos imóveis (0,2% a.m. sobre aportes acumulados)
    
    Returns:
        dict: { "YYYY-MM-DD": valor_mercado }
    """
    # Ordenar movimentações por data
    mov_sorted = sorted(movimentacoes_imoveis, key=lambda x: x["data"])
    
    # Primeira data: primeiro aporte
    data_inicio = datetime.strptime(mov_sorted[0]["data"], "%Y-%m-%d")
    # Última data: 31/dez/2025 (data de corte)
    data_fim = datetime(2025, 12, 31)
    
    # Criar dicionário de aportes por mês
    aportes_por_mes = defaultdict(float)
    for mov in mov_sorted:
        data = datetime.strptime(mov["data"], "%Y-%m-%d")
        mes_key = data.strftime("%Y-%m")
        aportes_por_mes[mes_key] += mov["valor_total"]
    
    # Calcular valorização mês a mês
    valores = {}
    base_acumulada = 0.0
    
    current_date = data_inicio.replace(day=1)  # Primeiro dia do mês inicial
    
    while current_date <= data_fim:
        mes_key = current_date.strftime("%Y-%m")
        
        # Adicionar aportes do mês
        if mes_key in aportes_por_mes:
            base_acumulada += aportes_por_mes[mes_key]
        
        # Aplicar valorização
        base_acumulada *= (1 + TAXA_VALORIZACAO)
        
        # Salvar valor no último dia do mês
        ultimo_dia = (current_date.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        valores[ultimo_dia.strftime("%Y-%m-%d")] = round(base_acumulada, 2)
        
        # Próximo mês
        current_date = (current_date.replace(day=28) + timedelta(days=4)).replace(day=1)
    
    return valores


def agregar_por_ano(valores_mensais):
    """
    Agrega valores mensais por ano (último valor de cada ano)
    
    Returns:
        list: [{ "ano": YYYY, "valor": float }]
    """
    valores_anuais = {}
    
    for data_str, valor in valores_mensais.items():
        ano = datetime.strptime(data_str, "%Y-%m-%d").year
        valores_anuais[ano] = valor  # Sobrescreve com último valor do ano
    
    return [{"ano": ano, "valor": round(valor, 2)} for ano, valor in sorted(valores_anuais.items())]


def calcular_alugueis_por_ano(movimentacoes_aluguel):
    """
    Agrega aluguéis recebidos por ano
    
    Returns:
        list: [{ "ano": YYYY, "total": float }]
    """
    alugueis_anuais = defaultdict(float)
    
    for mov in movimentacoes_aluguel:
        data = datetime.strptime(mov["data"], "%Y-%m-%d")
        alugueis_anuais[data.year] += mov["valor_total"]
    
    return [{"ano": ano, "total": round(total, 2)} for ano, total in sorted(alugueis_anuais.items())]


def calcular_rentabilidade_acumulada(valores_por_ano, alugueis_por_ano, total_investido):
    """
    Calcula rentabilidade acumulada por ano
    
    Formula: ((Valor Mercado + Aluguéis Acumulados - Total Investido) / Total Investido) * 100
    
    Returns:
        list: [{ "ano": YYYY, "percentual": float }]
    """
    # Criar dicionário de aluguéis acumulados por ano
    alugueis_dict = {item["ano"]: item["total"] for item in alugueis_por_ano}
    alugueis_acumulados = 0.0
    
    rentabilidade = []
    
    for item in valores_por_ano:
        ano = item["ano"]
        valor_mercado = item["valor"]
        
        # Acumular aluguéis até o ano corrente
        if ano in alugueis_dict:
            alugueis_acumulados += alugueis_dict[ano]
        
        # Calcular rentabilidade
        rent_percentual = ((valor_mercado + alugueis_acumulados - total_investido) / total_investido) * 100
        
        rentabilidade.append({
            "ano": ano,
            "percentual": round(rent_percentual, 2)
        })
    
    return rentabilidade


def main():
    print("📊 Gerando Dashboard de Imóveis de Renda...")
    
    # Carregar JSONs
    with open(IMOVEL_JSON, "r", encoding="utf-8") as f:
        imovel_data = json.load(f)
    
    with open(ALUGUEL_JSON, "r", encoding="utf-8") as f:
        aluguel_data = json.load(f)
    
    # Calcular valores
    print("  ⏳ Calculando valorização mensal (0,2% a.m.)...")
    valores_mensais = calcular_valorizacao_mensal(imovel_data["movimentacoes"])
    
    print("  📈 Agregando por ano...")
    valores_por_ano = agregar_por_ano(valores_mensais)
    
    print("  💰 Calculando aluguéis por ano...")
    alugueis_por_ano = calcular_alugueis_por_ano(aluguel_data["movimentacoes"])
    
    # Calcular KPIs
    print("  🧮 Calculando KPIs...")
    num_imoveis = len(set([mov["ativo"] for mov in imovel_data["movimentacoes"]]))
    valor_mercado_atual = valores_por_ano[-1]["valor"]
    total_investido = sum([mov["valor_total"] for mov in imovel_data["movimentacoes"]])
    total_alugueis = sum([mov["valor_total"] for mov in aluguel_data["movimentacoes"]])
    
    # Aluguéis últimos 12 meses (2025)
    alugueis_12m = sum([
        mov["valor_total"] 
        for mov in aluguel_data["movimentacoes"]
        if mov["data"].startswith("2025")
    ])
    
    dy_12m = (alugueis_12m / valor_mercado_atual) * 100
    rentabilidade_total = ((valor_mercado_atual + total_alugueis - total_investido) / total_investido) * 100
    
    # Calcular rentabilidade acumulada por ano
    rentabilidade_acumulada = calcular_rentabilidade_acumulada(
        valores_por_ano, 
        alugueis_por_ano, 
        total_investido
    )
    
    # Montar JSON de saída
    dashboard_data = {
        "kpis": {
            "num_imoveis": num_imoveis,
            "valor_mercado_atual": round(valor_mercado_atual, 2),
            "alugueis_12m": round(alugueis_12m, 2),
            "dy_12m": round(dy_12m, 2),
            "rentabilidade_total": round(rentabilidade_total, 2)
        },
        "series": {
            "valor_por_ano": valores_por_ano,
            "alugueis_por_ano": alugueis_por_ano,
            "rentabilidade_acumulada": rentabilidade_acumulada
        },
        "metadata": {
            "data_geracao": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total_investido": round(total_investido, 2),
            "total_alugueis": round(total_alugueis, 2),
            "taxa_valorizacao_mensal": TAXA_VALORIZACAO
        }
    }
    
    # Salvar JSON
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(dashboard_data, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Dashboard gerado: {OUTPUT_JSON}")
    print("\n📊 KPIs:")
    print(f"  • Número de Imóveis: {num_imoveis}")
    print(f"  • Valor de Mercado: R$ {valor_mercado_atual:,.2f}")
    print(f"  • Aluguéis 12m: R$ {alugueis_12m:,.2f}")
    print(f"  • DY 12m: {dy_12m:.2f}%")
    print(f"  • Rentabilidade Total: {rentabilidade_total:.2f}%")
    print(f"\n💾 Total Investido: R$ {total_investido:,.2f}")
    print(f"💰 Total Aluguéis (histórico): R$ {total_alugueis:,.2f}")


if __name__ == "__main__":
    main()
