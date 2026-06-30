from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.core.validators import RegexValidator
from .models import User


class SignUpForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("This email address is already in use.")
        return email


class EmailAuthenticationForm(AuthenticationForm):
    username = forms.EmailField(
        label="Email",
        widget=forms.EmailInput(attrs={'autofocus': True})
    )
    password = forms.CharField(
        widget=forms.PasswordInput()
    )

    error_messages = {
        **AuthenticationForm.error_messages,
        'invalid_login': "The email address or password is incorrect.",
        'inactive': "This account is inactive.",
    }



class ProfileSetupForm(forms.ModelForm):
    GPA_SCALE_CHOICES = (
        ('4', '4.0 Scale'),
        ('100', '100 Scale'),
    )

    gpa_scale = forms.ChoiceField(
        choices=GPA_SCALE_CHOICES, initial='4', required=False,
        label="Average Assessment System",
        widget=forms.Select()
    )

    gpa = forms.DecimalField(
        max_digits=5, decimal_places=2, required=False,
        widget=forms.NumberInput(attrs={'step': '0.01'})
    )

    class Meta:
        model = User
        fields = ('field_of_study', 'degree_level', 'gpa', 'country',
                  'languages', 'cv_file')
        widgets = {
            'field_of_study': forms.TextInput(),
            'degree_level': forms.Select(),
            'country': forms.TextInput(),
            'languages': forms.TextInput(attrs={'placeholder': 'e.g. Arabic, English'}),
            'cv_file': forms.FileInput(),
        }

    def clean(self):
        cleaned_data = super().clean()
        gpa = cleaned_data.get('gpa')
        scale = cleaned_data.get('gpa_scale', '4')

        if gpa is not None:
            if scale == '100':
                if gpa < 0 or gpa > 100:
                    raise forms.ValidationError("The average on a scale of 100 must be between 0 and 100.")
                cleaned_data['gpa'] = round((gpa / 100) * 4, 2)
            else:
                if gpa < 0 or gpa > 4:
                    raise forms.ValidationError("The average on a 4.0 scale should be between 0 and 4.")

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.gpa = self.cleaned_data.get('gpa')
        if commit:
            instance.save()
        return instance