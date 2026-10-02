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
| `GET api/Dmbs/{utvalgsId}` | Ett utvalg: `Id`, `Name`, `ShortCode` | Bekreftet |
| `GET api/DmbMembers/GetByDmbBoard/{utvalgsId}` | Dagens medlemmer og varamedlemmer i utvalget | Bekreftet |
| `GET api/DmbSearch/MeetingsSearch` | Søk i møter og saker | Fra koden |
| `GET api/Cases`, `api/RegistryEntries` | Saksmapper og journalposter | Fra koden |

Utvalgs-ID er `UT_ID` fra møtelisten, for eksempel 10 for kommunestyret.
`api/Dmbs` og `api/DmbMembers?dmbId=…`, slik de først ble lest ut av koden,
finnes ikke. Portalen svarer da med 200 og appens forside som HTML, ikke med
404. Et svar som ikke er JSON, betyr altså feil adresse.

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

### DmbMembers/GetByDmbBoard/{utvalgsId}

Bekreftet 2. oktober 2026 fra siden «Kalender og medlemmer»
(`DmbBoard/{utvalgsId}`) i portalen. Flat liste, én rad per verv. Gir bare
dagens medlemmer, ikke historikk.

| Felt | Betydning |
|---|---|
| `UserName.Id` | Personens ID i portalen. Fast på tvers av utvalg |
| `UserName.Name` | Navnet, slik oppmøtelisten ofte skriver det |
| `Function.Description` | `Leder`, `Nestleder`, `Medlem` eller `Varamedlem` |
| `Represents.ShortCode`, `Represents.Name` | Parti, eller kommune i interkommunale utvalg |
| `UserName.User.Address`, `Gender`, `Picture` | Mobilnummer, e-post og kjønn. Lagres ikke |

Kommunestyret: 39 faste medlemmer og 57 varamedlemmer.

## Dokumentadresser

Lest ut av app-koden. Testet 2. oktober 2026 med ett kall hver, og deretter
med hele 2026-samlingen (ADR-013).

| Dokument | Mønster |
|---|---|
| Vedtak for én sak | `Documents/ShowDmbHandlingDocument/{Database}/{sakId}/Protokoll` |
| Møtedokument | `Documents/ShowMeetingDocument/{Database}/{møteId}/{typekode}/{dokId}` |
| Saksframlegg og vedlegg | `Documents/ShowDocument/{Database}/{journalpostId}/{dokumentId}` |

Vedtaksadressen gjelder bare når `ProtocolPublished` er sann og
`ProtocolRestricted` er usann.

### Svar

| Egenskap | Observert |
|---|---|
| Status | 200. 404 når dokumentet er trukket tilbake etter uttrekket |
| `Content-Type` | `application/pdf`, eller Word (`…wordprocessingml.document`) for vedtak fra noen møter |
| `Content-Length` | Mangler. Størrelsen er først kjent når filen er lastet ned |
| `Content-Disposition` | `inline` med filnavn, for eksempel `Saksprotokoll KS.PDF` |
| Header `Accept: application/json` | Påvirker ikke svaret |

Saksframlegg og vedtak er PDF 1.7, de fleste merket PDF/A-2. Møteinnkallingen
er satt sammen av portalen og er stor: 41 MB og 221 sider for HPNM 13.10.2026.

### Eksempler

Med `D` = `b069d4f5-192a-4fee-be37-dc006441e271`:

```
Documents/ShowMeetingDocument/D/1290/MI/5497     møteinnkalling HPNM 13.10
Documents/ShowDocument/D/502569/835161            saksframlegg
Documents/ShowDocument/D/502569/846205            vedlegg
Documents/ShowDmbHandlingDocument/D/8356/Protokoll   vedtak KS 16.09
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
Formatet for vedtak står ikke i API-et. Ved nedlasting var 22 av 375 Word-filer.

## Begrensninger

- Portalen viser normalt dokumenter for siste 365 dager
  (`DateIntervalRelative: -365`). Eldre møter kan mangle dokumenter.
- reCAPTCHA er aktivert i portalen, men ble ikke utløst av noen av kallene over.
  Den gjelder trolig dokumentbestilling og søk.
- API-et er udokumentert og kan endres ved oppdatering av Elements.
- `robots.txt` ber automatiske verktøy holde seg unna. Se ADR-007.
