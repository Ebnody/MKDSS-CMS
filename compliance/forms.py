from django import forms
from django.contrib.auth.models import User
from .models import Department, Document, DocumentVersion, ComplianceRequest, DocumentReview, Role, SystemSetting
from .services import validate_document_file


class DocumentAudienceFieldsMixin:
    def clean(self):
        data = super().clean()
        audience = data.get("audience")
        if audience == Document.Audience.UNCLASSIFIED:
            self.add_error("audience", "Choose a publication audience before saving or publishing this document.")
        if audience == Document.Audience.DEPARTMENT and not data.get("audience_department"):
            self.add_error("audience_department", "Choose the department allowed to read this document.")
        if audience != Document.Audience.DEPARTMENT:
            data["audience_department"] = None
        managers = data.get("audience_managers")
        if audience == Document.Audience.SELECTED_MANAGERS and not managers:
            self.add_error("audience_managers", "Select at least one manager.")
        if audience != Document.Audience.SELECTED_MANAGERS:
            data["audience_managers"] = User.objects.none()
        return data


class DocumentMetaForm(DocumentAudienceFieldsMixin, forms.ModelForm):
    audience = forms.ChoiceField(choices=Document.Audience.choices, label="Who may read this document?")
    audience_department = forms.ModelChoiceField(queryset=Department.objects.filter(active=True), required=False, label="Permitted department")
    audience_managers = forms.ModelMultipleChoiceField(queryset=User.objects.filter(is_active=True, profile__role=Role.MANAGER), required=False, label="Selected managers")

    class Meta:
        model = Document
        fields = ["title", "document_number", "category", "audience", "audience_department", "audience_managers"]


