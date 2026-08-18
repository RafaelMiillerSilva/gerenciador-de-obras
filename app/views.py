import secrets
import string
import json
from datetime import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth.views import LoginView
from django.core.mail import send_mail
from django.http import HttpRequest, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.conf import settings

from app.forms import (
    SolicitacaoCadastroForm, BootstrapAuthenticationForm,
    ReciboForm, RelatoForm, TermoForm, ProprietarioForm
)
from app.models import (
    PerfilUsuario, SolicitacaoCadastro, Caderneta,
    Recibo, Relato, Termo, Proprietario
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

    # 3. Todas as Obras (Cadernetas) criadas por todos os Engenheiros/Agrônomos
    obras = Caderneta.objects.all().select_related('usuario', 'recibo__proprietario').order_by('-criado_em')

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
        'obras': obras,
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
    caderneta = get_object_or_404(
        Caderneta,
        pk=pk,
        usuario=request.user
    )

    recibo = getattr(caderneta, 'recibo', None)

    relatos = []
    termo = None

    if recibo:
        relatos = recibo.relatos.all()

        try:
            termo = recibo.termo
        except:
            termo = None

    return render(request, 'app/detalhe_caderneta.html', {
        'title': caderneta.apelido,
        'year': datetime.now().year,
        'caderneta': caderneta,
        'recibo': recibo,
        'relatos': relatos,
        'termo': termo,
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
    recibo = get_object_or_404(Recibo, pk=pk, caderneta__usuario=request.user)

    if request.method == 'POST':
        proprietario_form = ProprietarioForm(request.POST, prefix='prop', instance=recibo.proprietario)
        recibo_form = ReciboForm(request.POST, instance=recibo)

        if proprietario_form.is_valid() and recibo_form.is_valid():
            proprietario_form.save()
            recibo_obj = recibo_form.save(commit=False)
            recibo_obj.status = 'em_andamento'
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
        form = RelatoForm(request.POST)
        if form.is_valid():
            relato = form.save(commit=False)
            relato.recibo = recibo
            relato.save()

            messages.success(request, 'Relato criado com sucesso!')
            return redirect('detalhe_caderneta', pk=pk)
        else:
            for field, errors in form.errors.items():
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
        form = RelatoForm(request.POST, instance=relato)
        if form.is_valid():
            relato_obj = form.save(commit=False)
            relato_obj.status = 'em_andamento'
            relato_obj.save()

            messages.success(request, 'Relato atualizado com sucesso! Status resetado para "Em andamento".')
            return redirect('detalhe_caderneta', pk=relato.recibo.caderneta.pk)
        else:
            for field, errors in form.errors.items():
                messages.error(request, f'{field}: {errors[0]}')
    else:
        form = RelatoForm(instance=relato)

    return render(request, 'app/detalhe_relato.html', {
        'title': f'Relato - {relato.data}',
        'year': datetime.now().year,
        'relato': relato,
        'relato_servicos': relato.get_servicos_lista(),
        'form': form,
    })


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
            for field, errors in form.errors.items():
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
            for field, errors in form.errors.items():
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