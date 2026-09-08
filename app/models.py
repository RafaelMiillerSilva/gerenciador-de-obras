# -*- coding: utf-8 -*-
# pyright: reportMissingTypeStubs=false
from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
import json


# Choices
NIVEL_CHOICES = [
    (1, 'Nivel 1 - Dev'),
    (2, 'Nivel 2 - Gestor'),
    (3, 'Nivel 3 - Engenheiro'),
]

STATUS_SOLICITACAO = [
    ('pendente', 'Pendente'),
    ('aprovado', 'Aprovado'),
    ('negado',   'Negado'),
]

STATUS_DOCUMENTO = [
    ('em_andamento',    'Em andamento'),
    ('pronto_assinar',  'Pronto para assinar'),
    ('concluido',       'Concluido'),
    ('cancelado',       'Cancelado'),
]

TIPO_EDIFICACAO = [
    ('residencial', 'Residencial'),
    ('industrial',  'Industrial'),
    ('comercial',   'Comercial'),
]

ATIVIDADE_TECNICA = [
    ('direcao_tecnica', 'Direção técnica'),
    ('execucao',        'Execução'),
    ('fiscalizacao',    'Fiscalização'),
    ('projeto',         'Projeto'),
]

POSICAO_OBRA_CHOICES = [
    ('de_acordo',    'De acordo com o projeto'),
    ('em_desacordo', 'Em desacordo com o projeto'),
    ('em_andamento', 'Em andamento'),
    ('paralisada',   'Paralisada'),
]

CONFORMIDADE_CHOICES = POSICAO_OBRA_CHOICES

TIPO_SIGNATARIO = [
    ('engenheiro',   'Engenheiro'),
    ('proprietario', 'Proprietario'),
]

TIPO_DOC_ASSINATURA = [
    ('recibo', 'Recibo'),
    ('relato', 'Relato de Visita'),
    ('termo',  'Termo de Conclusao'),
]

STATUS_ASSINATURA = [
    ('pendente',   'Pendente'),
    ('parcial',    'Parcialmente assinado'),
    ('concluido',  'Concluido'),
    ('rejeitado',  'Rejeitado'),
]

SERVICOS_CHOICES = [
    ('fundacao',        'Fundacao'),
    ('alvenaria',       'Alvenaria'),
    ('cobertura',       'Cobertura'),
    ('estrutura',       'Estrutura'),
    ('hidraulica',      'Hidraulica'),
    ('eletrica',        'Eletrica'),
    ('acabamento',      'Acabamento'),
    ('outros',          'Outros'),
]


class PerfilUsuario(models.Model):
    usuario         = models.OneToOneField(User, on_delete=models.CASCADE, related_name='perfil')
    nivel           = models.IntegerField('Nivel de acesso', choices=NIVEL_CHOICES, default=3)
    celular         = models.CharField('Celular',        max_length=20,  blank=True)
    data_nascimento = models.DateField('Data de Nascimento', null=True, blank=True)
    numero_crea     = models.CharField('Numero do CREA', max_length=30,  blank=True)
    cep             = models.CharField('CEP',            max_length=10,  blank=True)
    logradouro      = models.CharField('Logradouro',     max_length=200, blank=True)
    numero          = models.CharField('Numero',         max_length=10,  blank=True)
    complemento     = models.CharField('Complemento',    max_length=100, blank=True)
    bairro          = models.CharField('Bairro',         max_length=100, blank=True)
    cidade          = models.CharField('Cidade',         max_length=100, blank=True)
    estado          = models.CharField('Estado',         max_length=2,   blank=True)

    class Meta:
        verbose_name        = 'Perfil'
        verbose_name_plural = 'Perfis'

    def __str__(self):
        return f'Perfil de {self.usuario.username} (Nivel {self.nivel})'

    @property
    def is_dev(self):
        return self.nivel == 1

    @property
    def is_gestor(self):
        return self.nivel == 2

    @property
    def is_admin(self):
        return self.nivel in (1, 2)


