"""Specifica canonica dei campi dell'anagrafica azienda.

Scheda, template, importazione ed export consumano questa struttura.  Le
intestazioni Excel non devono essere duplicate in router o frontend.
"""

from __future__ import annotations

from collections import OrderedDict


SPEC_VERSION = "2026-08-03.1"

PROVINCE = (
    "AG", "AL", "AN", "AO", "AP", "AQ", "AR", "AT", "AV", "BA", "BG", "BI", "BL", "BN",
    "BO", "BR", "BS", "BT", "BZ", "CA", "CB", "CE", "CH", "CL", "CN", "CO", "CR", "CS",
    "CT", "CZ", "EN", "FC", "FE", "FG", "FI", "FM", "FR", "GE", "GO", "GR", "IM", "IS",
    "KR", "LC", "LE", "LI", "LO", "LT", "LU", "MB", "MC", "ME", "MI", "MN", "MO", "MS",
    "MT", "NA", "NO", "NU", "OR", "PA", "PC", "PD", "PE", "PG", "PI", "PN", "PO", "PR",
    "PT", "PU", "PV", "PZ", "RA", "RC", "RE", "RG", "RI", "RM", "RN", "RO", "SA", "SI",
    "SO", "SP", "SR", "SS", "SU", "SV", "TA", "TE", "TN", "TO", "TP", "TR", "TS", "TV",
    "UD", "VA", "VB", "VC", "VE", "VI", "VR", "VT", "VV",
)

GROUPS = OrderedDict((
    ("identificazione", "Identificazione"),
    ("sede_legale", "Sede legale"),
    ("contatti", "Contatti e web"),
    ("dati_contrattuali", "Dati contrattuali e fondi"),
    ("legale_rappresentante", "Legale rappresentante"),
    ("riferimenti_commerciali", "Riferimenti commerciali"),
    ("note", "Note"),
))


def _field(name, label, field_type="text", *, group, required=False, importable=True,
           validation=None, options=None, sensitive=False, resolver=None):
    return {
        "name": name,
        "label": label,
        "type": field_type,
        "required": required,
        "importable": importable,
        "group": group,
        "validation": validation,
        "options": list(options or ()),
        "sensitive": sensitive,
        "resolver": resolver,
    }


COMPANY_FIELDS = [
    _field("ragione_sociale", "Ragione sociale", group="identificazione", required=True, validation="min:2|max:200"),
    _field("natura_giuridica", "Natura giuridica", group="identificazione", validation="max:50"),
    _field("partita_iva", "Partita IVA", group="identificazione", required=True, validation="partita_iva"),
    _field("codice_fiscale", "Codice fiscale", group="identificazione", validation="codice_fiscale"),
    _field("settore_ateco", "Codice ATECO", group="identificazione", validation="max:10"),
    _field("settore_codice", "Codice settore", group="identificazione", validation="max:10"),
    _field("settore_descrizione", "Descrizione settore", group="identificazione", validation="max:255"),
    _field("attivita_erogate", "Attività / servizi erogati", "multiline", group="identificazione"),
    _field("indirizzo", "Indirizzo sede legale", group="sede_legale", validation="max:200"),
    _field("citta", "Comune sede legale", group="sede_legale", validation="max:100"),
    _field("cap", "CAP sede legale", group="sede_legale", validation="cap"),
    _field("provincia", "Provincia sede legale", "choice", group="sede_legale", validation="provincia", options=PROVINCE),
    _field("email", "Email", "email", group="contatti", validation="email"),
    _field("pec", "PEC", "email", group="contatti", validation="email"),
    _field("telefono", "Telefono", group="contatti", validation="max:20"),
    _field("sito_web", "Sito web", "url", group="contatti", validation="url"),
    _field("linkedin_url", "LinkedIn azienda", "url", group="contatti", validation="url"),
    _field("facebook_url", "Facebook azienda", "url", group="contatti", validation="url"),
    _field("instagram_url", "Instagram azienda", "url", group="contatti", validation="url"),
    _field("ccnl_prevalente", "CCNL prevalente", group="dati_contrattuali", validation="max:255"),
    _field("num_dipendenti", "Numero dipendenti", "integer", group="dati_contrattuali", validation="integer>=0"),
    _field("matricola_inps", "Matricola INPS", group="dati_contrattuali", validation="max:30"),
    _field("anno_adesione", "Anno prima adesione", group="dati_contrattuali", validation="year"),
    _field("regime_aiuto_default", "Regime aiuti predefinito", "choice", group="dati_contrattuali", options=("non_definito", "de_minimis", "esenzione"), validation="choice"),
    _field("legale_rappresentante_nome", "Nome", group="legale_rappresentante", validation="max:100"),
    _field("legale_rappresentante_cognome", "Cognome", group="legale_rappresentante", validation="max:100"),
    _field("legale_rappresentante_codice_fiscale", "Codice fiscale", group="legale_rappresentante", validation="codice_fiscale"),
    _field("legale_rappresentante_email", "Email", "email", group="legale_rappresentante", validation="email"),
    _field("legale_rappresentante_telefono", "Telefono", group="legale_rappresentante", validation="max:30"),
    _field("legale_rappresentante_indirizzo", "Indirizzo", group="legale_rappresentante", validation="max:255"),
    _field("legale_rappresentante_linkedin", "LinkedIn", "url", group="legale_rappresentante", validation="url"),
    _field("legale_rappresentante_facebook", "Facebook", "url", group="legale_rappresentante", validation="url"),
    _field("legale_rappresentante_instagram", "Instagram", "url", group="legale_rappresentante", validation="url"),
    _field("legale_rappresentante_tiktok", "TikTok", "url", group="legale_rappresentante", validation="url"),
    _field("referente_nome", "Nome referente", group="riferimenti_commerciali", validation="max:100"),
    _field("referente_cognome", "Cognome referente", group="riferimenti_commerciali", validation="max:100"),
    _field("referente_ruolo", "Ruolo referente", group="riferimenti_commerciali", validation="max:100"),
    _field("referente_email", "Email referente", "email", group="riferimenti_commerciali", validation="email"),
    _field("referente_telefono", "Telefono referente", group="riferimenti_commerciali", validation="max:30"),
    _field("referente_indirizzo", "Indirizzo referente", group="riferimenti_commerciali", validation="max:255"),
    _field("referente_luogo_nascita", "Luogo di nascita referente", group="riferimenti_commerciali", validation="max:100"),
    _field("referente_data_nascita", "Data di nascita referente", "date", group="riferimenti_commerciali", validation="date:YYYY-MM-DD"),
    _field("referente_linkedin", "LinkedIn referente", "url", group="riferimenti_commerciali", validation="url"),
    _field("referente_facebook", "Facebook referente", "url", group="riferimenti_commerciali", validation="url"),
    _field("referente_instagram", "Instagram referente", "url", group="riferimenti_commerciali", validation="url"),
    _field("referente_tiktok", "TikTok referente", "url", group="riferimenti_commerciali", validation="url"),
    _field("agenzia_id", "Agenzia di riferimento", "foreign_key", group="riferimenti_commerciali", resolver="agenzia_nome"),
    _field("consulente_id", "Consulente / agente commerciale", "foreign_key", group="riferimenti_commerciali", resolver="consulente_nome"),
    _field("note", "Note", "multiline", group="note"),
    _field("attivo", "Stato azienda", "choice", group="note", options=("Sì", "No"), validation="boolean"),
]

