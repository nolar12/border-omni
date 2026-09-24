import os
import uuid
from django.db import models
from apps.core.models import Organization


def _dog_media_upload(instance, filename):
    ext = os.path.splitext(filename)[1].lower()
    return f'kennel/dogs/{uuid.uuid4().hex}{ext}'


def _litter_media_upload(instance, filename):
    ext = os.path.splitext(filename)[1].lower()
    return f'kennel/litters/{uuid.uuid4().hex}{ext}'


def _litter_template_upload(instance, filename):
    ext = os.path.splitext(filename)[1].lower() or '.pdf'
    return f'kennel/litter_templates/{uuid.uuid4().hex}{ext}'


def _litter_registration_upload(instance, filename):
    ext = os.path.splitext(filename)[1].lower() or '.pdf'
    return f'kennel/litter_registrations/{uuid.uuid4().hex}{ext}'


class Litter(models.Model):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name='litters'
    )
    name = models.CharField(max_length=200)
    # Pai e mãe são FK para Dog (definidos após Dog, usando string)
    father = models.ForeignKey(
        'Dog', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='litters_as_father'
    )
    mother = models.ForeignKey(
        'Dog', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='litters_as_mother'
    )
    mating_date = models.DateField(null=True, blank=True)
    expected_birth_date = models.DateField(null=True, blank=True)
    birth_date = models.DateField(null=True, blank=True)
    male_count = models.PositiveIntegerField(default=0)
    female_count = models.PositiveIntegerField(default=0)
    cbkc_number = models.CharField(max_length=100, blank=True)
    is_featured = models.BooleanField(default=False)
    registration_data = models.JSONField(default=dict, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'kennel_litters'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.organization})"

    @property
    def total_count(self):
        return self.male_count + self.female_count


class Dog(models.Model):
    SEX_MALE = 'M'
    SEX_FEMALE = 'F'
    SEX_CHOICES = [(SEX_MALE, 'Macho'), (SEX_FEMALE, 'Fêmea')]

    STATUS_AVAILABLE = 'available'
    STATUS_RESERVED = 'reserved'
    STATUS_SOLD = 'sold'
    STATUS_OWN = 'own'
    STATUS_DECEASED = 'deceased'
    STATUS_CHOICES = [
        (STATUS_AVAILABLE, 'Disponível'),
        (STATUS_RESERVED, 'Reservado'),
        (STATUS_SOLD, 'Vendido'),
        (STATUS_OWN, 'Plantel próprio'),
        (STATUS_DECEASED, 'Falecido'),
    ]

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name='dogs'
    )
    name = models.CharField(max_length=200)
    breed = models.CharField(max_length=100, default='Border Collie')
    sex = models.CharField(max_length=1, choices=SEX_CHOICES)
    birth_date = models.DateField(null=True, blank=True)
    color = models.CharField(max_length=100, blank=True)
    pedigree_number = models.CharField(max_length=100, blank=True)
    microchip = models.CharField(max_length=100, blank=True)
    tattoo = models.CharField(max_length=100, blank=True)

    father = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='offspring_as_father'
    )
    mother = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='offspring_as_mother'
    )
    origin_litter = models.ForeignKey(
        Litter, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='puppies'
    )

    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_AVAILABLE
    )
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'kennel_dogs'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.get_sex_display()}) — {self.get_status_display()}"


