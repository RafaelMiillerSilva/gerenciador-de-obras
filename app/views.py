import secrets
import string
import json
import hashlib
import uuid
import re
from urllib.parse import quote
from datetime import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth.views import LoginView
from django.core.mail import send_mail
from django.http import HttpRequest, HttpResponseForbidden, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.conf import settings
from django.utils import timezone
from django.urls import reverse

from app.forms import (
    SolicitacaoCadastroForm, BootstrapAuthenticationForm,
    ReciboForm, RelatoForm, TermoForm, ProprietarioForm
)
from app.models import (
    PerfilUsuario, SolicitacaoCadastro, Caderneta,
    Recibo, Relato, FotoRelato, Termo, Proprietario,
    AssinaturaDocumento
)


class CustomLoginView(LoginView):
    template_name = 'app/login.html'
    authentication_form = BootstrapAuthenticationForm

    def get_success_url(self):
        user = self.request.user
        try:
            nivel = user.perfil.nivel
            if nivel in (1, 2):
                return '/painel/'
            else:
                return '/cadernetas/'
        except PerfilUsuario.DoesNotExist:
            return '/'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Entrar'
        context['year'] = datetime.now().year
        return context


def _is_admin(user):
    try:
        return user.perfil.is_admin
    except PerfilUsuario.DoesNotExist:
        return False


def _gerar_senha(tamanho=12):
    chars = string.ascii_letters + string.digits + '!@#$%'
    return ''.join(secrets.choice(chars) for _ in range(tamanho))


def _gerar_username(nome_completo):
    base = nome_completo.lower().split()[0]
    username = base
    contador = 1
    while User.objects.filter(username=username).exists():
        username = f'{base}{contador}'
        contador += 1
    return username


def _enviar_email_aprovacao(user, senha_temp, solicitacao):
    assunto = 'CREA Adamantina - Seu cadastro foi aprovado!'
    corpo = (
        f'Ola, {user.first_name}!\n\n'
        f'Sua solicitacao de cadastro no sistema do CREA de Adamantina foi APROVADA.\n\n'
        f'Seus dados de acesso:\n'
        f'  Usuario: {user.username}\n'
        f'  Senha:   {senha_temp}\n\n'
        f'Acesse o sistema em: {settings.SITE_URL}\n'
        f'Recomendamos que voce altere sua senha no primeiro acesso.\n\n'
        f'Atenciosamente,\n'
        f'Equipe CREA Adamantina'
    )
    try:
        send_mail(
            assunto, corpo,
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=False,
        )
    except Exception as e:
        print(f'[CREA] Erro ao enviar e-mail para {user.email}: {e}')


def _enviar_email_negacao(solicitacao):
    assunto = 'CREA Adamantina - Solicitacao de cadastro nao aprovada'
    motivo = solicitacao.motivo_negacao or 'Nao informado.'
    corpo = (
        f'Ola, {solicitacao.nome_completo}!\n\n'
        f'Infelizmente sua solicitacao de cadastro no sistema do CREA de Adamantina nao foi aprovada.\n\n'
        f'Motivo: {motivo}\n\n'
        f'Se acredita que houve um engano, entre em contato com a administracao do CREA.\n\n'
        f'Atenciosamente,\n'
        f'Equipe CREA Adamantina'
    )
    try:
        send_mail(
            assunto, corpo,
            settings.DEFAULT_FROM_EMAIL,
            [solicitacao.email],
            fail_silently=False,
        )
    except Exception as e:
        print(f'[CREA] Erro ao enviar e-mail para {solicitacao.email}: {e}')


def _get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '127.0.0.1')


def _enviar_email_recibo_homologado(recibo):
    assunto = f'CREA Adamantina - Recibo Homologado: Obra {recibo.caderneta.apelido}'
    corpo = (
        f'Ola, {recibo.usuario.first_name}!\n\n'
        f'Informamos que o Recibo de Responsabilidade Tecnica da obra "{recibo.caderneta.apelido}" '
        f'foi HOMOLOGADO E ASSINADO DIGITALMENTE pelo Gestor do CREA Adamantina.\n\n'
        f'Dados da Obra:\n'
        f'  Obra: {recibo.caderneta.apelido}\n'
        f'  Contratante: {recibo.proprietario.nome}\n'
        f'  Data de Homologacao: {datetime.now().strftime("%d/%m/%Y %H:%M")}\n\n'
        f'Acesse o sistema para visualizar o documento oficial homologado:\n'
        f'  {settings.SITE_URL}/cadernetas/{recibo.caderneta.pk}/\n\n'
        f'Atenciosamente,\n'
        f'Equipe CREA Adamantina'
    )
    try:
        send_mail(
            assunto, corpo,
            settings.DEFAULT_FROM_EMAIL,
            [recibo.usuario.email],
            fail_silently=False,
        )
    except Exception as e:
        print(f'[CREA] Erro ao enviar e-mail de homologacao para {recibo.usuario.email}: {e}')


