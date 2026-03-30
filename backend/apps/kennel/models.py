from django.db import models
from apps.core.models import Organization


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
    dog = models.ForeignKey(Dog, on_delete=models.CASCADE, related_name='media')
    file = models.ImageField(upload_to='kennel/dogs/')
    caption = models.CharField(max_length=200, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'kennel_dog_media'
        ordering = ['uploaded_at']

    def __str__(self):
        return f"Foto de {self.dog.name}"


class LitterMedia(models.Model):
    litter = models.ForeignKey(Litter, on_delete=models.CASCADE, related_name='media')
    file = models.ImageField(upload_to='kennel/litters/')
    caption = models.CharField(max_length=200, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'kennel_litter_media'
        ordering = ['uploaded_at']

    def __str__(self):
        return f"Foto de {self.litter.name}"


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
