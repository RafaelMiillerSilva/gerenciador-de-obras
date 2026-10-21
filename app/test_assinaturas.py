import hashlib
import django.template.context
from django.template.context import BaseContext

# Compatibilidade do test runner Django com Python 3.14
def _patched_copy(self):
    obj = self.__class__.__new__(self.__class__)
    obj.dicts = self.dicts[:]
    return obj
BaseContext.__copy__ = _patched_copy

from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.utils import timezone
from app.models import PerfilUsuario, Caderneta, Proprietario, Recibo, Relato, Termo, AssinaturaDocumento


class AssinaturaFluxoTestCase(TestCase):
    def setUp(self):
        self.client = Client()

        # Cria engenheiro
        self.eng_user = User.objects.create_user(
            username='eng_teste',
            email='engenheiro@teste.com',
            password='eng123',
            first_name='Carlos',
            last_name='Silva'
        )
        self.eng_perfil = PerfilUsuario.objects.create(
            usuario=self.eng_user,
            nivel=3,
            numero_crea='123456/SP'
        )

        # Cria gestor do CREA
        self.gestor_user = User.objects.create_user(
            username='gestor_teste',
            email='gestor@teste.com',
            password='gestor123',
            first_name='Mariana',
            last_name='Gestora'
        )
        self.gestor_perfil = PerfilUsuario.objects.create(
            usuario=self.gestor_user,
            nivel=2,
            numero_crea='987654/SP'
        )

        # Cria caderneta e recibo
        self.caderneta = Caderneta.objects.create(
            apelido='Residência Teste',
            usuario=self.eng_user
        )
        self.proprietario = Proprietario.objects.create(
            nome='João Proprietário',
            cpf_cnpj='123.456.789-00',
            email='joao@email.com',
            celular='18999998888'
        )
        self.recibo = Recibo.objects.create(
            caderneta=self.caderneta,
            usuario=self.eng_user,
            proprietario=self.proprietario,
            local_obra='Rua das Flores, 100, Adamantina/SP',
            atividade_tecnica='execucao',
            tipo_edificacao='unifamiliar',
            data='2026-10-20',
            valor_obra='250000.00',
            status='em_andamento'
        )

    def test_fluxo_completo_recibo_homologacao_e_recusa(self):
        # 1. Engenheiro loga e solicita homologação do recibo
        self.client.login(username='engenheiro@teste.com', password='eng123')
        resp = self.client.post(f'/recibos/{self.recibo.pk}/solicitar-homologacao/')
        self.assertEqual(resp.status_code, 302)

        self.recibo.refresh_from_db()
        self.assertEqual(self.recibo.status, 'aguardando_gestor')
        self.assertIsNotNone(self.recibo.assinado_eng_em)

        # 2. Gestor loga e visualiza no painel
        self.client.logout()
        self.client.login(username='gestor@teste.com', password='gestor123')
        resp_painel = self.client.get('/painel/')
        self.assertEqual(resp_painel.status_code, 200)
        self.assertContains(resp_painel, 'Residência Teste')
        self.assertContains(resp_painel, 'Carlos Silva')

        # 3. Gestor tenta homologar com senha errada -> deve falhar
        resp_err = self.client.post(f'/recibos/{self.recibo.pk}/homologar/', {'senha_gestor': 'senha_incorreta'})
        self.assertEqual(resp_err.status_code, 302)
        self.recibo.refresh_from_db()
        self.assertEqual(self.recibo.status, 'aguardando_gestor')

        # 4. Gestor recusa informando motivo
        motivo_teste = 'Inconsistência na metragem quadrada informada.'
        resp_recusa = self.client.post(f'/recibos/{self.recibo.pk}/recusar/', {'motivo_recusa': motivo_teste})
        self.assertEqual(resp_recusa.status_code, 302)

        self.recibo.refresh_from_db()
        self.assertEqual(self.recibo.status, 'recusado')
        self.assertEqual(self.recibo.motivo_recusa, motivo_teste)
        self.assertFalse(self.recibo.recusa_visualizada)

        # 5. Engenheiro loga e acessa a caderneta -> deve ver o pop-up de alerta
        self.client.logout()
        self.client.login(username='engenheiro@teste.com', password='eng123')
        resp_caderneta = self.client.get(f'/cadernetas/{self.caderneta.pk}/')
        self.assertEqual(resp_caderneta.status_code, 200)
        self.assertContains(resp_caderneta, 'modalAlertaRecusa')
        self.assertContains(resp_caderneta, motivo_teste)

        # 6. Engenheiro dispensa a recusa -> libera para edição
        resp_dispensa = self.client.get(f'/recibos/{self.recibo.pk}/dispensar-recusa/')
        self.assertEqual(resp_dispensa.status_code, 302)

        self.recibo.refresh_from_db()
        self.assertEqual(self.recibo.status, 'em_andamento')
        self.assertTrue(self.recibo.recusa_visualizada)

        # 7. Engenheiro solicita novamente a homologação
        resp_re_solicita = self.client.post(f'/recibos/{self.recibo.pk}/solicitar-homologacao/')
        self.assertEqual(resp_re_solicita.status_code, 302)
        self.recibo.refresh_from_db()
        self.assertEqual(self.recibo.status, 'aguardando_gestor')

        # 8. Gestor aprova e homologa com a senha correta
        self.client.logout()
        self.client.login(username='gestor@teste.com', password='gestor123')
        resp_ok = self.client.post(f'/recibos/{self.recibo.pk}/homologar/', {'senha_gestor': 'gestor123'})
        self.assertEqual(resp_ok.status_code, 302)

        self.recibo.refresh_from_db()
        self.assertEqual(self.recibo.status, 'concluido')
        self.assertIsNotNone(self.recibo.assinado_gestor_em)
        self.assertEqual(self.recibo.gestor_signatario, self.gestor_user)
        self.assertTrue(len(self.recibo.hash_documento) == 64)

        # 9. Verificação da certidão pública
        resp_validar = self.client.get(f'/validar/{self.recibo.hash_documento}/')
        self.assertEqual(resp_validar.status_code, 200)
        self.assertContains(resp_validar, 'Certidão de Autenticidade e Fé Pública')
        self.assertContains(resp_validar, 'Mariana Gestora')

    def test_fluxo_assinatura_whatsapp_proprietario(self):
        # 1. Cria relato de visita
        relato = Relato.objects.create(
            recibo=self.recibo,
            data='2026-10-20',
            posicao_obra='de_acordo',
            opcoes_servicos='Alvenaria, Pintura',
            observacoes='Concretagem de estacas concluída.',
            status='em_andamento'
        )

        # 2. Engenheiro gera link do WhatsApp
        self.client.login(username='engenheiro@teste.com', password='eng123')
        resp_zap = self.client.get(f'/cadernetas/{self.caderneta.pk}/assinar-whatsapp/relato/{relato.pk}/')
        self.assertEqual(resp_zap.status_code, 302)
        self.assertTrue('wa.me/5518999998888' in resp_zap.url)

        # 3. Verifica assinatura criada no banco
        assinatura = AssinaturaDocumento.objects.filter(tipo_documento='relato', documento_id=relato.pk).first()
        self.assertIsNotNone(assinatura)
        self.assertEqual(assinatura.status, 'pendente')

        # 4. Proprietário abre o link sem autenticação
        self.client.logout()
        resp_publico = self.client.get(f'/assinar/{assinatura.token}/')
        self.assertEqual(resp_publico.status_code, 200)
        self.assertContains(resp_publico, 'João Proprietário')
        self.assertContains(resp_publico, 'Concretagem de estacas concluída')

        # 5. Proprietário tenta assinar com CPF incorreto
        resp_cpf_err = self.client.post(f'/assinar/{assinatura.token}/confirmar/', {
            'cpf': '999.888.777-66',
            'concordo': '1'
        })
        self.assertEqual(resp_cpf_err.status_code, 302)
        assinatura.refresh_from_db()
        self.assertEqual(assinatura.status, 'pendente')

        # 6. Proprietário assina com CPF correto e concorda com os termos
        resp_cpf_ok = self.client.post(f'/assinar/{assinatura.token}/confirmar/', {
            'cpf': '123.456.789-00',
            'concordo': '1'
        })
        self.assertEqual(resp_cpf_ok.status_code, 302)

        assinatura.refresh_from_db()
        self.assertEqual(assinatura.status, 'concluido')
        self.assertIsNotNone(assinatura.assinado_em)

        relato.refresh_from_db()
        self.assertEqual(relato.status, 'concluido')
        self.assertIsNotNone(relato.assinado_prop_em)

        # 7. Validar certidão pública do relato
        resp_validar = self.client.get(f'/validar/{assinatura.token}/')
        self.assertEqual(resp_validar.status_code, 200)
        self.assertContains(resp_validar, 'Certidão de Autenticidade e Fé Pública')
        self.assertContains(resp_validar, 'João Proprietário')
