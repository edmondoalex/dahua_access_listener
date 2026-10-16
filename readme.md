# Dahua Access Listener

**Versione componente: 3.0.0**

![Logo](logo.png)

Integrazione personalizzata per Home Assistant dedicata ai dispositivi di controllo accessi Dahua. Riceve in tempo reale gli eventi dal dispositivo, espone i dati di accesso come sensori e permette di azionare i relè delle porte.

## Funzionamento

- Apre lo stream eventi Dahua tramite `eventManager.cgi`.
- Riceve eventi di accesso, stato porta, lettore, tessera e impronta digitale.
- Aggiorna automaticamente sensori ed entità porta.
- Consente l'apertura dei relè tramite le entità lock o il servizio `dahua_access_listener.open_relay`.

## Installazione con HACS

1. Apri HACS e aggiungi questo repository come repository personalizzato di tipo **Integrazione**.
2. Installa **Dahua Access Listener**.
3. Riavvia Home Assistant.
4. Vai in **Impostazioni → Dispositivi e servizi → Aggiungi integrazione**.
5. Cerca **Dahua Access Reader** e inserisci i dati del dispositivo.

## Configurazione

Durante la configurazione vengono richiesti:

- nome dell'installazione;
- host o indirizzo IP del dispositivo Dahua;
- username;
- password;
- numero di relè, da 1 a 8.

## Entità create

### Sensori

- Event Code
- Event Action
- Index
- Door Status
- User ID
- User Name
- Access Method
- Event Type
- Reader ID
- Fingerprint ID
- Raw Data
- un sensore per ogni relè configurato

### Porte

- un'entità lock per ogni relè configurato

## Apertura manuale di un relè

Esempio di chiamata servizio:

```yaml
action: dahua_access_listener.open_relay
data:
  relay: 1
```

## Log di debug

Per abilitare i log dettagliati, aggiungi a `configuration.yaml`:

```yaml
logger:
  default: warning
  logs:
    custom_components.dahua_access_listener: debug
```

Riavvia Home Assistant dopo la modifica.
