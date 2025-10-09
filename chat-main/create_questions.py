#!/usr/bin/env python
import os
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'configs.settings')
django.setup()

from questions.models import Question

# Perguntas básicas para o chatbot de propostas corporativas
perguntas = [
    "Qual é o nome da sua empresa?",
    "Qual é o seu nome?",
    "Em qual segmento sua empresa atua?",
    "Qual é o porte da sua empresa? (Pequena, Média, Grande)",
    "Qual é o objetivo principal desta proposta?",
    "Qual é o prazo desejado para implementação?",
    "Qual é o orçamento estimado para este projeto?",
    "Quem são os principais stakeholders envolvidos?",
    "Qual é o maior desafio que sua empresa enfrenta atualmente?",
    "Como você gostaria que nossa solução ajudasse sua empresa?",
    "Há algum requisito técnico específico?",
    "Qual é a expectativa de retorno sobre o investimento?",
]

# Limpar perguntas existentes
Question.objects.all().delete()

# Criar novas perguntas
for i, pergunta in enumerate(perguntas, 1):
    Question.objects.create(
        question=pergunta,
        index=i
    )
    print(f"✅ Pergunta {i} criada: {pergunta}")

print(f"\n🎉 Total de {len(perguntas)} perguntas criadas com sucesso!")