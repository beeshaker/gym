from django.http import HttpResponse
from django.shortcuts import redirect, render


def index(request):
    return redirect('gym_dashboard')


def pin(request):
    return HttpResponse('pin stub')


def dashboard(request):
    return HttpResponse('dashboard stub')
