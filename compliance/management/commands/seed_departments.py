from django.core.management.base import BaseCommand
from compliance.models import Department
class Command(BaseCommand):
    help="Create the standard MKDSS departments if missing. Does not create users or documents."
    def handle(self,*args,**kwargs):
        for name in ["QC","Personalization","IT","Data Processing","HR","Office","Technic","Utility","Production"]:
            Department.objects.get_or_create(name=name)
        self.stdout.write(self.style.SUCCESS("Departments ensured."))