def _enviar_email_recibo_recusado(recibo):
    assunto = f'CREA Adamantina - Pendencia Apontada no Recibo: Obra {recibo.caderneta.apelido}'
    corpo = (
        f'Ola, {recibo.usuario.first_name}!\n\n'
        f'O Recibo de Responsabilidade Tecnica da obra "{recibo.caderneta.apelido}" '
        f'foi analisado pelo Gestor do CREA e NAO pode ser homologado no momento.\n\n'
        f'Motivo / Inconsistencia apontada pelo Gestor:\n'
        f'  "{recibo.motivo_recusa}"\n\n'
        f'O formulario do Recibo foi liberado para edicao no sistema para que voce faca as correcoes necessarias '
        f'e solicite novamente a homologacao.\n\n'
        f'Acesse a obra para corrigir:\n'
        f'  {settings.SITE_URL}/recibos/{recibo.pk}/\n\n'
        f'Atenciosamente,\n'
        f'Equipe CREA Adamantina'
    )
    try:
        send_mail(
            assunto, corpo,
            settings.DEFAULT_FROM_EMAIL,
            [recibo.usuario.email],
            fail_silently=False,
        )
    except Exception as e:
        print(f'[CREA] Erro ao enviar e-mail de recusa para {recibo.usuario.email}: {e}')


def home(request):
    assert isinstance(request, HttpRequest)
    return render(request, 'app/index.html', {
        'title': 'Inicio',
        'year': datetime.now().year,
    })


def contact(request):
    assert isinstance(request, HttpRequest)
    return render(request, 'app/contact.html', {
        'title': 'Contato',
        'year': datetime.now().year,
    })


def about(request):
    assert isinstance(request, HttpRequest)
    return render(request, 'app/about.html', {
        'title': 'Sobre',
        'year': datetime.now().year,
    })


def solicitar_cadastro(request):
    assert isinstance(request, HttpRequest)

    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        form = SolicitacaoCadastroForm(request.POST)
        if form.is_valid():
            solicitacao = form.save(commit=False)
            solicitacao.status = 'pendente'
            solicitacao.save()

            admins_list = list(filter(None,
                User.objects.filter(perfil__nivel__in=[1, 2])
                            .values_list('email', flat=True)
            ))

            if admins_list:
                try:
                    send_mail(
                        'Nova solicitacao de cadastro — CREA Adamantina',
                        f'Solicitacao de cadastro:\n\nNome: {solicitacao.nome_completo}\nEmail: {solicitacao.email}\n\nAcesse o painel para revisar.',
                        settings.DEFAULT_FROM_EMAIL,
                        admins_list,
                        fail_silently=False,
                    )
                except Exception as e:
                    print(f'[CREA] Erro ao enviar e-mail de notificacao: {e}')

            return redirect('solicitacao_enviada')
    else:
        form = SolicitacaoCadastroForm()

    return render(request, 'app/solicitar_cadastro.html', {
        'title': 'Solicitar Cadastro',
        'year': datetime.now().year,
        'form': form,
    })


def solicitacao_enviada(request):
    assert isinstance(request, HttpRequest)
    return render(request, 'app/solicitacao_enviada.html', {
        'title': 'Solicitacao Enviada',
        'year': datetime.now().year,
    })


# ─── MODIFICADO: PAINEL ADMINISTRATIVO MACRO ───────────────────
def painel_admin(request):
    assert isinstance(request, HttpRequest)

    if not _is_admin(request.user):
        return HttpResponseForbidden('Acesso negado.')

    # 1. Filtros das Solicitações segregadas por Status
    pendentes = SolicitacaoCadastro.objects.filter(status='pendente').order_by('-criado_em')
    aprovadas = SolicitacaoCadastro.objects.filter(status='aprovado').order_by('-atualizado_em')
    negadas = SolicitacaoCadastro.objects.filter(status='negado').order_by('-atualizado_em')

    # 2. Todos os Usuários do Sistema (com carregamento do Perfil para evitar queries N+1)
    usuarios = User.objects.all().select_related('perfil').order_by('-date_joined')

    # 3. Obras com solicitação de assinatura (Regra: Gestor só visualiza quando solicitada a assinatura)
    recibos_pendentes = Recibo.objects.filter(status='aguardando_gestor').select_related('caderneta', 'usuario', 'proprietario').order_by('-atualizado_em')
    recibos_homologados = Recibo.objects.filter(status='concluido').select_related('caderneta', 'usuario', 'proprietario', 'gestor_signatario').order_by('-assinado_gestor_em')

    # 4. Captura o nível do Admin logado com segurança
    nivel = request.user.perfil.nivel

    return render(request, 'app/painel_admin.html', {
        'title': 'Painel Administrativo',
        'year': datetime.now().year,
        'nivel': nivel,
        'pendentes': pendentes,
        'aprovadas': aprovadas,
        'negadas': negadas,
        'usuarios': usuarios,
        'recibos_pendentes': recibos_pendentes,
        'recibos_homologados': recibos_homologados,
    })


