DB to Django models
```
python manage.py inspectdb > models.py
```
- chanmges the AutoField to IntegerField
- add max_length to CharFields
- In contig.sequence change CharField to TextField
- Add primary_keys
- python manage.py makemigrations
- python manage.py migrate