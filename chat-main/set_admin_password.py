#!/usr/bin/env python
import os
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'configs.settings')
django.setup()

from chatbot.models import CustomUser

# Definir senha para o usuário admin
try:
    user = CustomUser.objects.get(username='admin')
    user.set_password('admin123')  # Senha simples para desenvolvimento
    user.save()
    print("✅ Senha definida com sucesso para o usuário 'admin'")
    print("📧 Email: admin@exemplo.com")
    print("🔑 Senha: admin123")
except CustomUser.DoesNotExist:
    print("❌ Usuário 'admin' não encontrado")