def aprovar_solicitacao(request, pk):
    if not _is_admin(request.user):
        return HttpResponseForbidden('Acesso negado.')

    solicitacao = get_object_or_404(SolicitacaoCadastro, pk=pk)

    if solicitacao.status != 'pendente':
        messages.error(request, 'Esta solicitacao ja foi processada.')
        return redirect('painel_admin')

    username = _gerar_username(solicitacao.nome_completo)
    senha_temp = _gerar_senha()

    user = User.objects.create_user(
        username=username,
        email=solicitacao.email,
        password=senha_temp,
        first_name=solicitacao.nome_completo.split()[0],
        last_name=' '.join(solicitacao.nome_completo.split()[1:]),
    )

    PerfilUsuario.objects.create(
        usuario=user,
        nivel=3,
        celular=solicitacao.celular,
        data_nascimento=solicitacao.data_nascimento,
        numero_crea=solicitacao.numero_crea,
        cep=solicitacao.cep,
        logradouro=solicitacao.logradouro,
        numero=solicitacao.numero,
        complemento=solicitacao.complemento,
        bairro=solicitacao.bairro,
        cidade=solicitacao.cidade,
        estado=solicitacao.estado,
    )

    solicitacao.status = 'aprovado'
    solicitacao.analisado_por = request.user
    solicitacao.save()

    _enviar_email_aprovacao(user, senha_temp, solicitacao)

    messages.success(request, f'Solicitacao de {solicitacao.nome_completo} aprovada com sucesso!')
    return redirect('painel_admin')


def negar_solicitacao(request, pk):
    if not _is_admin(request.user):
        return HttpResponseForbidden('Acesso negado.')

    solicitacao = get_object_or_404(SolicitacaoCadastro, pk=pk)

    if solicitacao.status != 'pendente':
        messages.error(request, 'Esta solicitacao ja foi processada.')
        return redirect('painel_admin')

    if request.method == 'POST':
        motivo = request.POST.get('motivo', '').strip()

        if not motivo:
            messages.error(request, 'Informe um motivo para a negacao.')
            return redirect('painel_admin')

        solicitacao.status = 'negado'
        solicitacao.motivo_negacao = motivo
        solicitacao.analisado_por = request.user
        solicitacao.save()

        _enviar_email_negacao(solicitacao)

        messages.success(request, f'Solicitacao de {solicitacao.nome_completo} negada.')
        return redirect('painel_admin')

    return render(request, 'app/negar_solicitacao.html', {
        'title': 'Negar Solicitacao',
        'year': datetime.now().year,
        'solicitacao': solicitacao,
    })


# ─── CADERNETAS ────────────────────────────────────────────────

@login_required
def cadernetas(request):
    """Exibe todas as cadernetas do usuário com filtro de status."""
    cadernetas_list = (
        Caderneta.objects
        .filter(usuario=request.user)
        .select_related('recibo__proprietario')
        .order_by('-criado_em')
    )

    cadernetas_andamento = [
        c for c in cadernetas_list if not c.concluida
    ]

    cadernetas_concluidas = [
        c for c in cadernetas_list if c.concluida
    ]

    anos = sorted(
        set(c.criado_em.year for c in cadernetas_list),
        reverse=True
    )

    return render(request, 'app/cadernetas.html', {
        'title': 'Cadernetas',
        'year': datetime.now().year,
        'cadernetas_andamento': cadernetas_andamento,
        'cadernetas_concluidas': cadernetas_concluidas,
        'anos': anos,
    })


@require_POST
@login_required
def criar_caderneta(request):
    """Cria uma nova caderneta para o usuário autenticado."""
    apelido = request.POST.get('apelido', '').strip()

    if not apelido:
        messages.error(request, 'Informe um nome para a caderneta.')
        return redirect('cadernetas')

    Caderneta.objects.create(
        usuario=request.user,
        apelido=apelido,
    )

    messages.success(request, 'Caderneta criada com sucesso!')
    return redirect('cadernetas')


