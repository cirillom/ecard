# ecard

Front-end + backend mockado do e-Card (carteirinha digital), pra iniciação científica.
Segue o mesmo padrão de projeto/deploy do `tarefas-casa`: build via GitHub Actions,
imagem publicada no GHCR, servidor só puxa e roda.

Backend Flask/SQLite (`app.py`) + frontend estático (`static/`) servido pelo próprio Flask.
Fotos enviadas ficam em `/data/photos` (volume), caminho salvo no SQLite.

## Funcionalidades

- **`GET /`** — formulário para cadastrar um novo usuário (username, nome, RA, instituto, link do QR, foto)
- **`GET /<username>`** — exibe o e-Card daquele usuário (ou, se não existir, mostra o
  formulário de cadastro já com o username preenchido)
- Botão "Editar dados deste usuário" na tela do cartão volta pro formulário, agora em modo edição
- Botão "RENOVAR CODIGO QR" chama o backend e atualiza a data de expiração (+3 dias a partir de agora)
- Sem autenticação/senha — qualquer um pode criar ou editar qualquer usuário (uso interno,
  mock pra demonstração ao time)

Usuário de exemplo criado automaticamente no primeiro boot: `/exemplo`
(Nome Sobrenome do Aluno / RA 00000000 / Unidade de Ensino Exemplo — sem foto).

## Desenvolver

```bash
docker compose up --build
```

Abre em `http://localhost:8000`. O SQLite e as fotos ficam em `./data-dev` (ignorado pelo git).
Como `app.py` e `static/` são copiados na imagem, qualquer mudança neles exige `--build` de novo.

## Lançar uma versão

```bash
git tag v1.0.0
git push origin v1.0.0
```

Isso dispara `.github/workflows/release.yml`, que:
1. builda a imagem Docker,
2. publica em `ghcr.io/<seu-usuario>/ecard:latest` e `:v1.0.0`,
3. cria uma Release no GitHub anexando `docker-compose.example.yml`.

> Ajuste `ghcr.io/cirillom/ecard` no `docker-compose.example.yml` e no workflow
> se seu usuário/organização no GHCR for diferente.

## Implantar no servidor

O servidor **não builda nada** — só puxa a imagem já pronta. Ver `docker-compose.example.yml`
para o compose de referência (mesmo padrão do `~/services/tarefas-casa/docker-compose.yml`,
adaptado pra `~/services/ecard/docker-compose.yml`).

Se o pacote no GHCR for privado, autentique uma vez no servidor:

```bash
echo "<PAT com escopo read:packages>" | docker login ghcr.io -u cirillom --password-stdin
```

### Passos específicos deste projeto

1. Criar o diretório de dados: `mkdir -p /mnt/hdd/ecard/data/photos`
2. Copiar `docker-compose.example.yml` pra `~/services/ecard/docker-compose.yml`
   (ajustando a imagem se necessário)
3. `docker compose up -d`
4. Adicionar `"~/services/ecard/docker-compose.yml"` ao array `COMPOSE_SERVICES`
   em `/usr/local/bin/homeserver-config.sh`
5. Adicionar um `server` block em `/mnt/hdd/nginx.conf` apontando pro serviço
   `ecard` na rede `proxy` — igual ao que já existe pro `tarefas-casa`, trocando
   o nome do upstream e a porta/host (`http://ecard.cirillo`)

## Atualizar depois de uma nova release

Sem Watchtower — é manual, dois comandos no servidor:

```bash
cd ~/services/ecard
docker compose pull
docker compose up -d
```

## Sobre os dados

Este projeto guarda **apenas dados fictícios/de teste** criados manualmente pelo time
via formulário (nome, RA, instituto, foto). Nenhum dado real de aluno (das telas de
referência originais usadas pra desenhar o layout) foi incluído no código, no banco
ou nos assets do projeto. Ao usar fotos reais de pessoas do time para demonstração,
tenha o consentimento delas — o app não tem controle de acesso, então qualquer
pessoa com a URL consegue ver o cartão.