class DogMedia(models.Model):
    TYPE_IMAGE = 'IMAGE'
    TYPE_VIDEO = 'VIDEO'
    TYPE_CHOICES = [(TYPE_IMAGE, 'Imagem'), (TYPE_VIDEO, 'Vídeo')]

    dog = models.ForeignKey(Dog, on_delete=models.CASCADE, related_name='media')
    file = models.FileField(upload_to=_dog_media_upload)
    media_type = models.CharField(max_length=10, choices=TYPE_CHOICES, default=TYPE_IMAGE)
    caption = models.CharField(max_length=200, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'kennel_dog_media'
        ordering = ['uploaded_at']

    def __str__(self):
        return f"{'Vídeo' if self.media_type == self.TYPE_VIDEO else 'Foto'} de {self.dog.name}"


class LitterMedia(models.Model):
    TYPE_IMAGE = 'IMAGE'
    TYPE_VIDEO = 'VIDEO'
    TYPE_CHOICES = [(TYPE_IMAGE, 'Imagem'), (TYPE_VIDEO, 'Vídeo')]

    litter = models.ForeignKey(Litter, on_delete=models.CASCADE, related_name='media')
    file = models.FileField(upload_to=_litter_media_upload)
    media_type = models.CharField(max_length=10, choices=TYPE_CHOICES, default=TYPE_IMAGE)
    caption = models.CharField(max_length=200, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'kennel_litter_media'
        ordering = ['uploaded_at']

    def __str__(self):
        return f"{'Vídeo' if self.media_type == self.TYPE_VIDEO else 'Foto'} de {self.litter.name}"


class DogHealthRecord(models.Model):
    TYPE_VACCINE = 'vaccine'
    TYPE_DEWORMING = 'deworming'
    TYPE_EXAM = 'exam'
    TYPE_OTHER = 'other'
    TYPE_CHOICES = [
        (TYPE_VACCINE, 'Vacina'),
        (TYPE_DEWORMING, 'Vermifugação'),
        (TYPE_EXAM, 'Exame'),
        (TYPE_OTHER, 'Outro'),
    ]

    dog = models.ForeignKey(Dog, on_delete=models.CASCADE, related_name='health_records')
    record_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    description = models.CharField(max_length=200)
    date = models.DateField()
    next_date = models.DateField(null=True, blank=True)
    vet = models.CharField(max_length=200, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'kennel_dog_health'
        ordering = ['-date']

    def __str__(self):
        return f"{self.get_record_type_display()} — {self.dog.name} ({self.date})"


class LitterHealthRecord(models.Model):
    TYPE_VACCINE = 'vaccine'
    TYPE_DEWORMING = 'deworming'
    TYPE_EXAM = 'exam'
    TYPE_OTHER = 'other'
    TYPE_CHOICES = [
        (TYPE_VACCINE, 'Vacina'),
        (TYPE_DEWORMING, 'Vermifugação'),
        (TYPE_EXAM, 'Exame'),
        (TYPE_OTHER, 'Outro'),
    ]

    litter = models.ForeignKey(Litter, on_delete=models.CASCADE, related_name='health_records')
    record_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    description = models.CharField(max_length=200)
    date = models.DateField()
    next_date = models.DateField(null=True, blank=True)
    vet = models.CharField(max_length=200, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'kennel_litter_health'
        ordering = ['-date']

    def __str__(self):
        return f"{self.get_record_type_display()} — {self.litter.name} ({self.date})"


class LitterDocumentTemplate(models.Model):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name='litter_document_templates'
    )
    name = models.CharField(max_length=200)
    source_file = models.FileField(upload_to=_litter_template_upload)
    field_mapping = models.JSONField(default=dict, blank=True)
    required_fields = models.JSONField(default=list, blank=True)
    field_inventory = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'kennel_litter_document_templates'
        ordering = ['-updated_at']

    def __str__(self):
        return f"{self.name} ({self.organization})"


class LitterRegistrationDocument(models.Model):
    STATUS_DRAFT = 'draft'
    STATUS_GENERATED = 'generated'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Rascunho'),
        (STATUS_GENERATED, 'Gerado'),
        (STATUS_FAILED, 'Falha'),
    ]

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name='litter_registration_documents'
    )
    litter = models.ForeignKey(
        Litter, on_delete=models.CASCADE, related_name='registration_documents'
    )
    template = models.ForeignKey(
        LitterDocumentTemplate, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='generated_documents'
    )
    extra_data = models.JSONField(default=dict, blank=True)
    generated_file = models.FileField(upload_to=_litter_registration_upload, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    error_message = models.TextField(blank=True)
    generated_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'kennel_litter_registration_documents'
        ordering = ['-created_at']

    def __str__(self):
        return f"Registro ninhada #{self.id} — {self.litter.name}"
