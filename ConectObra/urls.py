from django.urls import path
from django.contrib import admin
from django.contrib.auth.views import LogoutView
from app import views

urlpatterns = [
    path('', views.home, name='home'),
    path('contact/', views.contact, name='contact'),
    path('about/', views.about, name='about'),

    # Cadernetas
    path('cadernetas/', views.cadernetas, name='cadernetas'),
    path('cadernetas/criar/', views.criar_caderneta, name='criar_caderneta'),
    path('cadernetas/<int:pk>/', views.detalhe_caderneta, name='detalhe_caderneta'),

    # Recibos
    path('cadernetas/<int:pk>/recibo/criar/', views.criar_recibo, name='criar_recibo'),
    path('recibos/<int:pk>/', views.detalhe_recibo, name='detalhe_recibo'),

    # Relatos
    path('cadernetas/<int:pk>/relato/criar/', views.criar_relato, name='criar_relato'),
    path('relatos/<int:pk>/', views.detalhe_relato, name='detalhe_relato'),

    # Termos
    path('cadernetas/<int:pk>/termo/criar/', views.criar_termo, name='criar_termo'),
    path('termos/<int:pk>/', views.detalhe_termo, name='detalhe_termo'),

    # Solicitacoes de Cadastro
    path('solicitar-cadastro/', views.solicitar_cadastro, name='solicitar_cadastro'),
    path('solicitar-cadastro/enviado/', views.solicitacao_enviada, name='solicitacao_enviada'),

    # Autenticacao
    path('login/', views.CustomLoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(next_page='/'), name='logout'),

    # Painel Admin
    path('painel/', views.painel_admin, name='painel_admin'),
    path('painel/aprovar/<int:pk>/', views.aprovar_solicitacao, name='aprovar_solicitacao'),
    path('painel/negar/<int:pk>/', views.negar_solicitacao, name='negar_solicitacao'),

    path('admin/', admin.site.urls),

    path('painel/usuario/<int:pk>/editar/', views.editar_usuario_admin, name='editar_usuario_admin'),
]
