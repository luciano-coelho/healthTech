from django.contrib import auth, messages
from django.shortcuts import redirect, render


def login(request):
    
    if request.method == "POST":
        username = request.POST["username"]
        password = request.POST["password"]

        authenticate = auth.authenticate(request, username=username, password=password)
        
        if authenticate:
            auth.login(request, authenticate)
            return redirect("chat_view")

        else:
            messages.info(request, 'Usuário ou Senha incorretos.')
            return redirect("login")
        
    else:
        return render(request, "login.html")


def logout(request):
    auth.logout(request)
    return redirect("login")


