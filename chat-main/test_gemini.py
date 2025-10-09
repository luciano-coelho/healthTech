#!/usr/bin/env python
import os
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'configs.settings')
django.setup()

from chatbot.views import call_gemini_api

# Teste simples da API
response = call_gemini_api("Olá! Como você está hoje?")
if response:
    print("✅ API do Gemini funcionando!")
    print(f"Resposta: {response}")
else:
    print("❌ Erro na API do Gemini")