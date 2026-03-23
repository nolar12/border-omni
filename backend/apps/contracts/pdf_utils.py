import io
import logging
from decimal import Decimal
from django.template.loader import render_to_string
from django.core.files.base import ContentFile
from django.utils import timezone

logger = logging.getLogger('apps')


def _fmt_brl(value):
    if value is None:
        return '—'
    try:
        v = float(value)
        return f"R$ {v:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
    except (TypeError, ValueError):
        return str(value)


def _fmt_date(d):
    if d is None:
        return '—'
    try:
        return d.strftime('%d/%m/%Y')
    except Exception:
        return str(d)


def build_contract_context(contract):
    price = contract.price or Decimal('0')
    deposit = contract.deposit_amount or Decimal('0')
    balance = price - deposit

    buyer_sig = None
    if contract.signature_data and contract.signature_data.startswith('data:image'):
        buyer_sig = contract.signature_data

    return {
        'contract_id': contract.id,
        'buyer_name': contract.buyer_name or '',
        'buyer_cpf': contract.buyer_cpf or '',
        'buyer_marital_status': contract.buyer_marital_status or '',
        'buyer_address': contract.buyer_address or '',
        'buyer_cep': contract.buyer_cep or '',
        'buyer_email': contract.buyer_email or '',
        'puppy_sex_display': contract.get_puppy_sex_display(),
        'puppy_color': contract.puppy_color or '',
        'puppy_microchip': contract.puppy_microchip or '',
        'puppy_father': contract.puppy_father or '',
        'puppy_mother': contract.puppy_mother or '',
        'puppy_birth_date_display': _fmt_date(contract.puppy_birth_date),
        'price_display': _fmt_brl(contract.price),
        'deposit_display': _fmt_brl(contract.deposit_amount),
        'balance_display': _fmt_brl(balance),
        'buyer_signature': buyer_sig,
        'signed_date': _fmt_date(contract.signed_at.date() if contract.signed_at else None),
    }


def generate_contract_pdf(contract):
    """Gera o PDF do contrato usando WeasyPrint e salva no model. Retorna bytes."""
    try:
        from weasyprint import HTML as WeasyHTML
    except ImportError:
        raise RuntimeError(
            "WeasyPrint não está instalado. Execute: pip install weasyprint"
        )

    context = build_contract_context(contract)
    html_string = render_to_string('contracts/contract_template.html', context)

    pdf_bytes = WeasyHTML(string=html_string).write_pdf()

    filename = f"contrato_{contract.id}_{contract.token}.pdf"
    contract.pdf_file.save(filename, ContentFile(pdf_bytes), save=True)
    logger.info("PDF gerado para contrato #%s", contract.id)
    return pdf_bytes


def render_contract_html(contract):
    """Retorna o HTML renderizado do contrato (para preview)."""
    context = build_contract_context(contract)
    return render_to_string('contracts/contract_template.html', context)
