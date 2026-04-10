import os
import uuid
from django.db import models


def _contract_pdf_path(instance, filename):
    ext = os.path.splitext(filename)[1].lower() or '.pdf'
    return f'contracts/pdfs/{uuid.uuid4().hex}{ext}'
from apps.core.models import Organization
from apps.leads.models import Lead


class SaleContract(models.Model):
    STATUS_DRAFT = 'draft'
    STATUS_SENT = 'sent'
    STATUS_BUYER_FILLED = 'buyer_filled'
    STATUS_APPROVED = 'approved'
    STATUS_SIGNED = 'signed'

    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Rascunho'),
        (STATUS_SENT, 'Enviado ao comprador'),
        (STATUS_BUYER_FILLED, 'Preenchido pelo comprador'),
        (STATUS_APPROVED, 'Aprovado'),
        (STATUS_SIGNED, 'Assinado'),
    ]

    SEX_MALE = 'M'
    SEX_FEMALE = 'F'
    SEX_CHOICES = [(SEX_MALE, 'Macho'), (SEX_FEMALE, 'Fêmea')]

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name='contracts'
    )
    lead = models.ForeignKey(
        Lead, on_delete=models.CASCADE, related_name='contracts', null=True, blank=True
    )
    dog = models.ForeignKey(
        'kennel.Dog', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='contracts'
    )

    # Dados do filhote (admin preenche)
    puppy_sex = models.CharField(max_length=1, choices=SEX_CHOICES)
    puppy_color = models.CharField(max_length=100)
    puppy_microchip = models.CharField(max_length=100, blank=True)
    puppy_father = models.CharField(max_length=200, blank=True)
    puppy_mother = models.CharField(max_length=200, blank=True)
    puppy_birth_date = models.DateField(null=True, blank=True)

    # Preço (calculado automaticamente conforme sexo)
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    deposit_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    # Dados do comprador (comprador preenche na página pública)
    buyer_name = models.CharField(max_length=200, blank=True)
    buyer_cpf = models.CharField(max_length=14, blank=True)
    buyer_marital_status = models.CharField(max_length=50, blank=True)
    buyer_address = models.CharField(max_length=500, blank=True)
    buyer_cep = models.CharField(max_length=9, blank=True)
    buyer_email = models.EmailField(blank=True)

    # Controle de fluxo
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    # Assinatura
    signature_data = models.TextField(blank=True)
    signature_type = models.CharField(max_length=20, blank=True)  # 'canvas' ou 'govbr'

    # PDF gerado
    pdf_file = models.FileField(upload_to=_contract_pdf_path, null=True, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    buyer_filled_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    signed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'sale_contracts'
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if self.dog_id:
            dog = self.dog
            self.puppy_sex = dog.sex
            self.puppy_color = dog.color or self.puppy_color
            self.puppy_microchip = dog.microchip or self.puppy_microchip
            self.puppy_birth_date = dog.birth_date or self.puppy_birth_date
            if dog.father:
                self.puppy_father = dog.father.name
            if dog.mother:
                self.puppy_mother = dog.mother.name
            if dog.price:
                self.price = dog.price
        if not self.price:
            self.price = 4000.00
        if self.price:
            self.deposit_amount = round(float(self.price) * 0.30, 2)
        super().save(*args, **kwargs)

    def __str__(self):
        buyer = self.buyer_name or 'Comprador não informado'
        return f"Contrato #{self.id} — {buyer} ({self.get_status_display()})"
