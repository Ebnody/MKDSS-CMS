from django import forms
from django.contrib.auth.models import User
from .models import Department, Document, DocumentVersion, ComplianceRequest, DocumentReview, Role, SystemSetting
from .services import validate_document_file


class DocumentMetaForm(forms.ModelForm):
    class Meta:
        model = Document
        fields = ["title", "document_number", "category"]


class DocumentUploadForm(forms.ModelForm):
    class Meta:
        model = DocumentVersion
        fields = ["version", "original_file"]
        widgets = {"version": forms.TextInput(attrs={"placeholder": "1.0"})}

    def clean_original_file(self):
        value = self.cleaned_data["original_file"]
        try: validate_document_file(value)
        except ValueError as exc: raise forms.ValidationError(str(exc))
        return value


class VersionUploadForm(DocumentUploadForm):
    pass


class ExistingDocumentUploadForm(forms.Form):
    """Metadata and file form for documents that pre-date this system."""
    title = forms.CharField(max_length=255, label="Document Title")
    document_number = forms.CharField(max_length=80, required=False, label="Document Number")
    category = forms.CharField(max_length=120, required=False, label="Category")
    version = forms.CharField(max_length=30, initial="1.0", label="Version")
    original_file = forms.FileField(label="Existing Document File")

    def clean_original_file(self):
        value = self.cleaned_data["original_file"]
        try:
            validate_document_file(value)
        except ValueError as exc:
            raise forms.ValidationError(str(exc))
        return value


class ReviewForm(forms.ModelForm):
    class Meta:
        model = DocumentReview
        fields = ["decision", "remarks"]
        widgets = {"remarks": forms.Textarea(attrs={"rows": 6})}

    def clean(self):
        data = super().clean()
        if data.get("decision") == DocumentReview.Decision.REVISION_REQUIRED and not (data.get("remarks") or "").strip():
            self.add_error("remarks", "Remarks are required when requesting revision.")
        return data


class NewDocumentRequestForm(forms.ModelForm):
    class Meta:
        model = ComplianceRequest
        fields = ["requested_title", "department", "reason", "description", "additional_notes"]
        widgets = {"reason": forms.Textarea(attrs={"rows": 4}), "description": forms.Textarea(attrs={"rows": 5}), "additional_notes": forms.Textarea(attrs={"rows": 3})}


class ChangeRequestForm(forms.ModelForm):
    class Meta:
        model = ComplianceRequest
        fields = ["existing_document", "department", "requested_change", "reason", "additional_notes"]
        widgets = {"requested_change": forms.Textarea(attrs={"rows": 5}), "reason": forms.Textarea(attrs={"rows": 4}), "additional_notes": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["existing_document"].queryset = Document.objects.filter(state=Document.State.PUBLISHED).select_related("current_version")


class ApprovalForm(forms.ModelForm):
    class Meta:
        model = ComplianceRequest
        fields = ["approval_comments"]
        widgets = {"approval_comments": forms.Textarea(attrs={"rows": 5})}

    def clean_approval_comments(self):
        return self.cleaned_data["approval_comments"].strip()


class UserForm(forms.ModelForm):
    role = forms.ChoiceField(choices=[choice for choice in Role.choices if choice[0] != "REVIEWER"])
    department = forms.ModelChoiceField(queryset=Department.objects.filter(active=True), required=False)
    password1 = forms.CharField(label="Password", widget=forms.PasswordInput, required=False, min_length=10)
    password2 = forms.CharField(label="Confirm password", widget=forms.PasswordInput, required=False)

    class Meta:
        model = User
        fields = ["username", "first_name", "last_name", "email", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["role"].initial = self.instance.profile.role
            self.fields["department"].initial = self.instance.profile.department
        else:
            self.fields["password1"].required = True
            self.fields["password2"].required = True

    def clean(self):
        data = super().clean()
        p1, p2 = data.get("password1"), data.get("password2")
        if p1 or p2:
            if p1 != p2: self.add_error("password2", "Passwords do not match.")
        return data

    def save(self, commit=True):
        user = super().save(commit)
        profile = user.profile
        profile.role = self.cleaned_data["role"]
        profile.department = self.cleaned_data["department"]
        profile.active = user.is_active
        profile.save()
        if self.cleaned_data.get("password1"):
            user.set_password(self.cleaned_data["password1"])
            user.save(update_fields=["password"])
        return user


class DepartmentForm(forms.ModelForm):
    class Meta:
        model = Department
        fields = ["name", "active"]


class ReportFilterForm(forms.Form):
    start_date = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    end_date = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    document = forms.ModelChoiceField(queryset=Document.objects.all(), required=False, empty_label="All documents")
    version = forms.ModelChoiceField(queryset=DocumentVersion.objects.none(), required=False, empty_label="All versions")
    user = forms.ModelChoiceField(queryset=User.objects.filter(is_active=True, profile__role=Role.USER).order_by("username"), required=False, empty_label="All users")
    department = forms.ModelChoiceField(queryset=Department.objects.filter(active=True), required=False, empty_label="All departments")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["document"].queryset = Document.objects.order_by("title")
        document_id = self.data.get("document") or self.initial.get("document")
        if document_id:
            self.fields["version"].queryset = DocumentVersion.objects.filter(document_id=document_id).order_by("version")
        else:
            self.fields["version"].queryset = DocumentVersion.objects.order_by("document__title", "version")

    def clean(self):
        data = super().clean()
        if data.get("start_date") and data.get("end_date") and data["start_date"] > data["end_date"]:
            raise forms.ValidationError("Start date cannot be after end date.")
        return data


class RestoreForm(forms.Form):
    backup = forms.FileField(help_text="Upload a backup ZIP created by this system.")


class SystemSettingForm(forms.ModelForm):
    class Meta:
        model = SystemSetting
        fields = ["key", "value"]
