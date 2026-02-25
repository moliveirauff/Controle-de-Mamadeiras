#!/usr/bin/env python3
"""
Gera fluxo de caixa mensal de opções no formato CORRETO para dashboards
Estrutura esperada por opcoes.html e outros consumidores
"""

import json
from pathlib import Path
from collections import defaultdict
from datetime import datetime

# Caminhos
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
OPCOES_BR = DATA_DIR / "opcoes_br.json"
OPCOES_US = DATA_DIR / "opcoes_intl.json"
OUTPUT = DATA_DIR / "fluxo_caixa_opcoes_mensal.json"


def calcular_fluxo_br(opcoes):
    """Calcula fluxo de caixa BR por mês"""
    fluxo = defaultdict(float)
    
    for op in opcoes:
        # ABERTURA
        mes_abertura = op['data_operacao'][:7]
        preco_ab = op.get('preco_opcao_abertura', 0)
        qtd = op.get('quantidade', 0)
        taxa_ab = op.get('taxas_abertura', 0) or 3.5
        
        if op['operacao'] == 'Venda':
            # Venda: recebe - taxa
            fluxo[mes_abertura] += (preco_ab * qtd) - taxa_ab
        else:  # Compra
            # Compra: paga + taxa
            fluxo[mes_abertura] -= (preco_ab * qtd) + taxa_ab
        
        # FECHAMENTO
        if op['status'] == 'fechada' and op.get('data_fechamento'):
            mes_fech = op['data_fechamento'][:7]
            preco_fech = op.get('preco_opcao_fechamento', 0)
            taxa_fech = op.get('taxas_fechamento', 0) or 3.5
            
            if op['operacao'] == 'Venda':
                # Venda precisa recomprar: paga + taxa
                fluxo[mes_fech] -= (preco_fech * qtd) + taxa_fech
            else:  # Compra
                # Compra revende: recebe - taxa
                fluxo[mes_fech] += (preco_fech * qtd) - taxa_fech
    
    return fluxo


def calcular_fluxo_us(opcoes):
    """
    Calcula fluxo de caixa US por mês (em USD e BRL)
    Usa cotação da data de ABERTURA para toda a operação
    """
    import requests
    
    fluxo_usd = defaultdict(float)
    fluxo_brl = defaultdict(float)
    cache_cotacoes = {}
    
    def buscar_cotacao(data_str):
        """Busca cotação do dólar no Bacen"""
        if data_str in cache_cotacoes:
            return cache_cotacoes[data_str]
        
        try:
            data_obj = datetime.strptime(data_str, '%Y-%m-%d')
            data_bacen = data_obj.strftime('%m-%d-%Y')
            url = f"https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata/CotacaoDolarDia(dataCotacao=@dataCotacao)?@dataCotacao='{data_bacen}'&$format=json"
            
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                if 'value' in data and len(data['value']) > 0:
                    cotacao = float(data['value'][0]['cotacaoVenda'])
                    cache_cotacoes[data_str] = cotacao
                    print(f"  Cotação {data_str}: R$ {cotacao:.4f}")
                    return cotacao
        except Exception as e:
            print(f"  ⚠️ Erro ao buscar {data_str}: {e}")
        
        # Fallback
        cache_cotacoes[data_str] = 5.70
        return 5.70
    
    for op in opcoes:
        data_abertura = op['data_operacao']
        mes_abertura = data_abertura[:7]
        cotacao = buscar_cotacao(data_abertura)
        
        preco_ab = op.get('preco_opcao_abertura', 0)
        qtd = op.get('quantidade', 0)
        taxa_ab = op.get('taxas_abertura', 0)
        
        # ABERTURA
        if op['operacao'] == 'Venda':
            fluxo_usd_ab = (preco_ab * qtd) - taxa_ab
            fluxo_usd[mes_abertura] += fluxo_usd_ab
            fluxo_brl[mes_abertura] += fluxo_usd_ab * cotacao
        else:  # Compra
            fluxo_usd_ab = (preco_ab * qtd) + taxa_ab
            fluxo_usd[mes_abertura] -= fluxo_usd_ab
            fluxo_brl[mes_abertura] -= fluxo_usd_ab * cotacao
        
        # FECHAMENTO (mesma cotação da abertura!)
        if op['status'] == 'fechada' and op.get('data_fechamento'):
            mes_fech = op['data_fechamento'][:7]
            preco_fech = op.get('preco_opcao_fechamento', 0)
            taxa_fech = op.get('taxas_fechamento', 0)
            
            if op['operacao'] == 'Venda':
                fluxo_usd_fech = (preco_fech * qtd) + taxa_fech
                fluxo_usd[mes_fech] -= fluxo_usd_fech
                fluxo_brl[mes_fech] -= fluxo_usd_fech * cotacao
            else:  # Compra
                fluxo_usd_fech = (preco_fech * qtd) - taxa_fech
                fluxo_usd[mes_fech] += fluxo_usd_fech
                fluxo_brl[mes_fech] += fluxo_usd_fech * cotacao
    
    return fluxo_usd, fluxo_brl


def main():
    print("📊 Gerando Fluxo de Caixa Mensal (formato dashboard)\n")
    
    # Carregar JSONs
    with open(OPCOES_BR, 'r') as f:
        br_data = json.load(f)
    
    with open(OPCOES_US, 'r') as f:
        us_data = json.load(f)
    
    # Calcular fluxos
    print("📈 Processando Opções BR...")
    fluxo_br = calcular_fluxo_br(br_data['operacoes'])
    
    print("\n📈 Processando Opções US...")
    fluxo_us_usd, fluxo_us_brl = calcular_fluxo_us(us_data['operacoes'])
    
    # Consolidar por mês
    todos_meses = sorted(set(
        list(fluxo_br.keys()) + 
        list(fluxo_us_brl.keys())
    ))
    
    fluxo_mensal = []
    total_br = 0
    total_us_usd = 0
    total_us_brl = 0
    
    for mes in todos_meses:
        br = fluxo_br.get(mes, 0)
        us_usd = fluxo_us_usd.get(mes, 0)
        us_brl = fluxo_us_brl.get(mes, 0)
        total = br + us_brl
        
        total_br += br
        total_us_usd += us_usd
        total_us_brl += us_brl
        
        fluxo_mensal.append({
            "mes": mes,
            "br_brl": round(br, 2),
            "us_usd": round(us_usd, 2),
            "us_brl": round(us_brl, 2),
            "total_brl": round(total, 2)
        })
    
    # Montar JSON FINAL (formato esperado pelo dashboard)
    output = {
        "versao": "1.0",
        "data_geracao": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "descricao": "Fluxo de caixa mensal de operações de opções (BR + US)",
        "observacao": "Valores positivos = entrada de caixa, valores negativos = saída de caixa",
        "totais": {
            "br_total_brl": round(total_br, 2),
            "us_total_usd": round(total_us_usd, 2),
            "us_total_brl": round(total_us_brl, 2),
            "total_geral_brl": round(total_br + total_us_brl, 2)
        },
        "fluxo_mensal": fluxo_mensal
    }
    
    # Salvar
    with open(OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Salvo em: {OUTPUT}")
    print(f"\n📊 Totais:")
    print(f"  BR: R$ {total_br:,.2f}")
    print(f"  US: $ {total_us_usd:,.2f} = R$ {total_us_brl:,.2f}")
    print(f"  TOTAL GERAL: R$ {total_br + total_us_brl:,.2f}")


if __name__ == "__main__":
    main()
