# app/backends.py
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import User
from django.db.models import Q

class EmailOrCreaBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None:
            username = kwargs.get('username')
            
        try:
            # O parâmetro 'username' do Django receberá o que for digitado no campo de login
            # Fazemos uma busca onde o email OU o numero_crea sejam iguais ao valor digitado
            user = User.objects.get(
                Q(email__iexact=username) | Q(perfil__numero_crea__iexact=username)
            )
        except User.DoesNotExist:
            return None
        except User.MultipleObjectsReturned:
            # Caso raríssimo de duplicidade no banco, retorna o primeiro usuário encontrado
            user = User.objects.filter(
                Q(email__iexact=username) | Q(perfil__numero_crea__iexact=username)
            ).order_by('id').first()

        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None