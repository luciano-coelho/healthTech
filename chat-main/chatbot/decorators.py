from django.shortcuts import redirect


def update_password(view_func):
    def decorator_func(request, *args, **kwargs):
        if request.user.is_authenticated and request.user.reset_password == False:
            return redirect('change_password')
        return view_func(request, *args, **kwargs)
    return decorator_func
