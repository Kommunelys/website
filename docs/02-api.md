# Portalens API

Steinkjer kommunes møtekalender er en React-app (Elements Publikum fra Sikri)
som henter alt innhold fra et åpent JSON-API. Ingen innlogging, ingen cookies,
bare én fast header.

Kartlagt 1. oktober 2026 fra et HAR-opptak i nettleseren og fra app-koden som
lastes med siden.

## Grunnlag

| Egenskap | Verdi |
|---|---|
| Portal for mennesker | `https://prod01.elementscloud.no/publikum/840029212_PROD-840029212/Dmb` |
| Basis-URL | `https://prod01.elementscloud.no/publikum/` |
| Påkrevd header | `tenant: 840029212_PROD-840029212` |
| Anbefalt header | `Accept: application/json` |
| Database-ID (Steinkjer) | `b069d4f5-192a-4fee-be37-dc006441e271` |
| Autentisering | Ingen |

Database-ID-en følger med i feltet `Database` på hvert objekt og brukes i
dokumentadressene.

## Datamodellen i fire nivåer

| Nivå | Nøkkel | Eksempel |
|---|---|---|
| Utvalg | `UT_ID` / `DmbId` | 34 = Hovedutvalg plan, næring og miljø (HPNM) |
| Møte | `MO_ID` / `MeetingId` | 1290 = HPNM 13.10.2026 |
| Behandling | `Id` på DmbHandling | 8414 = PS 47/2026 Organisering av renovasjonstjenesten |
| Journalpost | `RegistryEntry.Id` | 502569 |
| Dokument | `DocumentDescription.Id` | 835161 |

## Endepunkter

«Bekreftet» betyr observert med svar. «Fra koden» betyr lest ut av app-koden,
men ikke testet.

| Endepunkt | Gir | Status |
|---|---|---|
| `GET api/PredefinedQuery/DmbMeetings?year={år}` | Alle møter i alle utvalg for et år | Bekreftet |
| `GET api/Meetings/{møteId}` | Ett møte med møtedokumenter | Bekreftet |
| `GET api/DmbHandlings/GetByMeetingId/{møteId}` | Sakslisten for møtet | Bekreftet |
| `GET api/DmbHandlings/{sakId}` | Én sak med journalpost, dokumenter og saksgang | Bekreftet |
| `GET api/ConfigProvider/GetConfigs` | Portaloppsett, blant annet datointervall | Bekreftet |
| `GET api/Dmbs` | Liste over utvalg | Fra koden |
| `GET api/DmbMembers` | Medlemmer i utvalg | Fra koden |
| `GET api/DmbSearch/MeetingsSearch` | Søk i møter og saker | Fra koden |
| `GET api/Cases`, `api/RegistryEntries` | Saksmapper og journalposter | Fra koden |

### DmbMeetings

Flat liste. For 2026: 120 møter fordelt på 21 utvalg.

| Felt | Betydning |
|---|---|
| `MO_ID` | Møte-ID, brukes i alle videre kall |
| `MO_START`, `MO_SLUTT` | Lokal tid, uten tidssone |
| `MO_STED`, `MO_ROM` | Fritekst, kan være `null` |
| `UT_ID`, `UT_NAVN` | Utvalgets ID og navn |

### Meetings/{møteId}

| Felt | Betydning |
|---|---|
| `MeetingNumber` | Møtenummer i utvalget det året |
| `DMB.Name`, `DMB.ShortCode` | Utvalg og kortkode (FS, HPNM, KS …) |
| `MeetingDocuments[]` | `Id`, `Title`, `DmbDocumentTypeId`, `IsRestricted` |

### DmbHandlings/GetByMeetingId/{møteId}

Sakslisten uten dokumentdetaljer. `RegistryEntry` er alltid tom her.

| Felt | Betydning |
|---|---|
| `Id` | Behandlings-ID, nøkkelen for sak og protokoll |
| `MeetingCaseTypeId`, `SequenceNumber`, `Year` | Saksnummer, for eksempel PS 47/2026 |
| `Title` | Kan være `null` når saken er skjermet |
| `ProtocolPublished` | `true` når vedtaket er publisert |
| `ProtocolRestricted` | `true` når vedtaket er skjermet |