@login_required
def detalhe_caderneta(request, pk):
    """Exibe os detalhes de uma caderneta específica."""
    if _is_admin(request.user):
        caderneta = get_object_or_404(Caderneta, pk=pk)
    else:
        caderneta = get_object_or_404(Caderneta, pk=pk, usuario=request.user)

    recibo = getattr(caderneta, 'recibo', None)
    relatos = []
    termo = None
    alerta_recusa = False

    if recibo:
        relatos = recibo.relatos.all()
        try:
            termo = recibo.termo
        except:
            termo = None

        if recibo.status == 'recusado' and not recibo.recusa_visualizada and request.user == caderneta.usuario:
            alerta_recusa = True

    return render(request, 'app/detalhe_caderneta.html', {
        'title': caderneta.apelido,
        'year': datetime.now().year,
        'caderneta': caderneta,
        'recibo': recibo,
        'relatos': relatos,
        'termo': termo,
        'alerta_recusa': alerta_recusa,
        'is_gestor': _is_admin(request.user),
    })


# ─── RECIBOS, RELATOS E TERMOS ─────────────────────────────────

@login_required
def criar_recibo(request, pk):
    """Cria um novo recibo para a caderneta."""
    caderneta = get_object_or_404(Caderneta, pk=pk, usuario=request.user)

    if hasattr(caderneta, 'recibo'):
        messages.warning(request, 'Esta caderneta ja possui um recibo.')
        return redirect('detalhe_caderneta', pk=pk)

    if request.method == 'POST':
        proprietario_form = ProprietarioForm(request.POST, prefix='prop')
        recibo_form = ReciboForm(request.POST)

        if proprietario_form.is_valid() and recibo_form.is_valid():
            proprietario = proprietario_form.save()
            recibo = recibo_form.save(commit=False)
            recibo.caderneta = caderneta
            recibo.usuario = request.user
            recibo.proprietario = proprietario
            recibo.save()

            messages.success(request, 'Recibo criado com sucesso!')
            return redirect('detalhe_caderneta', pk=pk)
        else:
            if proprietario_form.errors:
                for field, errors in proprietario_form.errors.items():
                    messages.error(request, f'Proprietario - {field}: {errors[0]}')
            if recibo_form.errors:
                for field, errors in recibo_form.errors.items():
                    messages.error(request, f'Recibo - {field}: {errors[0]}')
    else:
        proprietario_form = ProprietarioForm(prefix='prop')
        recibo_form = ReciboForm()

    return render(request, 'app/criar_recibo.html', {
        'title': 'Criar Recibo',
        'year': datetime.now().year,
        'caderneta': caderneta,
        'proprietario_form': proprietario_form,
        'recibo_form': recibo_form,
    })


@login_required
def detalhe_recibo(request, pk):
    """Exibe e edita os detalhes de um recibo."""
    if _is_admin(request.user):
        recibo = get_object_or_404(Recibo, pk=pk)
    else:
        recibo = get_object_or_404(Recibo, pk=pk, caderneta__usuario=request.user)

    is_gestor = _is_admin(request.user)
    is_owner = (recibo.caderneta.usuario == request.user)
    is_locked = recibo.status in ('aguardando_gestor', 'concluido')
    alerta_recusa = (recibo.status == 'recusado' and not recibo.recusa_visualizada and is_owner)

    if request.method == 'POST':
        if is_locked and not is_gestor:
            messages.error(request, 'Este documento está sob análise do CREA ou já foi homologado e não pode ser editado.')
            return redirect('detalhe_recibo', pk=recibo.pk)

        proprietario_form = ProprietarioForm(request.POST, prefix='prop', instance=recibo.proprietario)
        recibo_form = ReciboForm(request.POST, instance=recibo)

        if proprietario_form.is_valid() and recibo_form.is_valid():
            proprietario_form.save()
            recibo_obj = recibo_form.save(commit=False)
            recibo_obj.status = 'em_andamento'
            recibo_obj.motivo_recusa = ''
            recibo_obj.recusa_visualizada = False
            recibo_obj.save()

            messages.success(request, 'Recibo atualizado com sucesso! Status resetado para "Em andamento".')
            return redirect('detalhe_caderneta', pk=recibo.caderneta.pk)
        else:
            if proprietario_form.errors:
                for field, errors in proprietario_form.errors.items():
                    messages.error(request, f'Proprietario - {field}: {errors[0]}')
            if recibo_form.errors:
                for field, errors in recibo_form.errors.items():
                    messages.error(request, f'Recibo - {field}: {errors[0]}')
    else:
        proprietario_form = ProprietarioForm(instance=recibo.proprietario, prefix='prop')
        recibo_form = ReciboForm(instance=recibo)

    return render(request, 'app/detalhe_recibo.html', {
        'title': f'Recibo - {recibo.caderneta.apelido}',
        'year': datetime.now().year,
        'recibo': recibo,
        'proprietario_form': proprietario_form,
        'recibo_form': recibo_form,
        'is_gestor': is_gestor,
        'is_owner': is_owner,
        'is_locked': is_locked,
    })



