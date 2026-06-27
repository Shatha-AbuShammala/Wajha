from django import forms
from .models import GrantOpportunity, GrantDegreeLevel


# ============================================================
# Admin: Add / Edit Grant
# ============================================================

class GrantForm(forms.ModelForm):

    # Tag fields (comma-separated input)
    fields_of_study = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g. Computer Science, Engineering'
        }),
        help_text='Separate multiple fields with commas.'
    )

    degree_levels = forms.MultipleChoiceField(
        choices=GrantDegreeLevel.DEGREE_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple(),
        help_text='Select all that apply.'
    )

    countries = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g. Palestine, Germany, Jordan'
        }),
        help_text='Separate multiple countries with commas.'
    )

    class Meta:
        model = GrantOpportunity
        fields = [
            'title', 'organization', 'description',
            'eligibility_text', 'eligibility_summary',
            'funding_type', 'deadline', 'source_url', 'status',
        ]

        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Grant title'
            }),
            'organization': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Organization name'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4
            }),
            'eligibility_text': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4
            }),
            'eligibility_summary': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3
            }),
            'funding_type': forms.Select(attrs={
                'class': 'form-select'
            }),
            'deadline': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'source_url': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://'
            }),
            'status': forms.Select(attrs={
                'class': 'form-select'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Pre-fill tag fields when editing existing grant
        if self.instance.pk:
            self.fields['fields_of_study'].initial = ', '.join(
                self.instance.fields.values_list('field_name', flat=True)
            )

            self.fields['degree_levels'].initial = list(
                self.instance.degree_levels.values_list('degree', flat=True)
            )

            self.fields['countries'].initial = ', '.join(
                self.instance.countries.values_list('country_name', flat=True)
            )


# ============================================================
# Student: Search & Filter Grants
# ============================================================

class GrantSearchForm(forms.Form):

    query = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search by title or organization...',
            'id': 'search-input'
        })
    )

    degree_level = forms.MultipleChoiceField(
        choices=GrantDegreeLevel.DEGREE_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple()
    )

    country = forms.CharField(
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select',
            'id': 'country-filter'
        })
    )

    field_of_study = forms.CharField(
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select',
            'id': 'field-filter'
        })
    )

    deadline_within = forms.IntegerField(
        required=False,
        min_value=1,
        max_value=365,
        widget=forms.NumberInput(attrs={
            'class': 'form-range',
            'type': 'range',
            'min': '1',
            'max': '365',
            'id': 'deadline-slider'
        })
    )