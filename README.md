# ConectObra — Gerenciador e Caderneta de Obras

Sistema web para gestão, acompanhamento técnico e documentação oficial de obras da construção civil, atuando como um **Livro de Ordem Digital** integrado às normas de responsabilidade técnica (CREA Adamantina).

---

## 📌 Principais Funcionalidades

### 1. Biblioteca de Cadernetas
- Painel central com visualização de obras organizadas por status (**Em andamento** e **Concluídas**).
- Identificação rápida do apelido da obra, proprietário/contratante e ano de abertura.
- Filtros dinâmicos por texto, ano e status.

### 2. Recibo Oficial de Registro Técnico
- Documento formal de abertura com estética timbrada.
- Cadastro completo do contratante/proprietário (Nome, CPF/CNPJ, E-mail).
- Quadro técnico de áreas ($m^2$): construir, ampliar, reformar e regularizar, com cálculo automático da área total.
- Classificação restrita por tipo de edificação (*Residencial*, *Industrial*, *Comercial*) e atividade técnica (*Direção técnica*, *Execução*, *Fiscalização*, *Projeto*).
- Campo para controle de assinaturas digitais.

### 3. Diário de Obra (Relatos de Visita Técnica)
- Registro cronológico de visitas ao canteiro.
- **Posição da Obra**: *De acordo com o projeto*, *Em desacordo com o projeto*, *Em andamento* ou *Paralisada*.
- Checklist estruturado de serviços executados (Fundação, Alvenaria, Cobertura, Estrutura, Hidráulica, Elétrica, Acabamento, Outros).
- Registro de observações e decisões técnicas tomadas.
- Galeria de anexos fotográficos com suporte a upload de múltiplas fotos, pré-visualização e exclusão.

### 4. Termo de Conclusão da Obra
- Documento solene de encerramento da obra com formato de laudo/termo oficial.
- Cláusula de abertura obrigatória:
  > *"Nós, abaixo assinados, proprietário e profissional responsável, pela execução da obra acima apontada declaramos que..."*
- Texto descritivo dos serviços concluídos e condições de habitabilidade.
- Cláusula de encerramento legal obrigatória com referência às legislações vigentes e preenchimento dinâmico de cidade e data.
- Campo formal para assinaturas do Proprietário e do Responsável Técnico.

---

## 🛠️ Tecnologias Utilizadas

- **Linguagem**: Python 3.12+
- **Framework Web**: Django 5.1
- **Processamento de Imagens**: Pillow (uploads de fotos e ícones)
- **Tipagem**: `django-stubs`
- **Banco de Dados**: SQLite (padrão de desenvolvimento)
- **Frontend**: Django Templates, HTML5 semântico, CSS3 (design de documento oficial / folha timbrada) e JavaScript puro

---

## 🚀 Como Executar o Projeto Localmente

1. **Clone o repositório e acesse a pasta:**
   ```bash
   git clone https://github.com/RafaelMiillerSilva/gerenciador-de-obras.git
   cd gerenciador-de-obras
   ```

2. **Ative o ambiente virtual:**
   ```bash
   # No Windows (PowerShell):
   .\venv\Scripts\Activate.ps1
   ```

3. **Instale as dependências:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Aplique as migrações do banco de dados:**
   ```bash
   python manage.py migrate
   ```

5. **Inicie o servidor de desenvolvimento:**
   ```bash
   python manage.py runserver
   ```

Acesse em seu navegador: [http://127.0.0.1:8000](http://127.0.0.1:8000)