class SolicitacaoCadastro(models.Model):
    status          = models.CharField('Status', max_length=10, choices=STATUS_SOLICITACAO,
                                       default='pendente', db_index=True)
    criado_em       = models.DateTimeField('Solicitado em',  auto_now_add=True)
    atualizado_em   = models.DateTimeField('Atualizado em',  auto_now=True)
    analisado_por   = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                        related_name='solicitacoes_analisadas')
    motivo_negacao  = models.TextField('Motivo da negacao', blank=True)
    nome_completo   = models.CharField('Nome completo',     max_length=150)
    email           = models.EmailField('E-mail')
    celular         = models.CharField('Celular',           max_length=20,  blank=True)
    data_nascimento = models.DateField('Data de nascimento', null=True, blank=True)
    numero_crea     = models.CharField('Numero do CREA',    max_length=30,  blank=True)
    cep             = models.CharField('CEP',               max_length=10,  blank=True)
    logradouro      = models.CharField('Logradouro',        max_length=200, blank=True)
    numero          = models.CharField('Numero',            max_length=10,  blank=True)
    complemento     = models.CharField('Complemento',       max_length=100, blank=True)
    bairro          = models.CharField('Bairro',            max_length=100, blank=True)
    cidade          = models.CharField('Cidade',            max_length=100, blank=True)
    estado          = models.CharField('Estado',            max_length=2,   blank=True)

    class Meta:
        verbose_name        = 'Solicitacao de Cadastro'
        verbose_name_plural = 'Solicitacoes de Cadastro'
        ordering            = ['-criado_em']

    def __str__(self):
        return f'{self.nome_completo} - {self.get_status_display()}'


class Caderneta(models.Model):
    usuario      = models.ForeignKey(User, on_delete=models.PROTECT, related_name='cadernetas')
    apelido      = models.CharField('Nome / Apelido da obra', max_length=150)
    icone        = models.ImageField('Icone da obra', upload_to='cadernetas/icones/',
                                     null=True, blank=True)
    criado_em    = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'Caderneta'
        verbose_name_plural = 'Cadernetas'
        ordering            = ['-criado_em']

    def __str__(self):
        return str(self.apelido)

    @property
    def concluida(self):
        """Caderneta concluida = todos os documentos internos assinados."""
        recibo = getattr(self, 'recibo', None)
        if not recibo:
            return False
        if recibo.status != 'concluido':
            return False
        if recibo.relatos.exclude(status='concluido').exists():
            return False
        termo = getattr(recibo, 'termo', None)
        if not termo or termo.status != 'concluido':
            return False
        return True

    @property
    def ano(self):
        return getattr(self.criado_em, 'year', None)

    @property
    def proprietario_nome(self):
        recibo = getattr(self, 'recibo', None)
        if recibo and getattr(recibo, 'proprietario', None):
            return str(recibo.proprietario.nome)
        return None


class Proprietario(models.Model):
    nome     = models.CharField('Nome',     max_length=150)
    cpf_cnpj = models.CharField('CPF/CNPJ', max_length=18)
    email    = models.EmailField('E-mail')

    class Meta:
        verbose_name        = 'Proprietario'
        verbose_name_plural = 'Proprietarios'

    def __str__(self):
        return str(self.nome)


