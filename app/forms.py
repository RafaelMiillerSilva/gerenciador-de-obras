# -*- coding: utf-8 -*-
import json
from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.utils.translation import gettext_lazy as _

from app.models import SolicitacaoCadastro, Recibo, Relato, Termo, Proprietario
from app.models import SERVICOS_CHOICES, CONFORMIDADE_CHOICES


ESTADOS_BR = [
    ('', 'UF'),
    ('AC','AC'),('AL','AL'),('AP','AP'),('AM','AM'),('BA','BA'),
    ('CE','CE'),('DF','DF'),('ES','ES'),('GO','GO'),('MA','MA'),
    ('MT','MT'),('MS','MS'),('MG','MG'),('PA','PA'),('PB','PB'),
    ('PR','PR'),('PE','PE'),('PI','PI'),('RJ','RJ'),('RN','RN'),
    ('RS','RS'),('RO','RO'),('RR','RR'),('SC','SC'),('SP','SP'),
    ('SE','SE'),('TO','TO'),
]


class BootstrapAuthenticationForm(AuthenticationForm):
    # Sobrescrevemos o campo username para exibir "E-mail ou Número do CREA"
    username = forms.CharField(
        label="E-mail ou Número do CREA",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Seu e-mail ou número do CREA',
            'autofocus': True
        })
    )
    password = forms.CharField(
        label="Senha",
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Sua senha',
        })
    )


class SolicitacaoCadastroForm(forms.ModelForm):

    data_nascimento = forms.DateField(
        label='Data de nascimento',
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'autocomplete': 'bday',
        })
    )

    estado = forms.ChoiceField(
        label='Estado',
        choices=ESTADOS_BR,
        required=False,
    )

    termos = forms.BooleanField(
        label='Li e aceito os Termos de Uso',
        required=True,
        error_messages={'required': 'Voce precisa aceitar os termos para continuar.'},
    )

    class Meta:
        model  = SolicitacaoCadastro
        fields = [
            'nome_completo', 'email', 'celular', 'data_nascimento', 'numero_crea',
            'cep', 'logradouro', 'numero', 'complemento', 'bairro', 'cidade', 'estado',
        ]
        widgets = {
            'nome_completo': forms.TextInput(attrs={'placeholder': 'Ex: Joao da Silva', 'autocomplete': 'name'}),
            'email':         forms.EmailInput(attrs={'placeholder': 'seu@email.com', 'autocomplete': 'email'}),
            'celular':       forms.TextInput(attrs={'placeholder': '(00) 90000-0000', 'autocomplete': 'tel'}),
            'numero_crea':   forms.TextInput(attrs={'placeholder': 'Ex: 5062345678/SP'}),
            'cep':           forms.TextInput(attrs={'placeholder': '00000-000', 'autocomplete': 'postal-code'}),
            'logradouro':    forms.TextInput(attrs={'placeholder': 'Rua, Avenida, Estrada...', 'autocomplete': 'address-line1'}),
            'numero':        forms.TextInput(attrs={'placeholder': 'Ex: 123'}),
            'complemento':   forms.TextInput(attrs={'placeholder': 'Apto, Bloco, Casa...'}),
            'bairro':        forms.TextInput(attrs={'placeholder': 'Bairro'}),
            'cidade':        forms.TextInput(attrs={'placeholder': 'Cidade', 'autocomplete': 'address-level2'}),
        }

    def clean_email(self):
        from django.contrib.auth.models import User
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('Este e-mail ja possui uma conta ativa no sistema.')
        if SolicitacaoCadastro.objects.filter(email=email, status='pendente').exists():
            raise forms.ValidationError('Ja existe uma solicitacao pendente para este e-mail.')
        if SolicitacaoCadastro.objects.filter(email=email, status='aprovado').exists():
            raise forms.ValidationError('Este e-mail ja foi aprovado. Use a opcao de login.')
        # status 'negado' permite nova solicitacao — ok
        return email


class ProprietarioForm(forms.ModelForm):
    class Meta:
        model = Proprietario
        fields = ['nome', 'cpf_cnpj', 'email']
        widgets = {
            'nome': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nome completo do proprietario',
                'maxlength': '150'
            }),
            'cpf_cnpj': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'XXX.XXX.XXX-XX ou XX.XXX.XXX/0001-XX',
                'maxlength': '18'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'email@example.com'
            }),
        }


class ReciboForm(forms.ModelForm):
    class Meta:
        model = Recibo
        fields = [
            'empresa', 'local_obra',
            'area_construir', 'area_ampliar', 'area_reformar', 'area_regularizar',
            'tipo_edificacao', 'tipo_outros',
            'atividade_tecnica', 'atividade_outros',
            'data', 'valor_obra', 'status'
        ]
        widgets = {
            'empresa': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nome da empresa contratante',
                'maxlength': '200'
            }),
            'local_obra': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Local da obra (endereco)',
                'maxlength': '200'
            }),
            'area_construir': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '0,00',
                'step': '0.01'
            }),
            'area_ampliar': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '0,00',
                'step': '0.01'
            }),
            'area_reformar': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '0,00',
                'step': '0.01'
            }),
            'area_regularizar': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '0,00',
                'step': '0.01'
            }),
            'tipo_edificacao': forms.Select(attrs={
                'class': 'form-control'
            }),
            'tipo_outros': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Se selecionou "Outros"',
                'maxlength': '100'
            }),
            'atividade_tecnica': forms.Select(attrs={
                'class': 'form-control'
            }),
            'atividade_outros': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Se selecionou "Outros"',
                'maxlength': '100'
            }),
            'data': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'valor_obra': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '0,00',
                'step': '0.01'
            }),
            'status': forms.Select(attrs={
                'class': 'form-control'
            }),
        }


class RelatoForm(forms.ModelForm):
    opcoes_servicos = forms.MultipleChoiceField(
        label='Servicos executados',
        choices=SERVICOS_CHOICES,
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'form-check-input'
        }),
        required=True
    )

    class Meta:
        model = Relato
        fields = ['data', 'opcoes_servicos', 'conformidade', 'observacoes', 'decisoes_tecnicas', 'status']
        widgets = {
            'data': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'conformidade': forms.Select(attrs={
                'class': 'form-control'
            }),
            'observacoes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Observacoes adicionais sobre a visita...'
            }),
            'decisoes_tecnicas': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Decisoes tecnicas tomadas...'
            }),
            'status': forms.Select(attrs={
                'class': 'form-control'
            }),
        }

    def save(self, commit=True):
        instance = super().save(commit=False)
        servicos = self.cleaned_data.get('opcoes_servicos', [])
        instance.opcoes_servicos = json.dumps(servicos)
        if commit:
            instance.save()
        return instance


class TermoForm(forms.ModelForm):
    class Meta:
        model = Termo
        fields = ['descricao', 'decisoes_tecnicas', 'status']
        widgets = {
            'descricao': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 6,
                'placeholder': 'Descricao da conclusao da obra...'
            }),
            'decisoes_tecnicas': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 6,
                'placeholder': 'Decisoes tecnicas e consideracoes finais...'
            }),
            'status': forms.Select(attrs={
                'class': 'form-control'
            }),
        }
