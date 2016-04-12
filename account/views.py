from django.shortcuts import render, get_object_or_404, redirect
from django.http import Http404, JsonResponse, HttpResponse
from django.views.decorators.http import require_GET, require_POST,require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.core.urlresolvers import reverse
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.template import loader
from .forms import LoginForm, ForgotPassword, SetPasswordForm, SignupForm
from .models import MyUser, create_otp, get_valid_otp_object
import urllib.request
import requests
import json

# Create your views here.
def hello(request):
    return HttpResponse('<h1>Hello</h1>');

@require_http_methods(['GET', 'POST'])
def login(request):
    if request.user.is_authenticated():
        return redirect(reverse('home', kwargs={'id': request.user.id}));
    if request.method == 'GET':
        context = { 'f' : LoginForm()};
        return render(request, 'account/auth/login.html', context);
    else:
        f = LoginForm(request.POST);
        if not f.is_valid():
            return render(request, 'account/auth/login.html', {'f' : f});
        else:
            user = f.authenticated_user
            print('login stats ', user.is_active)
            if not user.is_active:
                return HttpResponse('Account not activated')
            auth_login(request, user)
            print('login stats ', user.is_active)
            return redirect(reverse('home', kwargs={'id': user.id}));

def forgot_password(request):
    if request.user.is_authenticated():
        return redirect(reverse('home', kwargs={'id': request.user.id}));
    if request.method == 'GET':
        context = { 'f' : ForgotPassword()};
        return render(request, 'account/auth/forgot_password.html', context);
    else:
        f = ForgotPassword(request.POST);
        if not f.is_valid():
            return render(request, 'account/auth/forgot_password.html', {'f' : f});
        else:
            user = MyUser.objects.get(username = f.cleaned_data['username'])
            otp = create_otp(user = user, purpose = 'FP')
            email_body_context = { 'u' : user, 'otp' : otp}
            body = loader.render_to_string('account/auth/email/forgot_password.txt', email_body_context)
            message = EmailMultiAlternatives("Reset Password", body, settings.EMAIL_HOST_USER, [user.email])
            #message.attach_alternative(html_body, 'text/html')
            message.send()
            return render(request, 'account/auth/forgot_email_sent.html', {'u': user});

def reset_password(request, id = None, otp = None):
    if request.user.is_authenticated():
        return redirect(reverse('home', kwargs={'id': request.user.id}));
    user = get_object_or_404(MyUser, id=id);
    otp_object = get_valid_otp_object(user = user, purpose='FP', otp = otp)
    if not otp_object:
        raise Http404();
    if request.method == 'GET':
        f = SetPasswordForm()
    else:
        f = SetPasswordForm(request.POST)
        if f.is_valid():
            user.set_password(f.cleaned_data['new_password'])
            user.save()
            otp_object.delete()
            return render(request, 'account/auth/set_password_success.html', { 'u' : user})
    context = { 'f' : f, 'otp': otp_object.otp, 'uid': user.id}
    return render(request, 'account/auth/set_password.html', context)

@require_GET
@login_required
def home(request, id):
    return redirect(reverse('get-fare'))

def logout(request):
    auth_logout(request)
    return redirect(reverse('login'));


def signup(request):
    if request.user.is_authenticated():
        return redirect(reverse('home', kwargs = {'id' : request.user.id}))
    if request.method == 'GET':
        context = {'f' : SignupForm() }
        return render(request, 'account/auth/signup.html', context)
    else:
        f = SignupForm(request.POST, request.FILES)
        if not f.is_valid():
            return render(request, 'account/auth/signup.html', {'f' : f})
        else:
            user = f.save(commit = False)
            user.set_password(f.cleaned_data['password'])            
            user.is_active = False            
            user.save()
            otp = create_otp(user = user, purpose = 'AA')
            email_body_context = {'u': user, 'otp': otp}
            body = loader.render_to_string('account/auth/email/signup_mail.txt', email_body_context)
            message = EmailMultiAlternatives('Activate account', body, settings.EMAIL_HOST_USER, [user.email])
            message.send()
            return render(request, 'account/auth/activate_mail_sent.html', {'u': user})


