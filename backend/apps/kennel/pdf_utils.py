import io
from datetime import date, datetime
from decimal import Decimal
from typing import Any


def _import_pypdf():
    try:
        from pypdf import PdfReader, PdfWriter
    except ImportError as exc:
        raise RuntimeError(
            "pypdf nao esta instalado. Execute: pip install pypdf"
        ) from exc
    return PdfReader, PdfWriter


def extract_pdf_fields(file_obj) -> list[dict[str, Any]]:
    PdfReader, _ = _import_pypdf()
    reader = PdfReader(file_obj)
    fields = reader.get_fields() or {}
    result: list[dict[str, Any]] = []
    for name, meta in sorted(fields.items(), key=lambda item: item[0].lower()):
        value = meta.get('/V')
        result.append({
            'name': name,
            'type': str(meta.get('/FT') or ''),
            'value': '' if value is None else str(value),
        })
    return result


def build_cbkc_default_mapping(field_inventory: list[dict[str, Any]]) -> dict[str, str]:
    """Retorna mapping padrão para o formulário CBKC (Mapa de Registro de Ninhada)."""
    field_names = {item.get('name') for item in field_inventory if isinstance(item, dict)}
    mapping: dict[str, str] = {}

    basic_map = {
        'Código': 'extra.general.code',
        'Nome do Canil ou Criador Eventual': 'extra.general.canil',
        'Raça': 'extra.general.raca',
        'Variedade': 'extra.general.variedade',
        'Proprietários': 'extra.general.criadores',
        'Dia de Nascimento da Ninhada_es_:date': 'litter.birth_day',
        'Mês de Nascimento da Ninhada_es_:date': 'litter.birth_month',
        'Ano de Nascimento da Ninhada_es_:date': 'litter.birth_year',
        'Criador ou Canil': 'extra.general.creator_or_kennel',
        'Nome do Macho (Padreador)': 'father.name',
        'Número de Registro do Macho (Padreador)': 'father.pedigree_number',
        'Microchip do Macho (Padreador)': 'father.microchip',
        'Proprietário do Macho (Padreador)': 'extra.father.owner_name',
        'Endereço do Macho (Padreador)': 'extra.father.owner_address',
        'CEP Padreador': 'extra.father.owner_zip_1',
        'CEP Padreador pt2': 'extra.father.owner_zip_2',
        'E-mail Padreador': 'extra.father.owner_email',
        'Tel Padreador_ddd': 'extra.father.owner_phone_ddd',
        'Tel Padreador': 'extra.father.owner_phone',
        'Assinatura Padreador': 'extra.father.signature',
        'Nome do Fêmea (Matriz)': 'mother.name',
        'Número de Registro da Fêmea (Matriz)': 'mother.pedigree_number',
        'Microchip do Fêmea (Matriz)': 'mother.microchip',
        'Proprietário da Fêmea (Matriz)': 'extra.mother.owner_name',
        'Endereço da Fêmea (Matriz)': 'extra.mother.owner_address',
        'CEP Matriz': 'extra.mother.owner_zip_1',
        'CEP Matriz pt2': 'extra.mother.owner_zip_2',
        'E-mail Matriz': 'extra.mother.owner_email',
        'Tel Matriz_ddd': 'extra.mother.owner_phone_ddd',
        'Tel Matriz': 'extra.mother.owner_phone',
        'Assinatura Matriz': 'extra.mother.signature',
    }
    for field_name, source_path in basic_map.items():
        if field_name in field_names:
            mapping[field_name] = source_path

    for idx in range(1, 13):
        puppy_idx = idx - 1
        pair_map = {
            f'Filhote{idx}': f'puppies.{puppy_idx}.resolved_name',
            f'MF{idx}': f'puppies.{puppy_idx}.sex',
            f'Cor{idx}': f'puppies.{puppy_idx}.color',
            f'Microchip{idx}': f'puppies.{puppy_idx}.microchip',
            f'LE{idx}': f'extra.puppies.{puppy_idx}.pedigree',
            f'PE{idx}': f'extra.puppies.{puppy_idx}.exportacao',
            f'TP{idx}': f'extra.puppies.{puppy_idx}.transferencia',
            f'PP{idx}': f'extra.puppies.{puppy_idx}.propriedade',
            f'4G{idx}': f'extra.puppies.{puppy_idx}.pedigree_pet',
            f'Limitação Filhote {idx}': f'extra.puppies.{puppy_idx}.limitation',
        }
        for field_name, source_path in pair_map.items():
            if field_name in field_names:
                mapping[field_name] = source_path
    return mapping


