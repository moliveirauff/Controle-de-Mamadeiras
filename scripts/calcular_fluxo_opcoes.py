#!/usr/bin/env python3
"""
Script de Cálculo de Fluxo de Caixa de Opções
Autor: InvestBot
Data: 2026-02-24
"""

import json
import requests
from datetime import datetime, timedelta
from collections import defaultdict

# Configurações
DATA_DIR = "/root/.openclaw/familia-donato-suarez/data/"
COTACAO_FALLBACK = 5.70  # Média conservadora 2025

def buscar_cotacao_dolar(data_str):
    """
    Busca cotação do dólar no Bacen para uma data específica.
    Formato: YYYY-MM-DD
    """
    try:
        data_obj = datetime.strptime(data_str, '%Y-%m-%d')
        # Formato para API Bacen: MM-DD-YYYY
        data_bacen = data_obj.strftime('%m-%d-%Y')
        
        url = f"https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata/CotacaoDolarDia(dataCotacao=@dataCotacao)?@dataCotacao='{data_bacen}'&$format=json"
        
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if 'value' in data and len(data['value']) > 0:
                return float(data['value'][0]['cotacaoVenda'])
    except Exception as e:
        print(f"⚠️  Erro ao buscar cotação para {data_str}: {e}")
    
    # Fallback
    return COTACAO_FALLBACK

def calcular_fluxo_br(opcoes_br):
    """Calcula fluxo de caixa mensal das opções BR"""
    fluxo_mensal = defaultdict(lambda: {'entradas': 0, 'saidas': 0, 'total': 0})
    
    for op in opcoes_br:
        if not op.get('data_operacao'):
            continue
            
        mes_abertura = op['data_operacao'][:7]  # YYYY-MM
        
        # Fluxo de ABERTURA
        preco_abertura = op.get('preco_opcao_abertura') or 0
        quantidade = op.get('quantidade') or 0
        taxas = op.get('taxas') or 0
        
        if op['operacao'] == 'Venda':
            # Venda: Entrada de dinheiro
            fluxo_abertura = (preco_abertura * quantidade) - taxas
            fluxo_mensal[mes_abertura]['entradas'] += fluxo_abertura
        else:  # Compra
            # Compra: Saída de dinheiro
            fluxo_abertura = (preco_abertura * quantidade) + taxas
            fluxo_mensal[mes_abertura]['saidas'] += fluxo_abertura
        
        # Fluxo de FECHAMENTO (se fechada)
        if op['status'] == 'fechada' and op.get('data_fechamento'):
            mes_fechamento = op['data_fechamento'][:7]
            preco_fechamento = op.get('preco_opcao_fechamento') or 0
            
            if op['operacao'] == 'Venda':
                # Venda precisa ser recomprada (Saída)
                fluxo_fechamento = (preco_fechamento * quantidade) + taxas
                fluxo_mensal[mes_fechamento]['saidas'] += fluxo_fechamento
            else:  # Compra
                # Compra pode ser vendida (Entrada)
                fluxo_fechamento = (preco_fechamento * quantidade) - taxas
                fluxo_mensal[mes_fechamento]['entradas'] += fluxo_fechamento
    
    # Calcular total
    for mes in fluxo_mensal:
        fluxo_mensal[mes]['total'] = fluxo_mensal[mes]['entradas'] - fluxo_mensal[mes]['saidas']
    
    return fluxo_mensal

