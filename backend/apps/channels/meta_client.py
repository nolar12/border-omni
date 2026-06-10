"""
Helper functions for Meta Graph API — Business Integration System User Token (SUAT) flow.

All tokens here are SUAT (Business Integration System User Tokens), which belong to the
client's Business Portfolio — never tied to any personal Facebook account.
"""
import logging
import requests

logger = logging.getLogger('apps')

GRAPH_URL = 'https://graph.facebook.com/v22.0'


def exchange_code_for_suat(code: str, app_id: str, app_secret: str) -> str:
    """
    Exchange the authorization code returned by FB.login() for a SUAT.
    No redirect_uri is needed — Meta accepts the code from the JS SDK without it.
    Returns the access token string.
    """
    resp = requests.get(
        f'{GRAPH_URL}/oauth/access_token',
        params={
            'client_id': app_id,
            'client_secret': app_secret,
            'code': code,
        },
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    if 'error' in data:
        raise ValueError(data['error'].get('message', 'Falha ao trocar code por token'))
    token = data.get('access_token')
    if not token:
        raise ValueError('access_token ausente na resposta da Meta')
    return token


def get_client_business_id(suat: str) -> str | None:
    """Return the client_business_id from a Business Integration System User Token."""
    resp = requests.get(
        f'{GRAPH_URL}/me',
        params={'fields': 'client_business_id', 'access_token': suat},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json().get('client_business_id')


def get_waba_assets(suat: str) -> list[dict]:
    """
    Discover WhatsApp Business Accounts and their phone numbers accessible via SUAT.
    Returns a list of {waba_id, waba_name, phone_numbers: [{id, display_phone_number, verified_name}]}
    """
    biz_id = get_client_business_id(suat)
    if not biz_id:
        # fallback: try /me/businesses
        resp = requests.get(
            f'{GRAPH_URL}/me',
            params={
                'fields': 'businesses{id,name,whatsapp_business_accounts{id,name}}',
                'access_token': suat,
            },
            timeout=15,
        )
        if not resp.ok:
            return []
        biz_list = resp.json().get('businesses', {}).get('data', [])
        wabas = []
        for biz in biz_list:
            for waba in biz.get('whatsapp_business_accounts', {}).get('data', []):
                wabas.append(waba)
    else:
        resp = requests.get(
            f'{GRAPH_URL}/{biz_id}/owned_whatsapp_business_accounts',
            params={
                'fields': 'id,name,currency,timezone_id',
                'access_token': suat,
            },
            timeout=15,
        )
        resp.raise_for_status()
        wabas = resp.json().get('data', [])

    assets = []
    for waba in wabas:
        phones_resp = requests.get(
            f'{GRAPH_URL}/{waba["id"]}/phone_numbers',
            params={
                'fields': 'id,display_phone_number,verified_name,quality_rating',
                'access_token': suat,
            },
            timeout=15,
        )
        phones = phones_resp.json().get('data', []) if phones_resp.ok else []
        assets.append({
            'waba_id': waba['id'],
            'waba_name': waba.get('name', ''),
            'phone_numbers': phones,
        })
    return assets


def get_page_assets(suat: str) -> list[dict]:
    """
    Discover Facebook Pages (with Page Access Tokens) and linked Instagram accounts.
    Returns a list of {id, name, access_token, instagram_business_account?{id, username}}
    """
    resp = requests.get(
        f'{GRAPH_URL}/me/accounts',
        params={
            'fields': 'id,name,access_token,instagram_business_account{id,username,name}',
            'access_token': suat,
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json().get('data', [])


def subscribe_waba_webhook(
    waba_id: str,
    app_access_token: str,
    callback_url: str,
    verify_token: str,
) -> bool:
    """
    Subscribe the app to WABA webhooks and set a custom callback URL + verify token.
    app_access_token should be the app's own token: "{app_id}|{app_secret}".
    """
    resp = requests.post(
        f'{GRAPH_URL}/{waba_id}/subscribed_apps',
        params={
            'access_token': app_access_token,
            'override_callback_uri': callback_url,
            'verify_token': verify_token,
        },
        timeout=15,
    )
    if not resp.ok:
        logger.warning('subscribe_waba_webhook failed for %s: %s', waba_id, resp.text)
        resp.raise_for_status()
    return resp.json().get('success', False)


def subscribe_page_webhook(
    page_id: str,
    page_token: str,
    subscribed_fields: list[str],
) -> bool:
    """
    Subscribe a Facebook Page to webhook events.
    page_token must be a Page Access Token (not the SUAT).
    """
    resp = requests.post(
        f'{GRAPH_URL}/{page_id}/subscribed_apps',
        params={
            'access_token': page_token,
            'subscribed_fields': ','.join(subscribed_fields),
        },
        timeout=15,
    )
    if not resp.ok:
        logger.warning('subscribe_page_webhook failed for %s: %s', page_id, resp.text)
        resp.raise_for_status()
    return resp.json().get('success', False)


def verify_phone_number(phone_number_id: str, suat: str) -> dict:
    """
    Fetch basic info about a WhatsApp phone number to confirm connection is healthy.
    """
    resp = requests.get(
        f'{GRAPH_URL}/{phone_number_id}',
        params={
            'fields': 'display_phone_number,verified_name,quality_rating,status',
            'access_token': suat,
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()
