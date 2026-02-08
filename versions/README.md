# 📌 Histórico de Versões do Hub

Este diretório contém **snapshots completos** de todas as versões anteriores do Hub da Família.

## Conceito

A versão é **GLOBAL** - qualquer mudança em qualquer dashboard resulta em bump de versão.

## Estrutura

```
versions/
├── v1.0/
│   ├── index.html
│   ├── matheus.html
│   ├── matheus-crescimento.html
│   ├── compras.html
│   ├── viagem.html
│   ├── receitas.html
│   └── data/  ← Dados da época
├── v1.1/
│   └── [snapshot completo]
└── README.md (este arquivo)
```

## Política de Versionamento

- **MINOR (1.0 → 1.1):** Melhorias, otimizações, correções, novos recursos
- **MAJOR (1.9 → 2.0):** Mudanças estruturais (apenas quando solicitado pelo usuário)
- **URL sempre a mesma:** Os arquivos principais nunca mudam de nome
- **Backup automático:** Script cria snapshot completo antes de cada bump

## Como usar

```bash
# Atualizar versão do hub
/root/clawd/scripts/bump_hub_version.sh

# Ou major
/root/clawd/scripts/bump_hub_version.sh major
```

Documentação completa: `sub_agents/desenvolvimento.md`

## Changelog

### v1.0 (2026-02-08)
- ✅ Sistema de versionamento global implementado
- ⚡ Dashboard de crescimento: curvas OMS simplificadas (P10/P50/P90)
- 🎨 Badge de versão no index.html
- 📦 Estrutura de backup completo