def calcular_fluxo_us(opcoes_us):
    """Calcula fluxo de caixa mensal das opções US (convertido para BRL)"""
    fluxo_mensal = defaultdict(lambda: {'entradas': 0, 'saidas': 0, 'total': 0, 'cotacoes': {}})
    
    # Cache de cotações
    cache_cotacoes = {}
    
    for op in opcoes_us:
        if not op.get('data_operacao'):
            continue
            
        mes_abertura = op['data_operacao'][:7]
        data_abertura = op['data_operacao']
        
        # Buscar cotação do dólar (cache)
        if data_abertura not in cache_cotacoes:
            cotacao = buscar_cotacao_dolar(data_abertura)
            cache_cotacoes[data_abertura] = cotacao
            print(f"Cotação {data_abertura}: R$ {cotacao:.4f}")
        else:
            cotacao = cache_cotacoes[data_abertura]
        
        # Fluxo de ABERTURA
        preco_abertura = op.get('preco_opcao_abertura') or 0
        quantidade = op.get('quantidade_opcoes') or 0
        taxas = op.get('taxas') or 0
        
        if op['operacao'] == 'Venda':
            # Venda: Entrada em USD → BRL
            fluxo_abertura_usd = (preco_abertura * quantidade) - taxas
            fluxo_abertura_brl = fluxo_abertura_usd * cotacao
            fluxo_mensal[mes_abertura]['entradas'] += fluxo_abertura_brl
        else:  # Compra
            # Compra: Saída em USD → BRL
            fluxo_abertura_usd = (preco_abertura * quantidade) + taxas
            fluxo_abertura_brl = fluxo_abertura_usd * cotacao
            fluxo_mensal[mes_abertura]['saidas'] += fluxo_abertura_brl
        
        # Fluxo de FECHAMENTO (usa MESMA cotação da abertura)
        if op['status'] == 'fechada' and op.get('data_fechamento'):
            mes_fechamento = op['data_fechamento'][:7]
            preco_fechamento = op.get('preco_opcao_fechamento') or 0
            
            if op['operacao'] == 'Venda':
                # Recompra (Saída)
                fluxo_fechamento_usd = (preco_fechamento * quantidade) + taxas
                fluxo_fechamento_brl = fluxo_fechamento_usd * cotacao  # Mesma cotação!
                fluxo_mensal[mes_fechamento]['saidas'] += fluxo_fechamento_brl
            else:  # Compra
                # Venda (Entrada)
                fluxo_fechamento_usd = (preco_fechamento * quantidade) - taxas
                fluxo_fechamento_brl = fluxo_fechamento_usd * cotacao
                fluxo_mensal[mes_fechamento]['entradas'] += fluxo_fechamento_brl
        
        # Armazenar cotação usada
        fluxo_mensal[mes_abertura]['cotacoes'][data_abertura] = cotacao
    
    # Calcular total
    for mes in fluxo_mensal:
        fluxo_mensal[mes]['total'] = fluxo_mensal[mes]['entradas'] - fluxo_mensal[mes]['saidas']
    
    return fluxo_mensal

def consolidar_fluxo(fluxo_br, fluxo_us):
    """Consolida fluxo BR + US em uma única estrutura mensal"""
    todos_meses = sorted(set(list(fluxo_br.keys()) + list(fluxo_us.keys())))
    
    consolidado = []
    total_br = 0
    total_us = 0
    
    for mes in todos_meses:
        br = fluxo_br.get(mes, {}).get('total', 0)
        us = fluxo_us.get(mes, {}).get('total', 0)
        total = br + us
        
        total_br += br
        total_us += us
        
        consolidado.append({
            'mes': mes,
            'fluxo_br': round(br, 2),
            'fluxo_us': round(us, 2),
            'fluxo_total': round(total, 2)
        })
    
    # Adicionar linha de total
    consolidado.append({
        'mes': 'TOTAL',
        'fluxo_br': round(total_br, 2),
        'fluxo_us': round(total_us, 2),
        'fluxo_total': round(total_br + total_us, 2)
    })
    
    return consolidado

def main():
    print("🚀 Calculando Fluxo de Caixa de Opções...\n")
    
    # Carregar dados
    with open(DATA_DIR + 'opcoes_br.json', 'r') as f:
        br_data = json.load(f)
    
    with open(DATA_DIR + 'opcoes_intl.json', 'r') as f:
        us_data = json.load(f)
    
    # Processar
    print("📊 Processando Opções BR...")
    fluxo_br = calcular_fluxo_br(br_data['operacoes'])
    
    print("\n📊 Processando Opções US (buscando cotações do dólar)...")
    fluxo_us = calcular_fluxo_us(us_data['operacoes'])
    
    # Consolidar
    print("\n📊 Consolidando resultados...")
    resultado = consolidar_fluxo(fluxo_br, fluxo_us)
    
    # Salvar JSON
    output = {
        'versao': '2026.2.24',
        'data_calculo': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'descricao': 'Fluxo de caixa mensal de operações com opções (BR + US)',
        'detalhamento_mensal': resultado
    }
    
    with open(DATA_DIR + 'fluxo_caixa_opcoes.json', 'w') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    # Exibir tabela
    print("\n" + "="*70)
    print("📊 FLUXO DE CAIXA MENSAL - OPÇÕES")
    print("="*70)
    print(f"{'Mês':<12} {'BR (R$)':>15} {'US (R$)':>15} {'Total (R$)':>15}")
    print("-"*70)
    
    for item in resultado:
        mes = item['mes']
        br = item['fluxo_br']
        us = item['fluxo_us']
        total = item['fluxo_total']
        
        if mes == 'TOTAL':
            print("="*70)
        
        print(f"{mes:<12} {br:>15,.2f} {us:>15,.2f} {total:>15,.2f}")
    
    print("="*70)
    print(f"\n✅ Resultado salvo em: {DATA_DIR}fluxo_caixa_opcoes.json")

if __name__ == "__main__":
    main()