class DocumentAudienceForm(DocumentAudienceFieldsMixin, forms.Form):
    audience = forms.ChoiceField(choices=Document.Audience.choices, label="Who may read this document?")
    audience_department = forms.ModelChoiceField(queryset=Department.objects.filter(active=True), required=False, label="Permitted department")
    audience_managers = forms.ModelMultipleChoiceField(queryset=User.objects.filter(is_active=True, profile__role=Role.MANAGER), required=False, label="Selected managers")


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
    """Metadata and audience form for documents that pre-date this system."""
    audience = forms.ChoiceField(choices=Document.Audience.choices, label="Who may read this document?")
    audience_department = forms.ModelChoiceField(queryset=Department.objects.filter(active=True).order_by("name"), required=False, label="Permitted department")
    audience_departments = forms.ModelMultipleChoiceField(
        queryset=Department.objects.filter(active=True).order_by("name"), required=False,
        label="Departments whose managers may read this document", help_text="Select one or more departments from the dropdown.",
        widget=forms.SelectMultiple(attrs={"size": "1"}),
    )
    # The view still saves the existing audience_managers relation, avoiding a database migration.
    audience_managers = forms.ModelMultipleChoiceField(queryset=User.objects.none(), required=False)
    title = forms.CharField(max_length=255, label="Document Title")
    document_number = forms.CharField(max_length=80, required=False, label="Document Number")
    category = forms.CharField(max_length=120, required=False, label="Category")
    version = forms.CharField(max_length=30, initial="1.0", label="Version")
    original_file = forms.FileField(label="Existing Document File")

    def clean(self):
        data = super().clean()
        audience = data.get("audience")
        if audience == Document.Audience.UNCLASSIFIED:
            self.add_error("audience", "Choose who may read this document before publishing.")
        if audience == Document.Audience.DEPARTMENT and not data.get("audience_department"):
            self.add_error("audience_department", "Choose the permitted department.")
        if audience != Document.Audience.DEPARTMENT:
            data["audience_department"] = None
        selected_departments = data.get("audience_departments")
        if audience == Document.Audience.SELECTED_MANAGERS:
            if not selected_departments:
                self.add_error("audience_departments", "Select at least one department.")
                managers = User.objects.none()
            else:
                managers = User.objects.filter(
                    is_active=True, profile__active=True, profile__role=Role.MANAGER,
                    profile__department__in=selected_departments,
                ).distinct()
                if not managers.exists():
                    self.add_error("audience_departments", "The selected departments have no active manager accounts.")
        else:
            managers = User.objects.none()
        data["audience_managers"] = managers
        if audience != Document.Audience.SELECTED_MANAGERS:
            data["audience_departments"] = Department.objects.none()
        return data

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
    REQUEST_KIND_CHOICES = (
        ("NEW_DOCUMENT", "New Document"),
        ("ADOPTION", "Adoption of External Document"),
    )
    request_kind = forms.ChoiceField(
        choices=REQUEST_KIND_CHOICES,
        label="Please identify the type of request by marking one",
        widget=forms.RadioSelect,
        required=True,
    )

    class Meta:
        model = ComplianceRequest
        # Existing database columns are retained and presented with the new
        # controlled-form labels; this avoids a schema migration.
        fields = ["description", "requested_title", "reason", "additional_notes"]
        labels = {
            "description": "1. Affected Process(es)",
            "requested_title": "2. Process Owner",
            "reason": "3. Justification for the request",
            "additional_notes": "4. Enclosure (Title and No. of pages)",
        }
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "reason": forms.Textarea(attrs={"rows": 4}),
            "additional_notes": forms.Textarea(attrs={"rows": 3}),
            "requested_title": forms.TextInput(attrs={"placeholder": "Enter the process owner's name or position"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["description"].required = True
        self.fields["requested_title"].required = True
        self.fields["additional_notes"].required = True


class ChangeRequestForm(forms.ModelForm):
    """Shared Document Change Request form for every authorized requester role."""

    class Meta:
        model = ComplianceRequest
        fields = ["existing_document", "requested_change", "reason", "description", "additional_notes"]
        labels = {
            "existing_document": "Document to be changed",
            "requested_change": "1.1 Change Statement",
            "reason": "1.2 Justification for the Change Request",
            "description": "1.3 Affected Process(es), Customers, Other Stakeholders",
            "additional_notes": "1.4 Enclosure Justifying the Change (Title and No. of Pages)",
        }
        help_texts = {
            "reason": "Update the document according to the PCI-CP requirement.",
            "additional_notes": "Enter the enclosure title and number of pages. If there is no enclosure, enter N/A.",
        }
        widgets = {
            "requested_change": forms.Textarea(attrs={"rows": 4}),
            "reason": forms.Textarea(attrs={"rows": 4}),
            "description": forms.Textarea(attrs={"rows": 4}),
            "additional_notes": forms.TextInput(attrs={"placeholder": "Enclosure title and number of pages"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["existing_document"].queryset = Document.objects.none()
        if user is not None:
            self.fields["existing_document"].queryset = Document.objects.filter(
                state=Document.State.PUBLISHED,
                archived_at__isnull=True,
                versions__uploaded_by=user,
            ).select_related("current_version").distinct()
        for field_name in ("requested_change", "reason", "description", "additional_notes"):
            self.fields[field_name].required = True


class ApprovalForm(forms.ModelForm):
    class Meta:
        model = ComplianceRequest
        fields = ["approval_comments"]
        widgets = {"approval_comments": forms.Textarea(attrs={"rows": 5})}

    def clean_approval_comments(self):
        return self.cleaned_data["approval_comments"].strip()


class UserForm(forms.ModelForm):
    role = forms.ChoiceField(choices=[choice for choice in Role.choices if choice[0] not in {"USER"}])
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
        if data.get("role") == Role.MANAGER and not data.get("department"):
            self.add_error("department", "A department is required for every Manager account.")
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
    user = forms.ModelChoiceField(queryset=User.objects.filter(is_active=True, profile__role__in=[Role.READER, Role.MANAGER]).order_by("username"), required=False, empty_label="All users")
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