def build_litter_registration_context(litter, extra_data: dict[str, Any] | None = None) -> dict[str, Any]:
    extra_data = extra_data or {}
    father = litter.father
    mother = litter.mother
    puppies = list(litter.puppies.select_related('father', 'mother').order_by('id'))
    birth_day = ''
    birth_month = ''
    birth_year = ''
    if litter.birth_date:
        birth_day = f'{litter.birth_date.day:02d}'
        birth_month = f'{litter.birth_date.month:02d}'
        birth_year = f'{litter.birth_date.year}'

    return {
        'litter': {
            'id': litter.id,
            'name': litter.name,
            'mating_date': litter.mating_date,
            'expected_birth_date': litter.expected_birth_date,
            'birth_date': litter.birth_date,
            'male_count': litter.male_count,
            'female_count': litter.female_count,
            'total_count': litter.total_count,
            'cbkc_number': litter.cbkc_number,
            'notes': litter.notes,
            'birth_day': birth_day,
            'birth_month': birth_month,
            'birth_year': birth_year,
        },
        'father': {
            'id': father.id if father else None,
            'name': father.name if father else '',
            'pedigree_number': father.pedigree_number if father else '',
            'microchip': father.microchip if father else '',
            'tattoo': father.tattoo if father else '',
            'color': father.color if father else '',
            'birth_date': father.birth_date if father else None,
        },
        'mother': {
            'id': mother.id if mother else None,
            'name': mother.name if mother else '',
            'pedigree_number': mother.pedigree_number if mother else '',
            'microchip': mother.microchip if mother else '',
            'tattoo': mother.tattoo if mother else '',
            'color': mother.color if mother else '',
            'birth_date': mother.birth_date if mother else None,
        },
        'puppies': [
            {
                'id': puppy.id,
                'name': puppy.name,
                'resolved_name': (
                    (
                        ((extra_data.get('puppies') or [])[idx] or {})
                        if isinstance(extra_data.get('puppies'), list) and len(extra_data.get('puppies') or []) > idx
                        else {}
                    ).get('name_override') or puppy.name
                ),
                'sex': puppy.sex,
                'sex_display': puppy.get_sex_display(),
                'color': puppy.color,
                'pedigree_number': puppy.pedigree_number,
                'microchip': puppy.microchip,
                'tattoo': puppy.tattoo,
                'birth_date': puppy.birth_date,
                'status': puppy.status,
            }
            for idx, puppy in enumerate(puppies)
        ],
        'extra': extra_data,
    }


def _resolve_context_path(context: dict[str, Any], path: str) -> Any:
    current: Any = context
    for chunk in path.split('.'):
        if isinstance(current, list):
            try:
                idx = int(chunk)
            except (TypeError, ValueError):
                return None
            if idx < 0 or idx >= len(current):
                return None
            current = current[idx]
            continue
        if isinstance(current, dict):
            current = current.get(chunk)
            continue
        return None
    return current


def _format_pdf_value(value: Any) -> str:
    if value is None:
        return ''
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, (date, datetime)):
        return value.strftime('%d/%m/%Y')
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (list, tuple)):
        return ', '.join(_format_pdf_value(item) for item in value if item is not None)
    return str(value)


def resolve_mapping(
    mapping: dict[str, str],
    context: dict[str, Any],
    required_fields: list[str] | None = None,
) -> tuple[dict[str, str], list[str]]:
    required_fields = required_fields or []
    values: dict[str, str] = {}
    missing_required: list[str] = []
    for field_name, path in mapping.items():
        raw_value = _resolve_context_path(context, path)
        value = _format_pdf_value(raw_value)
        values[field_name] = value
        if field_name in required_fields and not value.strip():
            missing_required.append(field_name)
    return values, missing_required


def fill_pdf_template(file_obj, mapping_values: dict[str, str]) -> bytes:
    PdfReader, PdfWriter = _import_pypdf()
    reader = PdfReader(file_obj)
    fields = reader.get_fields() or {}
    writer = PdfWriter()
    writer.clone_document_from_reader(reader)
    normalized_values: dict[str, str] = {}

    for field_name, raw_value in mapping_values.items():
        field_meta = fields.get(field_name, {})
        states = field_meta.get('/_States_') or []
        states_clean = [str(state) for state in states]
        off_state = next((state for state in states_clean if state.lower() == '/off'), '/Off')
        on_candidates = [state for state in states_clean if state.lower() != '/off']
        on_state = on_candidates[0] if on_candidates else '/Yes'

        value_str = str(raw_value or '').strip()
        lowered = value_str.lower()
        if lowered in {'', 'false', 'off', '/off', '0', 'nao', 'não'}:
            normalized_values[field_name] = off_state
            continue
        if lowered in {'true', 'on', 'yes', '/yes', 'sim', '/sim', '1', '/1'}:
            normalized_values[field_name] = on_state
            continue
        normalized_values[field_name] = value_str

    for page in writer.pages:
        writer.update_page_form_field_values(page, normalized_values, auto_regenerate=False)
    writer.set_need_appearances_writer(True)
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()