@require_GET
def activate(request, id = None, otp = None):
    if request.user.is_authenticated():
        return redirect(reverse('home', kwargs = {'id': request.user.id}))
    user = get_object_or_404(MyUser, id = id)
    otp_object = get_valid_otp_object(user = user, purpose = 'AA', otp = otp)
    if not otp_object:
        raise Http404()
    print('active stats before', user.is_active)
    user.is_active = True
    user.save()
    print('active stats after', user.is_active)
    otp_object.delete()
    return render(request, 'account/auth/activation_success.html', { 'u' : user})


def get_fare(request):
    if request.method == 'GET':
        return render(request, 'account/auth/get_fare.html')
    else:
        src = request.POST.get('src', '')
        dest = request.POST.get('dest', '')
        if src and dest:
            apikey = "AIzaSyAYggcG8B3s_bWghBUY9s-MuUALVOjGs1U"
            string = "https://maps.googleapis.com/maps/api/distancematrix/json?origins="+src+"&destinations="+dest+"&key="+apikey
            obj=urllib.request.urlopen(string)
            jsonRaw = obj.read().decode('utf-8')
            json_data = json.loads(jsonRaw)
            distance = json_data.get('rows')[0].get('elements')[0].get('distance').get('text')
            sourceString = "https://maps.googleapis.com/maps/api/geocode/json?address="+src+"&key="+apikey
            destinationString = "https://maps.googleapis.com/maps/api/geocode/json?address="+dest+"&key="+apikey
            obj= urllib.request.urlopen(sourceString)
            jsonRaw = obj.read().decode('utf-8')
            json_data_source = json.loads(jsonRaw)
            loc = json_data_source.get('results')[0].get('geometry').get('location')
            sourceLattitude = loc.get('lat')
            sourceLongitude = loc.get('lng')
            obj= urllib.request.urlopen(destinationString)
            jsonRaw = obj.read().decode('utf-8')
            json_data_destination = json.loads(jsonRaw)
            loc = json_data_destination.get('results')[0].get('geometry').get('location')
            destinationLattitude = loc.get('lat')
            destinationLongitude = loc.get('lng')

            #Hitting Uber Servers

            uberUrl = "https://www.uber.com/api/fare-estimate?" \
                      "pickupRef=&pickupLat="+str(sourceLattitude)+"&pickupLng="+str(sourceLongitude)+"&destinationRef=" \
                      "&destinationLat="+str(destinationLattitude)+"&destinationLng="+str(destinationLongitude)
            obj = urllib.request.urlopen(uberUrl)
            jsonRaw=obj.read().decode('utf-8')
            json_data_uber = json.loads(jsonRaw)

            poolCostRange=json_data_uber.get('prices')[0].get('fareString')
            print(type(poolCostRange))
            uberGoCostRange=json_data_uber.get('prices')[2].get('fareString')
            print(uberGoCostRange)
            uberXCostRange = json_data_uber.get('prices')[4].get('fareString')
            print(uberXCostRange)
            uberXlCostRange = json_data_uber.get('prices')[6].get('fareString')
            print(uberXlCostRange)

            #jugnoo Calculation
            jugnooCostRange=float(distance[0])*9.12+15
            print(jugnooCostRange)

            #Ola Calculation
            if float(distance[0])<=8.00:
                olaCostRange = 200;
            else:
                olaCostRange = float(distance[0])*18 + 200;
            print(olaCostRange)

            #Dtc bus calculation
            kms = float(distance[0])
            if kms<=5.00:
                greenbusCostRange = 5
                RedBusCostRange = 10
            if kms >5  and kms <=10:
                greenbusCostRange=10;
                redBusCostRange=20;
            else:
                greenbusCostRange = 15;
                redBusCostRange =  25;

            context = {'poolCostRange': poolCostRange, 'uberGoCostRange': uberGoCostRange,
            'uberXCostRange': uberXCostRange, 'uberXlCostRange': uberXlCostRange,
            'jugnooCostRange': jugnooCostRange, 'olaCostRange': olaCostRange,
            'greenBusCostRange': greenbusCostRange, 'redBusCostRange': redBusCostRange
            }
            return render(request, 'account/auth/results.html', context)
            #return HttpResponse(json_data.get('rows')[0].get('elements')[0].get('distance').get('text'))
        else:

            context = {'error' : 'Please enter valid source, destination'}
            return render(request, 'account/auth/get_fare.html', context)