SHEET_SPECS = OrderedDict((
    ("Sedi", [
        _field("partita_iva", "Partita IVA azienda", group="sedi", required=True, validation="partita_iva"),
        _field("nome", "Denominazione sede", group="sedi", required=True, validation="max:150"),
        _field("tipo", "Tipo sede", "choice", group="sedi", required=True, options=("operativa", "amministrativa", "accreditata"), validation="choice"),
        _field("indirizzo", "Indirizzo", group="sedi", validation="max:255"),
        _field("citta", "Comune", group="sedi", validation="max:100"),
        _field("provincia", "Provincia", "choice", group="sedi", options=PROVINCE, validation="provincia"),
        _field("cap", "CAP", group="sedi", validation="cap"),
        _field("email", "Email sede", "email", group="sedi", validation="email"),
        _field("telefono", "Telefono sede", group="sedi", validation="max:30"),
        _field("is_principale", "Sede principale", "choice", group="sedi", options=("Sì", "No"), validation="boolean"),
        _field("note", "Note sede", "multiline", group="sedi"),
    ]),
    ("Conti", [
        _field("partita_iva", "Partita IVA azienda", group="conti", required=True, validation="partita_iva"),
        _field("banca", "Banca", group="conti", validation="max:200"),
        _field("agenzia", "Agenzia / filiale", group="conti", validation="max:200"),
        _field("iban", "IBAN", group="conti", required=True, validation="iban", sensitive=True),
        _field("bic_swift", "BIC / SWIFT", group="conti", validation="bic"),
        _field("intestatario", "Intestatario", group="conti", required=True, validation="max:200"),
        _field("is_predefinito", "Conto predefinito", "choice", group="conti", options=("Sì", "No"), validation="boolean"),
        _field("is_active", "Conto attivo", "choice", group="conti", options=("Sì", "No"), validation="boolean"),
        _field("note", "Note conto", "multiline", group="conti"),
    ]),
    ("Fondi", [
        _field("partita_iva", "Partita IVA azienda", group="fondi", required=True, validation="partita_iva"),
        _field("fondo", "Fondo interprofessionale", group="fondi", required=True, validation="max:100"),
        _field("data_inizio", "Data inizio adesione", "date", group="fondi", required=True, validation="date:YYYY-MM-DD"),
        _field("data_fine", "Data fine adesione", "date", group="fondi", validation="date:YYYY-MM-DD"),
        _field("note", "Note adesione", "multiline", group="fondi"),
    ]),
))


def public_spec():
    return {
        "version": SPEC_VERSION,
        "groups": [{"name": key, "label": value} for key, value in GROUPS.items()],
        "fields": COMPANY_FIELDS,
        "sheets": [{"name": name, "fields": fields} for name, fields in SHEET_SPECS.items()],
    }


def importable_company_fields():
    return [field for field in COMPANY_FIELDS if field["importable"]]


def headers(fields):
    return [field["label"] for field in fields]


def field_by_label(fields):
    return {field["label"].strip().casefold(): field for field in fields}
