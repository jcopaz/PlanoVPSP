# Plano VP — Manual do usuário

Aplicação do **Plano de Manutenção da Via Permanente**: compara o que o PCM planejou
para o trimestre com o que as equipes executaram.

## Perfis

| Perfil | Pode |
|---|---|
| **Administrador** | tudo, inclusive usuários, auditoria e editar trimestre fechado |
| **PCM / Planejamento** | importar o plano, carregar histórico, configurar o sistema, lançar em qualquer Depto |
| **Programador** | lançar e corrigir atividades **do seu Depto**; configurar SLA e equipes do seu Depto |
| **Leitura** | ver o Dashboard e exportar planilhas |

## Primeiro acesso

- Entre com a **matrícula** e a **senha provisória** recebida do administrador; o sistema pede
  para criar a sua senha (mínimo 8 caracteres, com letras e números).
- Esqueceu a senha? Peça ao administrador: Configurações → Usuários → *Gerar nova senha provisória*.
- O **trimestre** em análise é escolhido no menu lateral e vale para todas as telas.

---

## PCM — início do trimestre (1 vez)

1. No painel do PCM, exporte os 2 arquivos do trimestre:
   - **pesos por meta** (ex.: `data (9).xlsx`, com a coluna *Peso Item Redist*);
   - **Planejamento PCM** (visão congelada, uma linha por dia/meta/equipe).
2. **Dados → Upload → Plano do trimestre (exports do PCM)**: envie os dois arquivos.
3. Confira a pré-visualização e os avisos (ex.: "9 metas sem Unidade/SLA") e clique em **Importar**.
4. Em **Configurações → SLA e Unidades**, preencha Unidade e SLA das metas novas.

> O PCM revisou o plano? Importe de novo: pesos e plano são trocados, **os lançamentos ficam**.

## Programador — lançar a execução

1. **Lançamentos**: escolha a(s) semana(s) (vem marcada a semana atual).
2. Opcional: abra **📌 Plano PCM congelado** e clique em **Trazer estas linhas do plano para lançar** —
   as atividades planejadas entram na grade com a Quantidade Programada preenchida.
3. Na grade (funciona como o Excel):
   - **Quantidade Realizada**: o que foi executado;
   - **No Plano**: *Sim* (atividade do plano) ou *Não* (extra plano);
   - **Justificativa**: obrigatória quando o realizado fica abaixo do programado;
   - **incluir**: digite na última linha em branco; **excluir**: selecione a linha e apague;
   - **corrigir**: edite a célula.
4. Clique em **💾 Salvar**. Nada é gravado antes disso; **↩️ Descartar** desfaz a edição.

O sistema recusa: data fora do trimestre, Depto que não é o seu, "No Plano" diferente de Sim/Não.
E avisa (sem bloquear): meta sem peso no seu Depto, realizado abaixo do programado sem justificativa.

## Pré-configuração do programador

- **Configurações → SLA e Unidades**: SLA = **produção esperada de uma equipe por dia** na
  unidade da meta (ex.: Socaria de Linha 84 m/dia). Preencha uma vez; vale para todos os
  trimestres. Com ele o Dashboard mostra **Dias de equipe p/ concluir** (pendente ÷ SLA).
- **Configurações → Equipes**: equipes do seu Depto (aparecem no menu da grade). Desmarque
  *Ativa* para tirar do menu sem perder o histórico.

## Dashboard

| Aba | O que mostra |
|---|---|
| **Resumo** | cartões da Gerência (aderência, projeção, mínimo semanal, último lançamento), um cartão por coordenação, quadro-resumo e as atividades que mais pesam no que falta |
| **Gerencial** | curva da Gerência; curvas das coordenações (realizado × meta); quadro e atividades |
| **Por Coordenação** | curva e atividades da coordenação (filtro por equipe e atividade), SLA, dias de equipe e motivos de não execução |
| **Financeiro** | curva OPEX (precisa do arquivo de orçamento configurado) |
| **Evolução** | aderência por trimestre e por ano, Gerência e coordenações |