@login_required
def criar_relato(request, pk):
    """Cria um novo relato de visita."""
    caderneta = get_object_or_404(Caderneta, pk=pk, usuario=request.user)
    
    try:
        recibo = caderneta.recibo
    except Caderneta.recibo.RelatedObjectDoesNotExist:
        messages.error(request, 'Eh necessario criar um recibo antes de adicionar relatos de visita.')
        return redirect('detalhe_caderneta', pk=pk)

    if request.method == 'POST':
        form = RelatoForm(request.POST, request.FILES)
        if form.is_valid():
            relato = form.save(commit=False)
            relato.recibo = recibo
            relato.save()

            # Salvar multiplas fotos anexadas
            for f in request.FILES.getlist('fotos'):
                FotoRelato.objects.create(relato=relato, imagem=f)

            messages.success(request, 'Relato criado com sucesso!')
            return redirect('detalhe_caderneta', pk=pk)
        else:
            for field, errors in (form.errors or {}).items():
                messages.error(request, f'{field}: {errors[0]}')
    else:
        form = RelatoForm()

    return render(request, 'app/criar_relato.html', {
        'title': 'Criar Relato de Visita',
        'year': datetime.now().year,
        'caderneta': caderneta,
        'recibo': recibo,
        'form': form,
    })


@login_required
def detalhe_relato(request, pk):
    """Exibe e edita os detalhes de um relato."""
    relato = get_object_or_404(Relato, pk=pk, recibo__caderneta__usuario=request.user)

    if request.method == 'POST':
        form = RelatoForm(request.POST, request.FILES, instance=relato)
        if form.is_valid():
            relato_obj = form.save(commit=False)
            relato_obj.status = 'em_andamento'
            relato_obj.save()

            # Salvar multiplas fotos anexadas
            for f in request.FILES.getlist('fotos'):
                FotoRelato.objects.create(relato=relato_obj, imagem=f)

            messages.success(request, 'Relato atualizado com sucesso! Status resetado para "Em andamento".')
            return redirect('detalhe_relato', pk=relato.pk)
        else:
            for field, errors in (form.errors or {}).items():
                messages.error(request, f'{field}: {errors[0]}')
    else:
        form = RelatoForm(instance=relato)

    return render(request, 'app/detalhe_relato.html', {
        'title': f'Relato - {relato.data}',
        'year': datetime.now().year,
        'relato': relato,
        'relato_servicos': relato.get_servicos_lista(),
        'fotos': relato.fotos.all(),
        'form': form,
    })


@require_POST
@login_required
def remover_foto_relato(request, pk):
    """Remove uma foto específica de um relato."""
    foto = get_object_or_404(FotoRelato, pk=pk, relato__recibo__caderneta__usuario=request.user)
    relato_pk = foto.relato.pk
    foto.delete()
    messages.success(request, 'Foto removida com sucesso!')
    return redirect('detalhe_relato', pk=relato_pk)


@login_required
def criar_termo(request, pk):
    """Cria um novo termo de conclusão."""
    caderneta = get_object_or_404(Caderneta, pk=pk, usuario=request.user)
    
    try:
        recibo = caderneta.recibo
    except Caderneta.recibo.RelatedObjectDoesNotExist:
        messages.error(request, 'Eh necessario criar um recibo antes de gerar um termo de conclusao.')
        return redirect('detalhe_caderneta', pk=pk)

    if hasattr(recibo, 'termo'):
        messages.warning(request, 'Esta caderneta ja possui um termo de conclusao.')
        return redirect('detalhe_caderneta', pk=pk)

    if request.method == 'POST':
        form = TermoForm(request.POST)
        if form.is_valid():
            termo = form.save(commit=False)
            termo.recibo = recibo
            termo.save()

            messages.success(request, 'Termo criado com sucesso!')
            return redirect('detalhe_caderneta', pk=pk)
        else:
            for field, errors in (form.errors or {}).items():
                messages.error(request, f'{field}: {errors[0]}')
    else:
        form = TermoForm()

    return render(request, 'app/criar_termo.html', {
        'title': 'Gerar Termo de Conclusao',    
        'year': datetime.now().year,
        'caderneta': caderneta,
        'recibo': recibo,
        'form': form,
    })


