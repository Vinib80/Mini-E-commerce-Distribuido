# Mini E-commerce Distribuído - Guia de Execução

Este guia descreve como iniciar todos os microsserviços, o API Gateway, e como testar as funcionalidades implementadas (autenticação JWT, replicação de produtos, consistência, balanceamento de carga e tolerância a falhas).

## 1. Pré-requisitos
- Python 3.9+
- Ambiente virtual (recomendado)
- SQLite3 instalado no sistema (para testar alteração de permissão)

```bash
# Criação do ambiente virtual e instalação das dependências
python -m venv .venv
source .venv/bin/activate  # no Linux/Mac
# ou no Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

## 2. Inicialização dos Serviços

Cada serviço deve ser iniciado em um terminal diferente (lembre-se de ativar o ambiente virtual em cada um deles).

**Terminal 1: Microsserviço de Usuários**
```bash
cd users
PORT=5001 python -m app.main
```

**Terminal 2: Microsserviço de Produtos (Primário)**
Este será a fonte primária de escritas.
```bash
cd products
PORT=5002 SECONDARY_URL=http://localhost:5012 python -m app.main
```

**Terminal 3: Microsserviço de Produtos (Secundário - Réplica)**
Este serviço atua apenas como leitura e réplica de dados do primário.
```bash
cd products
PORT=5012 python -m app.main
```

**Terminal 4: Microsserviço de Pedidos**
```bash
cd orders
PORT=5003 python -m app.main
```

**Terminal 5: API Gateway**
Responsável por rotear as chamadas, balancear carga, verificar heartbeats e encapsular as rotas.
```bash
cd gateway
python main.py
```

---

## 3. Roteiro de Testes das Funcionalidades

Abaixo está o passo a passo para testar as regras de negócio via cURL (ou Postman). Todas as requisições devem ser feitas através do **API Gateway (porta 5000)**.

### 3.1. Segurança (JWT)

**1. Registrar um novo usuário:**
```bash
curl -X POST http://localhost:5000/users/register \
     -H "Content-Type: application/json" \
     -d '{"name": "Alice", "email": "alice@example.com", "password": "senha"}'
```

**2. Dar privilégios de Admin:**
A criação e remoção de produtos é restrita para contas `admin`. Atualize manualmente a role no banco de dados do microsserviço de usuários (execute na raiz do projeto):
```bash
sqlite3 users/users.db "UPDATE users SET role='admin' WHERE email='alice@example.com';"
```

**3. Fazer Login e obter o JWT:**
```bash
curl -X POST http://localhost:5000/users/login \
     -H "Content-Type: application/json" \
     -d '{"email": "alice@example.com", "password": "senha"}'
```
> Copie o `access_token` retornado. Ele será usado no cabeçalho `Authorization: Bearer <TOKEN>` nas chamadas seguintes.

### 3.2. Consistência e Replicação (Produtos)

O cadastro de um novo produto (escrita) é sempre encaminhado para o serviço primário (`5002`), que salva e realiza uma chamada interna para replicar os dados no secundário (`5012`).

**Criar um produto (Lembre-se de substituir o TOKEN):**
```bash
curl -X POST http://localhost:5000/products \
     -H "Authorization: Bearer SEU_TOKEN_AQUI" \
     -H "Content-Type: application/json" \
     -d '{"name": "Notebook", "description": "Notebook Gamer", "price": 4500.00, "stock": 10}'
```
*👉 Observe nos logs do terminal do Produto Primário e do Produto Secundário que a replicação ocorreu com sucesso.*

### 3.3. Balanceamento de Carga (Round-Robin em Leitura)

O API Gateway distribui as requisições de leitura de produtos de forma alternada (Round-Robin) entre as instâncias `5002` e `5012`.

**Listar produtos (Execute várias vezes):**
```bash
curl -X GET http://localhost:5000/products
```
*👉 Verifique os logs dos terminais dos microsserviços de Produtos (`5002` e `5012`). Você verá as requisições de GET sendo recebidas ora no primário, ora no secundário.*

### 3.4. Microsserviços Interligados (Pedidos)

A rota de pedidos valida seu token (via microsserviço de pedidos, recebido repassado do gateway) simulando o ecossistema integrado.

**Criar um pedido:**
```bash
curl -X POST http://localhost:5000/orders \
     -H "Authorization: Bearer SEU_TOKEN_AQUI" \
     -H "Content-Type: application/json" \
     -d '{"items": [{"product_id": 1, "quantity": 1}]}'
```

### 3.5. Tolerância a Falhas (Heartbeat)

O Gateway verifica a integridade de todos os microsserviços ativamente a cada 5 segundos através da rota interna `/health`.

1. **Simule a queda:** Pare o serviço **Secundário de Produtos** (Terminal 3: pressione `Ctrl + C`).
2. **Detecção:** Aguarde alguns segundos. Observe os **logs do Gateway**. Após 2 tentativas falhas consecutivas, o Gateway marcará o serviço como `Down` e logará o erro (*"Falha detectada: O serviço http://localhost:5012 não respondeu..."*).
3. **Comportamento 503:** Tente acessar listar produtos (`GET http://localhost:5000/products`) seguidas vezes. Quando o algoritmo Round-Robin apontar para a réplica indisponível, o API Gateway imediatamente protegerá o sistema e retornará o erro `503 Service Unavailable`, e funcionará normalmente quando cair na primária (5002).
4. **Recuperação:** Suba o serviço **Secundário de Produtos** novamente (Terminal 3).
5. **Auto-healing:** Observe os logs do Gateway indicando recuperação automática: *"Recuperação: O serviço http://localhost:5012 voltou a responder."*