### DmbHandlings/{sakId}

Samme felter, pluss:

| Felt | Betydning |
|---|---|
| `RegistryEntry` | Journalposten med saksframlegget |
| `RegistryEntry.Documents[]` | Hoveddokument (`IsMainDocument: true`) og vedlegg |
| `AdditionalDmbHandlings[]` | Samme sak i andre utvalg, med egen `Id` og eget saksnummer |

Eksempel: sak 8414 er PS 47/2026 i HPNM 13.10.2026 og har tilleggsbehandling
8415, PS 108/2026 i Formannskapet 15.10.2026.

## Dokumentadresser

Lest ut av app-koden. **Ikke testet med et nedlastingskall ennå.**

| Dokument | Mønster |
|---|---|
| Vedtak for én sak | `Documents/ShowDmbHandlingDocument/{Database}/{sakId}/Protokoll` |
| Møtedokument | `Documents/ShowMeetingDocument/{Database}/{møteId}/{typekode}/{dokId}` |
| Saksframlegg og vedlegg | `Documents/ShowDocument/{Database}/{journalpostId}/{dokumentId}` |

Vedtaksadressen gjelder bare når `ProtocolPublished` er sann og
`ProtocolRestricted` er usann.

### Eksempler

Med `D` = `b069d4f5-192a-4fee-be37-dc006441e271`:

```
Documents/ShowMeetingDocument/D/1290/MI/5497     møteinnkalling HPNM 13.10
Documents/ShowDocument/D/502569/835161            saksframlegg
Documents/ShowDocument/D/502569/846205            vedlegg
Documents/ShowDmbHandlingDocument/D/8414/Protokoll   vedtak
```

## Kodeverdier

**Sakstype** (`MeetingCaseTypeId`)

| Kode | Betydning |
|---|---|
| PS | Politisk sak, får et vedtak |
| OS | Orienteringssak |
| RS | Referatsak |
| FO | Forespørsel |

**Møtedokumenttype** (`DmbDocumentTypeId`)

| Kode | Betydning |
|---|---|
| MI | Møteinnkalling |
| MP | Møteprotokoll |
| SP | Saksprotokoll |
| SF | Saksframlegg |
| FI | Forside |

**Dokumentkobling** (`DocumentLinkTypeId`): `SF` hoveddokument, `V` vedlegg.

**Flagg for tilgang**

| Felt | Betydning |
|---|---|
| `ProtocolPublished` | Vedtaket er publisert |
| `ProtocolRestricted` | Vedtaket finnes, men er skjermet |
| `IsRestricted` | Møtedokumentet vises ikke |
| `DocumentDescription.IsPublished` | Dokumentet kan lastes ned |
| `AccessCodeId` + `IsPublicVariantAvailable` | Skjermet; sladdet variant kan finnes |

## Omfang for 2026

| Enhet | Antall |
|---|---|
| Møter | 120 |
| Behandlinger | 634 |
| Saker etter sammenslåing | 503 |
| Politiske saker, uten formaliteter | 265 |
| Unike saksdokumenter | 1 076 (351 hoveddokument, 725 vedlegg) |
| Saksprotokoller | 368 |
| Møtedokumenter | 158 (91 innkalling, 67 protokoll) |
| **Totalt å laste ned** | **1 602** |

Filformat: 1 403 `RA-PDF`, 23 `JPEG`, 4 `PDF`. Samlingen er altså ikke bare PDF.

## Begrensninger

- Portalen viser normalt dokumenter for siste 365 dager
  (`DateIntervalRelative: -365`). Eldre møter kan mangle dokumenter.
- reCAPTCHA er aktivert i portalen, men ble ikke utløst av noen av kallene over.
  Den gjelder trolig dokumentbestilling og søk.
- API-et er udokumentert og kan endres ved oppdatering av Elements.
- `robots.txt` ber automatiske verktøy holde seg unna. Se ADR-007.