@login_required
def detalhe_termo(request, pk):
    """Exibe e edita os detalhes de um termo."""
    termo = get_object_or_404(Termo, pk=pk, recibo__caderneta__usuario=request.user)

    if request.method == 'POST':
        form = TermoForm(request.POST, instance=termo)
        if form.is_valid():
            termo_obj = form.save(commit=False)
            termo_obj.status = 'em_andamento'
            termo_obj.save()

            messages.success(request, 'Termo atualizado com sucesso! Status resetado para "Em andamento".')
            return redirect('detalhe_caderneta', pk=termo.recibo.caderneta.pk)
        else:
            for field, errors in (form.errors or {}).items():
                messages.error(request, f'{field}: {errors[0]}')
    else:
        form = TermoForm(instance=termo)

    return render(request, 'app/detalhe_termo.html', {
        'title': f'Termo - {termo.recibo.caderneta.apelido}',
        'year': datetime.now().year,
        'termo': termo,
        'form': form,
    })

@require_POST
@login_required
def editar_usuario_admin(request, pk):
    if not _is_admin(request.user):
        return HttpResponseForbidden('Acesso negado.')

    usuario = get_object_or_404(User, pk=pk)
    
    # Atualiza User
    usuario.first_name = request.POST.get('first_name', usuario.first_name)
    usuario.last_name = request.POST.get('last_name', usuario.last_name)
    usuario.email = request.POST.get('email', usuario.email)
    
    status_ativo = request.POST.get('is_active')
    if status_ativo:
        usuario.is_active = (status_ativo == 'true')
        
    usuario.save()

    # Atualiza Perfil
    if hasattr(usuario, 'perfil'):
        usuario.perfil.numero_crea = request.POST.get('numero_crea', usuario.perfil.numero_crea)
        usuario.perfil.celular = request.POST.get('celular', usuario.perfil.celular)
        nivel = request.POST.get('nivel')
        if nivel:
            usuario.perfil.nivel = int(nivel)
        usuario.perfil.save()

    messages.success(request, f'Dados de {usuario.first_name} atualizados com sucesso!')
    return redirect('painel_admin')


# ─── ASSINATURA E HOMOLOGAÇÃO DO RECIBO (ENGENHEIRO ⟷ GESTOR CREA) ───

@require_POST
@login_required
def solicitar_homologacao_recibo(request, pk):
    """Engenheiro assina digitalmente o recibo e envia para homologação do CREA."""
    recibo = get_object_or_404(Recibo, pk=pk, caderneta__usuario=request.user)

    if recibo.status not in ('em_andamento', 'recusado'):
        messages.warning(request, 'O recibo já foi enviado ou homologado.')
        return redirect('detalhe_recibo', pk=recibo.pk)

    dados_hash = f"{recibo.caderneta.apelido}|{recibo.proprietario.cpf_cnpj}|{recibo.area_total}|{recibo.local_obra}|{recibo.data}|{timezone.now()}"
    recibo.hash_documento = hashlib.sha256(dados_hash.encode('utf-8')).hexdigest()
    recibo.assinado_eng_em = timezone.now()
    recibo.ip_eng = _get_client_ip(request)
    recibo.status = 'aguardando_gestor'
    recibo.motivo_recusa = ''
    recibo.recusa_visualizada = False
    recibo.save()

    messages.success(request, 'Recibo assinado com sucesso! O documento foi travado e enviado para a fila de homologação do CREA.')
    return redirect('detalhe_caderneta', pk=recibo.caderneta.pk)


@require_POST
@login_required
def homologar_recibo_gestor(request, pk):
    """Gestor do CREA valida sua senha institucional e assina/homologa o recibo."""
    if not _is_admin(request.user):
        return HttpResponseForbidden('Acesso negado. Apenas gestores do CREA podem homologar documentos.')

    recibo = get_object_or_404(Recibo, pk=pk)

    if recibo.status != 'aguardando_gestor':
        messages.warning(request, 'Este recibo não está aguardando homologação.')
        return redirect('detalhe_recibo', pk=recibo.pk)

    senha = request.POST.get('senha_gestor', '')
    if not request.user.check_password(senha):
        messages.error(request, 'Senha institucional incorreta! A homologação não foi realizada.')
        return redirect('detalhe_recibo', pk=recibo.pk)

    recibo.assinado_gestor_em = timezone.now()
    recibo.gestor_signatario = request.user
    recibo.ip_gestor = _get_client_ip(request)
    recibo.status = 'concluido'
    recibo.save()

    _enviar_email_recibo_homologado(recibo)

    messages.success(request, f'Recibo da obra "{recibo.caderneta.apelido}" HOMOLOGADO e assinado digitalmente com sucesso!')
    return redirect('painel_admin')


