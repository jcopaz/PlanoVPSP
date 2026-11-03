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

Como ler: **Meta PCM** = quanto do plano deveria estar feito até a semana; **Realizado** = quanto foi
feito; **Projeção** = onde o trimestre fecha mantendo o ritmo médio; **Mín. semanal p/ meta** =
quanto precisa render por semana daqui em diante para fechar 100%.

## Dados

- **Exportação** (todos): baixa a planilha do trimestre no mesmo modelo do Excel (Pesos, Plano_PCM,
  Lancamentos, Listas) — serve de backup e pode ser reenviada. O **backup completo** (.zip) traz
  todos os trimestres e os cadastros. Recomendado: gerar ao fechar cada trimestre.
- **Upload → Planilha de trimestre** (PCM/admin): carrega trimestres passados (planilha antiga com
  Diário, modelo v3 ou backup). Escolha o que gravar (Pesos+Plano e/ou Lançamentos); o que estiver
  marcado **substitui** o que existe naquele trimestre.

## Fechar um trimestre

Configurações → Trimestres → Status **fechado**: os lançamentos ficam somente leitura (o
administrador ainda pode corrigir). Exporte o backup completo em seguida.
