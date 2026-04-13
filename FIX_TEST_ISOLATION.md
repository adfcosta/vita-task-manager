# Fix v2.2.1 — Isolamento de Testes e Proteção de Dados

## Problema
Testes e comandos CLI podem contaminar o diretório de dados real da skill.

## Soluções Implementadas

### 1. Prefixo de Proteção em Testes
```python
# test_core.py — já usa tempfile, mas adicionar prefixo VISÍVEL
with tempfile.TemporaryDirectory(prefix="vita_test_") as tmp:
    ...
```

### 2. Validação em CLI
```python
# cli.py — adicionar verificação antes de operar em dados
if "test" not in str(data_dir) and os.environ.get("VITA_DRY_RUN"):
    print("⚠️ Modo dry-run ativo. Nenhuma alteração será feita.")
```

### 3. Arquivo de Bloqueio
```python
# ledger.py — criar .lock durante operações
```

### 4. Diretório de Testes Automático
```python
# Se data_dir não especificado, usar default seguro
```

## Comando de Limpeza

```bash
# Limpar dados de teste
rm -f /home/node/.openclaw/workspace/vita/skills/vita-task-manager/data/historico/*test*.jsonl
```

## Prevenção Futura

- Sempre usar `tempfile.TemporaryDirectory()` em testes
- Nunca hardcoded paths em scripts
- Validar paths antes de escrita
- Usar prefixos claros para distinguir teste/produção
