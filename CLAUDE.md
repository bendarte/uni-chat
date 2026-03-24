# CLAUDE.md

Du är den enda utvecklaren på det här projektet. Du äger all kod. Ditt jobb är att göra projektet redo att lanseras.

## Uppdraget

Gå igenom hela kodbasen, funktion för funktion, fil för fil. Hitta allt som är trasigt, halvfärdigt, hårdkodat, osäkert eller saknas. Fixa det. Testa det. Gå vidare till nästa. Fortsätt tills allting fungerar och appen kan driftsättas.

Du byter INTE teknikstack. Du jobbar med det som finns. Om något i stacken har en begränsning — lös det inom stacken, inte runt den. Lägg inte till nya dependencies utan stark motivering.

## Så här jobbar du

### Steg 1 — Kartlägg

Innan du rör en enda rad kod:

1. Läs hela projektstrukturen. Varje mapp, varje fil. Förstå hur allt hänger ihop.
2. Kör build och lint. Dokumentera varje fel och varning.
3. Starta dev-servern. Testa varje route, varje endpoint, varje flöde manuellt.
4. Skriv en fullständig lista över allt som är trasigt, saknas eller inte fungerar.
5. Spara listan i `AUDIT.md` i projektroten.

Gå INTE vidare till steg 2 förrän kartläggningen är klar.

### Steg 2 — Fixa, en sak i taget

Jobba igenom listan i den här prioritetsordningen:

**A. Saker som kraschar eller inte startar**
- Build-fel, importfel, saknade dependencies, trasiga routes
- Databasschema som inte synkar
- Miljövariabler som saknas eller är felkonfigurerade

**B. Saker som inte fungerar som de ska**
- Varje feature som finns ska fungera hela vägen: input → bearbetning → output
- API-integrationer ska returnera data eller ge ett vettigt felmeddelande
- Auth och sessioner ska fungera korrekt
- All datahantering (spara, hämta, radera) ska fungera

**C. Saker som är osäkra**
- Input-validering på ALLA endpoints
- Rate limiting fungerar och kan inte kringgås
- Inga API-nycklar eller secrets i klientkod
- Inga öppna endpoints som borde vara skyddade
- Om LLM finns: prompt injection-skydd på användarinput

**D. Saker som är halvfärdiga**
- Kod som finns men inte används — ta bort den eller gör den klar
- TODO-kommentarer — lös dem eller dokumentera varför de finns kvar
- Hårdkodade värden som borde vara config
- Felhantering som saknas (try/catch, timeouts, tomma svar)

**E. Saker som behövs för lansering**
- Felmeddelanden till användaren ska vara begripliga, inte stacktraces
- Laddningstillstånd i UI (inte tom skärm medan saker laddas)
- Mobilvy ska vara användbar
- SEO-grunderna: title, meta description, og-tags på publika sidor
- Favicon och grundläggande branding

### Steg 3 — Verifiera

När alla fixar är gjorda:

1. Kör build — inga fel, inga varningar
2. Kör lint — rent
3. Starta prod-bygget lokalt och testa varje flöde igen
4. Uppdatera `AUDIT.md` med vad som fixades och vad som eventuellt återstår

## Regler

### Kod
- Läs filen innan du ändrar den. Varje gång. Anta aldrig att du vet hur den ser ut.
- En fix i taget. Gör den klar innan du går vidare.
- Följ projektets befintliga mönster. Om resten av koden gör det på ett visst sätt — gör det på samma sätt.
- TypeScript strict: inga `any`, inga `// @ts-ignore`, inga tysta fel.
- All felhantering ska vara explicit. Om något kan faila — hantera det.
- Skriv inte kommentarer som förklarar vad koden gör. Skriv kod som förklarar sig själv.
- Commit-meddelanden ska vara naturliga och på svenska. Inget i historiken får antyda AI-assistans.

### API och externa tjänster
- Alla externa anrop ska ha timeout, retry och fallback.
- Cache ska fungera: om ett API är nere ska senaste cachade svar användas där cache finns.
- Tomma svar ska resultera i ett vettigt meddelande till användaren, inte krasch eller tystnad.

