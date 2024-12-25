from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from accounts.forms import UserProfileForm, CompanyForm
from accounts.models import Company

@login_required
def home(request):
    return render(request, 'dashboard/home.html')

@login_required
def settings(request):
    # Get or create company instance
    company, created = Company.objects.get_or_create(user=request.user)
    
    context = {
        'user': request.user,
        'company': company
    }
    return render(request, 'dashboard/settings.html', context)

@login_required
def update_profile(request):
    if request.method == 'POST':
        form = UserProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully!')
        else:
            messages.error(request, 'Please correct the errors below.')
    return redirect('dashboard:settings')

@login_required
def update_company(request):
    if request.method == 'POST':
        company, created = Company.objects.get_or_create(user=request.user)
        form = CompanyForm(request.POST, instance=company)
        if form.is_valid():
            form.save()
            messages.success(request, 'Company details updated successfully!')
        else:
            messages.error(request, 'Please correct the errors below.')
    return redirect('dashboard:settings')