A aderência segue a **regra oficial do PCM** (a mesma "Adr_Ativo" do Power BI): cada meta conta no
máximo 100% do seu plano (fazer a mais numa meta não compensa a que ficou para trás), e metas de
Saneamento Vegetal e Drenagem não entram na conta da Via (Configurações → Parâmetros).

Como ler: **Meta PCM** = quanto do plano deveria estar feito até a semana; **Realizado** = quanto foi
feito; **Projeção** = onde o trimestre fecha mantendo o ritmo médio; **Mín. semanal p/ meta** =
quanto precisa render por semana daqui em diante para fechar 100%.

## Dados

- **Exportação** (todos): baixa a planilha do trimestre no mesmo modelo do Excel (Pesos, Plano_PCM,
  Lancamentos, Listas) — serve de backup e pode ser reenviada. O **backup completo** (.zip) traz
  todos os trimestres e os cadastros. Recomendado: gerar ao fechar cada trimestre.
- **Upload → Planilha de trimestre** (PCM/admin): carrega trimestres passados. Aceita **vários arquivos
  juntos**: os exports do Power BI do PCM — **Planejado** (congelado, 1 ou mais trimestres), **Realizado**
  (o que os programadores lançaram no sistema) e o **export de pesos** (ex.: `data (9).xlsx`) — ou uma
  planilha antiga (Diário), modelo v3 ou backup. Antes de gravar aparece uma prévia por trimestre; o
  plano e os lançamentos de cada trimestre escolhido são **substituídos** pelos do PCM.
  Ordens sem Descrição Meta (fora do catálogo do plano) ficam de fora por padrão. Escolha o que gravar (Pesos+Plano e/ou Lançamentos); o que estiver
  marcado **substitui** o que existe naquele trimestre.

## Realizado pelo Power BI (quando a equipe não lança no app)

Dados → Upload → **Realizado do trimestre (export do Power BI)** (PCM/admin): exporte do Power BI do PCM a
tabela de ordens do trimestre (a mesma do "Realizado 1 ao 4º Tri") e envie. A tela mostra, por Depto, quantas
linhas vieram, quantas há hoje e quantas foram **digitadas no app**. Marque os Deptos a atualizar — por padrão
só os que não lançam no app, para a mesma ordem não contar duas vezes. Só os Deptos marcados são
substituídos; pode reenviar toda semana (substitui, não duplica).

## Lista de ativos

Dados → Upload → **Lista de ativos** (PCM/admin): envie o Excel com a relação, escolha a coluna do ativo e,
se houver, a de Depto ou Coordenação. A coluna **Ativo** da tela de Lançamentos passa a ser lista suspensa;
com Depto, cada programador vê só os ativos dele. Um novo envio **substitui** a lista inteira. Ajustes
pontuais: Configurações → Listas → Ativo (mostra os ativos que valem para todos os Deptos). Enquanto
nenhuma lista for enviada, o campo continua livre.

## Meus dados estão seguros?

- **O app "dormir" não apaga nada**: os dados ficam no banco (Neon). Se o app perder a ligação com o
  banco, aparece no menu lateral o aviso **"Banco local temporário"**: nesse caso **não lance nada** e
  avise o administrador (o que for gravado some ao reiniciar).
- **Subir de novo não duplica**: substitui os dados daquele trimestre.
- Se um upload for **apagar lançamentos digitados no app**, a tela avisa quantos são e só
  continua se você marcar "Entendo e quero substituir".
- **Trimestre fechado** não aceita upload (só o administrador).
- **Cópia automática**: antes de todo upload que troca lançamentos e antes de excluir um trimestre, o
  sistema guarda uma cópia. O administrador restaura em **Configurações → Trimestres → ♻️ Restaurar
  lançamentos** (as 10 últimas cópias de cada trimestre).
- Boa prática: **uma fonte por trimestre** — ou os programadores lançam no app, ou o PCM sobe o
  Realizado do SAP. E gere o **backup completo** (.zip) ao fechar cada trimestre.

## Fechar um trimestre

Configurações → Trimestres → Status **fechado**: os lançamentos ficam somente leitura e o
trimestre não aceita upload (o administrador ainda pode corrigir). Exporte o backup completo em seguida.
