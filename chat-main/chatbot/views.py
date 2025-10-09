import json
import secrets
import string
import threading
import requests

from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt

from chatbot.services import generate_doc, send_email
from questions.models import Question

from .decorators import update_password
from .models import Briefing, CustomUser, Teacher


@login_required(redirect_field_name='login')
@update_password
def chat_view(request):
    request.session['chat_history'] = []
    array_questions = Question.objects.all()
    return render(request, 'chatbot/chat.html', {'array_questions': array_questions.values()})


def send_message(request):
    if request.method == 'POST':
        message = request.POST.get('message')
        response = generate_response(message, request)
        chat_history = request.session.get('chat_history', [])
        chat_history.append({'role': 'user', 'parts': [{'text': message}]},)
        chat_history.append({'role': 'model', 'parts': [{'text': response}]},)
        request.session['chat_history'] = chat_history
        return JsonResponse({'message': message, 'response': response})


def call_gemini_api(message):
    """Chama a API do Google Gemini diretamente via REST"""
    try:
        api_key = settings.GOOGLE_AI_API_KEY
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
        
        headers = {
            'Content-Type': 'application/json',
        }
        
        data = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": message
                        }
                    ]
                }
            ]
        }
        
        response = requests.post(url, headers=headers, json=data, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            if 'candidates' in result and len(result['candidates']) > 0:
                content = result['candidates'][0]['content']['parts'][0]['text']
                return content
            else:
                return None
        else:
            print(f"Erro na API Gemini: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        print(f"Erro ao chamar API Gemini: {e}")
        return None

def generate_response(message, request):
    chat_history = request.session.get('chat_history', [])
    
    # Tentar usar a API do Gemini
    ai_response = call_gemini_api(message)
    
    if ai_response:
        # Se a mensagem contém "Crie uma proposta", tentar extrair JSON da resposta
        if "Crie uma proposta" in message:
            try:
                # Procurar por JSON na resposta (pode estar envolto em texto)
                import re
                json_match = re.search(r'\{.*\}', ai_response, re.DOTALL)
                if json_match:
                    json_str = json_match.group()
                    # Validar se é JSON válido
                    json.loads(json_str)
                    return json_str
                else:
                    # Se não encontrou JSON válido, usar template de fallback
                    return generate_fallback_proposal_json(request)
            except (json.JSONDecodeError, AttributeError):
                # Se falhou o parse do JSON, usar template de fallback
                return generate_fallback_proposal_json(request)
        else:
            # Para outras mensagens, retornar resposta normal da IA
            return ai_response
    else:
        # Fallback para quando a API falha
        if "Crie uma proposta" in message:
            return generate_fallback_proposal_json(request)
        else:
            return "Obrigado pela informação. Vamos para a próxima pergunta."

def generate_fallback_proposal_json(request):
    """Função auxiliar para gerar JSON de proposta quando a IA não consegue"""
    from datetime import datetime
    
    exemplo_proposta = {
        "data": datetime.now().strftime("%d/%m/%Y"),
        "cliente": "Empresa Exemplo",
        "destinatario": "Cliente Teste", 
        "titulo": "Proposta de Treinamento Corporativo",
        "objetivo": "Desenvolver e aprimorar as competências da equipe através de um programa de capacitação abrangente e inovador.",
        "periodo": "60 dias",
        "detalhamento_proposta": [
            {
                "titulo_etapa": "Análise e Diagnóstico",
                "carga_horaria_necessaria": "8",
                "publico_alvo": "Gestores e supervisores",
                "objetivo_da_etapa": "Identificar necessidades de capacitação",
                "conteudo_programatico": [
                    "Avaliação de competências",
                    "Mapeamento de necessidades", 
                    "Definição de objetivos"
                ]
            }
        ],
        "carga_horaria_total": "40 Horas",
        "valor_investimento": "R$ 15.000,00",
        "type": "private",
        "atribuicao_senac": "Coordenação de projetos",
        "atribuicao_cliente": "Acompanhamento de resultados"
    }
    return json.dumps(exemplo_proposta)


def update_password(request):

    if request.method == "POST":
        password = request.POST['password']
        repeat_password = request.POST['repeat_password']

        if password == repeat_password:
            update_user = request.user
            update_user.set_password(password)
            update_user.reset_password = True
            update_user.save()
            login(request, update_user)
            return redirect('chat_view')

        else:
            return redirect('update_password')

    else:
        return render(request, 'chatbot/change_password.html')


@login_required(redirect_field_name='login')
def list_users(request):
    users = CustomUser.objects.all().order_by('-id')
    return render(request, 'chatbot/list_users.html', {'users': users})


@login_required(redirect_field_name='login')
def list_teachers(request):
    teachers = Teacher.objects.all().order_by('-id')

    for teacher in teachers:
        teacher.competency = teacher.competency.split(',')
    return render(request, 'chatbot/list_teachers.html', {'teachers': teachers})


def create_user(request):
    username = request.POST['username']
    email = request.POST['email']
    admin = request.POST['admin']
    password = request.POST['password']

    new_user = CustomUser.objects.create_user(
        username=username, email=email, password=password)

    if admin == '1':
        new_user.is_superuser = True
        new_user.save()

    return redirect('list-users')


def edit_user(request):
    id = request.POST['id-user']
    email = request.POST['email']
    admin = request.POST['admin']
    active = request.POST['active']

    user = CustomUser.objects.get(id=id)
    user.email = email
    user.is_superuser = admin
    user.is_active = active
    user.save()
    return redirect('list-users')


def delete_user(request, id):
    CustomUser.objects.get(id=id).delete()
    return redirect('list-users')


def create_teacher(request):
    name = request.POST['name']
    education = request.POST['education']
    area = request.POST['area']
    competency = request.POST['competency']
    Teacher.objects.create(name=name, education=education,
                           area=area, competency=competency)
    return redirect('list-teachers')


def edit_teacher(request):
    id = request.POST['teacher-id']
    name = request.POST['name']
    education = request.POST['education']
    area = request.POST['area']
    competency = request.POST['competency']
    print(competency)
    teacher = Teacher.objects.get(id=id)

    teacher.name = name
    teacher.education = education
    teacher.area = area
    teacher.competency = competency
    teacher.save()

    return redirect('list-teachers')


def delete_teacher(request, id):
    Teacher.objects.get(id=id).delete()
    return redirect('list-teachers')


@csrf_exempt
def download_doc(request):
    if request.method != "POST":
        return HttpResponse(status=405)
    
    proposal = request.POST.get('proposal')
    proposal_json = json.loads(proposal)
    file = generate_doc(proposal_json)

    filename = "generated.docx"
    response = FileResponse(file, as_attachment=True, filename=filename)

    response['File-Path'] = file.name

    # Envia o e-mail em uma thread separada
    email_thread = threading.Thread(
        target=send_email_in_background,
        args=(request.user.email, "Proposta Gerada GenIA", file.name)
    )
    email_thread.start()

    return response



def list_proposals(request):
    proposals = Briefing.objects.all().order_by('-id')
    return render(request, 'chatbot/list_proposals.html', {'proposals': proposals})


def update_proposal(request):

    id = request.POST.get('id')
    question_16 = request.POST.get('question_16')
    question_17 = request.POST.get('question_17')
    question_18 = request.POST.get('question_18')
    question_19 = request.POST.get('question_19')
    question_20 = request.POST.get('question_20')
    question_21 = request.POST.get('question_21')
    question_22 = request.POST.get('question_22')
    question_23 = request.POST.get('question_23')
    question_24 = request.POST.get('question_24')

    proposal = Briefing.objects.get(id=id)
    proposal.question_16 = question_16
    proposal.question_17 = question_17
    proposal.question_18 = question_18
    proposal.question_19 = question_19
    proposal.question_20 = question_20
    proposal.question_21 = question_21
    proposal.question_22 = question_22
    proposal.question_23 = question_23
    proposal.question_24 = question_24
    proposal.completed = True
    proposal.save()
    print(question_24)
    return HttpResponse("Proposta atualizada.")


def form_briefing(request):
    return render(request, 'chatbot/briefing.html')


def generate_prosal(request):
    name = request.POST.get('name')
    phone = request.POST.get('phone')
    email = request.POST.get('email')
    question_1 = request.POST.get('question_1')
    question_2 = request.POST.get('question_2')
    question_3 = request.POST.get('question_3')
    question_4 = request.POST.get('question_4')
    question_5 = request.POST.get('question_5')
    question_6 = request.POST.get('question_6')
    question_7 = request.POST.get('question_7')
    question_8 = request.POST.get('question_8')
    question_9 = request.POST.get('question_9')
    question_10 = request.POST.get('question_10')
    question_11 = request.POST.get('question_11')
    question_12 = request.POST.get('question_12')
    question_13 = request.POST.get('question_13')
    question_14 = request.POST.get('question_14')
    question_15 = request.POST.get('question_15')

    Briefing.objects.create(
        name=name,
        phone=phone,
        email=email,
        question_1=question_1,
        question_2=question_2,
        question_3=question_3,
        question_4=question_4,
        question_5=question_5,
        question_6=question_6,
        question_7=question_7,
        question_8=question_8,
        question_9=question_9,
        question_10=question_10,
        question_11=question_11,
        question_12=question_12,
        question_13=question_13,
        question_14=question_14,
        question_15=question_15
    )

    return JsonResponse({'message': 'Proposta enviada com sucesso.'}, status=200)


def testchat(request):
    return render(request, 'chatbot/testchat.html')


def send_email_in_background(email, subject, file_path):
    try:
        send_email(email, subject, file_path)
        print(f"E-mail enviado para {email}")
    except Exception as e:
        print(f"Erro ao enviar e-mail -> {e}")


def reset_password(request):
    email = request.POST['email']

    user = CustomUser.objects.filter(email=email).first()
    if not user:
        print("user not found")
        return

    password = gerar_senha_temporaria()
    user.reset_password = False
    user.set_password(password)
    user.save()

    send_email(email, "Senha Temporária", body=f"SENHA TEMPORÁRIA: {password}")


def gerar_senha_temporaria(tamanho=12):
    caracteres = string.ascii_letters + string.digits
    senha = ''.join(secrets.choice(caracteres) for i in range(tamanho))
    return senha
