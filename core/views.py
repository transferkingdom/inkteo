from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required
from django.urls import reverse

@login_required
def verification_required_view(request):
    if request.user.emailaddress_set.filter(verified=True).exists():
        return redirect('home')
    return render(request, 'account/verification_required.html')

@login_required
def home_view(request):
    if not request.user.emailaddress_set.filter(verified=True).exists():
        return redirect('verification_required')
    return render(request, 'home.html')