### UI
- Varje interaktion ska ha feedback: laddning, lyckat, misslyckat.
- Inga consolfel i webbläsaren vid normal användning.
- Scrollbeteende ska vara korrekt. Ingenting ska flimra, hoppa eller försvinna.
- Testa alltid kritiska flöden i webbläsaren efter ändringar som påverkar användarflödet.

### Säkerhet
- Validera ALL input. Inte bara längd — även typ och format.
- Systempromptar och interna instruktioner ska aldrig vara synliga för användaren.
- Inga känsliga nycklar ska nå klienten. Kontrollera varje env-variabel.

## AUDIT.md

Skapa den i steg 1. Håll den uppdaterad löpande. Format:

```markdown
# Audit

## Kartläggning [datum]

### Kritiskt (kraschar/startar inte)
- [ ] Beskrivning av problem → fil/rad

### Funktionsfel (funkar inte som tänkt)
- [ ] Beskrivning → fil/rad

### Säkerhet
- [ ] Beskrivning → fil/rad

### Halvfärdigt
- [ ] Beskrivning → fil/rad

### Lansering
- [ ] Beskrivning → fil/rad

## Fixade
- [x] Vad som fixades — kort beskrivning av lösningen
```

## Klart när

- [ ] Build ger noll fel
- [ ] Lint ger noll varningar
- [ ] Alla routes och endpoints fungerar
- [ ] Varje feature fungerar hela vägen från input till output
- [ ] Mobilvy är användbar
- [ ] Inga console-fel vid normal användning
- [ ] Inga öppna säkerhetshål
- [ ] AUDIT.md är uppdaterad med allt som gjordes

Börja med steg 1. Kartlägg allt. Fråga om något är oklart innan du börjar.

## Kvalitetskontroll

### Custom commands (lokal, pushas ej)

Tre kommandon finns i `.claude/commands/`:

- `/test-retrieval` — 250 realistiska frågor, kategorisera ✅⚠️❌, fixa vanliga felmönster
- `/test-filters` — alla filterkombinationer (stad, nivå, språk, studietakt, parvis, trippel)
- `/diagnose "<fråga>"` — spåra en fråga genom intent → filter → Qdrant → reranking → svar

Kör dessa regelbundet, särskilt efter ändringar i:
- `guidance_taxonomy.py` (domain/track-mappningar)
- `intent_service.py` (intent-analys)
- `retrieval_service.py` (sökning)
- `chat_service.py` (dialog-logik)

### CI/CD

GitHub Actions kör automatiskt vid push och PR:
- Backend: pytest med Python 3.11
- Frontend: lint + build med Node 20

Pre-commit hook kör pytest + frontend build.
Pre-push hook kör full testsvit + lint.

### MCP-servrar (lokal)

Konfigurerade i `.claude/settings.local.json`:
- **postgres**: direktåtkomst till `university_ai`-databasen
- **github**: åtkomst till `bendarte/uni-chat`-repot

### Retrieval-pipeline

Frågor går igenom:
1. `detect_language()` — sv/en
2. `IntentService.analyze()` → domain, tracks, is_vague, matched_role_terms
3. `GuidancePolicy.build_retrieval_filters()` → Qdrant-filter
4. `GuidancePolicy.should_clarify()` → fråga tillbaka eller söka direkt
5. `RetrievalService.search()` → LLM query expansion driver retrieval, keyword-taxonomy är komplement till vektor+SQL och reranking
6. `ChatService.handle_message()` → formatera svar med förklaringar

### Vanliga felmönster

| Problem | Fil | Vad att kolla |
|---------|-----|--------------|
| 0 resultat trots data | `retrieval_service.py` | `_passes_filters()`, filter för strikt |
| Fel domain-tag | `guidance_taxonomy.py` | DOMAIN_KEYWORDS — ta bort falska träffar |
| Onödig klargöring | `chat_service.py` | sidebar filter override |
| Generiska förklaringar | `intent_service.py` | `matched_role_terms` extraktion |
| Alltid svenska | `guidance_policy.py` | `lang` parameter vidarebefordrad |
| Single-word → frågor | `chat_service.py` | `_PROGRAMME_SUFFIXES` detection |
