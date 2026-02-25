#!/usr/bin/env python3
"""
Atualiza operações de opções US com fechamentos e novas aberturas
Data: 2026-02-25
"""

import json
from datetime import datetime
from pathlib import Path

# Caminhos
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
OPCOES_US_JSON = DATA_DIR / "opcoes_intl.json"

def main():
    print("📊 Atualizando Opções US...")
    
    # Carregar JSON
    with open(OPCOES_US_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    operacoes = data["operacoes"]
    
    # 1. FECHAR IBIT C43.5 (27/fev) - Compra CALL
    print("\n1. Fechando IBIT C43.5 (27/fev)...")
    for op in operacoes:
        if (op["ticker"] == "IBIT" and 
            op["strike"] == 43.50 and 
            op["vencimento"] == "2026-02-27" and
            op["tipo_contrato"] == "CALL" and
            op["operacao"] == "Compra" and
            op["status"] == "aberta"):
            
            op["data_fechamento"] = "2026-02-25"
            op["preco_acao_fechamento"] = 40.50  # Estimar (não fornecido)
            op["preco_opcao_fechamento"] = 0.02
            op["taxas_fechamento"] = 0.89
            op["taxas_total"] = op["taxas_abertura"] + 0.89
            
            # Calcular resultado
            # Compra: pagou na abertura, recebeu no fechamento
            custo_abertura = op["preco_opcao_abertura"] * op["quantidade"] + op["taxas_abertura"]
            receita_fechamento = op["preco_opcao_fechamento"] * op["quantidade"]
            resultado = receita_fechamento - custo_abertura - op["taxas_fechamento"]
            
            op["resultado"] = round(resultado, 2)
            op["status"] = "fechada"
            print(f"   ✅ Fechada | Resultado: ${resultado:.2f}")
            break
    
    # 2. FECHAR IBIT C41 (27/fev) - Venda CALL
    print("\n2. Fechando IBIT C41 (27/fev)...")
    for op in operacoes:
        if (op["ticker"] == "IBIT" and 
            op["strike"] == 41.00 and 
            op["vencimento"] == "2026-02-27" and
            op["tipo_contrato"] == "CALL" and
            op["operacao"] == "Venda" and
            op["status"] == "aberta"):
            
            op["data_fechamento"] = "2026-02-25"
            op["preco_acao_fechamento"] = 40.50  # Estimar (não fornecido)
            op["preco_opcao_fechamento"] = 0.06
            op["taxas_fechamento"] = 0.87
            op["taxas_total"] = op["taxas_abertura"] + 0.87
            
            # Calcular resultado
            # Venda: recebeu na abertura, pagou no fechamento
            receita_abertura = op["preco_opcao_abertura"] * op["quantidade"]
            custo_fechamento = op["preco_opcao_fechamento"] * op["quantidade"]
            resultado = receita_abertura - custo_fechamento - op["taxas_abertura"] - op["taxas_fechamento"]
            
            op["resultado"] = round(resultado, 2)
            op["status"] = "fechada"
            print(f"   ✅ Fechada | Resultado: ${resultado:.2f}")
            break
    
    # 3. NOVA ABERTURA: IBIT C43 (06/mar) - Compra CALL
    print("\n3. Adicionando IBIT C43 (06/mar) - Compra CALL...")
    nova_op_1 = {
        "ticker": "IBIT",
        "data_operacao": "2026-02-25",
        "preco_acao_na_operacao": 40.50,  # Estimar
        "operacao": "Compra",
        "tipo_contrato": "CALL",
        "vencimento": "2026-03-06",
        "strike": 43.00,
        "quantidade": 700,
        "preco_opcao_abertura": 0.21,
        "data_fechamento": None,
        "preco_acao_fechamento": None,
        "preco_opcao_fechamento": None,
        "taxas_abertura": 7.87,
        "taxas_fechamento": None,
        "taxas_total": 7.87,
        "resultado": None,
        "status": "aberta"
    }
    operacoes.append(nova_op_1)
    print(f"   ✅ Adicionada | Strike: $43 | Qtd: 700 | Preço: $0.21")
    
    # 4. NOVA ABERTURA: IBIT C41 (06/mar) - Venda CALL
    print("\n4. Adicionando IBIT C41 (06/mar) - Venda CALL...")
    nova_op_2 = {
        "ticker": "IBIT",
        "data_operacao": "2026-02-25",
        "preco_acao_na_operacao": 40.50,  # Estimar
        "operacao": "Venda",
        "tipo_contrato": "CALL",
        "vencimento": "2026-03-06",
        "strike": 41.00,
        "quantidade": 700,
        "preco_opcao_abertura": 0.56,
        "data_fechamento": None,
        "preco_acao_fechamento": None,
        "preco_opcao_fechamento": None,
        "taxas_abertura": 7.89,
        "taxas_fechamento": None,
        "taxas_total": 7.89,
        "resultado": None,
        "status": "aberta"
    }
    operacoes.append(nova_op_2)
    print(f"   ✅ Adicionada | Strike: $41 | Qtd: 700 | Preço: $0.56")
    
    # Atualizar estatísticas
    print("\n5. Atualizando estatísticas...")
    total_ops = len(operacoes)
    fechadas = [op for op in operacoes if op["status"] == "fechada"]
    abertas = [op for op in operacoes if op["status"] == "aberta"]
    
    resultado_total = sum([op["resultado"] for op in fechadas if op["resultado"] is not None])
    
    vitorias = len([op for op in fechadas if op["resultado"] and op["resultado"] > 0])
    derrotas = len([op for op in fechadas if op["resultado"] and op["resultado"] <= 0])
    win_rate = (vitorias / len(fechadas)) * 100 if fechadas else 0
    
    data["estatisticas"] = {
        "total_operacoes": total_ops,
        "operacoes_fechadas": len(fechadas),
        "operacoes_abertas": len(abertas),
        "resultado_total_realizado_usd": round(resultado_total, 2),
        "vitorias": vitorias,
        "derrotas": derrotas,
        "win_rate_percentual": round(win_rate, 2)
    }
    
    data["versao"] = "2.2"
    data["data_atualizacao"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Salvar JSON atualizado
    with open(OPCOES_US_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ JSON atualizado: {OPCOES_US_JSON}")
    print(f"\n📊 Estatísticas:")
    print(f"   • Total de operações: {total_ops}")
    print(f"   • Fechadas: {len(fechadas)} | Abertas: {len(abertas)}")
    print(f"   • Resultado Total Realizado: ${resultado_total:,.2f}")
    print(f"   • Vitórias: {vitorias} | Derrotas: {derrotas}")
    print(f"   • Win Rate: {win_rate:.2f}%")


if __name__ == "__main__":
    main()
