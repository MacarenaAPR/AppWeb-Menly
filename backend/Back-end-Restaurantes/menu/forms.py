from django import forms

class ProductoCSVImportForm(forms.Form):
    archivo_csv = forms.FileField(label="Archivo CSV")