class Recibo(models.Model):
    caderneta        = models.OneToOneField(Caderneta, on_delete=models.CASCADE,
                                            related_name='recibo',
                                            verbose_name='Caderneta')
    usuario          = models.ForeignKey(User, on_delete=models.PROTECT,
                                         related_name='recibos',
                                         verbose_name='Responsavel tecnico')
    proprietario     = models.ForeignKey(Proprietario, on_delete=models.PROTECT,
                                         related_name='recibos',
                                         verbose_name='Proprietario')
    empresa          = models.CharField('Empresa contratante', max_length=200)
    local_obra       = models.CharField('Local da obra',       max_length=200)

    area_construir   = models.DecimalField('Area a construir',   max_digits=10, decimal_places=2, null=True, blank=True)
    area_ampliar     = models.DecimalField('Area a ampliar',     max_digits=10, decimal_places=2, null=True, blank=True)
    area_reformar    = models.DecimalField('Area a reformar',    max_digits=10, decimal_places=2, null=True, blank=True)
    area_regularizar = models.DecimalField('Area a regularizar', max_digits=10, decimal_places=2, null=True, blank=True)

    tipo_edificacao  = models.CharField('Tipo de edificacao',  max_length=30, choices=TIPO_EDIFICACAO)
    tipo_outros      = models.CharField('Tipo (outros)',        max_length=100, blank=True)
    atividade_tecnica = models.CharField('Atividade tecnica',  max_length=20, choices=ATIVIDADE_TECNICA)
    atividade_outros = models.CharField('Atividade (outros)',  max_length=100, blank=True)

    data             = models.DateField('Data da obra')
    valor_obra       = models.DecimalField('Valor da obra', max_digits=12, decimal_places=2)
    status           = models.CharField('Status', max_length=20, choices=STATUS_DOCUMENTO, default='em_andamento')
    criado_em        = models.DateTimeField(auto_now_add=True)
    atualizado_em    = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'Recibo'
        verbose_name_plural = 'Recibos'

    def __str__(self):
        return f'Recibo - {self.caderneta.apelido}'

    @property
    def area_total(self):
        total = 0.0
        if self.area_construir:
            total += float(str(self.area_construir))
        if self.area_ampliar:
            total += float(str(self.area_ampliar))
        if self.area_reformar:
            total += float(str(self.area_reformar))
        if self.area_regularizar:
            total += float(str(self.area_regularizar))
        return total


class Relato(models.Model):
    recibo           = models.ForeignKey(Recibo, on_delete=models.CASCADE, related_name='relatos')
    data             = models.DateField('Data da visita')
    opcoes_servicos  = models.TextField('Servicos executados', help_text='Marque os servicos realizados')
    posicao_obra     = models.CharField('Posição da obra', max_length=30, choices=POSICAO_OBRA_CHOICES, default='de_acordo')
    observacoes      = models.TextField('Observacoes', blank=True)
    decisoes_tecnicas = models.TextField('Decisoes tecnicas', blank=True)
    imagem           = models.ImageField('Foto / Imagem da visita', upload_to='relatos/fotos/', null=True, blank=True)
    status           = models.CharField('Status', max_length=20, choices=STATUS_DOCUMENTO, default='em_andamento')
    criado_em        = models.DateTimeField(auto_now_add=True)
    atualizado_em    = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'Relato'
        verbose_name_plural = 'Relatos'
        ordering            = ['-data']

    def __str__(self):
        return f'Relato - {self.data}'

    @property
    def conformidade(self):
        return self.get_posicao_obra_display()

    def get_servicos_lista(self):
        """Retorna lista de servicos selecionados."""
        try:
            return json.loads(self.opcoes_servicos) if isinstance(self.opcoes_servicos, str) else self.opcoes_servicos
        except:
            return []


class FotoRelato(models.Model):
    relato    = models.ForeignKey(Relato, on_delete=models.CASCADE, related_name='fotos')
    imagem    = models.ImageField('Foto da visita', upload_to='relatos/fotos/')
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = 'Foto do Relato'
        verbose_name_plural = 'Fotos do Relato'
        ordering            = ['criado_em']

    def __str__(self):
        return f'Foto {self.pk} de Relato {self.relato.pk}'


class Termo(models.Model):
    recibo           = models.OneToOneField(Recibo, on_delete=models.CASCADE, related_name='termo')
    declaracao_texto = models.TextField('Declaracao de conclusao', blank=True)
    decidido         = models.BooleanField('Decidido', default=False)
    status           = models.CharField('Status', max_length=20, choices=STATUS_DOCUMENTO, default='em_andamento')
    criado_em        = models.DateTimeField(auto_now_add=True)
    atualizado_em    = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'Termo'
        verbose_name_plural = 'Termos'

    def __str__(self):
        return f'Termo - {self.recibo.caderneta.apelido}'