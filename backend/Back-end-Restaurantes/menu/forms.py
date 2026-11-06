from django import forms

class ProductoCSVImportForm(forms.Form):
    archivo_csv = forms.FileField(label="Archivo CSV")


class PedidoPruebaCSVImportForm(forms.Form):
    MODO_VALIDAR = "validar"
    MODO_PREPARAR = "preparar"
    archivo_csv = forms.FileField(label="Archivo CSV de pedidos de prueba")
    modo = forms.ChoiceField(
        choices=[
            (MODO_VALIDAR, "Sólo validar (dry-run, sin escritura)"),
            (MODO_PREPARAR, "Validar y preparar confirmación de importación"),
        ],
        initial=MODO_VALIDAR,
    )

    def clean_archivo_csv(self):
        archivo = self.cleaned_data["archivo_csv"]
        if archivo.size > 2 * 1024 * 1024:
            raise forms.ValidationError("El CSV no puede superar 2 MB.")
        if not archivo.name.lower().endswith(".csv"):
            raise forms.ValidationError("El archivo debe tener extensión .csv.")
        return archivo