@require_POST
@login_required
def recusar_recibo_gestor(request, pk):
    """Gestor do CREA recusa a homologação e registra a justificativa técnica."""
    if not _is_admin(request.user):
        return HttpResponseForbidden('Acesso negado. Apenas gestores do CREA podem avaliar documentos.')

    recibo = get_object_or_404(Recibo, pk=pk)

    if recibo.status != 'aguardando_gestor':
        messages.warning(request, 'Este recibo não está aguardando homologação.')
        return redirect('detalhe_recibo', pk=recibo.pk)

    motivo = request.POST.get('motivo_recusa', '').strip()
    if not motivo:
        messages.error(request, 'É obrigatório descrever o motivo da inconsistência técnica para recusar o recibo.')
        return redirect('detalhe_recibo', pk=recibo.pk)

    recibo.motivo_recusa = motivo
    recibo.recusa_visualizada = False
    recibo.assinado_eng_em = None  # reseta assinatura do engenheiro para retificação
    recibo.status = 'recusado'
    recibo.save()

    _enviar_email_recibo_recusado(recibo)

    messages.warning(request, f'Homologação do Recibo recusada. O engenheiro responsável foi notificado com o motivo apontado.')
    return redirect('painel_admin')


@login_required
def dispensar_recusa_recibo(request, pk):
    """Engenheiro confirma ciência da recusa e libera o recibo para edição."""
    recibo = get_object_or_404(Recibo, pk=pk, caderneta__usuario=request.user)
    recibo.recusa_visualizada = True
    recibo.status = 'em_andamento'
    recibo.save()

    messages.info(request, 'Recibo desbloqueado para edição. Efetue as correções necessárias e solicite nova homologação.')
    return redirect('detalhe_recibo', pk=recibo.pk)


# ─── ASSINATURA ELETRÔNICA DO PROPRIETÁRIO VIA WHATSAPP (RELATOS E TERMO) ───

@login_required
def enviar_whatsapp_assinatura(request, pk, tipo_doc, doc_id):
    """Gera o token de assinatura segura e redireciona para o WhatsApp do proprietário."""
    caderneta = get_object_or_404(Caderneta, pk=pk, usuario=request.user)

    if not hasattr(caderneta, 'recibo') or not caderneta.recibo.proprietario:
        messages.error(request, 'Caderneta não possui recibo ou proprietário cadastrado.')
        return redirect('detalhe_caderneta', pk=pk)

    proprietario = caderneta.recibo.proprietario
    if not proprietario.celular:
        messages.error(request, 'Cadastre o número de Celular/WhatsApp do proprietário no Recibo antes de enviar.')
        return redirect('detalhe_recibo', pk=caderneta.recibo.pk)

    if tipo_doc == 'relato':
        doc = get_object_or_404(Relato, pk=doc_id, recibo__caderneta=caderneta)
        nome_doc = f"Relato de Visita Técnica ({doc.data.strftime('%d/%m/%Y')})"
    elif tipo_doc == 'termo':
        doc = get_object_or_404(Termo, pk=doc_id, recibo__caderneta=caderneta)
        nome_doc = "Termo de Conclusão da Obra"
    else:
        raise Http404('Tipo de documento inválido.')

    # Engenheiro assina primeiro se ainda não assinou
    if not doc.assinado_eng_em:
        doc.assinado_eng_em = timezone.now()
        doc.ip_eng = _get_client_ip(request)
        doc.status = 'pronto_assinar'
        doc.save()

    # Cria ou recupera assinatura pendente com token seguro
    assinatura, created = AssinaturaDocumento.objects.get_or_create(
        tipo_documento=tipo_doc,
        documento_id=doc_id,
        papel_signatario='proprietario',
        status='pendente',
        defaults={
            'nome_signatario': proprietario.nome,
            'cpf_signatario': proprietario.cpf_cnpj,
            'canal_envio': f'WhatsApp ({proprietario.celular})',
            'token': uuid.uuid4().hex,
            'hash_documento': hashlib.sha256(f"{tipo_doc}|{doc_id}|{proprietario.cpf_cnpj}|{timezone.now()}".encode('utf-8')).hexdigest(),
        }
    )

    # Limpa o telefone para wa.me (apenas dígitos)
    celular_limpo = re.sub(r'\D', '', proprietario.celular)
    if not celular_limpo.startswith('55'):
        celular_limpo = '55' + celular_limpo

    link_assinar = request.build_absolute_uri(reverse('assinar_documento_publico', kwargs={'token': assinatura.token}))
    texto = (
        f"Olá {proprietario.nome}!\n\n"
        f"Aqui é o Eng. {request.user.first_name}. O *{nome_doc}* da obra *{caderneta.apelido}* "
        f"está pronto para sua conferência e assinatura digital com validade jurídica.\n\n"
        f"Acesse o link seguro para assinar pelo celular:\n"
        f"{link_assinar}\n\n"
        f"Sistema ConectObra • CREA Adamantina"
    )

    return redirect(f"https://wa.me/{celular_limpo}?text={quote(texto)}")


