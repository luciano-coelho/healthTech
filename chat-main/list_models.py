#!/usr/bin/env python
import os
import django
import requests

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'configs.settings')
django.setup()

from django.conf import settings

def list_available_models():
    """Lista os modelos disponíveis na API do Google"""
    try:
        api_key = settings.GOOGLE_AI_API_KEY
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
        
        response = requests.get(url, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            print("Modelos disponíveis:")
            for model in result.get('models', []):
                name = model.get('name', '')
                if 'generateContent' in model.get('supportedGenerationMethods', []):
                    print(f"✅ {name}")
                else:
                    print(f"❌ {name} (não suporta generateContent)")
        else:
            print(f"Erro: {response.status_code} - {response.text}")
            
    except Exception as e:
        print(f"Erro: {e}")

list_available_models()