def assinar_documento_publico(request, token):
    """Página pública mobile para o proprietário visualizar e assinar o documento."""
    assinatura = get_object_or_404(AssinaturaDocumento, token=token)

    documento = None
    caderneta = None
    fotos = []
    servicos = []

    if assinatura.tipo_documento == 'relato':
        documento = get_object_or_404(Relato, pk=assinatura.documento_id)
        caderneta = documento.recibo.caderneta
        fotos = documento.fotos.all()
        servicos = documento.get_servicos_lista()
        nome_doc = f"Relato de Visita — {documento.data.strftime('%d/%m/%Y')}"
    elif assinatura.tipo_documento == 'termo':
        documento = get_object_or_404(Termo, pk=assinatura.documento_id)
        caderneta = documento.recibo.caderneta
        nome_doc = "Termo de Conclusão dos Serviços Técnicos"
    else:
        raise Http404('Documento inválido.')

    proprietario = caderneta.recibo.proprietario
    engenheiro = caderneta.usuario

    return render(request, 'app/assinar_publico.html', {
        'title': f'Assinatura Digital - {nome_doc}',
        'year': datetime.now().year,
        'assinatura': assinatura,
        'documento': documento,
        'caderneta': caderneta,
        'proprietario': proprietario,
        'engenheiro': engenheiro,
        'nome_doc': nome_doc,
        'fotos': fotos,
        'servicos': servicos,
    })


@require_POST
def confirmar_assinatura_publico(request, token):
    """Confirma a assinatura eletrônica do proprietário mediante validação de CPF."""
    assinatura = get_object_or_404(AssinaturaDocumento, token=token)

    if assinatura.status == 'concluido':
        messages.info(request, 'Este documento já foi assinado anteriormente.')
        return redirect('assinar_documento_publico', token=token)

    cpf_digitado = request.POST.get('cpf', '').strip()
    cpf_digitado_limpo = re.sub(r'\D', '', cpf_digitado)
    cpf_cadastrado_limpo = re.sub(r'\D', '', assinatura.cpf_signatario)

    if not cpf_digitado_limpo or cpf_digitado_limpo != cpf_cadastrado_limpo:
        messages.error(request, 'O CPF informado não confere com o titular cadastrado neste documento. Por favor, verifique.')
        return redirect('assinar_documento_publico', token=token)

    concordo = request.POST.get('concordo')
    if not concordo:
        messages.error(request, 'É necessário concordar com os termos da declaração para assinar.')
        return redirect('assinar_documento_publico', token=token)

    # Grava trilha de auditoria
    agora = timezone.now()
    ip = _get_client_ip(request)
    user_agent = request.META.get('HTTP_USER_AGENT', '')

    assinatura.assinado_em = agora
    assinatura.ip_origem = ip
    assinatura.user_agent = user_agent
    assinatura.termo_aceite = "Declaro que li e concordo com as informações e termos descritos neste documento técnico para todos os fins de direito."
    assinatura.status = 'concluido'
    assinatura.save()

    # Atualiza documento subjacente
    if assinatura.tipo_documento == 'relato':
        relato = get_object_or_404(Relato, pk=assinatura.documento_id)
        relato.assinado_prop_em = agora
        relato.ip_prop = ip
        relato.status = 'concluido'
        relato.save()
    elif assinatura.tipo_documento == 'termo':
        termo = get_object_or_404(Termo, pk=assinatura.documento_id)
        termo.assinado_prop_em = agora
        termo.ip_prop = ip
        termo.status = 'concluido'
        termo.save()

    messages.success(request, 'Documento assinado digitalmente com sucesso! Sua assinatura foi chancelada e arquivada.')
    return redirect('assinar_documento_publico', token=token)


def validar_documento_publico(request, token):
    """Página pública de validação de autenticidade (aberta ao escanear o QR Code)."""
    assinatura = AssinaturaDocumento.objects.filter(token=token).first()
    recibo = None

    if not assinatura:
        # Pode ser o hash de um recibo homologado
        recibo = Recibo.objects.filter(hash_documento=token).first()
        if not recibo:
            raise Http404('Documento ou certidão de autenticidade não localizada.')

    return render(request, 'app/validar_publico.html', {
        'title': 'Certidão de Autenticidade Digital',
        'year': datetime.now().year,
        'assinatura': assinatura,
        'recibo': recibo,
    })